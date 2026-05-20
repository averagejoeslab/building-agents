# Add observability

> **Harness component: structured tracing.** What the harness reports about its own activity — every LLM call, every tool call, every turn — so you can debug, replay, and improve it.

Module 7 made the agent safer. It also made it more opaque. Approval gates fire and the prompts scroll off the terminal. Sentiment classifiers flag and the warning disappears. Retries happen silently inside the SDK. The hallucination judge runs once and forgets.

When the agent does the wrong thing, *"what just happened?"* is the first question. Module 5's `print()` statements aren't enough — they're ephemeral and unstructured. The harness needs to watch itself and write down what it sees.

By the end you have [`examples/traced_agent.py`](../../examples/traced_agent.py).

## What observability gives you

A trace is a structured record of one unit of agent work. Three things become possible once traces exist:

- **Debugging.** When yesterday's run produced a wrong answer, you can replay exactly what the model saw, what tools it called, what they returned. No "let me see if I can reproduce" — the answer is in the log.
- **Operating.** Token usage per turn, latency per tool, error rates over time — the metrics you need to know whether the agent is healthy in production all fall out of a good trace stream.
- **Evaluation.** The next module (M9) judges agent behaviour. Its inputs are traces. Without observability there's no eval signal beyond the final answer.

The hard part isn't writing log lines. It's making them *structured* enough that you can grep, query, and feed them to downstream systems without parsing free-form text.

## The span model

The standard mental model is borrowed directly from OpenTelemetry: a **span** is one unit of work with a name, a start and end time, a set of attributes, and an optional parent. Spans form a tree: a top-level operation contains the calls it dispatched, each of which contains the calls *they* dispatched.

For an agent, the tree maps naturally to the TAO loop:

```
turn (one user input → final response)
├── llm.call (iteration 0)
│   ├── tool.call (read)
│   ├── tool.call (grep)
│   └── tool.call (bash)
├── llm.call (iteration 1)
│   └── tool.call (edit)
└── llm.call (iteration 2)   # no tool calls, loop exits
```

The `turn` span wraps an entire user-agent exchange. Inside it, each iteration of the TAO loop opens an `llm.call` span. Inside each `llm.call`, every tool dispatch opens a `tool.call` span. Spans nest by `parent_span_id`. A whole turn shares one `trace_id`.

Three identifiers tie the tree together:

- **`trace_id`** — unique per top-level operation (the turn). Every span in the tree shares this.
- **`span_id`** — unique per span. Generated when the span opens.
- **`parent_span_id`** — the `span_id` of the enclosing span. `null` for the root.

Given these three, you can reassemble the tree by simple joins, ask things like "show me every tool call for this turn" or "what was the cumulative duration of all llm.call spans," and feed any downstream tool (Langfuse, Honeycomb, custom dashboards) that understands OpenTelemetry's data model.

## JSONL as the wire format

Spans get written one per line to a single JSON-lines file:

```
~/.traced-agent/traces.jsonl
```

JSONL is the right shape for this:

- **Append-only.** Each new span is a single line, written atomically. No locking, no journaling, no race conditions across concurrent tools running in parallel.
- **Trivial to grep.** `grep '"name":"tool.call"' traces.jsonl` extracts every tool call ever.
- **Trivial to load.** `jq`, Python `for line in open(...)`, anything that streams. Loaders in every language are 5 lines.
- **Trivial to ship elsewhere.** Pipe it into Langfuse / Honeycomb / S3 / Loki. Vendors all speak JSONL or trivially-derived formats.

A typical span on disk looks like:

```json
{
  "trace_id": "a1b2c3d4e5f6a7b8",
  "span_id": "1234567890abcdef",
  "parent_span_id": "fedcba0987654321",
  "name": "tool.call",
  "start_time": "2026-05-19T14:32:11.043281+00:00",
  "end_time": "2026-05-19T14:32:11.087449+00:00",
  "duration_ms": 44.17,
  "attributes": {
    "tool.name": "read",
    "tool.input": {"path": "pyproject.toml"},
    "tool.output": "   1| [project]\n   2| name = \"examples\"\n   3| ..."
  }
}
```

