# Add observability

> **Harness component: structured tracing.** What the harness reports about its own activity — every LLM call, every tool call, every span — so you can debug, replay, and improve it.

> [!NOTE]
> **Coming soon.** This module is stubbed.

When the agent does the wrong thing, "what just happened?" is the first question. Without traces, the only answer is the terminal scrollback. Observability turns every loop iteration into a structured record you can search, replay, or feed to an eval.

## What this module will cover

- **The span model.** Borrowed from OpenTelemetry: every LLM call, tool call, and turn becomes a span with start/end timestamps, attributes, and a parent-child relationship.
- **JSONL as the wire format.** One span per line. Easy to write, easy to grep, easy to load into anything.
- **What to capture.** Full prompts and completions. Tool inputs and outputs. Token counts. Latency. Errors. The model's output text *and* its tool requests.
- **The trace decorator pattern.** A `@traced` wrapper that times a function call, captures its inputs/outputs, and emits a span — applied uniformly to LLM calls and tool calls.
- **Reading traces.** What a healthy trace looks like, what a stuck-loop trace looks like, what a "model couldn't find the tool" trace looks like.
- **The tooling landscape.** Where vendors fit (Langfuse, Arize, Honeycomb, custom): the file-based JSONL approach is a foundation, not a ceiling.

## Reference: traced_agent.py

The end state lives at [`examples/traced_agent.py`](../../examples/traced_agent.py). Every LLM call and tool call gets a JSONL span in `~/.traced-agent/traces.jsonl`:

```bash
cd examples
uv run traced_agent.py
```

After a session:

```bash
tail -n 20 ~/.traced-agent/traces.jsonl | jq
```

---

**Next:** [Module 9: Add evaluation](../09-add-evaluation/)
