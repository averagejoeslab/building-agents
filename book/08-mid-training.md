## 8. Mid-training: Knowing the Job

**Goal:** be good at what matters for the job.

Mid-training is the same task as pre-training, predicting every next token, on text chosen for what the model will need. A lab might mid-train on code, mathematics, long reasoning, or recordings of agents at work. The model already knows language; mid-training deepens what it knows about the job.

From here on, the model is Qwen3-0.6B-Base, in our code.

### The data

Our agent will act through the **shell**, the text window where a person types commands to a computer. So it needs to know shell commands well. Our data is [tldr-pages](https://github.com/tldr-pages/tldr): 6,787 short, freely licensed (CC BY 4.0) pages about shell commands. Each page has a one-line description, then examples, each a plain-English line and the command that does it:

```
# tar

> Archiving utility.
> More information: <https://www.gnu.org/software/tar>.

- [c]reate an archive and write it to a [f]ile:

`tar cf {{path/to/target.tar}} {{path/to/file1 path/to/file2 ...}}`

- [c]reate a g[z]ipped archive and write it to a [f]ile:

`tar czf {{path/to/target.tar.gz}} {{path/to/file1 path/to/file2 ...}}`
```

The pages are concatenated into one stream of tokens and cut into 512-token pieces, exactly as pre-training cut Shakespeare:

```python
def chunks(model, texts, length=512):
    ids = [i for t in texts for i in model.encode(t + "\n\n")]
    return torch.tensor(ids[:len(ids) // (length + 1) * (length + 1)]).view(-1, length + 1)
```

Two rules apply to the data before training.

**Hold some out.** The pages are shuffled; 200 are set aside and never trained on.

**Keep it apart from the evaluation.** The finished agent will be evaluated on 32 tasks (Chapter 15). Nothing the model trains on may resemble them, or the evaluation would measure memory instead of skill. So any page with an example whose words overlap an evaluation request by 40% or more is dropped. This is **decontamination**; the function that measures the overlap is in Chapter 17. Here it removed 14 pages, leaving 6,773, about 1,042,929 tokens.

### The training

Mid-training runs a fixed 60 steps of 4 pieces each: 240 pieces of 512 tokens, about an eighth of the pages, seen once.

```python
def midtrain(steps=60):
    model = ours(BASE)                                  # Qwen3-0.6B-Base, in our Release class
    data, held_out, tests = prepared("midtrain", lambda: mid_data(model))
    log("before:", chunk_loss(model, held_out), shell_check(model, tests))
    optimizer = trainable(model.model, lr=1e-5)         # AdamW, every parameter
    for step in range(1, steps + 1):
        optimizer.zero_grad()
        for piece in data[4 * step - 4:4 * step]:       # four pieces a step, one at a time to fit in memory
            loss = F.cross_entropy(model.model(piece[None, :-1])[0], piece[1:])
            (loss / 4).backward()                       # gradients add up across the four
        optimizer.step()
    log("after:", chunk_loss(model, held_out), shell_check(model, tests))
```

*Shortened from `model/train.py`, where the full version is.*

One detail: `(loss / 4).backward()` is called four times before one `optimizer.step()`. Gradients accumulate in `parameter.grad` until `zero_grad` clears them, so this is a batch of four, computed one at a time. It's the standard way to train with a bigger batch than fits in memory at once.

### Two checks

The stage gets two checks, before and after.

**Held-out loss**: cross-entropy on 32 pieces cut from the 200 held-out pages.

**The shell check**: can it name the right command? This is a base model, so it's asked by example. It's shown a held-out page as the page itself presents it, with the page's other examples first, and the plain-English line of the last example, up to the opening backtick of its command:

```
# docker buildx stop

> Stop a builder instance.
> More information: <https://docs.docker.com/reference/cli/docker/buildx/stop>.

- Stop the current builder instance:

`docker buildx stop`

- Stop a specific builder instance:

`
```

The model continues from the backtick. It passes if its command has the same first word as the page's, and every other word of the page's command appears, in any order, with any value allowed where the page has a `{{placeholder}}`:

```python
def fits(said, command):
    said, wanted = parts(said), parts(command)        # split into words; a {{placeholder}} stays whole
    return (bool(said) and said[0] == wanted[0]
            and all(any(re.fullmatch(pattern(w), f) for s in said for f in forms(s))
                    for w in wanted[1:]))
```

Order and exact flags vary between right answers (`-a` and `--all`, say), so the check asks for the words, not the exact string. One hundred held-out pages that have more than one example are checked.

### What happened

| | Held-out loss | Shell check |
|---|---|---|
| **Before: Qwen3-0.6B-Base** | 1.896 | 48/100 |
| **After 60 steps** | 1.411 | 53/100 |

It predicts the pages far better: a drop of 0.49 in loss means it finds the held-out pages about e⁰·⁴⁹ ≈ 1.6 times more likely per token. It names the right command a little more often.

The two numbers moved by different amounts because they measure different things. The loss is measured on every token of a page, and most of those are prose and placeholders: the page's layout, its "More information" line, `{{path/to/file}}`. The command is a few words of each page, and the base model already knew most of them from pre-training. A small dose of mid-training teaches the style of the pages more than new commands. A lab would give it far more, and would measure the thing it cares about directly.

(A note on the record: `runs/training/midtrain.txt` shows the shell check as 31/100 before and 22/100 after, from an earlier, stricter version of `fits` that compared exact strings. The check was rewritten to compare words, and run again on the same two models without retraining: `uv run model/train.py check`. Those are the 48 and 53 above. Chapter 20 has more to say about checks that are wrong.)

### What it can't do yet

Our model knows language, and knows the shell a little better. Ask it to do something, and it continues the text instead. It has never seen a conversation's turn end, a request answered, or a tool called. Post-training teaches that.

> **Reproduce it:** `uv run model/train.py mid`, then `uv run model/train.py check`. Appendix A has the details.
