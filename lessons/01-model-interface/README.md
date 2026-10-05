# Lesson 1: Model interface

> 🎥 **Video:** coming soon

The model is a function: **TokensOut = Model(TokensIn)**. The model interface is how the harness calls it. It sends tokens to the model as a request, and the model returns tokens as a response, just like any other API endpoint.

It's the only primitive that touches the model. Deciding what goes into the request and what to do with the response is the work of the other four, so this one comes first.

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

**What else would have worked:**
- **Streaming instead of waiting.** The reply arrives piece by piece as it's produced, so a person can watch it and a long reply can't time out. More code to read it.
- **Raw HTTP.** One POST with a JSON body. No dependency, but you parse the reply and the stream yourself.
- **A multi-provider library.** Swap models by changing a string, with a layer between you and each provider's features.
- **A local model.** No API key and no per-token bill, in exchange for your own hardware and usually a smaller model.

**What's missing:** the question is hardcoded, and the reply is just data dumped to the screen. The model said what to do, and nothing could do it. That's input and output.

**→ [Lesson 2: Input and output](../02-input-and-output/)**
