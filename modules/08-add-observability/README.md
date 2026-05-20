# Add observability

> **Harness component: structured tracing.** A complete, structured record of every action the harness took on every turn. What the model saw, what it produced, which tools fired with what arguments, what they returned, which guardrails ran, which memories were pulled. The harness watching itself.

Module 7 made the agent safer. It also made it more opaque. Approvals scroll off the terminal. Sentiment flags disappear. Retries happen silently inside the SDK. The hallucination judge runs once and forgets. When something goes wrong, *"what just happened?"* has no answer.

Module 8 fixes that by tracing the agent's entire activity to a structured log. By the end you have [`examples/traced_agent.py`](../../examples/traced_agent.py) — `safe_agent.py` plus a span-based observability layer, comprehensive enough to support **four distinct downstream uses**:

| Purpose | What it needs |
|---|---|
| **Auditability** | Post-hoc readability — what did the agent do, when, why, with what arguments. |
| **Replay** | Enough captured state to re-issue every LLM call and reproduce a turn. |
| **Checkpointing** | Enough captured state to resume from any point mid-turn. |
| **Evaluation** | Structured trajectories that an offline judge (M9) can score. |

These four shape every decision about *what* to capture and *how*. A trace that supports all four is a trace that captures the full agent activity, not just summaries.

## The four purposes, concretely

**Auditability.** A human (or compliance system) needs to read what the agent did. "On Tuesday at 2:14 PM the agent received this prompt; it consulted these stored memories; it called `read` on `pyproject.toml`; it returned this answer; the hallucination judge flagged it as ungrounded." Every step accounted for.

**Replay.** Given a trace_id, the harness should be able to re-issue every LLM call with the exact prompts originally sent. Useful for debugging non-deterministic failures ("what if the model had been asked again?"), for evaluating a prompt change ("re-run yesterday's turn with the new system prompt and see if it goes differently"), and for forensics.

**Checkpointing.** A long-running agent can crash, get interrupted, or hit the iteration cap mid-task. The trace plus the persisted state files (`messages.json`, `recall.json`) should be enough to resume — pick up at iteration N, feed in the same context, continue.

**Feeding evaluation.** Module 9 will judge agent behaviour automatically. Its inputs are traces: the trajectory of tool calls, the final response, the cost, the guardrail verdicts. Without tracing, M9 would have nothing to score except the final stdout.

## The span model

The unit of trace is a **span**: one operation with a name, a start/end time, attributes, and an optional parent. Spans form a tree. The pattern is borrowed from OpenTelemetry, adapted to the TAO loop.

For one user turn, the tree looks like this:

```
turn  (trace_id = T1)
├── memory.recall                   (query: "what does foo.py import?")
├── llm.call            (iter 0)
│   ├── tool.call       (read foo.py)
│   └── tool.call       (grep imports)
├── llm.call            (iter 1)
│   └── tool.call       (read bar.py)
├── llm.call            (iter 2)    ← no tool calls; final response
├── guardrail.sentiment             (POSITIVE 0.99)
├── guardrail.hallucination         (GROUNDED)
└── memory.summarize                (summary text)
```

Every span in this tree shares one `trace_id`. Each has a unique `span_id`. Each (except the root) points at its parent via `parent_span_id`. The shape is:

```json
{
  "trace_id": "a1b2c3d4e5f6a7b8",
  "span_id":  "1234567890abcdef",
  "parent_span_id": "fedcba0987654321",
  "name": "tool.call",
  "start_time": "2026-05-19T14:32:11.043281+00:00",
  "end_time":   "2026-05-19T14:32:11.087449+00:00",
  "duration_ms": 44.17,
  "attributes": {
    "tool.name": "read",
    "tool.input": {"path": "pyproject.toml"},
    "tool.output": "   1| [project]\n   2| name = \"examples\"\n..."
  }
}
```

Eight span types make up the full trace tree for one turn:

| Span | Captures | Why it exists |
|---|---|---|
| `turn` | user_input, system_prompt, recalled, final_response, iterations, aborted | Root. Audit-trail entry point. |
| `memory.recall` | query, candidates_scored, recalled | Which memories were pulled and why. |
| `llm.call` | model, iteration, system, messages, response_content, input_tokens, output_tokens | The prompt sent and the response received. **Load-bearing for replay.** |
| `tool.call` | tool.name, tool.input, tool.output, approval | Every action taken. |
| `guardrail.sentiment` | text, label, score | Classifier verdict. |
| `guardrail.hallucination` | user_input, response, evidence, grounded, reason | Judge verdict. |
| `memory.summarize` | summary, turn_messages_count | What got written back to recall. |

