import os
import re
import json
import time
import atexit
import asyncio
import hashlib
import inspect
import secrets
import subprocess
import glob as _glob
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from transformers import pipeline
import tiktoken
import numpy as np

load_dotenv()

client = AsyncAnthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=4,
    timeout=60.0,
)

MODEL = "claude-sonnet-4-5"
SUMMARY_MODEL = "claude-haiku-4-5"
CONTEXT_BUDGET = 150_000
MAX_RESPONSE_TOKENS = 1024
RECALL_K = 3
RECALL_THRESHOLD = 0.3
MAX_ITERATIONS = 30
DANGEROUS_TOOLS = {"write", "edit", "bash"}
IDEMPOTENT_TOOLS = {"read", "glob", "grep"}
SANDBOX_IMAGE = "building-agents-sandbox"

STATE_DIR = Path.home() / ".production-agent"
MESSAGES_FILE = STATE_DIR / "messages.json"
RECALL_FILE = STATE_DIR / "recall.json"
TRACE_FILE = STATE_DIR / "traces.jsonl"

input_ = input  # alias to avoid colliding with input dict param name


# --- Tracing (hierarchical, from M8) ---
#
# Spans are buffered as they close and assembled into a parent-child
# tree when the root span (the turn) closes. Each line of traces.jsonl
# is one complete trace tree — readable as a timeline without any
# post-processing. Full system + messages are captured on llm.call
# spans so replay_trace can reproduce a turn.

_pending_spans: list[dict] = []


def _new_id() -> str:
    return secrets.token_hex(8)


def _serialize_for_trace(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)


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
        node.pop("parent_span_id", None)
        for c in node["children"]:
            _strip(c)

    _strip(root)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
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


# --- Sandbox (from M6) ---

_sandbox_name: str | None = None


def start_sandbox(workspace: str) -> None:
    global _sandbox_name
    inspect_proc = subprocess.run(["docker", "image", "inspect", SANDBOX_IMAGE],
                                   capture_output=True)
    if inspect_proc.returncode != 0:
        print(f"Building sandbox image '{SANDBOX_IMAGE}'...")
        subprocess.run(
            ["docker", "build", "-f", "Dockerfile.sandbox", "-t", SANDBOX_IMAGE, "."],
            check=True,
        )
    _sandbox_name = f"production-agent-{secrets.token_hex(8)}"
    subprocess.run([
        "docker", "run", "-d", "--rm", "--name", _sandbox_name,
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",
        "-v", f"{workspace}:/workspace", "-w", "/workspace",
        "--memory", "512m", "--cpus", "1.0", "--pids-limit", "100",
        "--user", "1000:1000",
        SANDBOX_IMAGE, "sleep", "infinity",
    ], check=True, capture_output=True)


def stop_sandbox():
    if _sandbox_name:
        subprocess.run(["docker", "stop", "-t", "1", _sandbox_name],
                       check=False, capture_output=True, timeout=10)


# --- Tools (sync bodies; dispatched via asyncio.to_thread in execute_tool) ---
#
# Tool bodies are sync because they do blocking I/O (filesystem, subprocess).
# Wrapping them in async without await-points is a lie — the event loop
# blocks anyway. The honest shape is: sync bodies + asyncio.to_thread for
# concurrent dispatch. That's what makes asyncio.gather over tool calls
# actually parallel.

def read(path: str, offset: int | None = None, limit: int | None = None) -> str:
    with open(path, "r") as f:
        lines = f.read().splitlines()
    start = offset or 0
    end = start + limit if limit is not None else len(lines)
    selected = lines[start:end]
    return "\n".join(f"{i + 1 + start:4}| {line}" for i, line in enumerate(selected))


def write(path: str, content: str) -> str:
    with open(path, "w") as f:
        f.write(content)
    return f"wrote {len(content)} chars to {path}"


def edit(path: str, old: str, new: str, all: bool = False) -> str:
    with open(path, "r") as f:
        content = f.read()
    if old not in content:
        return f"error: 'old' string not found in {path}"
    count = content.count(old)
    if not all and count > 1:
        return f"error: 'old' appears {count} times — set all=true or make it more specific"
    result = content.replace(old, new) if all else content.replace(old, new, 1)
    with open(path, "w") as f:
        f.write(result)
    return "ok"