Every span has the same shape. The `attributes` dict carries whatever you want about the specific operation.

## What to capture

The shape is the easy part. The judgement is *what attributes go on each span*. Module 8 captures the following:

| Span | Attributes |
|---|---|
| `turn` | `user_input` (first 200 chars), `iterations`, `aborted` (if bound hit) |
| `llm.call` | `model`, `iteration`, `input_tokens`, `output_tokens`, `error` (if any) |
| `tool.call` | `tool.name`, `tool.input`, `tool.output` (first 500 chars), `error` (if any) |

A few choices worth knowing:

- **Truncate large fields.** Tool outputs are uncapped in memory but capped on disk. Saving the full output of every `bash` and `grep` call would balloon the trace file in minutes. 500 chars is enough to see what happened; for forensics, replay the agent against the same prompt.
- **Capture both input and output of tools.** "What did the model ask for" and "what came back" are both load-bearing for debugging.
- **Capture token counts on the LLM call.** Most observability questions in production are about cost, and cost is tokens.
- **Capture errors anywhere they happen.** The span context manager does this automatically.

## The `span()` context manager

The mechanism is one Python `@contextmanager`. It captures start/end times, generates IDs, accumulates attributes, and writes the span on exit:

```python
import secrets
import time
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

TRACE_FILE = Path.home() / ".traced-agent" / "traces.jsonl"


def _new_id() -> str:
    return secrets.token_hex(8)


def write_span(span: dict) -> None:
    TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACE_FILE, "a") as f:
        f.write(json.dumps(span, default=str) + "\n")


@contextmanager
def span(name: str, parent: str | None = None, trace_id: str | None = None, **attributes):
    span_id = _new_id()
    trace_id = trace_id or _new_id()
    start = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    rec = {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent,
        "name": name,
        "start_time": start.isoformat(),
        "attributes": dict(attributes),
    }
    try:
        yield rec
    except Exception as e:
        rec["attributes"]["error"] = str(e)
        raise
    finally:
        rec["end_time"] = datetime.now(timezone.utc).isoformat()
        rec["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        write_span(rec)
```

The pattern in use:

```python
with span("tool.call", parent=parent_span_id, trace_id=trace_id,
          **{"tool.name": "read", "tool.input": {"path": "foo.py"}}) as rec:
    result = await read(path="foo.py")
    rec["attributes"]["tool.output"] = result[:500]
```

Three properties make this clean:

1. **Wall-clock + monotonic timing.** `datetime.now()` gives ISO timestamps for humans; `time.perf_counter()` gives accurate durations regardless of system clock changes.
2. **Attributes are mutable inside the `with` block.** You don't have to know everything upfront. Open the span, do the work, attach `tool.output` once you have it, exit.
3. **Exceptions don't lose the span.** The `try / except / raise` re-raises after attaching an `error` attribute. `finally` writes the span regardless of how the block exits.

This is the OpenTelemetry SDK pattern in 25 lines of Python. Real OpenTelemetry would give you batched exporters, sampling, and pluggable backends. The baseline above is enough to ship and reach 99% of debugging needs.

## Wiring spans through the TAO loop

Three nested `with` blocks, one per span level. Inside `main()`:

```python
with span("turn", attributes={"user_input": user_input[:200]}) as turn_rec:
    trace_id = turn_rec["trace_id"]
    turn_span_id = turn_rec["span_id"]

    for iteration in range(MAX_ITERATIONS):
        messages, turn_start = enforce_budget(messages, turn_start, system)

        with span("llm.call", parent=turn_span_id, trace_id=trace_id,
                  iteration=iteration) as llm_rec:
            async with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_RESPONSE_TOKENS,
                system=system,
                messages=messages,
                tools=TOOL_SCHEMAS,
            ) as stream:
                async for text in stream.text_stream:
                    print(text, end="", flush=True)
                print()
                response = await stream.get_final_message()
            llm_rec["attributes"].update({
                "model": MODEL,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            })
            llm_span_id = llm_rec["span_id"]

        # ... tool dispatch, which opens its own tool.call spans ...
```

