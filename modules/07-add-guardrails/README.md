# Add guardrails

> **Harness component: safety constraints.** What the harness allows, what it asks the human about, what it refuses, and how long it's willing to run. The harness's policy layer.

> [!NOTE]
> **Coming soon.** This module is stubbed.

Sandboxing (Module 6) constrains *where* the agent can do damage. Guardrails constrain *whether* it gets to act at all. Three complementary controls:

## What this module will cover

- **Approval gates.** Before running a dangerous tool (`write`, `edit`, `bash`), prompt the human for confirmation. A `DANGEROUS_TOOLS` set + an interactive y/N gate, with the tradeoffs between always-ask, never-ask, and remembered-per-session.
- **Loop bounds.** A `MAX_ITERATIONS` cap on the inner TAO loop, and what to feed back to the model when the cap trips.
- **Retry and backoff.** Transient API errors (rate limits, 529s) shouldn't kill a long-running agent. Exponential backoff on the LLM call; a separate policy for tool errors (which the model handles itself by reading the error string).

## Reference: safe_agent.py

The end state lives at [`examples/safe_agent.py`](../../examples/safe_agent.py) — the sandboxed agent from Module 6 with approval gates, loop bounds, and retry/backoff added on top:

```bash
cd examples
uv run safe_agent.py
```

Try a `write` or `bash` call — the agent will pause and ask before executing.

---

**Next:** [Module 8: Add observability](../08-add-observability/)