def grep(pattern: str, path: str) -> str:
    regex = re.compile(pattern)
    hits = []
    for root, _, files in os.walk(path):
        if ".git" in root or "__pycache__" in root or ".venv" in root:
            continue
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                with open(fpath) as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            hits.append(f"{fpath}:{i}:{line.rstrip()}")
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(hits[:100]) or "no matches"


def glob(pattern: str) -> str:
    matches = sorted(_glob.glob(pattern, recursive=True))
    return "\n".join(matches) or "no matches"


def bash(cmd: str) -> str:
    try:
        result = subprocess.run(
            ["docker", "exec", _sandbox_name, "bash", "-c", cmd],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "error: command timed out after 30s"
    out = result.stdout + result.stderr
    return out.strip() or f"(exit {result.returncode})"


# --- Registry (with prompt-cache boundary on the last tool schema) ---

TOOLS = {
    "read": {
        "fn": read,
        "description": "Read a file's contents (with optional line pagination)",
        "params": {
            "path":   {"type": "string",  "description": "Path to the file"},
            "offset": {"type": "integer", "description": "First line to read, 0-indexed", "required": False},
            "limit":  {"type": "integer", "description": "Maximum lines to read", "required": False},
        },
    },
    "write": {
        "fn": write,
        "description": "Create or overwrite a file",
        "params": {
            "path":    {"type": "string", "description": "Path to write to"},
            "content": {"type": "string", "description": "Content to write"},
        },
    },
    "edit": {
        "fn": edit,
        "description": "Replace 'old' with 'new' in a file",
        "params": {
            "path": {"type": "string",  "description": "Path to edit"},
            "old":  {"type": "string",  "description": "Exact text to replace"},
            "new":  {"type": "string",  "description": "Replacement text"},
            "all":  {"type": "boolean", "description": "Replace every occurrence (default: require unique match)", "required": False},
        },
    },
    "grep": {
        "fn": grep,
        "description": "Search file contents for a regex pattern under a directory",
        "params": {
            "pattern": {"type": "string", "description": "Regex pattern"},
            "path":    {"type": "string", "description": "Directory to search under"},
        },
    },
    "glob": {
        "fn": glob,
        "description": "Find files matching a glob pattern (use ** for recursive)",
        "params": {
            "pattern": {"type": "string", "description": "Glob pattern"},
        },
    },
    "bash": {
        "fn": bash,
        "description": "Run a shell command (sandboxed)",
        "params": {
            "cmd": {"type": "string", "description": "Shell command to run"},
        },
    },
}


def build_tool_schemas(tools):
    """Build JSON Schema entries. Stamp cache_control on the last entry so
    the API caches everything up to and including the tool schema list."""
    schemas = []
    items = list(tools.items())
    for i, (name, meta) in enumerate(items):
        properties = {}
        required = []
        for pname, pmeta in meta["params"].items():
            properties[pname] = {"type": pmeta["type"], "description": pmeta["description"]}
            if pmeta.get("required", True):
                required.append(pname)
        schema = {
            "name": name,
            "description": meta["description"],
            "input_schema": {"type": "object", "properties": properties, "required": required},
        }
        if i == len(items) - 1:
            schema["cache_control"] = {"type": "ephemeral"}
        schemas.append(schema)
    return schemas


TOOL_SCHEMAS = build_tool_schemas(TOOLS)


# --- Tool output cache (content-addressed) ---

_tool_cache: dict[str, str] = {}


def _cache_key(name: str, input: dict) -> str:
    payload = json.dumps({"name": name, "input": input}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# --- Approval + tool execution ---

async def request_approval(name: str, input: dict) -> bool:
    print(f"\n⚠ Tool '{name}' wants to run with: {input}")
    answer = input_("approve? [y/N] ").strip().lower()
    return answer in ("y", "yes")


async def execute_tool(name: str, input: dict, parent_span: str, trace_id: str) -> str:
    """Open a tool.call span, apply cache + approval, dispatch via thread
    if the body is sync, capture full input/output in the span."""
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

        # HITL approval for dangerous tools
        if name in DANGEROUS_TOOLS:
            approved = await request_approval(name, input)
            rec["attributes"]["approval"] = "approved" if approved else "denied"
            if not approved:
                rec["attributes"]["error"] = "user denied approval"
                return "error: user denied approval"

        try:
            fn = tool["fn"]
            if inspect.iscoroutinefunction(fn):
                result = await fn(**input)
            else:
                # Push blocking I/O onto a worker thread so the event loop
                # can dispatch other tool calls concurrently.
                result = await asyncio.to_thread(fn, **input)
            output = result if isinstance(result, str) else str(result)
            rec["attributes"]["tool.output"] = output

            # Store in cache or invalidate everything if state changed
            if name in IDEMPOTENT_TOOLS:
                _tool_cache[_cache_key(name, input)] = output
            elif name in DANGEROUS_TOOLS:
                _tool_cache.clear()

            return output
        except Exception as e:
            rec["attributes"]["error"] = str(e)
            return f"error: {e}"


def has_dangerous(tool_calls) -> bool:
    return any(c.name in DANGEROUS_TOOLS for c in tool_calls)


# --- Persistence + budget (from M4/M5) ---

def _serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"can't serialize {type(obj)}")


def clean_assistant_content(blocks) -> list:
    """Strip SDK-internal fields from streamed Message blocks."""
    cleaned = []
    for block in blocks:
        if block.type == "text":
            cleaned.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            cleaned.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
    return cleaned


def load_messages() -> list:
    if not MESSAGES_FILE.exists():
        return []
    try:
        return json.loads(MESSAGES_FILE.read_text())
    except json.JSONDecodeError:
        return []


def save_messages(messages: list) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MESSAGES_FILE.write_text(json.dumps(messages, default=_serialize, indent=2))


_tokenizer = tiktoken.get_encoding("cl100k_base")


def approx_tokens(value) -> int:
    text = value if isinstance(value, str) else json.dumps(value, default=_serialize)
    return len(_tokenizer.encode(text))


def message_tokens(msg) -> int:
    return approx_tokens(msg["content"]) + 5


TOOL_SCHEMA_TOKENS = approx_tokens(json.dumps(TOOL_SCHEMAS))


def _is_tool_result(block) -> bool:
    if isinstance(block, dict):
        return block.get("type") == "tool_result"
    return getattr(block, "type", None) == "tool_result"


def find_turn_boundaries(messages: list) -> list:
    boundaries = []
    for i, msg in enumerate(messages):
        if msg["role"] != "user":
            continue
        content = msg["content"]
        if isinstance(content, str):
            boundaries.append(i)
        elif not any(_is_tool_result(b) for b in content):
            boundaries.append(i)
    return boundaries


def pack_messages(user_input: str, system, history: list) -> list:
    """Compute the budget upfront and fill the buffer newest-first to fit.

    `system` may be a list of content blocks (M10 structured prompt) or a
    string; approx_tokens handles both.
    """
    fixed_tokens = (
        MAX_RESPONSE_TOKENS
        + TOOL_SCHEMA_TOKENS
        + approx_tokens(system)
        + approx_tokens(user_input)
    )
    buffer_budget = CONTEXT_BUDGET - fixed_tokens
    if buffer_budget <= 0:
        return [{"role": "user", "content": user_input}]

    boundaries = find_turn_boundaries(history) + [len(history)]
    used = 0
    keep_from = len(history)
    for i in range(len(boundaries) - 2, -1, -1):
        turn = history[boundaries[i]:boundaries[i + 1]]
        turn_tokens = sum(message_tokens(m) for m in turn)
        if used + turn_tokens > buffer_budget:
            break
        keep_from = boundaries[i]
        used += turn_tokens

    return history[keep_from:] + [{"role": "user", "content": user_input}]


def enforce_budget(messages: list, turn_start: int, system) -> tuple[list, int]:
    """Within-turn eviction: drop oldest past-history turns until total fits."""
    fixed = MAX_RESPONSE_TOKENS + TOOL_SCHEMA_TOKENS + approx_tokens(system)
    budget = CONTEXT_BUDGET - fixed

    while sum(message_tokens(m) for m in messages) > budget:
        if turn_start == 0:
            break
        past_boundaries = find_turn_boundaries(messages[:turn_start])
        if len(past_boundaries) < 2:
            messages = messages[turn_start:]
            turn_start = 0
            break
        drop_to = past_boundaries[1]
        messages = messages[drop_to:]
        turn_start -= drop_to

    return messages, turn_start


# --- Recall (from M4, returns both selected and scored for the trace) ---

print("Loading embedding model...")
_embed_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> np.ndarray:
    return _embed_model.encode(text, convert_to_numpy=True, normalize_embeddings=True)


def load_recall() -> list[dict]:
    if not RECALL_FILE.exists():
        return []
    try:
        return json.loads(RECALL_FILE.read_text())
    except json.JSONDecodeError:
        return []


def save_recall(entries: list[dict]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RECALL_FILE.write_text(json.dumps(entries))


def add_to_recall(text: str, entries: list[dict]) -> None:
    vec = embed(text)
    entries.append({"text": text, "embedding": vec.tolist()})
    save_recall(entries)


def recall(query: str, entries: list[dict],
           k: int = RECALL_K, threshold: float = RECALL_THRESHOLD) -> tuple[list[str], list[tuple[float, str]]]:
    """Return (selected, all_scored). The scored list is captured by the trace."""
    if not entries:
        return [], []
    q_vec = embed(query)
    scored = []
    for e in entries:
        e_vec = np.array(e["embedding"])
        score = float(np.dot(q_vec, e_vec))
        scored.append((score, e["text"]))
    scored.sort(reverse=True)
    selected = [text for score, text in scored[:k] if score >= threshold]
    return selected, scored[:k]


async def summarize_turn(turn_messages: list) -> str:
    response = await client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=200,
        system="You write one-paragraph summaries of agent conversations. Capture what the user asked and what was concluded or done. No fluff.",
        messages=[{"role": "user",
                   "content": f"Summarize this exchange:\n\n{json.dumps(turn_messages, default=_serialize)[:8000]}"}],
    )
    return response.content[0].text


# --- Output guardrails (from M7) ---

print("Loading sentiment classifier...")
_sentiment_pipe = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english",
)


