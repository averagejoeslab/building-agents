# An LLM call

> **Harness component: the model interface.** The way I think about it, the harness has exactly one hard external dependency — the call out to the model itself. This module is where we build that call. Everything else in the curriculum gets added around it.

In this module we're going to walk through three things: **how to actually make an LLM call** in the first place, **the difference between the sync and async (streaming) versions** of that call and when each one matters, and **what's still missing** at the end of it before we can call any of this an agent.

## How to call an LLM

### The Messages API

The model sits behind a regular HTTP API — one POST per call, one JSON response back. The [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) specifies the full contract, but for now we only need to care about four fields:

| Field | Purpose |
|---|---|
| `model` | Which Claude model to call (we'll use `claude-sonnet-4-5`) |
| `max_tokens` | Cap on the response length |
| `system` | System prompt — context that applies to the whole conversation |
| `messages` | The conversation — a list of `{"role": "user", "content": "..."}` turns |

The response that comes back contains a `content` array of blocks. For a plain text response there's just one block in there with `type: "text"`.

### Setup

If you don't already have a project set up, here's the minimum you need to get going:

```bash
mkdir agent && cd agent
uv init
uv add anthropic python-dotenv
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
```

### The basic call

Create `llm_call_sync.py`. The whole thing is about a dozen lines:

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

You'll see the full three-sentence response print all at once after a short pause — the program just waits for the entire reply to come back before it does anything with it.

### What actually happened under the hood

Walking through what `client.messages.create(...)` did when you ran the script:

1. The SDK sent an HTTP POST to `https://api.anthropic.com/v1/messages`.
2. The request body contained `model`, `max_tokens`, `system`, and `messages`.
3. The API returned a JSON response with a `content` array.
4. `response.content[0].text` then pulled the actual text out of the first block.

That's the whole mechanic at this layer. The model saw the user message, generated a response, sent it back to your code.

## Sync vs async (streaming)

The version above is "sync" — it makes one request and blocks until the whole response is back. That's perfectly fine when the response is short. But for a longer response — a paragraph, a code block, a multi-step explanation — the user is going to stare at a blank screen for several seconds while the model is busy generating the entire message before any of it shows up.

**Streaming** is the alternative shape. Instead of waiting for the whole response to finish, the API sends each chunk back as the model generates it. The total latency actually stays exactly the same, but *time to first token* drops to near-instant. For anything interactive that's the difference between an app that feels frozen and one that feels alive.

The Anthropic API supports streaming over the same Messages endpoint, and most SDKs expose it as an async iterable — your program loops over the text chunks as they arrive, yielding control back to the runtime in between chunks. Every modern language has the same shape for this; the example below happens to be in Python using `async`/`await`.

### The async streaming version

Now we'll create `llm_call_async.py`:

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

The shape of the call is actually identical to the sync version — same `model`, same `messages`, same response — except the SDK opens a streaming connection underneath and your program loops over chunks instead of waiting on one big return value. Each chunk gets printed as it arrives.

```bash
uv run llm_call_async.py
```

The response now materializes a few words at a time rather than appearing all at once.

### When you need each

Both shapes are useful, just for different reasons. In my opinion the table below is the cleanest way to think about which one to reach for:

| Use case | `messages.create` (sync) | `messages.stream` (async streaming) |
|---|---|---|
| One-off scripts where you just need the answer | ✓ | overkill |
| Interactive UIs displaying responses | full-response wait per call | tokens land live |
| Agents that dispatch tools after the model is done | ✓ | ✓ — stream the text for UX, then `await stream.get_final_message()` for the structured response |

You might have heard somewhere that "streaming doesn't really fit for agents" but in my experience that's only a half-truth. You can't dispatch tools *mid-stream* — the model has to finish saying everything it wants to say before you can act on a `tool_use` block — but nothing stops you from streaming the model's text output for UX while the SDK quietly collects the full structured response in the background. When the stream finishes, `get_final_message()` gives you back the same `Message` shape you'd get from `messages.create` — including any `tool_use` blocks the model produced along the way.

**Every example downstream of this module uses async streaming via `AsyncAnthropic`.** The chatbots in Modules 3 and 4 just stream their text and that's the end of the turn. The agents in Module 5 and beyond stream the model's narration, then `await stream.get_final_message()` and dispatch tool calls from the structured response that comes back. We commit to async early on purpose so the same shape carries all the way from the chatbot through to the production agent — no halfway sync detour to have to come back and refactor later.

Both versions are committed at [`examples/llm_call_sync.py`](../../examples/llm_call_sync.py) and [`examples/llm_call_async.py`](../../examples/llm_call_async.py) — the sync one to anchor the API contract for you, and the async one to set up the pattern the rest of the curriculum runs on. From `examples/stateless_chatbot.py` onward every script in this repo follows the async-streaming shape.

## What's missing

By the end of this module you can call the model both ways — sync and async streaming — and you can pick the right one for the job. But the agent we eventually want to build is still a long way off. Two specific things are still missing at this point:

- **No tools.** The model can only produce text right now; it can't actually do anything in the world.
- **No state.** Each call is independent. Nothing the model said before carries forward into the next call.

## Where we go next

**Module 3** is where we tackle the "no state" problem. We wrap the LLM call in a loop and tie that loop to an environment — for this curriculum we pick the terminal because it has the least ceremony, but the loop itself is environment-agnostic and the same shape would just as well bind to a web socket, a Slack channel, or even a humanoid robot. By the end of Module 3 we'll have a chatbot that holds a real conversation within a single session, and we'll have set up the basic shape that every subsequent module builds on.

---

**Next:** [Module 3: Add a loop](../03-add-a-loop/)
