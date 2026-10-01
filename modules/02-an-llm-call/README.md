# An LLM call

> **Harness component: the model interface.** The harness has exactly one hard external dependency — the call out to the model. This module builds that call, in the shape the rest of the harness needs: streamed, event by event, so the harness can act *between* events.

In this module we walk through three things: **what an LLM call is**, **why quark streams every call and reads it event by event**, and **what's still missing** before any of this is an agent.

## The Messages API

The model sits behind a regular HTTP API — one POST per call, one response back. The [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) specifies the full contract, but a call needs only a few fields:

| Field | Purpose |
|---|---|
| `model` | Which model to call — quark uses `claude-sonnet-4-5` |
| `max_tokens` | Cap on the response length |
| `messages` | The conversation — a list of `{"role": ..., "content": ...}` turns |
| `system` | Context that applies to the whole conversation (we add this in [Module 5](../05-add-a-self-model/)) |

What comes back is a message whose `content` is a list of **blocks**. For a plain answer that's one `text` block. Later, when the model has a body, it can also contain `tool_use` blocks — requests to act.

The simplest possible call blocks until the whole response is ready:

```python
from anthropic import Anthropic

client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Write three sentences about agents."}],
)
print(response.content[0].text)
```

That works, and the [Module 1 toy](../../examples/01_toy.py) uses exactly this. But it hands the harness nothing until the model is completely done.

## Why a harness streams

With **streaming**, the API sends the response back as a sequence of events while the model generates it. There are two reasons a harness wants that:

1. **The human sees words immediately.** Total latency is the same, but time-to-first-token drops to near zero — the difference between an agent that feels alive and one that feels frozen.
2. **The harness gets control between events.** This is the one that matters for harness engineering. If you're iterating over events, you can check something before handling each one — like whether the human just pressed ESC ([Module 8](../08-add-interrupts/)) — and stop. A blocking `create()` call gives you no such moment.

So quark streams every main call, and it iterates over the raw events rather than a convenience text iterator, because the event loop *is* the place the harness gets to think.

## The checkpoint

[`examples/02_stream.py`](../../examples/02_stream.py) — the whole thing:

```python
import sys
from anthropic import Anthropic

client, MODEL = Anthropic(), "claude-sonnet-4-5"
working_memory = [{"role": "user", "content": " ".join(sys.argv[1:]) or "Write three sentences about agents."}]

with client.messages.stream(model=MODEL, max_tokens=4096, messages=working_memory) as stream:
    for ev in stream:
        if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
    saying = stream.current_message_snapshot
print()
print(f"[stop_reason: {saying.stop_reason} · tokens in/out: {saying.usage.input_tokens}/{saying.usage.output_tokens}]")
```

Line by line:

- **`client, MODEL = Anthropic(), "claude-sonnet-4-5"`** — one client for the whole program. With no arguments, the SDK reads `ANTHROPIC_API_KEY` from the environment.
- **`working_memory = [...]`** — the conversation, starting with one user message taken from the command line. We call it `working_memory` rather than `messages` on purpose: it's the agent's *mind*, the only thing the model will know on this call. The name pays off in Module 6, when it fills up.
- **`with client.messages.stream(...) as stream:`** — opens the streaming request. The `with` block guarantees the connection is closed when we leave it, including if we leave early with `break`. Closing the connection mid-stream tells the server to stop generating.
- **`for ev in stream:`** — every event the server sends: `message_start`, then for each content block a `content_block_start`, a run of `content_block_delta`s, and a `content_block_stop`, then `message_delta` (which carries the stop reason and final usage) and `message_stop`.
- **`if ev.type == "content_block_delta" and hasattr(ev.delta, "text")`** — print only text deltas. Deltas for `tool_use` blocks carry partial JSON (`input_json_delta`) instead of text; `hasattr` skips them without naming every delta type. `flush()` makes each fragment appear immediately rather than when Python's buffer fills.
- **`saying = stream.current_message_snapshot`** — the message accumulated *so far*, as a normal `Message` object. We use the snapshot rather than `get_final_message()` because of what Module 8 needs: if we stop iterating early, `get_final_message()` would keep reading until the model finished, while the snapshot returns exactly what had arrived. The variable is `saying` because that's what it is — the model's current utterance.
- **The last line** prints two things worth getting used to reading. `stop_reason` says *why* the model stopped: `end_turn` (it was done), `max_tokens` (it ran out of room — this matters a lot in Module 4), or `tool_use` (it's asking to act). `usage` is what you're billed for.

This is synchronous Python — no `async`, no `await`. quark never needs an event loop: the one piece of concurrency it has (watching the keyboard for ESC) is a single background thread, added in Module 8.

## Run it

```bash
cd examples
uv run 02_stream.py "explain what a harness is in one paragraph"
```

The answer appears a few words at a time, followed by its stop reason and token counts.

## What's missing

- **No conversation.** One call and the program exits. Nothing carries forward.
- **No environment.** The input comes from the command line once. There's no terminal session, no back-and-forth — the agent doesn't *live* anywhere yet.
- **No body.** The model can only produce text; it can't do anything.

Module 3 fixes the first two: it wraps this call in a loop and binds that loop to an environment.

---

**Next:** [Module 3: Add a loop](../03-add-a-loop/)
