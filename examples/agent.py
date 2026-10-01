import os
import re
import json
import asyncio
import subprocess
import glob as _glob
from pathlib import Path
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import tiktoken
import numpy as np

load_dotenv()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-4-5"
SUMMARY_MODEL = "claude-haiku-4-5"
CONTEXT_BUDGET = 150_000
MAX_RESPONSE_TOKENS = 1024
RECALL_K = 3
RECALL_THRESHOLD = 0.3

STATE_DIR = Path.home() / ".agent"
MESSAGES_FILE = STATE_DIR / "messages.json"
RECALL_FILE = STATE_DIR / "recall.json"


# --- Tools ---

async def read(path: str, offset: int | None = None, limit: int | None = None) -> str:
    with open(path, "r") as f:
        lines = f.read().splitlines()
    start = offset or 0
    end = start + limit if limit is not None else len(lines)
    selected = lines[start:end]
    return "\n".join(f"{i + 1 + start:4}| {line}" for i, line in enumerate(selected))


async def write(path: str, content: str) -> str:
    with open(path, "w") as f:
        f.write(content)
    return f"wrote {len(content)} chars to {path}"


async def edit(path: str, old: str, new: str, all: bool = False) -> str:
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


async def grep(pattern: str, path: str) -> str:
    regex = re.compile(pattern)
    hits = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".venv")]  # prune noise dirs
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


async def glob(pattern: str) -> str:
    matches = sorted(_glob.glob(pattern, recursive=True))
    return "\n".join(matches) or "no matches"


async def bash(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return "error: command timed out after 30s"
    out = result.stdout + result.stderr
    return out.strip() or f"(exit {result.returncode})"


# --- Registry ---

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
        "description": "Run a shell command",
        "params": {
            "cmd": {"type": "string", "description": "Shell command to run"},
        },
    },
}


def build_tool_schemas(tools):
    schemas = []
    for name, meta in tools.items():
        properties = {}
        required = []
        for pname, pmeta in meta["params"].items():
            properties[pname] = {"type": pmeta["type"], "description": pmeta["description"]}
            if pmeta.get("required", True):
                required.append(pname)
        schemas.append({
            "name": name,
            "description": meta["description"],
            "input_schema": {"type": "object", "properties": properties, "required": required},
        })
    return schemas


async def execute_tool(name: str, input: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"
    try:
        result = await tool["fn"](**input)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        return f"error: {e}"


TOOL_SCHEMAS = build_tool_schemas(TOOLS)


# --- Persistence ---

def _serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"can't serialize {type(obj)}")


def clean_assistant_content(blocks) -> list:
    """Convert streamed Message.content blocks to API-input shape.
    The streaming SDK attaches fields like `parsed_output` and `citations`
    that the API rejects when sent back as input — keep only what's valid."""
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
    except json.JSONDecodeError as e:
        print(f"warning: {MESSAGES_FILE} is corrupt ({e}); starting fresh")
        return []


def save_messages(messages: list) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MESSAGES_FILE.write_text(json.dumps(messages, default=_serialize, indent=2))


# --- Token budget (upfront computation) ---

_tokenizer = tiktoken.get_encoding("cl100k_base")


def approx_tokens(value) -> int:
    """Local BPE token count via tiktoken's cl100k_base encoding.
    Not exact for Claude (Claude has its own tokenizer) but close enough
    for budget arithmetic — typically within ~5% of Claude's count for
    English text, no API round-trip needed."""
    text = value if isinstance(value, str) else json.dumps(value, default=_serialize)
    return len(_tokenizer.encode(text))


def message_tokens(msg) -> int:
    return approx_tokens(msg["content"]) + 5  # role overhead


TOOL_SCHEMA_TOKENS = approx_tokens(json.dumps(TOOL_SCHEMAS))


def _is_tool_result(block) -> bool:
    if isinstance(block, dict):
        return block.get("type") == "tool_result"
    return getattr(block, "type", None) == "tool_result"


def find_turn_boundaries(messages: list) -> list:
    """Indices where a fresh user turn starts (not a reply carrying tool_results)."""
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


def assemble(user_input: str, system: str, history: list) -> list:
    """Compute the budget upfront and fill the buffer newest-first to fit.

    Budget formula:
        past_turn_budget = CONTEXT_BUDGET
                         - MAX_RESPONSE_TOKENS
                         - TOOL_SCHEMA_TOKENS
                         - approx_tokens(system)
                         - approx_tokens(user_input)
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
    """Within-turn eviction: drop oldest past-history turns until total fits.

    Called inside the TAO loop. As tool_use/tool_result pairs accumulate
    during a long agentic turn, messages can exceed the budget that was
    fitted at user-turn start. This re-checks and evicts whole past turns
    (only from messages[:turn_start]) until the total is back under budget.

    The in-progress turn (messages[turn_start:]) is never touched —
    splitting a tool_use/tool_result pair would make the API reject the
    request.
    """
    fixed = MAX_RESPONSE_TOKENS + TOOL_SCHEMA_TOKENS + approx_tokens(system)
    budget = CONTEXT_BUDGET - fixed

    while sum(message_tokens(m) for m in messages) > budget:
        if turn_start == 0:
            break  # no past history left to evict
        past_boundaries = find_turn_boundaries(messages[:turn_start])
        if len(past_boundaries) < 2:
            # Only one turn (or none) of past history — drop whole past
            messages = messages[turn_start:]
            turn_start = 0
            break
        # Drop the oldest past turn (everything up to the second boundary)
        drop_to = past_boundaries[1]
        messages = messages[drop_to:]
        turn_start -= drop_to

    return messages, turn_start


# --- Semantic recall ---

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


# --- Main loop ---

BASE_SYSTEM = "You are a helpful coding assistant."


async def main():
    history = load_messages()
    recall_entries = load_recall()

    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        recalled = recall(user_input, recall_entries)
        if recalled:
            memory_block = "\n\n".join(f"- {s}" for s in recalled)
            system = f"{BASE_SYSTEM}\n\n## Relevant memory from past conversations\n\n{memory_block}"
        else:
            system = BASE_SYSTEM

        messages = assemble(user_input, system, history)
        turn_start = len(messages) - 1

        # TAO loop
        while True:
            messages, turn_start = enforce_budget(messages, turn_start, system)
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

            messages.append({"role": "assistant", "content": clean_assistant_content(response.content)})

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                break

            outputs = await asyncio.gather(*(execute_tool(c.name, c.input) for c in tool_calls))
            messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": c.id, "content": o}
                            for c, o in zip(tool_calls, outputs)],
            })

        history += messages[turn_start:]  # persist the full turn; the trimmed buffer was only for this call
        save_messages(history)

        turn_messages = messages[turn_start:]
        summary = await summarize_turn(turn_messages)
        add_to_recall(summary, recall_entries)


asyncio.run(main())
