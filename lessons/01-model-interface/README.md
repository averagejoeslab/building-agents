# Lesson 1: Model interface

> 🎥 **Video:** coming soon

The model is a function: **TokensOut = Model(TokensIn)**. The model interface is how the harness calls it. It sends tokens to the model as a request, and the model returns tokens as a response, just like any other API endpoint.

It's the thinnest of the five primitives, and that's because of where it sits. The other four live on the harness's side: control flow decides when to call, input gathers what goes in, context decides how it's presented in the request, and output handles the response. The model interface is the boundary between the harness and the model. In **Agent = Harness(Model)**, it's the parentheses. Nothing reaches the model without it, so it comes first.

## The worked example

Here's the call at the center of [quark](https://github.com/averagejoeslab/quark), with nothing around it. It's the whole of [`quark.py`](./quark.py):

```python
from anthropic import Anthropic

client = Anthropic()
reply = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=16384,
    messages=[{"role": "user", "content": "What's in this directory?"}],
)
print(reply.model_dump_json(indent=2))
```

**`client = Anthropic()`** is where the request goes: Anthropic's hosted API, through the official SDK, which reads your key from `ANTHROPIC_API_KEY`.

**`messages=[...]`** is the tokens in: a list of messages, each with a `role` and `content`.

**`client.messages.create(...)`** sends the request and waits for the response. `model` picks which model, and `max_tokens` caps the tokens out; the model stops there, even mid-sentence.

**`reply`** is the response: the tokens out, plus details about how they were produced. The `print` shows all of it.

## Run it

From the root of the repo:

```bash
uv run lessons/01-model-interface/quark.py
```

Here's one run:

```json
{
  "id": "msg_011Cfjtdeu23hbWiRDRTpJxg",
  "container": null,
  "content": [
    {
      "signature": "CAQSwgUKEAgSGAI4AUIIdGhpbmtpbmcSDCu9/GfGfYwbroLG+RoMOqs4xtYaAvKYS9GoIjD/...",
      "thinking": "",
      "type": "thinking"
    },
    {
      "citations": null,
      "text": "I can't see your file system, so I can't tell what's in your directory. No files or tools have been shared in this conversation. Here's how you can check yourself:\n\n**macOS / Linux (Terminal)**\n```bash\nls          # basic listing\nls -la      # detailed listing, including hidden files\ntree        # tree view (may need to be installed)\n```\n\n**Windows Command Prompt**\n```cmd\ndir\ndir /a      # include hidden files\n```\n\n**Windows PowerShell**\n```powershell\nGet-ChildItem   # or: ls / dir\nGet-ChildItem -Force   # include hidden files\n```\n\nIf you paste the output here, I can help you interpret it, find specific files, clean things up, or write a script to work with them.\n\nIf you're using an IDE or tool that's supposed to give me file access, it may not be set up correctly. Let me know what you're working with and I can help troubleshoot.",
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
    "output_tokens": 331,
    "output_tokens_details": {
      "thinking_tokens": 38
    },
    "server_tool_use": null,
    "service_tier": "standard"
  }
}
```

Yours will be worded differently; the model's output varies from run to run. (The long `signature` is shortened here.) Three fields matter:

- **`content`** is the tokens out, as a list of blocks. This model thinks before it answers, so the first block is its `thinking` and the second is the `text` of its reply. By default the thinking text comes back empty, with only a `signature`: an encrypted copy of the reasoning that only the API can read.
- **`stop_reason`** is why it stopped. `end_turn` means it finished; `max_tokens` would mean it hit the cap.
- **`usage`** counts both sides: `input_tokens` is TokensIn, `output_tokens` is TokensOut, thinking included.

Read the `text`. The model knows the right next step is `ls`. It just can't take it.

## Going further

**What else a model interface can be:** the mechanism is always a request out and a response back, but it holds more in other harnesses than it does here.
- **Where the request goes.** A hosted API, a model on your own machine, a gateway in front of several providers.
- **How it travels.** An official SDK, raw HTTP, or a layer that speaks several providers' formats so the rest of the harness doesn't have to.
- **Which model answers.** One model, or a backup that takes over when the first is unavailable.
- **How the response arrives.** All at once, or streamed piece by piece as it's produced, so a long response can't time out.
- **How many go at once.** One request, or a batch of them.
- **What happens when a request fails.** Retry it, wait out a rate limit, give up after a timeout.
- **The request's settings.** How many tokens out, how much the model thinks first, whether you see a summary of its thinking.

It can hold enough to be a product on its own. Gateways like [LiteLLM](https://github.com/BerriAI/litellm) and [OpenRouter](https://openrouter.ai) are this primitive and nothing else: a harness sends them one request format, and they handle where it goes, which provider and model answer, backups when one is down, retries and rate limits. A harness that uses one has handed off its model interface.

Here's a model interface that does more of that, in [`model_interface.py`](./model_interface.py):

```python
import anthropic

