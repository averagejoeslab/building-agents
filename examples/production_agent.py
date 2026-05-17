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

input_ = input


# --- Tracing ---

def _new_id() -> str:
    return secrets.token_hex(8)


def write_span(span: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRACE_FILE, "a") as f:
        f.write(json.dumps(span, default=str) + "\n")


@contextmanager
def span(name: str, parent: str | None = None, trace_id: str | None = None, **attributes):
    span_id = _new_id()
    trace_id = trace_id or _new_id()
    start = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    rec = {
        "trace_id": trace_id, "span_id": span_id, "parent_span_id": parent,
        "name": name, "start_time": start.isoformat(),
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


# --- Sandbox ---

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


# --- Tools ---

def read_sync(path: str, offset: int | None = None, limit: int | None = None) -> str:
    with open(path, "r") as f:
        lines = f.read().splitlines()
    start = offset or 0
    end = start + limit if limit is not None else len(lines)
    selected = lines[start:end]
    return "\n".join(f"{i + 1 + start:4}| {line}" for i, line in enumerate(selected))


def write_sync(path: str, content: str) -> str:
    with open(path, "w") as f:
        f.write(content)
    return f"wrote {len(content)} chars to {path}"


def edit_sync(path: str, old: str, new: str, all: bool = False) -> str:
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


def grep_sync(pattern: str, path: str) -> str:
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


def glob_sync(pattern: str) -> str:
    matches = sorted(_glob.glob(pattern, recursive=True))
    return "\n".join(matches) or "no matches"


def bash_sync(cmd: str) -> str:
    try:
        result = subprocess.run(
            ["docker", "exec", _sandbox_name, "bash", "-c", cmd],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "error: command timed out after 30s"
    out = result.stdout + result.stderr
    return out.strip() or f"(exit {result.returncode})"


# --- Registry ---

TOOLS = {
    "read": {
        "fn": read_sync,
        "description": "Read a file's contents (with optional line pagination)",
        "params": {
            "path":   {"type": "string",  "description": "Path to the file"},
            "offset": {"type": "integer", "description": "First line to read, 0-indexed", "required": False},
            "limit":  {"type": "integer", "description": "Maximum lines to read", "required": False},
        },
    },
    "write": {
        "fn": write_sync,
        "description": "Create or overwrite a file",
        "params": {
            "path":    {"type": "string", "description": "Path to write to"},
            "content": {"type": "string", "description": "Content to write"},
        },
    },
    "edit": {
        "fn": edit_sync,
        "description": "Replace 'old' with 'new' in a file",
        "params": {
            "path": {"type": "string",  "description": "Path to edit"},
            "old":  {"type": "string",  "description": "Exact text to replace"},
            "new":  {"type": "string",  "description": "Replacement text"},
            "all":  {"type": "boolean", "description": "Replace every occurrence (default: require unique match)", "required": False},
        },
    },
    "grep": {
        "fn": grep_sync,
        "description": "Search file contents for a regex pattern under a directory",
        "params": {
            "pattern": {"type": "string", "description": "Regex pattern"},
            "path":    {"type": "string", "description": "Directory to search under"},
        },
    },
    "glob": {
        "fn": glob_sync,
        "description": "Find files matching a glob pattern (use ** for recursive)",
        "params": {
            "pattern": {"type": "string", "description": "Glob pattern"},
        },
    },
    "bash": {
        "fn": bash_sync,
        "description": "Run a shell command (sandboxed)",
        "params": {
            "cmd": {"type": "string", "description": "Shell command to run"},
        },
    },
}


def build_tool_schemas(tools):
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


_tool_cache: dict[str, str] = {}


def _cache_key(name: str, input: dict) -> str:
    payload = json.dumps({"name": name, "input": input}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


async def request_approval(name: str, input: dict) -> bool:
    print(f"\n⚠ Tool '{name}' wants to run with: {input}")
    answer = input_("approve? [y/N] ").strip().lower()
    return answer in ("y", "yes")


async def execute_tool(name: str, input: dict, parent_span: str, trace_id: str) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"

    with span("tool.call", parent=parent_span, trace_id=trace_id,
              **{"tool.name": name, "tool.input": input}) as rec:

        if name in IDEMPOTENT_TOOLS:
            key = _cache_key(name, input)
            if key in _tool_cache:
                rec["attributes"]["cache_hit"] = True
                rec["attributes"]["tool.output"] = _tool_cache[key][:500]
                return _tool_cache[key]

        if name in DANGEROUS_TOOLS:
            if not await request_approval(name, input):
                rec["attributes"]["error"] = "user denied approval"
                return "error: user denied approval"

        try:
            fn = tool["fn"]
            if inspect.iscoroutinefunction(fn):
                result = await fn(**input)
            else:
                result = await asyncio.to_thread(fn, **input)
            output = result if isinstance(result, str) else str(result)
            rec["attributes"]["tool.output"] = output[:500]

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


TOOL_SCHEMAS = build_tool_schemas(TOOLS)


# --- Persistence + budget ---

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


# --- Token budget (upfront computation) ---

_tokenizer = tiktoken.get_encoding("cl100k_base")


def approx_tokens(value) -> int:
    """Local BPE token count via tiktoken (~5% of Claude's actual count)."""
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

    `system` may be a list of content blocks (M10 structured prompt) or a string;
    we count whichever shape it has.
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


# --- Recall ---

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


def recall(query: str, entries: list[dict], k: int = RECALL_K, threshold: float = RECALL_THRESHOLD) -> list[str]:
    if not entries:
        return []
    q_vec = embed(query)
    scored = []
    for e in entries:
        e_vec = np.array(e["embedding"])
        score = float(np.dot(q_vec, e_vec))
        scored.append((score, e["text"]))
    scored.sort(reverse=True)
    return [text for score, text in scored[:k] if score >= threshold]


async def summarize_turn(turn_messages: list) -> str:
    response = await client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=200,
        system="You write one-paragraph summaries of agent conversations. Capture what the user asked and what was concluded or done. No fluff.",
        messages=[{"role": "user",
                   "content": f"Summarize this exchange:\n\n{json.dumps(turn_messages, default=_serialize)[:8000]}"}],
    )
    return response.content[0].text


# --- Structured system prompt + assemble() ---

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


def assemble(user_input: str, history: list, recall_entries: list) -> dict:
    """The convergence point: build {system, tools, messages} for the next LLM call.

    Packs the messages buffer to fit within the upfront-computed budget, so the
    caller never has to think about trimming separately.
    """
    recalled = recall(user_input, recall_entries)
    system = [
        {"type": "text", "text": BASE_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
    ]
    if recalled:
        memory_block = "\n\n".join(f"- {s}" for s in recalled)
        system.append({
            "type": "text",
            "text": f"## Recalled context from past conversations\n\n{memory_block}",
        })
    messages = pack_messages(user_input, system, history)
    return {"system": system, "tools": TOOL_SCHEMAS, "messages": messages}


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

        ctx = assemble(user_input, history, recall_entries)
        messages = ctx["messages"]
        turn_start = len(messages) - 1

        with span("turn", attributes={"user_input": user_input[:200]}) as turn_rec:
            trace_id = turn_rec["trace_id"]
            turn_span_id = turn_rec["span_id"]

            for iteration in range(MAX_ITERATIONS):
                messages, turn_start = enforce_budget(messages, turn_start, ctx["system"])
                with span("llm.call", parent=turn_span_id, trace_id=trace_id,
                          iteration=iteration) as llm_rec:
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
                    llm_rec["attributes"].update({
                        "model": MODEL,
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    })
                    llm_span_id = llm_rec["span_id"]

                messages.append({"role": "assistant", "content": clean_assistant_content(response.content)})

                tool_calls = [b for b in response.content if b.type == "tool_use"]

                if not tool_calls:
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
                print(f"\n⚠ Reached {MAX_ITERATIONS} iterations without completion.")
                turn_rec["attributes"]["aborted"] = True

            turn_rec["attributes"]["iterations"] = iteration + 1

        history = messages
        save_messages(history)

        turn_messages = messages[turn_start:]
        summary = await summarize_turn(turn_messages)
        add_to_recall(summary, recall_entries)


asyncio.run(main())
