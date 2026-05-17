# Add performance

> **Harness component: production hardening.** Prompt caching, tool output caching, threading, streaming the final answer, structured prompts, and the `assemble()` convergence — what turns a working harness into a fast and cheap one.

> [!NOTE]
> **Coming soon.** This module is stubbed.

A correct agent is the floor; a fast and cheap one is the bar. Long-running agents repeat work — the same system prompt, the same tool schemas, the same files. Caching, parallelism, and streaming claw that cost back without changing what the agent does.

## What this module will cover

- **Anthropic prompt caching.** Marking the system prompt and tool schemas with `cache_control` to amortize the input cost of long-lived prefixes across many turns. When it's worth it, when it isn't.
- **Tool output caching.** A read of the same file twice in one turn shouldn't pay twice. A small content-addressed cache around `read`, `grep`, `glob`.
- **Moving blocking work off the event loop.** When a tool does CPU work (regex over a big tree, embedding inference), it should run on a thread or worker so concurrent tool calls aren't serialized behind it.
- **Structured prompts and `assemble()`.** A single function that brings system prompt, recalled memories, tool schemas, and trimmed messages together — turning context-shaping into one named call site instead of inline construction in the loop.

(Streaming the response is already in place since Module 3 — every checkpoint downstream of the LLM-call module renders text token-by-token.)

## Reference: production_agent.py

The end state lives at [`examples/production_agent.py`](../../examples/production_agent.py) — prompt caching, tool output caching, threading, streaming, structured prompts, and the `assemble()` function, all stacked on top of the previous checkpoints. The curriculum's destination.

```bash
cd examples
uv run production_agent.py
```

Requires Docker (carries forward the Module 6 sandbox).

---

You've reached the end of the curriculum. Back to the [root README](../../README.md).
