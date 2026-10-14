## 9. Post-training: Learning to Behave

**Goal:** turn a model that continues text into one that takes turns, answers what it's asked, and stops.

A base model is like someone who has read everything and never had a conversation. Post-training teaches it to have one. It comes in two kinds, and an agent needs both:

- **Instruction-tuning** teaches by example. The model is shown conversations and learns to write the way the assistant in them does.
- **Reinforcement learning** teaches by practice. The model tries things, its tries are graded, and it learns to do more of what earned a good grade.

This chapter covers instruction-tuning's mechanics and what it teaches a model about conversation. Its most important work for an agent, learning to act in a harness, needs the harness to exist, so the agent half of the data (and all of reinforcement learning) is in Part IV.

### The chat template

To take turns, a model has to know whose turn it is. A conversation is laid out as text in a fixed pattern of special tokens that mark where each turn starts, who is speaking, and where each turn ends. That pattern is the **chat template**, and it ships with the model (Chapter 5). Qwen3's, which we adopt:

```
<|im_start|>system
You are quark, an agent. You act through bash, in /tmp/shop. Today is 2026-10-07.<|im_end|>
<|im_start|>user
Count the lines in a.txt.<|im_end|>
<|im_start|>assistant
<tool_call>
{"name": "bash", "arguments": {"command": "wc -l < a.txt"}}
</tool_call><|im_end|>
<|im_start|>user
<tool_response>
3
</tool_response><|im_end|>
<|im_start|>assistant
a.txt has 3 lines.<|im_end|>
```

Everything is tokens, including the markers: `<|im_start|>` and `<|im_end|>` are single special tokens. When a tool is available, the template adds its description to the system turn, in a fixed wording that tells the model to call it with `<tool_call>…</tool_call>` holding JSON. A tool's result comes back as a `user` turn wrapped in `<tool_response>`.

The template is a Jinja program stored in `tokenizer_config.json`. Our `Release.chat` renders it exactly as Qwen's library does, and the check in Chapter 5 confirmed the text matches to the character. That matters more than it sounds: Chapter 20 tells what happened when a template detail was off.

When the harness wants a reply, it lays out the conversation and ends with `<|im_start|>assistant\n`. The model writes from there. When it writes `<|im_end|>`, its turn is over.

### Learning from the assistant's tokens only

Instruction-tuning is still next-token prediction, with one change: the loss is computed only on the **assistant's** tokens. The model reads the user's words, the tool's results, and the system prompt, but isn't graded on predicting them. It's being taught to be the assistant, not the user.

```
<|im_start|>user
Count the lines in a.txt.<|im_end|>                       ← read, not learned
<|im_start|>assistant
<tool_call>{"name": "bash", …}</tool_call><|im_end|>      ← learned, including <|im_end|>
<|im_start|>user
<tool_response>3</tool_response><|im_end|>                ← read, not learned
<|im_start|>assistant
a.txt has 3 lines.<|im_end|>                              ← learned
```

The mask is built by splitting the rendered text at each assistant turn:

```python
def tokens_and_mask(model, text, most=1024):
    ids, learn = [], []
    pieces = re.split(r"(?<=<\|im_start\|>assistant\n)(.*?<\|im_end\|>)", text, flags=re.S)
    for n, piece in enumerate(pieces):   # odd pieces are assistant turns, through <|im_end|>
        piece_ids = model.encode(piece)
        ids += piece_ids
        learn += [n % 2 == 1] * len(piece_ids)
    return ids[:most], learn[:most]

def logprob(model, text, most=1024):     # log-probability of what the assistant said
    ids, learn = tokens_and_mask(model, text, most)
    ids, keep = torch.tensor([ids]), torch.tensor([learn[1:]])
    return -F.cross_entropy(model.model(ids[:, :-1], keep=keep), ids[:, 1:][keep])
```

`learn[1:]` shifts the mask by one, because position *i* predicts token *i* + 1: the first assistant token is predicted from the `assistant\n` marker, and `<|im_end|>` is predicted from the assistant's last word. Learning to write `<|im_end|>` is what teaches the model to *stop*, and a base model has barely seen that token.

The training step is the same two lines as every stage, with a weight that will matter in Chapter 18:

```python
def update(model, optimizer, texts, weights, most=1024):
    optimizer.zero_grad()
    for text, weight in zip(texts, weights):         # one at a time, to fit in memory
        (-weight * logprob(model, text, most) / len(texts)).backward()
    optimizer.step()
```

For instruction-tuning every weight is 1: maximize the log-probability of every example equally. That's cross-entropy with a mask.

### The data

The mix teaches broad habits with public data, and the agent's own habits with recordings of it at work. The public kinds, with the counts from round one:

| Kind | Source (licence) | Count | What it teaches |
|---|---|---|---|
| Talk | smol-smoltalk (Apache 2.0) | 300 | Everyday conversation, in turns |
| Ask for a command | NL2Bash (MIT) | 300 | A request in, one `<tool_call>` out |
| Reason | GSM8K (MIT), worked steps as a `<think>` block | 300 | Think first, then answer |
| Call tools | Hermes function-calling (Apache 2.0) | 300 | The tool-call format, across many tools |
| Write code | Magicoder OSS-Instruct (MIT) | 300 | Programs from descriptions |
| **Work as quark** | **Our own training tasks, run in the harness** | **900** | **Look, act, check, answer** (Chapter 17) |

Every conversation is rendered through the chat template into one text, so the model learns the format along with the content. Each kind is a few lines of `instruction_data` in `train.py`; the reasoning kind, for instance, turns GSM8K's worked answer into a thinking block:

```python
def worked(answer):                      # GSM8K: "steps #### number" → think, then answer
    steps, number = answer.split("####")
    return "<think>\n" + re.sub(r"<<.*?>>", "", steps).strip() + f"\n</think>\n\nThe answer is {number.strip()}."
```

Every public example is decontaminated against the evaluation (Chapter 17 shows how), and any conversation over 1,024 tokens is dropped. 48 conversations are held out as the stage's check. The rest, 2,352, are trained in one pass, in batches of 8, with AdamW at 1 × 10⁻⁵, every parameter trainable, including the embedding table, because the base model has barely learned `<|im_end|>`:

```python
for step in range(1, len(data) // 8 + 1):            # one pass: a second made the held-out loss rise
    update(model, optimizer, data[8 * step - 8:8 * step], [1.0] * 8)
```

*Shortened from `model/train.py`, where the full version is.*

294 steps, which took about six hours (357 minutes) on the CPU that made the record.

### Before and after

Held-out loss on the 48 conversations: **2.260 → 0.496**. More telling is what the model writes. The same three requests, before and after, from `runs/training/round1/instruct.txt`:

**"How do I make a cup of tea?"** Before, a line of repeated symbols: the base model, with no idea what an assistant turn is, emits a token and keeps emitting it. After:

```
To make a cup of tea, follow these steps:

1. Gather your materials: You will need a teapot, a cup, a teabag, and a pot of water.
2. Boil the water: Place the pot of water on the stove and bring it to a boil.
3. Add the teabag: Once the water is boiling, add the teabag to the pot.
…
```

**"Count the lines in notes.txt."** (with the bash tool offered) Before, it continues the template's own tool instructions back at us, mistaking them for text to extend. After:

```
<tool_call>
{"name": "bash", "arguments": {"command": "ls"}}
</tool_call>
```

A tool call, in the right format, that looks before it acts: the habit the quark sessions teach.

**A word problem.** *Pearl has $100, Athena has $25 more than Pearl, and Duchess has $50 more than Athena. How much do all three have?* Before, it writes a different word problem. After:

```
<think>
Athena has $25 + $100 = $125.
Duchess has $50 + $125 = $175.
All three girls have $125 + $175 = $200 combined.
</think>

The answer is 200.
```

*(The names in this example have been changed from the ones in the GSM8K question and the recorded reply; everything else is as the model wrote it.)*

It now takes turns, answers what was asked, and stops. It has the *shape* of reasoning but not yet the substance: it left Pearl out, and the right answer is 400. Instruction-tuning teaches behavior. It can't give a 600-million-parameter model arithmetic it doesn't have.

We have a mind that can hold a conversation. It still can't do anything. Now we build its body.

> **Reproduce it:** `uv run model/train.py post instruct`, about six hours on a CPU. The data pipeline needs network access on first run. Appendix A has the details.
