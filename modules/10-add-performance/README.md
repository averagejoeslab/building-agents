# Add performance

> **Harness component: production hardening.** What turns a working harness into a fast and cheap one — prompt caching, tool output caching, threading for blocking work, and a single named convergence point for context.

Module 8 made the agent observable. Module 9 made it measurable. The agent works. The traces are clean. The eval suite is green.

But it's still expensive. Every turn re-sends the same ~3000 tokens of system prompt + tool schemas as fresh input. Every turn re-reads files the previous iteration already pulled. Every blocking I/O call inside a tool body stops the event loop dead, so even when ten tool calls go out via `asyncio.gather` they execute serially. And the main loop assembles its context inline at the top of every turn — system prompt construction, recall lookup, tool schema reference, budget pack — duplicated logic, hard to swap.

Module 10 fixes those four. By the end you have [`examples/production_agent.py`](../../examples/production_agent.py): the same harness from M8 (sandbox + guardrails + hierarchical traces + replay) with four production optimizations bolted on. Nothing the previous modules built is lost; everything gets faster, cheaper, and easier to operate.

## Four optimizations, top to bottom

| # | Optimization | What it reduces |
|---|---|---|
| 1 | **Prompt caching** | Input token cost across a long session |
| 2 | **Tool output caching** | Wall-clock latency + token cost on repeat reads |
| 3 | **Threading for blocking work** | Wall-clock latency on parallel tool dispatch |
| 4 | **Structured prompts + `assemble()`** | Coupling between the loop and context construction |

## 1. Prompt caching

Anthropic's API supports **prompt caching** — mark a prefix of the request with `cache_control: {type: "ephemeral"}` and the server caches it for ~5 minutes. Subsequent requests that share the same prefix pay a tiny cache-read fee instead of the full input-token rate. For a long coding session sending the same ~3KB system prompt + ~1KB tool schemas every turn, this is a 5–10× input cost reduction.

The cache works on **prefix match**. Everything up to and including the marked block is what gets cached. Place the breakpoint after the static parts; everything before the breakpoint must be byte-identical across calls or the cache misses.

Two breakpoints in this harness:

**On the last tool schema** — tool schemas are static across the whole program, so they're the perfect cache prefix:

```python
def build_tool_schemas(tools):
    schemas = []
    items = list(tools.items())
    for i, (name, meta) in enumerate(items):
        # ... build properties / required from registry ...
        schema = {
            "name": name,
            "description": meta["description"],
            "input_schema": {"type": "object", "properties": properties, "required": required},
        }
        if i == len(items) - 1:
            schema["cache_control"] = {"type": "ephemeral"}
        schemas.append(schema)
    return schemas
```

**On the static base system prompt** — the base prompt never changes; recalled-memory blocks vary per turn. Mark only the static one:

```python
BASE_SYSTEM_PROMPT = """You are a coding agent. ..."""

def assemble(user_input, history, recalled):
    system_blocks = [
        {"type": "text", "text": BASE_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
    ]
    if recalled:
        memory_block = "\n\n".join(f"- {s}" for s in recalled)
        system_blocks.append({
            "type": "text",
            "text": f"## Recalled context from past conversations\n\n{memory_block}",
        })
    # ... pack messages, return {system, tools, messages} ...
```

The recalled-memory block has no `cache_control` because it changes turn-to-turn. The base prompt does, because it doesn't.

> [!NOTE]
> **The cache has a ~5-minute TTL.** If the agent goes idle longer than that, the next turn pays full input cost again. For interactive sessions this is fine; for batch workloads, pacing matters. A handful of turns inside 5 minutes pays once; the same turns spread across an hour pay every time.

## 2. Tool output caching

Two `read` calls on `pyproject.toml` in the same turn shouldn't pay twice — same input, same output. A small content-addressed cache around idempotent tools handles it.

```python
IDEMPOTENT_TOOLS = {"read", "glob", "grep"}

_tool_cache: dict[str, str] = {}

def _cache_key(name: str, input: dict) -> str:
    payload = json.dumps({"name": name, "input": input}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
```

`json.dumps(..., sort_keys=True)` makes the key stable regardless of dict insertion order. SHA-256 is overkill cryptographically but cheap; it just gives us a fixed-size string handle on the input.

Wired into `execute_tool`:

```python
async def execute_tool(name, input, parent_span, trace_id):
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"

    with span("tool.call", parent=parent_span, trace_id=trace_id,
              **{"tool.name": name, "tool.input": input}) as rec:

        # Cache lookup for idempotent reads
        if name in IDEMPOTENT_TOOLS:
            key = _cache_key(name, input)
            if key in _tool_cache:
                cached = _tool_cache[key]
                rec["attributes"]["cache_hit"] = True
                rec["attributes"]["tool.output"] = cached
                return cached

        # ... approval, dispatch, capture ...

        if name in IDEMPOTENT_TOOLS:
            _tool_cache[_cache_key(name, input)] = output
        elif name in DANGEROUS_TOOLS:
            _tool_cache.clear()
        return output
```

Two policies worth being explicit about:

**Only idempotent tools cache.** `read`, `glob`, `grep` are pure observations of the filesystem — same input, same output (within a turn). `write`, `edit`, `bash` change state and aren't safe to cache.

**Dangerous tools invalidate the entire cache.** If `bash rm foo.py` ran, the cached `read foo.py` is now wrong. Rather than tracking fine-grained dependencies (which file did `bash` touch?), the cache wipes on any state-changing tool. Conservative, but correct.

The `cache_hit: true` attribute lands in the span so the trace records *why* a tool call took 0ms.

## 3. Threading for blocking work

The TAO loop dispatches tools concurrently:

```python
outputs = await asyncio.gather(*(
    execute_tool(c.name, c.input, llm_span_id, trace_id)
    for c in tool_calls
))
```

`asyncio.gather` runs awaitables concurrently — but only if they actually yield control. If a tool body is `async def grep(...)` but does a synchronous `os.walk` that takes 300ms, the event loop is *blocked* for those 300ms. The other tool calls in the gather wait. They're not concurrent; they're serial with extra ceremony.

The honest shape is: write the tool bodies **sync**, then dispatch them via `asyncio.to_thread`:

```python
def grep(pattern: str, path: str) -> str:
    # blocking os.walk, regex, file reads — all synchronous
    ...

async def execute_tool(name, input, ...):
    ...
    fn = tool["fn"]
    if inspect.iscoroutinefunction(fn):
        result = await fn(**input)
    else:
        # Push blocking I/O onto a worker thread so the event loop
        # can dispatch other tool calls concurrently.
        result = await asyncio.to_thread(fn, **input)
```

`asyncio.to_thread` runs the function in Python's default thread pool. The event loop is free to dispatch the next gathered tool while this one's worker thread churns. Three `grep`s across a big tree go out at the same wall-clock time, not back-to-back.

`inspect.iscoroutinefunction` keeps the dispatch flexible — if you do have a genuinely async tool (e.g. an HTTP call with `aiohttp`), the executor still does the right thing. Sync tools get the thread; async tools get awaited directly.

> [!NOTE]
> **Python's GIL means CPU-bound work in a thread doesn't speed up.** Threads help here because the work is **I/O-bound** — `os.walk`, `subprocess.run`, `open(...).read()` release the GIL while they wait on the kernel. For genuinely CPU-bound tools (large embedding inference, heavy regex), use `asyncio.to_thread` for the I/O wait, or escalate to `loop.run_in_executor` with a `ProcessPoolExecutor`.

## 4. Structured prompts + `assemble()`

Modules 4–8 built up an inline context construction at the top of every turn: do the recall, build the system string, pack the messages buffer, reference the tool schemas. By M8 the main loop is doing five separate things before the first LLM call — and the same five things in slightly different shapes inside `replay_trace`.

The fix is to **converge** that work into one named function. `assemble()` returns the three things the LLM call needs as a dict:

```python
def assemble(user_input: str, history: list, recalled: list[str]) -> dict:
    """The convergence point: build {system, tools, messages} for the next LLM call."""
    system_blocks = [
        {"type": "text", "text": BASE_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
    ]
    if recalled:
        memory_block = "\n\n".join(f"- {s}" for s in recalled)
        system_blocks.append({
            "type": "text",
            "text": f"## Recalled context from past conversations\n\n{memory_block}",
        })
    messages = pack_messages(user_input, system_blocks, history)
    return {"system": system_blocks, "tools": TOOL_SCHEMAS, "messages": messages}
```

The main loop now reads as one line of setup per turn:

```python
with span("memory.recall", parent=turn_span_id, trace_id=trace_id, query=user_input) as recall_rec:
    recalled, scored = recall(user_input, recall_entries)
    recall_rec["attributes"]["recalled"] = recalled
    recall_rec["attributes"]["candidates_scored"] = scored

ctx = assemble(user_input, history, recalled)
```

Then `ctx["system"]`, `ctx["tools"]`, `ctx["messages"]` get passed straight to `client.messages.stream(...)`.