Note: the `llm.call` span captures the **full system prompt and full messages array**, not just token counts. That's what makes replay possible.

## JSONL as the wire format

`~/.traced-agent/traces.jsonl` is one JSON object per line — and **one line per turn**. The whole trace tree (`turn` and every span beneath it) gets nested into a single JSON object before being written. Reading the file directly shows the conversation timeline; no post-processing script needed.

A turn on disk looks like:

```json
{
  "trace_id": "342fbbaaf44527c2",
  "span_id":  "...",
  "name": "turn",
  "start_time": "...",
  "end_time": "...",
  "duration_ms": 12482.01,
  "attributes": {
    "user_input": "what does pyproject.toml import?",
    "system_prompt": "You are a helpful coding assistant.",
    "iterations": 2,
    "final_response": "The `pyproject.toml` file..."
  },
  "children": [
    {"name": "memory.recall", "...": "...", "children": []},
    {
      "name": "llm.call",
      "attributes": {"iteration": 0, "model": "...", "system": "...", "messages": [...], "response_content": [...], "input_tokens": 1059, "output_tokens": 84},
      "children": [
        {"name": "tool.call", "attributes": {"tool.name": "read", "tool.input": {...}, "tool.output": "..."}, "children": []}
      ]
    },
    {"name": "llm.call", "...": "...", "children": []},
    {"name": "guardrail.sentiment", "attributes": {"label": "POSITIVE", "score": 0.99}, "children": []},
    {"name": "guardrail.hallucination", "attributes": {"grounded": true, "reason": "..."}, "children": []},
    {"name": "memory.summarize", "attributes": {"summary": "..."}, "children": []}
  ]
}
```

The `children` array on each span carries the nested sub-spans, sorted by start time so reading the tree top-to-bottom is the same as reading the turn forward in time.

Properties of this format:

- **Self-contained.** Each line is a complete trace. You can `jq '.' < traces.jsonl` and immediately see the full turn.
- **Append-only at the file level.** One turn = one line, written atomically when the turn span closes. No locking across concurrent tools.
- **Easy to query.** Standard `jq` walks the `.children[]` arrays. Recursive descent (`..`) drills into every span in a tree.
- **Easy to ship.** Each line is a complete OpenTelemetry-style span tree; vendor SDKs (Langfuse, Honeycomb, etc.) accept the same shape.

To rotate: `mv traces.jsonl traces.jsonl.$(date +%s)`.

### Trade-off: live streaming vs. self-contained trees

The format above writes one turn-tree at a time when the turn completes. A `tail -f` watcher will see *completed turns appear as units*, not individual spans as they happen. If you want live span-by-span monitoring during long turns, swap the buffer-and-emit logic for "write each span flat as it closes" (M7-style) — the rest of the harness doesn't change. The chosen default favors human readability of the post-hoc file.

## The `span()` context manager + tree assembly

Two helpers do all the work. Individual `with span(...)` blocks accumulate into an in-memory buffer; when the root span (the `turn`) closes, the buffer gets assembled into a parent-child tree and written as one JSON line.

```python
_pending_spans: list[dict] = []


def _flush_trace(trace_id: str) -> None:
    """Build the parent-child tree for `trace_id` and append one JSON line."""
    spans = [s for s in _pending_spans if s["trace_id"] == trace_id]
    for s in spans:
        _pending_spans.remove(s)
    if not spans:
        return

    by_id = {s["span_id"]: s for s in spans}
    for s in spans:
        s["children"] = []

    root = None
    for s in spans:
        parent_id = s.get("parent_span_id")
        if parent_id is not None and parent_id in by_id:
            by_id[parent_id]["children"].append(s)
        elif parent_id is None:
            root = s

    def _sort(node):
        node["children"].sort(key=lambda c: c["start_time"])
        for c in node["children"]:
            _sort(c)

    if root is None:
        return
    _sort(root)

    def _strip(node):
        node.pop("parent_span_id", None)  # redundant with tree structure
        for c in node["children"]:
            _strip(c)

    _strip(root)

    with open(TRACE_FILE, "a") as f:
        f.write(json.dumps(root, default=_serialize_for_trace) + "\n")


@contextmanager
def span(name: str, parent: str | None = None, trace_id: str | None = None, **attributes):
    span_id = _new_id()
    trace_id = trace_id or _new_id()
    t0 = time.perf_counter()
    rec = {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent,
        "name": name,
        "start_time": datetime.now(timezone.utc).isoformat(),
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
        _pending_spans.append(rec)
        if parent is None:
            _flush_trace(trace_id)
```