client = anthropic.Anthropic(timeout=120, max_retries=3)
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]

def call(messages, max_tokens=16384, effort="high", thinking="summarized"):
    for model in MODELS:
        try:
            with client.messages.stream(model=model, max_tokens=max_tokens, output_config={"effort": effort}, thinking={"type": "adaptive", "display": thinking}, messages=messages) as stream:
                return stream.get_final_message()
        except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError):
            continue
    raise RuntimeError("no model answered")

reply = call([{"role": "user", "content": "What's in this directory?"}])
print(reply.model_dump_json(indent=2))
```

- **What happens when a request fails.** `timeout=120` gives up on a request that takes longer than two minutes. `max_retries=3` has the SDK retry dropped connections, rate limits and server errors, waiting longer each time.
- **Which model answers.** If every retry fails, `call` moves on to the next model in `MODELS`.
- **How the response arrives.** `stream` receives the response as it's produced, so a long one can't time out, and `get_final_message()` hands back the whole response once it's done. Nothing is printed along the way; showing it to a person would be output.
- **The request's settings.** `max_tokens`, `effort` (how much the model thinks first) and `thinking` are arguments the caller can set. `"summarized"` asks for a readable summary of the model's thinking instead of the empty default. The raw thinking itself is never returned.

Run it the same way:

```bash
uv run lessons/01-model-interface/model_interface.py
```

Here's one run:

```json
{
  "id": "msg_011Cfjmr2xbFAE1MRszzzWWX",
  "container": null,
  "content": [
    {
      "signature": "CAQS0AUKEAgSGAI4AUIIdGhpbmtpbmcSDJo1AOU3Q8nzeKwLQRoMqA3M2GGFMP3dZLX+IjCE...",
      "thinking": "I don't actually have access to this user's file system, so I can't see what's in their directory—I should explain that and suggest they paste the listing or output here instead.\n\n",
      "type": "thinking"
    },
    {
      "citations": null,
      "text": "I can't see your directory. I don't have file system access in this conversation, and nothing has been shared with me besides your message.\n\nTo find out what's in it, you can run one of these yourself:\n\n- **macOS/Linux:** `ls -la` (includes hidden files), or `ls -R` (recursive)\n- **Windows Command Prompt:** `dir`\n- **Windows PowerShell:** `Get-ChildItem` (or `ls`)\n- **Tree view:** `tree` (on Linux/macOS you may need to install it first)\n\nIf you paste the output here, I can help you make sense of it, such as explaining what the files are, finding something specific, or cleaning things up.",
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
    "output_tokens": 257,
    "output_tokens_details": {
      "thinking_tokens": 41
    },
    "server_tool_use": null,
    "service_tier": "standard"
  }
}
```

It looks like the first response (its `signature` is shortened too), with one difference: the `thinking` block has text. That's the summary `display: "summarized"` asked for. The rest of what this version adds only shows when something goes wrong: a dropped connection, a rate limit, a model that's down.

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
