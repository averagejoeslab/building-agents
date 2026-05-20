# Add memory

> **Harness component: memory and context management.** What the harness persists, what it evicts under budget pressure, and what it recalls when relevant. The harness is what gives the model continuity across sessions.

Module 3's chatbot can hold a conversation, but only inside a single session. Quit the program and the messages list — your only state — evaporates. Next session it's a stranger again.

Adding **memory** turns the chatbot into a **stateful chatbot** — one that recognizes you when you come back next week, instead of starting from zero every run. "Memory" sounds like one feature, but it's three distinct problems hiding under one word, and they need different solutions:

1. **Persistence** — the conversation must survive a restart. Save the messages list to disk, load it next session.
2. **Token budget** — the context window has a fixed size; eventually a long conversation overflows it. Trim old turns when needed.
3. **Semantic recall** — even after trimming, useful context shouldn't be lost forever. Summarize each turn into a vector store and pull back relevant pieces by similarity.

By the end you have [`examples/stateful_chatbot.py`](../../examples/stateful_chatbot.py).

## Persistence

The simplest fix: serialize `messages` to JSON at the end of every turn, load it at startup. Pick a state directory under the user's home so it survives reboots and isn't tied to where the program was launched from.

```python
from pathlib import Path
import json

STATE_DIR = Path.home() / ".stateful-chatbot"
MESSAGES_FILE = STATE_DIR / "messages.json"


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
```

Two subtleties:

**The SDK returns structured response objects, not raw JSON.** They need to be converted to a serializable form on the way to disk; on reload, the plain JSON shape is fine to send back to the API. (Most language SDKs follow the same pattern — typed objects out, JSON-friendly shape in.)

**Corrupt state shouldn't crash startup.** If the JSON is malformed (interrupted write, manual edit), recover gracefully: warn the user and start fresh. Losing one session is recoverable; failing to start at all is not.

Wire it into the loop — `load_messages()` at startup, `save_messages(messages)` after each turn:

```python
def main():
    messages = load_messages()  # was: messages = []

    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        # ... call the model, append response ...

        save_messages(messages)
```

That's persistence. Restart the chatbot and the prior conversation comes back.

## Token budget

The context window is a budget of tokens. Each Claude Sonnet 4.5 request can carry up to 200,000 input tokens; with 1M context enabled, up to 1,000,000. A long conversation eventually exceeds whatever budget you've set.

The trick is to **compute the budget upfront** — once, in one pass — rather than blindly cramming everything in and hoping it fits. The math is straightforward.

### The budget formula

Every request to the model consumes tokens from four places:

| What | Why it costs |
|---|---|
| `system` prompt | Sent every call |
| `tools` schemas | Sent every call (when tools are enabled) |
| The new `user` input | What the user just typed |
| Past conversation `messages` | The history you're carrying forward |

Plus the model needs room to *write its response*. That carve-out is the `max_tokens` you pass to `messages.create`.

So the past-conversation budget is whatever's left:

```
past_turn_budget = CONTEXT_BUDGET
                 - MAX_RESPONSE_TOKENS
                 - tokens(system)
                 - tokens(tools)         # 0 for a chatbot
                 - tokens(user_input)
```

`CONTEXT_BUDGET` is a number you pick *below* the model's hard limit — `150_000` for Sonnet 4.5 standard context leaves comfortable headroom for both your overhead estimate and the model's response.

### Counting tokens (locally)

You don't need an API round-trip per turn to count tokens. We use `tiktoken` — OpenAI's BPE tokenizer library — with the `cl100k_base` encoding. It's not Claude's tokenizer, but it produces counts that are within ~5% of Claude's for English text, and it runs locally with no API call:

```python
import tiktoken

_tokenizer = tiktoken.get_encoding("cl100k_base")


def approx_tokens(value) -> int:
    """Local BPE token count. Not exact for Claude (~5% off for English),
    but the budget runs below the hard limit so a small overcount is safe."""
    text = value if isinstance(value, str) else json.dumps(value, default=_serialize)
    return len(_tokenizer.encode(text))


def message_tokens(msg) -> int:
    return approx_tokens(msg["content"]) + 5  # role overhead
```

> [!NOTE]
> The Anthropic API also exposes a `count_tokens` endpoint that's exact for Claude. It costs an API round-trip per call, which adds latency and cost. For a budget that already runs at ~75% of the hard limit, the local tokenizer wins — same shape, no network. Use `count_tokens` when you need exactness, e.g. to bill users on token cost or to get within a percentage point of the hard limit.

### Walking turns newest-first

Once the budget is known, fill the buffer in one pass: walk past turns from newest to oldest, summing their tokens, until the next one wouldn't fit.

For a chatbot, every user message is a turn boundary (each `user` entry is a plain string — no tool_result replies yet):

```python
def find_turn_boundaries(messages: list) -> list:
    return [i for i, msg in enumerate(messages) if msg["role"] == "user"]


def assemble(user_input: str, system: str, history: list) -> list:
    """Compute the budget upfront and fill the buffer newest-first to fit."""
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
```

`assemble` takes the user's new input, the system prompt, and the persisted history; returns the messages list to send to the model. One pass, no iterative trimming.

