import os
import re
import json
import atexit
import asyncio
import secrets
import subprocess
import glob as _glob
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
SANDBOX_IMAGE = "building-agents-sandbox"

STATE_DIR = Path.home() / ".safe-agent"
MESSAGES_FILE = STATE_DIR / "messages.json"
RECALL_FILE = STATE_DIR / "recall.json"


# --- Sandbox ---

_sandbox_name: str | None = None


def start_sandbox(workspace: str) -> None:
    global _sandbox_name
    # Build image if missing
    inspect = subprocess.run(["docker", "image", "inspect", SANDBOX_IMAGE],
                              capture_output=True)
    if inspect.returncode != 0:
        print(f"Building sandbox image '{SANDBOX_IMAGE}'...")
        subprocess.run(
            ["docker", "build", "-f", "Dockerfile.sandbox", "-t", SANDBOX_IMAGE, "."],
            check=True,
        )

    _sandbox_name = f"safe-agent-{secrets.token_hex(8)}"
    subprocess.run([
        "docker", "run", "-d", "--rm",
        "--name", _sandbox_name,
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",
        "-v", f"{workspace}:/workspace",
        "-w", "/workspace",
        "--memory", "512m",
        "--cpus", "1.0",
        "--pids-limit", "100",
        "--user", "1000:1000",
        SANDBOX_IMAGE,
        "sleep", "infinity",
    ], check=True, capture_output=True)


def stop_sandbox():
    if _sandbox_name:
        subprocess.run(
            ["docker", "stop", "-t", "1", _sandbox_name],
            check=False, capture_output=True, timeout=10,
        )


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


async def glob(pattern: str) -> str:
    matches = sorted(_glob.glob(pattern, recursive=True))
    return "\n".join(matches) or "no matches"


async def bash(cmd: str) -> str:
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


async def request_approval(name: str, input: dict) -> bool:
    print(f"\n⚠ Tool '{name}' wants to run with: {input}")
    answer = input_(f"approve? [y/N] ").strip().lower()
    return answer in ("y", "yes")


# alias to avoid colliding with input dict param name in execute_tool
input_ = input


async def execute_tool(name: str, input: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"
    if name in DANGEROUS_TOOLS:
        if not await request_approval(name, input):
            return "error: user denied approval"
    try:
        result = await tool["fn"](**input)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        return f"error: {e}"


def has_dangerous(tool_calls) -> bool:
    return any(c.name in DANGEROUS_TOOLS for c in tool_calls)


TOOL_SCHEMAS = build_tool_schemas(TOOLS)


# --- Persistence ---

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
    except json.JSONDecodeError as e:
        print(f"warning: {MESSAGES_FILE} is corrupt ({e}); starting fresh")
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


def assemble(user_input: str, system: str, history: list) -> list:
    """Compute the budget upfront and fill the buffer newest-first to fit."""
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


# --- Output guardrails ---

# Classifier guardrail: BERT sentiment analysis on the final response.
# Loaded once at import; ~268MB on first run, cached locally afterward.
print("Loading sentiment classifier...")
_sentiment_pipe = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english",
)


def check_sentiment(text: str) -> tuple[str, float]:
    """Two-class BERT sentiment: POSITIVE / NEGATIVE with confidence."""
    if not text.strip():
        return ("POSITIVE", 1.0)
    result = _sentiment_pipe(text[:512])[0]  # truncate to BERT max-len
    return (result["label"], float(result["score"]))


async def hallucination_judge(user_input: str, response_text: str, tool_evidence: str) -> tuple[bool, str]:
    """LLM-as-judge guardrail: is the response grounded in tool evidence?

    Returns (grounded, reason). True = supported by evidence.
    """
    judge = await client.messages.create(
        model=SUMMARY_MODEL,  # claude-haiku-4-5
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
    """Concatenate tool_result blocks from the turn into one evidence string."""
    parts = []
    for msg in turn_messages:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    parts.append(str(block.get("content", ""))[:500])
    return "\n---\n".join(parts)


# --- Main loop ---

BASE_SYSTEM = "You are a helpful coding assistant."


async def main():
    start_sandbox(os.getcwd())
    atexit.register(stop_sandbox)

    history = load_messages()
    recall_entries = load_recall()

    while True:
        user_input = input_("❯ ")
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

        for iteration in range(MAX_ITERATIONS):
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
                # Model produced a final response: run output guardrails.
                final_text = "".join(b.text for b in response.content if b.type == "text")

                # Classifier guardrail: sentiment on the final response.
                label, score = check_sentiment(final_text)
                if label == "NEGATIVE" and score > 0.85:
                    print(f"\n⚠ guardrail: response shows negative sentiment ({score:.2f})")

                # LLM-as-judge guardrail: hallucination check against tool evidence.
                if final_text.strip():
                    tool_evidence = collect_tool_evidence(messages[turn_start:])
                    grounded, reason = await hallucination_judge(user_input, final_text, tool_evidence)
                    if not grounded:
                        print(f"\n⚠ guardrail: response may not be grounded — {reason}")
                break

            if has_dangerous(tool_calls):
                outputs = []
                for c in tool_calls:
                    outputs.append(await execute_tool(c.name, c.input))
            else:
                outputs = await asyncio.gather(*(execute_tool(c.name, c.input) for c in tool_calls))

            messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": c.id, "content": o}
                            for c, o in zip(tool_calls, outputs)],
            })
        else:
            print(f"\n⚠ Reached {MAX_ITERATIONS} iterations without completion. Aborting turn.")

        history = messages
        save_messages(history)

        turn_messages = messages[turn_start:]
        summary = await summarize_turn(turn_messages)
        add_to_recall(summary, recall_entries)


asyncio.run(main())
