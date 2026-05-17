# An LLM call

> **Harness component: the model interface.** The harness has exactly one external dependency — a call to the model. This module builds that call. Everything else in the curriculum is added around it.

This module makes one LLM call. One prompt in, one response out. No loop, no tools, no state between calls.

## The Messages API

The model is reached over HTTP. One POST per call, one JSON response. The [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) specifies the full contract; to start we need four fields:

| Field | Purpose |
|---|---|
| `model` | Which Claude model to call (we'll use `claude-sonnet-4-5`) |
| `max_tokens` | Cap on the response length |
| `system` | System prompt — context that applies to the whole conversation |
| `messages` | The conversation — a list of `{"role": "user", "content": "..."}` turns |

The response contains a `content` array of blocks. For a plain text response there's one block with `type: "text"`.

## Setup

```bash
mkdir agent && cd agent
uv init
uv add anthropic python-dotenv
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
```

## The sync version

Create `llm_call_sync.py`:

```python
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "Write three sentences about agents."}
    ],
)
print(response.content[0].text)
```

Run it:

```bash
uv run llm_call_sync.py
```

You'll see the full three-sentence response print all at once after a short pause — the program waits for the entire reply before doing anything with it. Same prompt as the streaming version below; same final output. The only difference is *when* the text appears.

## What just happened

1. The SDK sent an HTTP POST to `https://api.anthropic.com/v1/messages`
2. The request body contained `model`, `max_tokens`, `system`, and `messages`
3. The API returned a JSON response with a `content` array
4. `response.content[0].text` extracted the text from the first block

That's the whole mechanic. The model saw the user message, generated a response, sent it back.

## Why streaming matters

The code above waits for the full response before printing anything. For a short answer the wait is short. For a longer response — a paragraph, a code block, a multi-step explanation — the user stares at a blank screen for several seconds while the model generates the entire message.

**Streaming** sends each chunk as the model generates it. Total latency stays the same, but *time to first token* drops to near-instant. For interactive use, that's the difference between an app that feels frozen and one that feels alive.

The Anthropic API supports streaming over the same Messages endpoint. Most SDKs expose it as an async iterable — your program loops over text chunks as they arrive, yielding control to the runtime between chunks. Every modern language has the same shape; the example below uses Python's `async`/`await`.

## The async streaming version

Create `llm_call_async.py`:

```python
import os
import asyncio
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


async def main():
    async with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are a helpful assistant.",
        messages=[
            {"role": "user", "content": "Write three sentences about agents."}
        ],
    ) as stream:
        async for text in stream.text_stream:
            print(text, end="", flush=True)
    print()


asyncio.run(main())
```

The shape is the same as the sync call — same `model`, same `messages`, same response — except the SDK opens a streaming connection and the program loops over chunks instead of waiting for one return value. Each chunk is printed as it arrives.

```bash
uv run llm_call_async.py
```

The response materializes a few words at a time rather than appearing all at once.

## When you need each

| Use case | `messages.create` | `messages.stream` |
|---|---|---|
| One-off scripts where you just need the answer | ✓ | overkill |
| Interactive UIs displaying responses | full-response wait per call | tokens land live |
| Agents that dispatch tools after the model is done | ✓ | ✓ — stream the text for UX, then `await stream.get_final_message()` for the structured response |

The original "streaming doesn't fit for agents" is a half-truth. You can't dispatch tools *mid-stream*, but nothing stops you from streaming the model's text output for UX while the SDK collects the full structured response in the background. When the stream finishes, `get_final_message()` returns the same `Message` shape you'd get from `messages.create` — including `tool_use` blocks.

**Every example downstream of this module uses async streaming via `AsyncAnthropic`.** The chatbots in Modules 3-4 stream their text and that's the end of the turn; the agents in Modules 5+ stream the model's narration, then `await stream.get_final_message()` and dispatch tool calls from it. We commit to async early so the same shape holds from the chatbot through the production agent — no halfway sync detour to revisit later.

Both versions are committed at [`examples/llm_call_sync.py`](../../examples/llm_call_sync.py) and [`examples/llm_call_async.py`](../../examples/llm_call_async.py) — the sync one to anchor the API contract, the async one to set up the pattern the rest of the curriculum runs on. From `examples/stateless_chatbot.py` onward, every script follows the async-streaming shape.

## What's missing

- **No tools.** The model can only produce text; it can't act.
- **No state.** Each call is independent. Nothing carries forward.

---

**Next:** [Module 3: Add a loop](../03-add-a-loop/)