Four properties make this clean:

1. **Wall-clock + monotonic timing.** `datetime.now(timezone.utc)` produces ISO timestamps for humans; `time.perf_counter()` gives accurate durations regardless of system clock changes.
2. **Attributes are mutable inside the `with` block.** Open the span, do the work, attach the output once you have it, exit.
3. **Exceptions don't lose the span.** `try / except / raise` re-raises after attaching `error`; `finally` writes the span regardless of how the block exits.
4. **The tree builds itself.** When the root span (`parent=None`) closes, `_flush_trace()` runs automatically, assembling everything that was buffered for that trace into nested `children` arrays, dropping the now-redundant `parent_span_id` fields, and appending one JSON line.

This is the OpenTelemetry SDK pattern adapted for direct human readability. Real OpenTelemetry exporters would emit each span as a separate event; this format collapses each trace into one self-describing line. Either shape works — this one is easier to read with `jq`.

## Wiring spans through the agent

Open the `turn` span first; everything else nests under it.

```python
async def main():
    ...
    while True:
        user_input = input_("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        with span("turn", user_input=user_input) as turn_rec:
            trace_id = turn_rec["trace_id"]
            turn_span_id = turn_rec["span_id"]
            print(f"\n[trace_id: {trace_id}]")
            ...
```

Inside the turn, open a `memory.recall` span before consulting recall:

```python
            with span("memory.recall", parent=turn_span_id, trace_id=trace_id,
                      query=user_input) as recall_rec:
                recalled, scored = recall(user_input, recall_entries)
                recall_rec["attributes"]["recalled"] = recalled
                recall_rec["attributes"]["candidates_scored"] = scored
```

(Note: `recall()` now returns *both* the selected entries and the full scored candidate list. The candidates are captured by the trace — auditability for *what was considered* and not just *what was kept*.)

For each iteration, open an `llm.call` span and pass the full system + messages into its attributes:

```python
            for iteration in range(MAX_ITERATIONS):
                messages, turn_start = enforce_budget(messages, turn_start, system)

                with span("llm.call", parent=turn_span_id, trace_id=trace_id,
                          iteration=iteration,
                          model=MODEL,
                          system=system,
                          messages=messages) as llm_rec:
                    async with client.messages.stream(...) as stream:
                        ...
                        response = await stream.get_final_message()
                    response_content = clean_assistant_content(response.content)
                    llm_rec["attributes"].update({
                        "response_content": response_content,
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    })
                    llm_span_id = llm_rec["span_id"]
```

`execute_tool` opens a `tool.call` span and now captures the full input, full output, and the approval decision if applicable:

```python
async def execute_tool(name: str, input: dict, parent_span: str, trace_id: str) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"

    with span("tool.call", parent=parent_span, trace_id=trace_id,
              **{"tool.name": name, "tool.input": input}) as rec:
        if name in DANGEROUS_TOOLS:
            approved = await request_approval(name, input)
            rec["attributes"]["approval"] = "approved" if approved else "denied"
            if not approved:
                rec["attributes"]["error"] = "user denied approval"
                return "error: user denied approval"
        try:
            result = await tool["fn"](**input)
            output = result if isinstance(result, str) else str(result)
            rec["attributes"]["tool.output"] = output
            return output
        except Exception as e:
            rec["attributes"]["error"] = str(e)
            return f"error: {e}"
```

Output guardrails (sentiment + hallucination) each get their own span:

```python
                    with span("guardrail.sentiment", parent=turn_span_id, trace_id=trace_id,
                              text=final_text) as sent_rec:
                        label, score = check_sentiment(final_text)
                        sent_rec["attributes"].update({"label": label, "score": score})
                        if label == "NEGATIVE" and score > 0.85:
                            print(f"\n⚠ guardrail: response shows negative sentiment ({score:.2f})")

                    if final_text.strip():
                        tool_evidence = collect_tool_evidence(messages[turn_start:])
                        with span("guardrail.hallucination", parent=turn_span_id, trace_id=trace_id,
                                  user_input=user_input, response=final_text,
                                  evidence=tool_evidence) as hall_rec:
                            grounded, reason = await hallucination_judge(user_input, final_text, tool_evidence)
                            hall_rec["attributes"].update({"grounded": grounded, "reason": reason})
```

And after the turn, the recall-summary write gets a span too:

```python
        with span("memory.summarize", parent=turn_span_id, trace_id=trace_id) as sum_rec:
            summary = await summarize_turn(turn_messages)
            sum_rec["attributes"]["summary"] = summary
            sum_rec["attributes"]["turn_messages_count"] = len(turn_messages)
        add_to_recall(summary, recall_entries)
```

Every action the agent takes is now inside a span. The trace tree at the top of this module is the actual structure of the JSONL file.

## Auditability: reading traces

After a run, each turn is one line. Read it like a record:

```bash
jq '.' ~/.traced-agent/traces.jsonl | less
```

Compact timeline of one turn — the tree reads top-to-bottom as the conversation:

```bash
$ jq '{name, duration_ms, attributes: {user_input: .attributes.user_input, iterations: .attributes.iterations},
       children: [.children[] | {name, duration_ms, children: [.children[]?.name]}]}' \
     ~/.traced-agent/traces.jsonl
{
  "name": "turn",
  "duration_ms": 12482.01,
  "attributes": {
    "user_input": "what does pyproject.toml import?",
    "iterations": 2
  },
  "children": [
    {"name": "memory.recall",          "duration_ms": 0.02,    "children": []},
    {"name": "llm.call",               "duration_ms": 2774.32, "children": ["tool.call"]},
    {"name": "llm.call",               "duration_ms": 5201.68, "children": []},
    {"name": "guardrail.sentiment",    "duration_ms": 937.53,  "children": []},
    {"name": "guardrail.hallucination","duration_ms": 1553.44, "children": []},
    {"name": "memory.summarize",       "duration_ms": 2009.17, "children": []}
  ]
}
```

Most other questions are short `jq` walks over the tree. The recursive-descent operator (`..`) drills into every nested span at any depth:

Find the system prompt actually sent on the last iteration of the most recent turn:

```bash
jq -r '[.. | objects | select(.name? == "llm.call") | .attributes.system] | last' \
   ~/.traced-agent/traces.jsonl
```

Every tool call across every turn, with timing:

```bash
jq -c '.. | objects | select(.name? == "tool.call") | [.attributes["tool.name"], .duration_ms]' \
   ~/.traced-agent/traces.jsonl
```

Cumulative LLM token spend:

```bash
jq -s '[.[] | .. | objects | select(.name? == "llm.call") | .attributes.input_tokens + .attributes.output_tokens] | add' \
   ~/.traced-agent/traces.jsonl
```

Every hallucination flag fired:

```bash
jq -c '.. | objects | select(.name? == "guardrail.hallucination" and .attributes.grounded == false) | .attributes' \
   ~/.traced-agent/traces.jsonl
```

Every turn that hit the iteration cap:

```bash
jq -c 'select(.attributes.aborted == true) | {trace_id, user_input: .attributes.user_input}' \
   ~/.traced-agent/traces.jsonl
```

Each line of the file *is* the trace tree. The file is the audit log.

## Replay: re-issuing LLM calls from a trace

Because each `llm.call` span captures the full system prompt and full messages array, a turn can be reproduced. The example ships a `_walk()` helper that traverses the tree depth-first, and a `replay_trace(trace_id)` function that pulls every `llm.call` (at any depth) and re-issues them:

```python
def _walk(node, predicate=None):
    """Yield (depth, span) pairs from a trace tree, depth-first."""
    def _go(n, d):
        if predicate is None or predicate(n):
            yield d, n
        for c in n.get("children", []):
            yield from _go(c, d + 1)
    yield from _go(node, 0)


async def replay_trace(trace_id: str) -> None:
    """Re-issue every llm.call in a trace with the prompts originally sent."""
    trees = [json.loads(line) for line in open(TRACE_FILE)]
    root = next((t for t in trees if t["trace_id"] == trace_id), None)
    if root is None:
        print(f"No trace found for trace_id {trace_id}")
        return

    llm_calls = sorted(
        (s for _, s in _walk(root) if s["name"] == "llm.call"),
        key=lambda s: s["attributes"]["iteration"],
    )
    print(f"Replaying {len(llm_calls)} LLM call(s) from trace {trace_id}...")
    for s in llm_calls:
        attrs = s["attributes"]
        response = await client.messages.create(
            model=attrs["model"],
            max_tokens=MAX_RESPONSE_TOKENS,
            system=attrs["system"],
            messages=attrs["messages"],
            tools=TOOL_SCHEMAS,
        )
        print(f"\n--- iteration {attrs['iteration']} ---")
        for block in response.content:
            if block.type == "text":
                print(block.text)
            elif block.type == "tool_use":
                print(f"[tool_use: {block.name}({block.input})]")
```

`_walk()` is a small generator that lets any caller drill into the nested tree without remembering its shape — useful in many other places too (e.g. an eval harness that wants to score trajectory).

Modulo the model's non-determinism (sampling temperature, seed effects), the responses will be very close to the originals. For deterministic replay you'd also pin the model snapshot and disable sampling. The point is that **the trace alone contains everything needed** — no separate snapshot file, no out-of-band state.

You can use this:

- To debug *"why did the agent do X on iteration 2?"* — re-issue just that iteration and inspect.
- To A/B test prompt changes — replay yesterday's turn with a new system prompt and compare.
- To recover from a crash — the trace shows what was happening when things died.

## Checkpointing: resuming from any iteration

A long-running agent can crash, be interrupted, or hit the iteration cap before completing. The trace + the persisted state files (`messages.json` + `recall.json` from M4) together contain enough to resume.

The pattern (sketched, not in the example):

```python
async def resume_from(trace_id: str, from_iteration: int) -> None:
    """Replay the agent up to iteration N, then continue the live loop."""
    # Load the persisted state files (M4 already does this).
    history = load_messages()
    recall_entries = load_recall()

    # Walk forward through the trace, replaying each iteration up to from_iteration.
    spans = [json.loads(line) for line in open(TRACE_FILE)]
    turn_spans = [s for s in spans if s["trace_id"] == trace_id]
    llm_spans = sorted(
        (s for s in turn_spans if s["name"] == "llm.call"),
        key=lambda s: s["attributes"]["iteration"],
    )

    # Pull the system prompt and messages from the iteration we want to resume at.
    target = next(s for s in llm_spans if s["attributes"]["iteration"] == from_iteration)
    messages = target["attributes"]["messages"]
    system = target["attributes"]["system"]

    # Continue the TAO loop from here, in a new turn span if you want fresh tracing.
    ...
```

Because every `llm.call` span captures the exact `messages` and `system` that were sent at that iteration, you can pick any iteration N as the new starting point. The conversation state and the recall state are independently persisted (M4); the trace tells you what the in-flight loop was doing.

This is the discipline behind real agent fault-tolerance: durable state files + structured traces = recoverable agents.

## Feeding evaluation (preview of M9)

The next module judges agent behaviour automatically against a suite of cases. The signals that make a good eval are exactly what the trace already captures:

- **Trajectory.** How many tool calls? Which ones? In what order? Available from `tool.call` span chain.
- **Cost.** Sum `input_tokens + output_tokens` across `llm.call` spans.
- **Latency.** Span `duration_ms`.
- **Final answer.** `turn.final_response`.
- **Guardrail outcomes.** `guardrail.*` span verdicts.
- **Memory behaviour.** Did recall pull anything? What got summarized back?

An eval doesn't need to re-run the agent if it can score the trace. M9 will use this directly.

## A note on retention and PII

The example captures **everything** by default — full prompts, full responses, full tool outputs. For most local development that's exactly what you want; you're the only one reading the file and you control the data going through.

In production you may need to be more selective:

- **Truncate.** Replace `output` with `output[:500]` for large blobs.
- **Redact.** Run a PII / credential classifier (M7 style) over tool outputs before they hit the span.
- **Sample.** Trace 1% of turns at full fidelity, 99% with token counts only.
- **Ship to a managed platform.** Use an OpenTelemetry SDK or a vendor SDK (Langfuse, Honeycomb) that handles retention policy server-side.

All of these are changes to `write_span()` and the attributes passed into `span()`. The harness wiring stays the same.

## The tooling landscape

The file-based JSONL approach is the floor, not the ceiling. Real production agents ship traces to dedicated observability platforms. Worth knowing:

| Platform | Where it sits |
|---|---|
| **OpenTelemetry** | Open standard for traces, metrics, logs. Underneath most vendor offerings. The JSONL spans above translate directly to OTel SpanData. |
| **Langfuse** | LLM-native, open source. Built for prompt/trace inspection. Self-hostable. |
| **Arize Phoenix** | LLM-native, open source. Strong offline analysis and eval workflows. |
| **Honeycomb** | General observability. Fast queries over large traces. |
| **Helicone** | Lightweight LLM proxy capturing requests and responses. |
| **LangSmith** | Tight LangChain integration. |
| **Logfire** | Pydantic's observability product. Python-native, OpenTelemetry-compatible. |

Migration path: keep `span()` as your API, swap `write_span()` for the platform's SDK. Everything else stays.

## What the traced agent does, end to end

Compared to `safe_agent.py` (M7), three things changed:

1. **Imports + tracing module** at the top: `_new_id`, `write_span`, `span()` context manager.
2. **`execute_tool`** gains `parent_span` and `trace_id` parameters and captures full input, full output, and approval decisions in its `tool.call` span.
3. **`main()`** opens spans at every level: `turn` → `memory.recall` → `llm.call` (per iteration) → `tool.call` (per dispatch) → `guardrail.sentiment` → `guardrail.hallucination` → `memory.summarize`.

`recall()` was refactored to return both the selected entries and the full scored candidate list — the trace captures the candidates so you can see *why* certain memories were picked. Everything else — the M4 memory machinery, the M5 toolkit, the M6 sandbox, the M7 guardrails — is preserved unchanged.

State directory: `~/.traced-agent/` — `messages.json`, `recall.json`, and the new `traces.jsonl`.

## Run it

The end state lives at [`examples/traced_agent.py`](../../examples/traced_agent.py). Requires Docker.

```bash
cd examples
uv run traced_agent.py
```

Have a normal conversation. Each turn prints its trace_id:

```
❯ what does stateless_chatbot.py import?
[trace_id: a1b2c3d4e5f6a7b8]
The file imports anthropic and python-dotenv.
❯ /q
```

Inspect the trace tree for that turn (one line, hierarchical):

```bash
$ jq 'select(.trace_id == "a1b2c3d4e5f6a7b8") | {name, duration_ms, children: [.children[].name]}' \
     ~/.traced-agent/traces.jsonl
{
  "name": "turn",
  "duration_ms": 8240.55,
  "children": [
    "memory.recall",
    "llm.call",
    "llm.call",
    "guardrail.sentiment",
    "guardrail.hallucination",
    "memory.summarize"
  ]
}
```

Tail-watch turn completions (one line appears when a turn ends):

```bash
tail -f ~/.traced-agent/traces.jsonl | jq -c '{name, duration_ms, input: .attributes.user_input, iters: .attributes.iterations}'
```

Replay a turn:

```python
# In a Python REPL or another script:
import asyncio
from traced_agent import replay_trace
asyncio.run(replay_trace("a1b2c3d4e5f6a7b8"))
```

The harness re-issues every LLM call with the same prompts, and you see how the model responds the second time around.

## What's missing

- **The trace tells you what happened. It doesn't tell you whether it was *good*.** A turn with 30 tool calls and a wrong answer looks structurally identical to a turn with 30 tool calls and the right answer.
- **No way to score traces in batch.** You can read them; you can replay them; you can't easily ask "across the last 100 runs, did the agent get better at answering questions correctly?"
- **No regression detection.** Did adding the sentiment guardrail change agent behaviour for the worse? Hard to tell without scoring.

The harness needs a *judge for its traces* — a way to run a suite of test cases, score every turn, and compare runs against each other. That's evaluation.

---

**Next:** [Module 9: Add evaluation](../09-add-evaluation/)