def check_sentiment(text: str) -> tuple[str, float]:
    if not text.strip():
        return ("POSITIVE", 1.0)
    result = _sentiment_pipe(text[:512])[0]
    return (result["label"], float(result["score"]))


async def hallucination_judge(user_input: str, response_text: str, tool_evidence: str) -> tuple[bool, str]:
    judge = await client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=150,
        system=(
            "You evaluate whether an agent's response is grounded in evidence "
            "from its tool calls. Reply on the first line with exactly one word: "
            "GROUNDED or HALLUCINATED. Reply on the second line with a brief reason."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"User asked: {user_input}\n\n"
                f"Agent answered: {response_text}\n\n"
                f"Evidence from tool calls in this turn:\n"
                f"{tool_evidence or '(no tool calls)'}\n\n"
                f"Is the answer supported by the evidence?"
            ),
        }],
    )
    text = judge.content[0].text.strip()
    verdict_line, _, reason = text.partition("\n")
    grounded = verdict_line.strip().upper().startswith("GROUNDED")
    return grounded, reason.strip() or verdict_line


def collect_tool_evidence(turn_messages: list) -> str:
    parts = []
    for msg in turn_messages:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    parts.append(str(block.get("content", "")))
    return "\n---\n".join(parts)


# --- Replay (from M8) ---

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