Wire it into the loop (still async — we'll keep the same pattern across the curriculum):

```python
messages = assemble(user_input, system, history)

async with client.messages.stream(model=MODEL, system=system, messages=messages, ...) as stream:
    async for text in stream.text_stream:
        print(text, end="", flush=True)
    print()
    response = await stream.get_final_message()

messages.append({"role": "assistant", "content": response.content[0].text})
history = messages  # the assembled buffer becomes the next iteration's input
```

> [!NOTE]
> The next module adds tools, which means messages can carry `tool_use` and `tool_result` blocks. Splitting a `tool_use`/`tool_result` pair across an eviction boundary makes the API reject the request — so `find_turn_boundaries` extends to skip user messages that are *replies* to tool calls. We'll do that in the next module.

## Semantic recall

Trimming solves overflow, but everything trimmed is lost — even if the user comes back next week and asks about exactly that. Semantic recall is the bridge: when a turn ends, summarize it; embed the summary; store it. When a new user message arrives, embed it too and pull the most-similar summaries back into the system prompt.

Three pieces:

1. **Embed** — convert text to a vector. We use `sentence-transformers` (a small local model — no API call, no rate limits).
2. **Store** — keep a JSON list of `{text, embedding}` entries. For thousands of entries this is fine; for millions you'd want a vector database.
3. **Recall** — given a query, score each entry by dot product, return the top-k above a similarity threshold.

```python
from sentence_transformers import SentenceTransformer
import numpy as np

print("Loading embedding model...")
_embed_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> np.ndarray:
    return _embed_model.encode(text, convert_to_numpy=True, normalize_embeddings=True)


def add_to_recall(text: str, entries: list[dict]) -> None:
    vec = embed(text)
    entries.append({"text": text, "embedding": vec.tolist()})
    save_recall(entries)


def recall(query: str, entries: list[dict],
           k: int = 3, threshold: float = 0.3) -> list[str]:
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
```

Embeddings are normalized to unit length, so dot product equals cosine similarity. The threshold prevents irrelevant entries from leaking in when nothing matches well — better to recall nothing than recall noise.

### Summarizing a turn

Storing raw turn messages would be wasteful — long, full of detail, hard to scan. Summarize each turn down to one paragraph using a cheap model:

```python
def summarize_turn(turn_messages: list) -> str:
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        system=("You write one-paragraph summaries of conversations. "
                "Capture what the user asked and what was discussed. "
                "No fluff."),
        messages=[{"role": "user", "content":
                   f"Summarize this exchange:\n\n"
                   f"{json.dumps(turn_messages, default=_serialize)[:8000]}"}],
    )
    return response.content[0].text
```

Haiku is fast and cheap; turn summaries don't need Sonnet's reasoning.

### Wiring recall into the system prompt

When a new user message comes in, recall relevant memories *before* the model call and prepend them to the system prompt:

```python
BASE_SYSTEM = "You are a helpful assistant."

recalled = recall(user_input, recall_entries)
if recalled:
    memory_block = "\n\n".join(f"- {s}" for s in recalled)
    system = f"{BASE_SYSTEM}\n\n## Relevant memory from past conversations\n\n{memory_block}"
else:
    system = BASE_SYSTEM
```

After the turn finishes, summarize and add to recall:

```python
turn_messages = messages[turn_start:]
summary = summarize_turn(turn_messages)
add_to_recall(summary, recall_entries)
```

Now the chatbot has long-term memory: even after old turns are trimmed from the live context, their summaries can be pulled back when the user asks something related.

## Putting it together

The full per-turn shape:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#002D62','primaryBorderColor':'#EB6E1F','primaryTextColor':'#FFFFFF','lineColor':'#EB6E1F','secondaryColor':'#002D62','tertiaryColor':'#001638','edgeLabelBackground':'#001638','clusterBkg':'#002D62','clusterBorder':'#EB6E1F'}}}%%
flowchart LR
    User[User input] --> R[Recall<br/>relevant memories]
    R --> Sys[Build system prompt<br/>+ memories]
    Sys --> T[Trim messages<br/>to budget]
    T --> Call[LLM call]
    Call --> Save[Save messages]
    Save --> Sum[Summarize turn]
    Sum --> Add[Add to recall]
```

## Run it

The end state is [`examples/stateful_chatbot.py`](../../examples/stateful_chatbot.py):

```bash
cd examples
uv run stateful_chatbot.py
```

State lives in `~/.stateful-chatbot/`:

- `messages.json` — full conversation history.
- `recall.json` — turn summaries with embeddings.

Quit and restart; the conversation is still there. Have a long conversation; the chatbot trims old turns. Ask about something from a week ago; the chatbot recalls the summary.

> [!NOTE]
> **What these files are (and aren't).** `messages.json` and `recall.json` are **state files**: the agent's working memory. They're what the harness *reads at startup and writes after each turn* to keep being itself across sessions. They serve as the session-level checkpoint — quit and restart, and the agent picks up exactly where it left off.
>
> They are **not a record of what happened** during a turn. They don't capture which memories were considered but rejected, which tool calls were retried, which guardrails fired, how long anything took, or the full system prompt as actually sent. That history is what *observability* is for, and it belongs in a separate file with different durability and access patterns. We'll add that in M8 as `traces.jsonl` — a write-only audit trail that the agent itself never reads.
>
> The split matters because state and trace have different jobs: state is mutable, agent-consumed, and shaped for *the next turn*; trace is immutable, human/eval-consumed, and shaped for *understanding the last turn*. Production agent frameworks (LangSmith, OpenAI Assistants, Letta, Mastra, Logfire) all enforce this separation — usually as two distinct storage backends. We're doing it as two files in the same directory.

## Why this still isn't an agent

The chatbot now remembers — but it still can't *do* anything. It can describe how to read a file, recall what you said about a project last month, propose what a config change might look like — but it cannot read, run, or write.

To act, the model needs **tools**. That's the next module — and it's the moment the stateful chatbot becomes a stateful agent.

---

**Next:** [Module 5: Add tools](../05-add-tools/)
