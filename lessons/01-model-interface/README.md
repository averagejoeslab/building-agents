# Lesson 1: Model interface

> 🎥 **Video:** coming soon

The model is a function: **TokensOut = Model(TokensIn)**. The model interface is how the harness calls it. It sends tokens to the model as a request, and the model returns tokens as a response, just like any other API endpoint.

It's the thinnest of the five primitives, and that's because of where it sits. The other four live on the harness's side: they decide when to call, what goes into the request, and what to do with the response. The model interface is the boundary between the harness and the model. In **Agent = Harness(Model)**, it's the parentheses. Nothing reaches the model without it, so it comes first.

## The worked example

Here's the call at the center of [quark](https://github.com/averagejoeslab/quark), with nothing around it. It's the whole of [`agent.py`](./agent.py):

```python
from anthropic import Anthropic

client = Anthropic()
reply = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=1024,
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
uv run lessons/01-model-interface/agent.py
```

Here's one run:

```json
{
  "id": "msg_011CfjjRqV826eeqibZMLVHB",
  "container": null,
  "content": [
    {
      "signature": "CAQSxwUKEAgSGAI4AUIIdGhpbmtpbmcSDF0NourNS+7x6dB0gBoMNqBtr/ZssKlFVG1JIjBH...",
      "thinking": "",
      "type": "thinking"
    },
    {
      "citations": null,
      "text": "I can't see your directory because I don't have access to your file system in this conversation. Here are some ways to find out what's in it:\n\n**Command line**\n- macOS/Linux: `ls` (or `ls -la` to include hidden files and details)\n- Windows Command Prompt: `dir`\n- Windows PowerShell: `Get-ChildItem` (or `ls`)\n- Tree view: `tree` (works on most systems, though you may need to install it)\n\n**Graphical**\n- Open the folder in Finder (macOS), File Explorer (Windows), or your Linux file manager.\n\nIf you run one of these and paste the output here, I can help you interpret it, find a specific file, clean things up, or write a script to work with the contents.",
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
    "output_tokens": 273,
    "output_tokens_details": {
      "thinking_tokens": 40
    },
    "server_tool_use": null,
    "service_tier": "standard"
  }
}
```

Yours will be worded differently; the model's output varies from run to run. (The long `signature` is shortened here.) Three fields matter:

- **`content`** is the tokens out, as a list of blocks. This model thinks before it answers, so the first block is its `thinking` (kept private here; the API returns only a signature for it) and the second is the `text` of its reply.
- **`stop_reason`** is why it stopped. `end_turn` means it finished; `max_tokens` would mean it hit the cap.
- **`usage`** counts both sides: `input_tokens` is TokensIn, `output_tokens` is TokensOut, thinking included.

Read the `text`. The model knows the right next step is `ls`. It just can't take it.

## What to take away

**The rule:** the model interface sends tokens to the model as a request and gets tokens back as a response.

**What else a model interface can be:** the mechanism is always a request out and a response back, but it holds more in other harnesses than it does here.
- **Where the request goes.** A hosted API, a model on your own machine, a gateway in front of several providers.
- **How it travels.** An official SDK, raw HTTP, or a layer that speaks several providers' formats so the rest of the harness doesn't have to.
- **Which model answers.** One model, or a backup that takes over when the first is unavailable.
- **How the response arrives.** All at once, or streamed piece by piece as it's produced, so a long response can't time out.
- **How many go at once.** One request, or a batch of them.
- **What happens when a request fails.** Retry it, wait out a rate limit, give up after a timeout.
- **The request's settings.** How many tokens out, how much the model thinks first.

Notice what isn't on that list. When to call is control flow. What goes into the request is context. What happens to the response is output. The model interface only gets the request there and the response back.

**What's missing:** the question is hardcoded, and the reply is just data dumped to the screen. The model said what to do, and nothing could do it. That's input and output.

**→ [Lesson 2: Input and output](../02-input-and-output/)**