# --- Structured system prompt + assemble() convergence (M10) ---

BASE_SYSTEM_PROMPT = """You are a coding agent. Help the user understand and modify code in this workspace.

## Tools
You have read, write, edit, grep, glob, and bash. Prefer focused tools (read for files, grep for content, glob for paths) over bash unless you specifically need a shell.

## Working style
- Read before editing. Don't guess at file contents.
- For multi-step tasks, briefly narrate your plan before executing.
- If a tool returns an error, examine it before retrying.
- For simple questions answerable from prior context, answer directly without tool calls.

## When you're done
Stop calling tools. The user wants the answer, not more action."""


def assemble(user_input: str, history: list, recalled: list[str]) -> dict:
    """The convergence point: build {system, tools, messages} for the next LLM call.

    The system prompt is a list of content blocks. The static base prompt is
    marked cache_control: ephemeral; recalled memories (which vary per turn)
    are not cached. The messages buffer is packed to fit the upfront budget.
    """
    system_blocks: list[dict] = [
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


# --- Main loop ---

async def main():
    start_sandbox(os.getcwd())
    atexit.register(stop_sandbox)

    history = load_messages()
    recall_entries = load_recall()

    while True:
        user_input = input_("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        with span("turn", user_input=user_input) as turn_rec:
            trace_id = turn_rec["trace_id"]
            turn_span_id = turn_rec["span_id"]
            print(f"\n[trace_id: {trace_id}]")

            with span("memory.recall", parent=turn_span_id, trace_id=trace_id,
                      query=user_input) as recall_rec:
                recalled, scored = recall(user_input, recall_entries)
                recall_rec["attributes"]["recalled"] = recalled
                recall_rec["attributes"]["candidates_scored"] = scored

            ctx = assemble(user_input, history, recalled)
            turn_rec["attributes"]["system_prompt"] = ctx["system"]
            messages = ctx["messages"]
            turn_start = len(messages) - 1
            final_text = ""
            iteration = 0

            for iteration in range(MAX_ITERATIONS):
                messages, turn_start = enforce_budget(messages, turn_start, ctx["system"])

                with span("llm.call", parent=turn_span_id, trace_id=trace_id,
                          iteration=iteration,
                          model=MODEL,
                          system=ctx["system"],
                          messages=messages) as llm_rec:
                    async with client.messages.stream(
                        model=MODEL,
                        max_tokens=MAX_RESPONSE_TOKENS,
                        system=ctx["system"],
                        messages=messages,
                        tools=ctx["tools"],
                    ) as stream:
                        async for text in stream.text_stream:
                            print(text, end="", flush=True)
                        print()
                        response = await stream.get_final_message()
                    response_content = clean_assistant_content(response.content)
                    llm_rec["attributes"].update({
                        "response_content": response_content,
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    })
                    llm_span_id = llm_rec["span_id"]

                messages.append({"role": "assistant", "content": response_content})

                tool_calls = [b for b in response.content if b.type == "tool_use"]
                if not tool_calls:
                    final_text = "".join(b.text for b in response.content if b.type == "text")
                    turn_rec["attributes"]["final_response"] = final_text

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
                            if not grounded:
                                print(f"\n⚠ guardrail: response may not be grounded — {reason}")
                    break

                if has_dangerous(tool_calls):
                    outputs = []
                    for c in tool_calls:
                        outputs.append(await execute_tool(c.name, c.input, llm_span_id, trace_id))
                else:
                    outputs = await asyncio.gather(*(
                        execute_tool(c.name, c.input, llm_span_id, trace_id)
                        for c in tool_calls
                    ))

                messages.append({
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": c.id, "content": o}
                                for c, o in zip(tool_calls, outputs)],
                })
            else:
                print(f"\n⚠ Reached {MAX_ITERATIONS} iterations without completion. Aborting turn.")
                turn_rec["attributes"]["aborted"] = True

            turn_rec["attributes"]["iterations"] = iteration + 1

            turn_messages = messages[turn_start:]
            with span("memory.summarize", parent=turn_span_id, trace_id=trace_id) as sum_rec:
                summary = await summarize_turn(turn_messages)
                sum_rec["attributes"]["summary"] = summary
                sum_rec["attributes"]["turn_messages_count"] = len(turn_messages)

        history = messages
        save_messages(history)
        add_to_recall(summary, recall_entries)


if __name__ == "__main__":
    asyncio.run(main())
