# Lesson 1: Model interface

> 🎥 **Video:** coming soon

The model is a function: **TokensOut = Model(TokensIn)**. The model interface is how the harness calls it. It sends tokens to the model as a request, and the model returns tokens as a response, just like any other API endpoint.

It's the thinnest of the five primitives, and that's because of where it sits. The other four live on the harness's side: control flow decides when to call, input gathers what goes in, context decides how it's presented in the request, and output handles the response. The model interface is the boundary between the harness and the model. In **Agent = Harness(Model)**, it's the parentheses. Nothing reaches the model without it, so it comes first.

## The concept

Here's the idea with nothing around it, in [`model_interface.py`](./model_interface.py): one request out to the model, one response back.

```python
from anthropic import Anthropic

client = Anthropic()

request = {
    "model": "claude-sonnet-5-5",
    "max_tokens": 16384,
    "messages": [{"role": "user", "content": "What's in this directory?"}],
}
output = client.messages.create(**request)              # one request out, one response back, all at once

for block in output.content:
    print(f"[{block.type}]", getattr(block, "text", ""))
print("stop_reason:", output.stop_reason)
print("tokens in:", output.usage.input_tokens)
print("tokens out:", output.usage.output_tokens)
```

**`client = Anthropic()`** is where the request goes: Anthropic's hosted API, through the official SDK, which reads your key from `ANTHROPIC_API_KEY`.

**`request`** is the tokens in, and what to do with them. `model` names the model that answers. `messages` is a list of messages, each with a `role` and `content`; here there's one, from the user. `max_tokens` caps the tokens out; the model stops there, even mid-sentence.

**`client.messages.create(**request)`** sends it and waits. When the model is done, the whole response comes back at once, and that's **`output`**: the tokens out, plus details about how they were produced.

The rest prints three of those details. **`content`** is the tokens out, as a list of blocks, each with a `type`. **`stop_reason`** is why the model stopped. **`usage`** counts both sides: `input_tokens` is TokensIn, `output_tokens` is TokensOut.

That's the whole primitive. Run it from the root of the repo:

```bash
uv run lessons/01-model-interface/model_interface.py
```

Here's one run:

```
[thinking] 
[text] I can't see your directory. I don't have file system access in this conversation, and no files or attachments have been shared.

To see what's in a directory yourself, you can use:

- **macOS/Linux:** `ls` (basic), `ls -la` (includes hidden files and details)
- **Windows Command Prompt:** `dir`
- **Windows PowerShell:** `ls` or `Get-ChildItem`
- **Tree view:** `tree` (works on most systems, though you may need to install it)

If you paste the output here, I can help you interpret it, find specific files, clean things up, or whatever else you need.
stop_reason: end_turn
tokens in: 15
tokens out: 239
```

Two blocks came back. The first is `thinking`: this model thinks before it answers, and by default its thinking comes back empty (more on that below). The second is the `text` of its reply. It stopped with `end_turn`, which means it finished; `max_tokens` would mean it hit the cap. Fifteen tokens went in, 239 came out, thinking included.

## quark's implementation

quark makes the same call, with one change: it doesn't wait for the whole response. It's the whole of [`quark.py`](./quark.py):

```python
from anthropic import Anthropic

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def call(each=lambda event: None, **request):            # model interface: the response streams back, and each piece goes to each()
    with client.messages.stream(model=MODEL, **request) as stream:
        for event in stream: each(event)
        return stream.get_final_message()

output = call(max_tokens=16384, messages=[{"role": "user", "content": "What's in this directory?"}])
print(output.model_dump_json(indent=2))
```

**`client = Anthropic()`** is the same as before. **`MODEL`** is the model that answers, taken out of the request so every call sends the same one.

**`call()`** is the model interface, all of it: it sends a request to `MODEL` and returns the response. Every later lesson's `quark.py` calls the model through this one function, so the primitive stays in one place.

**`client.messages.stream(...)`** is quark's choice on top of the concept. The request is the same; what changes is how the response comes back: streamed, piece by piece, as the model produces it, instead of all at once at the end. A long response that arrives all at once can time out while you wait for it; one that streams keeps arriving, so it doesn't sit waiting. **`for event in stream: each(event)`** hands each piece, as it arrives, to `each()`. Here nothing is done with the pieces: `each` defaults to a function that ignores them. **`stream.get_final_message()`** then returns the whole response, put back together, so `call()` hands back the same response it would have if it had waited for all of it. What to do with the pieces as they arrive, like showing words as they're written, is output's job, and it comes in Lesson 2.

**`messages=[...]`** and **`max_tokens`** are the request, the same as in `model_interface.py`. `call()` takes them as `**request` and passes them through untouched.

**`output`** is the response, the same kind of object `create()` returned. This time the `print` shows all of it.

The section heading, `# ── model interface ──`, will stay at the top of `quark.py` through every lesson. Each lesson adds a section of its own.

### Run it

From the root of the repo:

```bash
uv run lessons/01-model-interface/quark.py
```

Here's one run:

```json
{
  "id": "msg_011CfmchdJHXQnQ1gNhjXJjf",
  "container": null,
  "content": [
    {
      "signature": "CAQSzwUKEAgSGAI4AUIIdGhpbmtpbmcSDAgH/jj7KMlOglfI8hoMai9nd4Mi9EZhjvr2IjBn...",
      "thinking": "",
      "type": "thinking"
    },
    {
      "citations": null,
      "text": "I can't see your directory. I don't have access to your file system in this conversation, and no files or attachments have been shared with me.\n\nYou can list the contents yourself with one of these:\n\n- **macOS/Linux:** `ls` (or `ls -la` to include hidden files and details)\n- **Windows Command Prompt:** `dir`\n- **Windows PowerShell:** `Get-ChildItem` (or `ls`)\n\nIf you paste the output here, I can help you interpret it, find something specific, or decide what to do next. If you're using a tool or IDE that's supposed to give me file access, it may not be set up for this chat.",
      "type": "text"
    }
  ],
  "diagnostics": null,
  "model": "claude-sonnet-5-5",
  "role": "assistant",
  "stop_details": null,
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "type": "message",
  "usage": {
    "cache_creation": {
      "ephemeral_1h_input_tokens": 0,
      "ephemeral_5m_input_tokens": 0
    },
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "inference_geo": "global",
    "input_tokens": 15,
    "output_tokens": 240,
    "output_tokens_details": {
      "thinking_tokens": 41
    },
    "server_tool_use": null,
    "service_tier": "standard"
  }
}
```

Yours will be worded differently; the model's output varies from run to run. (The long `signature` is shortened here.) It's the same response the concept printed parts of, now in full. Three fields matter:

- **`content`** is the tokens out, as a list of blocks. The first block is its `thinking` and the second is the `text` of its reply. Here you can see why the thinking printed empty: by default it comes back with no text, only a `signature`, an encrypted copy of the reasoning that only the API can read.
- **`stop_reason`** is why it stopped. `end_turn` means it finished; `max_tokens` would mean it hit the cap.
- **`usage`** counts both sides: `input_tokens` is TokensIn, `output_tokens` is TokensOut, thinking included.

Read the `text`. The model knows the right next step is `ls`. It just can't take it.

## Other things we could do

The mechanism is always a request out and a response back, but a model interface can hold more than quark's does.
- **Where the request goes.** A hosted API, a model on your own machine, a gateway in front of several providers.
- **How it travels.** An official SDK, raw HTTP, or a layer that speaks several providers' formats so the rest of the harness doesn't have to.
- **Which model answers.** One model, or a backup that takes over when the first is unavailable.
- **How the response arrives.** All at once, like `model_interface.py`, or streamed piece by piece as it's produced, like `quark.py`, so a long response doesn't sit waiting to time out.
- **How many go at once.** One request, or a batch of them.
- **What happens when a request fails.** Retry it, wait out a rate limit, give up after a timeout.
- **The request's settings.** How many tokens out, how much the model thinks first, whether you see a summary of its thinking.

A few of those are worth knowing in more detail, because quark's `call()` will pick some of them up later.

**Timeouts and retries.** The SDK can do both for you: `Anthropic(timeout=120, max_retries=3)` gives up when the API goes two minutes without sending anything, and retries dropped connections, rate limits and server errors, waiting longer each time. Without them, one dropped connection ends the run. With them, a brief hiccup costs a few seconds.

**A backup model.** Keep a list of models and, if every retry on the first one fails, send the same request to the next. It's worth catching only the failures that say "try again later": a dropped connection, a rate limit, a server error, or an overloaded model (the SDK raises `OverloadedError` for that one). A request that's wrong in itself, like one that's too long, would fail on the backup too, so it should be raised, not passed along. Lesson 8 adds exactly this to quark.

**Effort and thinking.** Two settings change how the model works before it answers. `effort` says how much it should think first: less is faster and cheaper, more is better on hard problems. `thinking` with `display: "summarized"` asks for a readable summary of its thinking in place of the empty `thinking` block you saw above. The raw thinking itself is never returned. Neither changes what the model interface is; they're just more of the request.

It can hold enough to be a product on its own. Gateways like [LiteLLM](https://github.com/BerriAI/litellm) and [OpenRouter](https://openrouter.ai) are this primitive and nothing else: a harness sends them one request format, and they handle where it goes, which provider and model answer, backups when one is down, retries and rate limits. A harness that uses one has handed off its model interface.

## What to take away

**The rule:** the model interface sends tokens to the model as a request and gets tokens back as a response.

Notice what the model interface never does. When to call is control flow. Gathering what goes in, from a person or the world, is input. How it's presented in the request is context. What happens to the response is output. The model interface only gets the request there and the response back.

**What's missing:** both ends of the path are stubs.

```
"What's in this directory?" ─► request ─► model interface ─► response ─► print(...)
      input (a stub)                                                     output (a stub)
```

The input is a hardcoded string no one typed, and the output dumps the whole response without handling any of it. The model said what to do, and nothing could do it. Making both ends real is input and output.

**→ [Lesson 2: Input and output](../02-input-and-output/)**