The win is testability and reuse. `assemble()` is pure — given (user_input, history, recalled), it returns the request shape. You can unit-test it, swap it for an A/B variant, or call it from a fresh process to reproduce what a turn looked like — without touching the loop.

The structured system prompt is also where this lands cleanly. The base prompt is now a multi-section piece of writing (tools, working style, when you're done) rather than a one-liner — and because it's a separate content block from the recalled memories, the cache breakpoint is unambiguous.

## What the production agent does, end to end

`production_agent.py` is `traced_agent.py` with the four optimizations bolted on. Everything from previous modules is preserved:

- **M4 memory:** `messages.json`, `recall.json`, budget eviction, semantic recall.
- **M5 toolkit:** 6 tools through a registry, central executor, parallel dispatch via gather.
- **M6 sandbox:** `bash` routed through `docker exec` with the same hardening flags.
- **M7 guardrails:** HITL approval, `MAX_ITERATIONS = 30`, retry/backoff at the SDK, DistilBERT sentiment + Haiku hallucination judge on the final response.
- **M8 observability:** Hierarchical trace tree (one JSON line per turn), all 8 span types, full system + messages captured on `llm.call` for replay, `replay_trace(trace_id)` re-issues a turn.

The differences from M8 are the four optimizations above and nothing else. Diff `traced_agent.py` against `production_agent.py` and every change should map to one of:

1. `cache_control` stamps on tool schemas + system block.
2. `IDEMPOTENT_TOOLS`, `_tool_cache`, `_cache_key`, cache lookup/store/invalidate inside `execute_tool`.
3. Tool bodies converted from `async def` to `def`; `inspect.iscoroutinefunction` + `asyncio.to_thread` dispatch.
4. `BASE_SYSTEM_PROMPT` as a multi-section string; `assemble()` returning the request dict.

State directory: `~/.production-agent/` — same shape as `traced-agent` (`messages.json`, `recall.json`, `traces.jsonl`).

## Run it

```bash
cd examples
uv run production_agent.py
```

Requires Docker. First run builds the sandbox image and downloads the DistilBERT + sentence-transformers models if they're not cached.

Try a session where the cache should pay off:

```
❯ what does pyproject.toml import?
❯ how is the embedding model loaded in stateful_chatbot.py?
❯ how does the tool registry work in agent.py?
❯ /q
```

After the first turn, subsequent turns send the same system prefix + tool schemas. The cache hits register inside Anthropic; you can verify by inspecting `response.usage.cache_read_input_tokens` if you instrument for it.

Inspect tool-cache hits in the trace:

```bash
jq -c '.. | objects | select(.name? == "tool.call" and .attributes.cache_hit == true) | [.attributes["tool.name"], .attributes["tool.input"]]' \
   ~/.production-agent/traces.jsonl
```

Replay a turn (same machinery as M8):

```python
import asyncio
from production_agent import replay_trace
asyncio.run(replay_trace("a1b2c3d4e5f6a7b8"))
```

Run the eval suite against it:

```bash
uv run --project examples evals/run.py examples/production_agent.py
```

## What this still leaves on the table

`production_agent.py` is a *production-shaped* harness — one user, one terminal, one process, one machine. To run it as an actual production service you still need:

- **Deployment shape.** A long-running process, signal handling beyond `atexit`, graceful shutdown that flushes pending spans, restart-on-crash. Today the agent dies on Ctrl-C and any in-flight `_pending_spans` not yet flushed are lost.
- **Multi-user concurrency.** Right now state lives in `~/.production-agent/`. Two users sharing a process would collide. A real deployment scopes state by user (or session), keeps per-session message buffers and recall stores, and isolates sandbox containers per user.
- **PII / secret redaction in traces.** The trace captures full prompts, full tool outputs, full responses. For local dev that's right. For a hosted service, run a classifier (M7-style) over tool outputs before they hit the span, or sample at 1% full-fidelity and store the rest as token-count summaries.
- **Vendor observability.** Replace the JSONL `write` with an OpenTelemetry exporter or a vendor SDK (Langfuse, Honeycomb, Logfire). `span()` stays the same; only `_flush_trace` changes.
- **Cost / latency dashboards.** The trace has token counts and `duration_ms` per span. Aggregating them into a dashboard (cost per session, p50/p95 latency per tool, guardrail flag rates) is a separate plumbing job.
- **CI integration of the eval suite.** Run `evals/run.py` on every commit, gate merges on the diff staying green. Today this is a manual command.

Each of those is a deployment-engineering concern, not a harness-engineering one. The harness is done.

---

You've reached the end of the curriculum. Back to the [root README](../../README.md).
