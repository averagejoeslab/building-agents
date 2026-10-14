## 7. Pre-training: Language and the World

**Goal:** know language, and as much about the world as the text can teach.

Pre-training is the first and by far the largest stage. The model reads an enormous amount of text and learns to predict every next token in it. Nothing else. No questions, no answers, no instructions. Just text, and the next token, everywhere.

It sounds too simple to work. But to predict the next token of a news story well, the model has to pick up grammar, facts, how arguments go, and what people tend to say next. Pre-training is where nearly all of a model's knowledge comes from.

### The experiment

We pre-train our model from random weights. It's the same code as Chapter 5's, made small enough to train on a CPU in a fixed twenty minutes:

| | Qwen3-0.6B | Ours |
|---|---|---|
| Vocabulary | 151,936 | 2,048, learned from the training text |
| Width (`dim`) | 1,024 | 256 |
| Blocks | 28 | 4 |
| Heads (query / kv) | 16 / 8 | 4 / 2 |
| MLP width | 3,072 | 768 |
| Parameters | ~600,000,000 | 3,672,832 |
| Training tokens | ~36,000,000,000,000 | 320,093 |

The text is about a million characters of Shakespeare's plays. The last tenth is held out. The code, from `model/train.py`, with the parts explained in Chapter 6 marked:

```python
def pretrain(minutes=20):
    text = pretrain_text()                              # data/shakespeare.txt
    tokenizer = Tokenizer.learn(text, 2048)             # our own tokenizer, from the same text
    data = torch.tensor(tokenizer.encode(text))
    cut = len(data) * 9 // 10
    data, held_out = data[:cut], data[cut:]             # the last tenth: never trained on
    model = Model(vocab=2048, dim=256, layers=4, heads=4, kv_heads=2, head_dim=64, hidden=768)
    log("before:", sample(model), held_out_loss(model, held_out))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    start, step = time.time(), 0
    while time.time() - start < minutes * 60:
        step += 1
        starts = torch.randint(len(data) - 257, (16,))                        # a batch of 16 windows
        inputs = torch.stack([data[i:i + 256] for i in starts])
        targets = torch.stack([data[i + 1:i + 257] for i in starts])          # one token on
        loss = F.cross_entropy(model(inputs).flatten(0, 1), targets.flatten())
        optimizer.zero_grad(); loss.backward(); optimizer.step()
        if step % 100 == 0:
            log(f"step {step}: loss {loss.item():.2f}")
    log("after:", sample(model), held_out_loss(model, held_out))
```

*Shortened from `model/train.py`, where the full version is.*

Two helpers: `held_out_loss` cuts the held-out tokens into 257-token windows and averages the cross-entropy over all of them, so the number is comparable before and after. `sample` generates 60 tokens after the prompt `ROMEO:\n` at temperature 0.8, to show what the model writes.

### What happened

The record, `runs/training/pretrain.txt`, trimmed:

```
text: 320,093 tokens of 2,048 kinds; model: 3,672,832 numbers, all random
before: "ROMEO:\nGR9Clengeracices marry confAh condThey villainoud might weep…"  held-out loss 7.69
step 100: loss 5.65
step 200: loss 5.05
step 300: loss 4.61
step 500: loss 3.90
step 700: loss 3.49
step 1000: loss 2.76
step 1300: loss 2.35
step 1400: loss 2.18
after 1405 steps, 20 minutes: "ROMEO:\nTwo of thy Romeoful days is smoak
To choose anointed jewry till now,
Sent both of them, and you shall publace;
But marve thy turn, I'll prove you at night.
I saw you to my young lady"  held-out loss 5.28
```

Read the losses with Chapter 6's table. **7.69** before training is a hair worse than a uniform guess over 2,048 tokens (7.62): random weights, as expected. The *training* loss falls steadily to **2.18**, but the *held-out* loss only reaches **5.28**. That gap is overfitting: 3.7 million parameters trained for 1,405 steps on 320,000 tokens have begun to memorize the plays. A lab's model sees each token roughly once; ours saw each about 18 times (1,405 steps × 4,096 tokens ÷ 320,093).

And yet the samples show real learning. Before: a jumble of fragments, because the tokenizer's merges are real words and the random model strings them together at random. After: verse, line breaks of the right length, a second-person address, real names, near-sense ("Sent both of them, and you shall…"). Nobody told it what a play looks like. It learned that from predicting the next token.

```
loss
 8 ┤●
 7 ┤
 6 ┤ ●
 5 ┤   ●●
 4 ┤      ●●
 3 ┤          ●●●
 2 ┤               ●●●●        training loss
   └──────────────────────── step
   0    400    800   1200
```

### What a single builder can't afford

The same code, trained by a lab, writes far better. The difference is scale: Qwen's models were pre-trained on about 36 trillion tokens, for months, on a large cluster. That's over 100 million times more text than our Shakespeare, and a model 160 times bigger.

This is the one stage a single builder can't match. So, as the labs' open releases allow, we borrow one that's been done: **Qwen3-0.6B-Base**, Qwen's model after its pre-training and mid-training, before any post-training. Because our code is built to Qwen3's design, its weights load straight in (`load_real` in `model.py`), and its tokenizer's merges load into our `Tokenizer`.

```python
def load_real(name="Qwen/Qwen3-0.6B-Base"):
    model = Model()                                     # the full-size shape
    weights = load_file(hf_hub_download(name, "model.safetensors"))
    weights.pop("lm_head.weight", None)                 # the output head is the embedding, shared
    model.load_state_dict({k.removeprefix("model.").replace("mlp.", ""): v.float()
                           for k, v in weights.items()}, strict=True)
    return model
```

`strict=True` is the check: every tensor in Qwen's file must find a home in our model, with the right shape, and every tensor in our model must be filled. The only translation is naming: Qwen's `model.layers.0.mlp.gate_proj.weight` is our `layers.0.gate_proj.weight`.

Asked to continue the same `ROMEO:`, it writes:

```
ROMEO:
I am Romeo, a man of the world, a man of the city, a man of the law, a man of the law,
a man of the law, a man of the law, a man of the law, …
```

Fluent, then stuck in a loop. (The loop is partly an artifact of greedy decoding: with temperature 0, a repeating pattern that's most likely at one step stays most likely.) It knows language, and a great deal about the world. Nothing has taught it how to behave: when to stop, what's being asked, how to take a turn.

That's what a base model is: a vast store of knowledge with no manners. The next two stages shape it. First, toward the job.

> **Reproduce it:** `uv run model/train.py pre`, which trains for a fixed 20 minutes. Appendix A has the details and what to expect.
