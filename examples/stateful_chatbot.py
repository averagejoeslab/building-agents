import os
import json
import asyncio
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

STATE_DIR = Path.home() / ".stateful-chatbot"
MESSAGES_FILE = STATE_DIR / "messages.json"
RECALL_FILE = STATE_DIR / "recall.json"


# --- Persistence ---

def _serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"can't serialize {type(obj)}")


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


def find_turn_boundaries(messages: list) -> list:
    """Indices where a fresh user turn starts. The chatbot has no tools yet
    so every user message is a boundary; M5 extends this to skip user
    messages that are replies carrying tool_result blocks."""
    return [i for i, msg in enumerate(messages) if msg["role"] == "user"]


def assemble(user_input: str, system: str, history: list) -> list:
    """Compute the budget upfront and fill the buffer newest-first to fit.

    Budget formula:
        past_turn_budget = CONTEXT_BUDGET
                         - MAX_RESPONSE_TOKENS
                         - approx_tokens(system)
                         - approx_tokens(user_input)
    """
    fixed_tokens = (
        MAX_RESPONSE_TOKENS
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


def recall(query: str, entries: list[dict],
           k: int = RECALL_K, threshold: float = RECALL_THRESHOLD) -> list[str]:
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
        system=("You write one-paragraph summaries of conversations. "
                "Capture what the user asked and what was discussed. No fluff."),
        messages=[{"role": "user", "content":
                   f"Summarize this exchange:\n\n"
                   f"{json.dumps(turn_messages, default=_serialize)[:8000]}"}],
    )
    return response.content[0].text


# --- Main loop ---

BASE_SYSTEM = "You are a helpful assistant."


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

        async with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_RESPONSE_TOKENS,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                print(text, end="", flush=True)
            print()
            response = await stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content[0].text})

        # Append the new turn (user + assistant) to persistent history.
        history = messages
        save_messages(history)

        turn_messages = messages[turn_start:]
        summary = await summarize_turn(turn_messages)
        add_to_recall(summary, recall_entries)


asyncio.run(main())
