# Lesson 1: Model interface

> 🎥 **Video:** coming soon

The model is a function: **TokensOut = Model(TokensIn)**. The model interface is the part of the harness that calls it. It's the only primitive that touches the model. The other four exist to prepare a call or to handle its reply, so this one comes first.

Whatever the provider, a model interface does three things:

1. **Package** the tokens in, in the shape the model expects.
2. **Send** them, and wait for tokens to come out.
3. **Keep** what comes back. That's more than text: the reply also says *why* the model stopped and how many tokens went in and out.

## quark's model interface

Here's [quark](https://github.com/averagejoeslab/quark)'s model interface with everything else removed. It's the whole of [`agent.py`](./agent.py):

```python
import sys
from anthropic import Anthropic

client, MODEL = Anthropic(), "claude-sonnet-4-5"
working_memory = [{"role": "user", "content": "What's in this directory?"}]

with client.messages.stream(model=MODEL, max_tokens=4096, messages=working_memory) as stream:
    for ev in stream:
        if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
    saying = stream.current_message_snapshot
print()
```

**`client, MODEL = ...`** is where the model lives and how quark reaches it: Anthropic's hosted API, through the official SDK, which reads your key from `ANTHROPIC_API_KEY`.

**`working_memory`** is the package: the tokens in, as a list of messages, each with a `role` and `content`.

**`client.messages.stream(...)`** sends it. quark streams instead of waiting for the whole reply, so you see words as they're produced and a long reply can't time out. The cost is a few more lines than `client.messages.create(...)`. `max_tokens` caps the tokens out; the model stops there, even mid-sentence.

**`for ev in stream`** prints the text as it arrives, so you can watch the reply come back. `hasattr(ev.delta, "text")` skips the events that don't carry text.

**`saying`** is what's kept: the whole reply as data, with its `content`, `stop_reason` and `usage`.

## Run it

From the root of the repo:

```bash
uv run lessons/01-model-interface/agent.py
```

The reply appears word by word. Here's one run:

```
I don't have access to view your current directory or any filesystem. I'm an AI assistant without the ability to execute commands or access files on your computer.

To see what's in a directory, you would need to run a command in your terminal:

- **Linux/Mac/Unix:** `ls` (or `ls -la` for detailed view)
- **Windows Command Prompt:** `dir`
- **Windows PowerShell:** `ls` or `Get-ChildItem`

If you'd like help understanding the output or working with specific files, feel free to share what you see and I can help you interpret it!
```

Yours will be worded differently; the model's output varies from run to run.

The model knows the right next step. It just can't take it.

## What to take away

**The rule:** the model interface packages tokens in, sends them, and keeps what comes back.

**What else would have worked:**
- **Waiting instead of streaming.** Fewer lines, and fine for short replies or a harness no one watches.
- **Raw HTTP.** One POST with a JSON body. No dependency, but you parse the reply and the stream yourself.
- **A multi-provider library.** Swap models by changing a string, with a layer between you and each provider's features.
- **A local model.** No API key and no per-token bill, in exchange for your own hardware and usually a smaller model.

**What's missing:** the question is hardcoded, and the reply only goes to the screen. The model said what to do, and nothing could do it. That's input and output.

**→ [Lesson 2: Input and output](../02-input-and-output/)**
