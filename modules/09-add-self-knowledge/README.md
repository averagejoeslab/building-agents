# Add self-knowledge

> **Harness component: self-knowledge.** The model can only know about its harness what the harness tells it. quark tells it everything: its own source code is embedded in the system prompt on every call.

Ask the Module 8 agent "what happens when I press ESC?" or "why did you summarize your memory?" and it can only guess. The behavior is in the harness, and the model has never seen the harness. You could write documentation into the prompt — but documentation drifts from the code it describes. quark skips the middleman and shows the model the code.

## The checkpoint

[`examples/09_self_knowledge.py`](../../examples/09_self_knowledge.py) adds one line and one prompt section.

```python
def mechanics(): return "\n".join('def system(): return "<system prompt redacted so you can see your self mechanics in harness>"' if l.startswith("def system():") else l for l in open(__file__).read().split("\n"))
```

`mechanics()` reads the harness's own source file (`__file__`) and returns it with one line replaced: the line that defines `system()`. That line *is* the system prompt — embedding it would put the whole prompt inside itself — so it's swapped for a one-line note saying it was redacted and why.

The system prompt gains a final section:

````markdown
# Mechanics

This code is your harness — shown so you know your self mechanics. The system prompt is redacted below because this is your system prompt.

```python
{mechanics()}
```
````

## What the model gets

Every line of the loop, verbatim: the stream and the interrupt check, the closures and their placeholder strings, the compaction state machine, the drain loop, the max-tokens guard. So the model can:

- **Answer questions about itself accurately.** "If I press ESC during a command, what do you see next?" — it can read the closure and tell you.
- **Interpret its own history.** When `[your doing stopped before done]` or `[your prior working memory, summarized]` shows up in its context, it can see exactly which line put it there and why.
- **Reason about improving itself.** Point quark at its own file and ask it to change something; it already knows the code.

And it can never be out of date. There's no separate description to maintain — if you edit the harness, the next call shows the model the new code.

This is where Module 5's shared vocabulary pays off in full. The prompt said *mind* and *body*; the model now reads `working_memory` and `body` in the code. The prompt said acts *reach the world*; the code says `"[your doing never reached the world]"`. The words the model was taught and the code it reads are the same words.

## The cost

The prompt grows from about 3,000 characters to about 9,300 — something like 1,500 to 2,000 more tokens, sent on every single call. For a harness that runs a model call per action, that adds up fast. Fortunately this is exactly the kind of cost the API lets you stop paying, which is the last module.

## Run it

```bash
cd examples
uv run 09_self_knowledge.py
> what happens if I press ESC while you're running a command?
> show me the line in your harness that handles a truncated tool call
```

## What's missing

- **The prompt is re-billed in full on every call**, and it just got a lot bigger.

---

**Next:** [Module 10: Add caching](../10-add-caching/)
