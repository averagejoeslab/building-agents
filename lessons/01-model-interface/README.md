# Lesson 1: Model interface

> 🎥 **Video:** coming soon

The model is a function: **TokensOut = Model(TokensIn)**. The model interface is the part of the harness that calls it. It's the only primitive that touches the model. The other four exist to prepare a call or to handle its reply, so this one comes first.

Whatever the provider, a model interface does three things:

1. **Package** the tokens in, in the shape the model expects.
2. **Send** them, and wait for tokens to come out.
3. **Keep** what comes back. That's more than text: the reply also says *why* the model stopped and how many tokens went in and out.

## The worked example

Here's the call at the center of [quark](https://github.com/averagejoeslab/quark), with nothing around it. It's the whole of [`agent.py`](./agent.py):

```python
from anthropic import Anthropic

client = Anthropic()
reply = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "What's in this directory?"}],
)
print(reply.model_dump_json(indent=2))
```

**`client = Anthropic()`** is how quark reaches the model: Anthropic's hosted API, through the official SDK, which reads your key from `ANTHROPIC_API_KEY`.

**`messages=[...]`** is the package: the tokens in, as a list of messages, each with a `role` and `content`.

**`client.messages.create(...)`** sends it and waits. `model` picks which model, and `max_tokens` caps the tokens out; the model stops there, even mid-sentence.

**`reply`** is what's kept: everything that came back, as data. The `print` shows all of it, so you can see what the model interface hands to the rest of the harness.

## Run it

From the root of the repo:

```bash
uv run lessons/01-model-interface/agent.py
```

Here's one run:

```json
{
  "id": "msg_011CfjjLu1KTynDxpWda5Tiw",
  "container": null,
  "content": [
    {
      "citations": null,
      "text": "I don't have access to view your current directory or file system. I'm an AI assistant without the ability to execute commands or access your local environment directly.\n\nTo see what's in your current directory, you can use:\n\n**On Linux/Mac:**\n```bash\nls\n```\nor for more details:\n```bash\nls -la\n```\n\n**On Windows (Command Prompt):**\n```cmd\ndir\n```\n\n**On Windows (PowerShell):**\n```powershell\nGet-ChildItem\n```\nor simply:\n```powershell\nls\n```\n\nIf you run one of these commands and share the output with me, I'd be happy to help you understand what files and folders are present!",
      "type": "text"
    }
  ],
  "diagnostics": null,
  "model": "claude-sonnet-4-5-20250929",
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
    "inference_geo": "not_available",
    "input_tokens": 13,
    "output_tokens": 161,
    "output_tokens_details": null,
    "server_tool_use": null,
    "service_tier": "standard"
  }
}
```

Yours will be worded differently; the model's output varies from run to run. Three fields matter:

- **`content`** is the tokens out: the model's reply.
- **`stop_reason`** is why it stopped. `end_turn` means it finished; `max_tokens` would mean it hit the cap.
- **`usage`** counts both sides: `input_tokens` is TokensIn, `output_tokens` is TokensOut.

Read the `text`. The model knows the right next step is `ls`. It just can't take it.

## What to take away

**The rule:** the model interface packages tokens in, sends them, and keeps what comes back.

**What else would have worked:**
- **Streaming instead of waiting.** The reply arrives piece by piece as it's produced, so a person can watch it and a long reply can't time out. More code to read it.
- **Raw HTTP.** One POST with a JSON body. No dependency, but you parse the reply and the stream yourself.
- **A multi-provider library.** Swap models by changing a string, with a layer between you and each provider's features.
- **A local model.** No API key and no per-token bill, in exchange for your own hardware and usually a smaller model.

**What's missing:** the question is hardcoded, and the reply is just data dumped to the screen. The model said what to do, and nothing could do it. That's input and output.

**→ [Lesson 2: Input and output](../02-input-and-output/)**