And `execute_tool` opens the deepest span:

```python
async def execute_tool(name: str, input: dict, parent_span: str, trace_id: str) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"

    with span("tool.call", parent=parent_span, trace_id=trace_id,
              **{"tool.name": name, "tool.input": input}) as rec:
        if name in DANGEROUS_TOOLS:
            if not await request_approval(name, input):
                rec["attributes"]["error"] = "user denied approval"
                return "error: user denied approval"
        try:
            result = await tool["fn"](**input)
            output = result if isinstance(result, str) else str(result)
            rec["attributes"]["tool.output"] = output[:500]
            return output
        except Exception as e:
            rec["attributes"]["error"] = str(e)
            return f"error: {e}"
```

The only signature change from Module 7 is that `execute_tool` now takes `parent_span` (the enclosing `llm.call`'s span ID) and `trace_id`. The call sites pass them down. Every tool dispatch is now a child of the LLM call that produced it, which is a child of the turn that started it.

## Reading traces

Once traces exist, the patterns you can see are striking. Three examples.

### A healthy trace

```bash
$ tail -n 12 ~/.traced-agent/traces.jsonl | jq -c '[.name, .duration_ms, .attributes]'
["turn", 8240.55, {"user_input": "what does stateless_chatbot.py import?", "iterations": 2}]
["llm.call", 1820.13, {"iteration": 0, "input_tokens": 3142, "output_tokens": 87, "model": "claude-sonnet-4-5"}]
["tool.call", 4.92, {"tool.name": "read", "tool.input": {"path": "stateless_chatbot.py"}, "tool.output": "..."}]
["llm.call", 6410.18, {"iteration": 1, "input_tokens": 4521, "output_tokens": 174, "model": "claude-sonnet-4-5"}]
```

Two iterations. One tool call (a `read`). 8.2s end-to-end. Token usage growing across iterations (the conversation got longer). Normal.

### A stuck-loop trace

```bash
$ grep '"name":"tool.call"' traces.jsonl | jq -c '.attributes["tool.name"]' | sort | uniq -c
     22 "bash"
      1 "read"
```

22 `bash` calls in one turn. Healthy turns have 2–5 tool calls total. Drop into the file and see what the model was doing:

```bash
$ jq -c 'select(.name == "tool.call" and .attributes["tool.name"] == "bash") | .attributes["tool.input"]' traces.jsonl
{"cmd": "ls"}
{"cmd": "ls /tmp"}
{"cmd": "ls /var"}
{"cmd": "ls /etc"}
...
```

Twenty-two `ls` calls. The model was looking for a file that didn't exist and refused to give up. This is the kind of pattern you'd never spot from the terminal scrollback — it just looks like "the agent took a while." The trace makes it diagnosable.

### A "model couldn't find the tool" trace

```bash
$ jq -c '[.name, .attributes]' traces.jsonl
["turn", {"user_input": "fetch the latest data from the api"}]
["llm.call", {"iteration": 0, "input_tokens": 2841, "output_tokens": 73}]
["llm.call", {"iteration": 1, "input_tokens": 2956, "output_tokens": 85}]
["llm.call", {"iteration": 2, "input_tokens": 3071, "output_tokens": 67}]
```

Three `llm.call` spans, zero `tool.call` spans. The model talked to itself three times and never dispatched a tool. Looking at the actual text content of the assistant responses (not on the trace by default, but easy to add): the model is asking the user to clarify which API. The trace tells you immediately that the issue isn't the tools — it's that the model's response didn't include a tool_use block at all.

## A note on the M7 guardrails

The classifier and judge calls from Module 7 are tracing-shaped too. With one extra `with span(...)` block, every sentiment check and hallucination judgement becomes a recorded span:

```python
with span("guardrail.sentiment", parent=turn_span_id, trace_id=trace_id) as rec:
    label, score = check_sentiment(final_text)
    rec["attributes"].update({"label": label, "score": score})
```

Then when a hallucination flag fires, you can trace back through the JSONL and see exactly which response triggered it and what the judge said. We don't wire this in by default — the point of M8 is the `span()` pattern itself. Adding more span types is a one-liner once the pattern exists.

## The tooling landscape

The file-based JSONL approach is the floor, not the ceiling. Real production agents ship traces to dedicated observability platforms. A few worth knowing:

| Platform | Where it sits |
|---|---|
| **OpenTelemetry** | Open standard for traces, metrics, logs. Underneath most vendor offerings. Your JSONL spans translate directly. |
| **Langfuse** | LLM-native, open source. Built for prompt/trace inspection. Self-hostable. |
| **Arize Phoenix** | LLM-native, open source. Good for offline trace analysis and eval workflows. |
| **Honeycomb** | General observability. Strong query model, fast over large traces. |
| **Helicone** | Lightweight LLM proxy that captures requests and responses. |
| **LangSmith** | Tightly coupled to LangChain. Good if you use it; less useful otherwise. |
| **Logfire** | Pydantic's observability product. Python-native, OpenTelemetry-compatible. |

The migration path is consistent: keep `span()` as the API, swap the `write_span()` implementation. Instead of writing to disk, push to the platform's SDK. The rest of the harness doesn't change.

For most agents, the discipline is what matters more than the vendor. Get the spans right, get them written, get them structured. Where they live afterward is a deployment choice.

## What the traced agent does, end to end

Three changes from Module 7:

1. The `span()` context manager and `write_span()` helper at the top of the file.
2. Three nested `with` blocks in `main()` opening `turn`, `llm.call`, and `tool.call` spans.
3. `execute_tool` gains two parameters (`parent_span`, `trace_id`) and opens its own span.

Everything else from Module 7 is preserved: the sandbox, the heuristic guardrails, the classifier and judge gates (when present), the persistence, the budget, the recall. Tracing wraps the existing components — it doesn't replace any of them.

State directory: `~/.traced-agent/` — adds `traces.jsonl` to the `messages.json` and `recall.json` from before.

## Run it

The end state lives at [`examples/traced_agent.py`](../../examples/traced_agent.py). Requires Docker.

```bash
cd examples
uv run traced_agent.py
```

Have a normal conversation:

```
❯ what does stateless_chatbot.py import?
...
❯ /q
```

Then inspect:

```bash
tail -n 20 ~/.traced-agent/traces.jsonl | jq
```

Each line is one span. You'll see one `turn`, one or more `llm.call`s, zero or more `tool.call`s underneath each.

Watch live as the agent runs:

```bash
# In another terminal:
tail -f ~/.traced-agent/traces.jsonl | jq -c '[.name, .duration_ms, .attributes["tool.name"] // .attributes["model"]]'
```

Useful aggregations:

```bash
# Total LLM cost (tokens) across all traces:
jq -s 'map(select(.name == "llm.call") | .attributes.input_tokens + .attributes.output_tokens) | add' ~/.traced-agent/traces.jsonl

# Average tool duration by name:
jq -s 'group_by(.attributes["tool.name"]) | map({tool: .[0].attributes["tool.name"], avg_ms: (map(.duration_ms) | add / length)})' \
   ~/.traced-agent/traces.jsonl

# Find any error spans:
jq -c 'select(.attributes.error)' ~/.traced-agent/traces.jsonl
```

The traces accumulate across runs. After a week of use you'll have a deep enough sample to spot patterns: tools that fail often, prompts that produce long turns, models that drift.

## What's missing

- **Traces tell you what happened. They don't tell you whether it was *good*.** A turn with 30 tool calls and a wrong answer looks the same in the JSONL as a turn with 30 tool calls and the right answer.
- **Manual inspection doesn't scale.** Watching `tail -f` is great for one agent on one developer machine. For a production agent or a curriculum like this with many checkpoints, you need automation.
- **No way to compare runs.** "Did adding the sentiment guardrail change anything?" You can't answer that question by reading traces.

The harness needs a way to *judge* its own behaviour, repeatably and quantitatively. That's evaluation — the next module.

---

**Next:** [Module 9: Add evaluation](../09-add-evaluation/)
