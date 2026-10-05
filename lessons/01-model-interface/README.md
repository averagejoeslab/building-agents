# Lesson 1: Model interface

> 🎥 **Video:** coming soon

The model interface is how the harness interfaces with the model: it sends tokens in and gets tokens out. By the end of this lesson you'll have [`agent.py`](./agent.py), 11 lines that call a model once and show its reply as it's written.

## What it is

The model is a function: **TokensOut = Model(TokensIn)**. The model interface is the part of the harness that calls that function. It's the only one of the five primitives that touches the model directly. The other four feed it or handle what it returns.

## Why a harness needs it

Without it there's no agent, just a model sitting on a server. Everything else the harness does, gathering input, assembling context, running tools, deciding whether to go again, exists to prepare a call or to deal with its reply. So the call comes first.

## How it works

Strip away the provider and every model interface does three things:

1. **Package** the tokens in, in the shape the model expects.
2. **Send** them, and wait for tokens to come out.
3. **Receive** the reply, and keep what the rest of the harness will need.

How you do each one is a choice:

- **Where the model lives.** A hosted API, a model on your own machine, a model behind your company's gateway.
- **How you reach it.** An official SDK, raw HTTP, a library that wraps many providers.
- **Wait or stream.** Get the whole reply at once, or piece by piece as it's produced.
- **What you keep.** The reply is more than text. It says *why* the model stopped, how many tokens went in and out, and, once there are tools, what the model asked to do.

The smallest model interface there is looks like this:

```python
from anthropic import Anthropic

client = Anthropic()
reply = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "What's in this directory?"}],
)
print(reply.content[0].text)
```

That's TokensOut = Model(TokensIn), used once. `messages` is the tokens in. `reply` is the tokens out.

## Show: quark's model interface

Here's the model interface from [quark](https://github.com/averagejoeslab/quark), with everything else removed. This is the whole of [`agent.py`](./agent.py):

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

Line by line, with the choice each one makes:

**`client, MODEL = Anthropic(), "claude-sonnet-4-5"`** says where the model lives and how quark reaches it: Anthropic's hosted API, through the official SDK. The client reads your key from `ANTHROPIC_API_KEY`. The model name is a constant because a harness usually calls the model from more than one place, and they should all agree.

**`working_memory = [...]`** is the tokens in, as a list of messages. Each message has a `role` (`user` or `assistant`) and `content`. quark calls it working memory because, once there's a loop, it holds everything that has happened in the session. Here it holds one message.

**`client.messages.stream(...)`** streams instead of waiting, for two reasons. You see words as they're produced, so a long answer doesn't look like a hang. And a long reply can take long enough that a request waiting for all of it times out; a stream doesn't. The cost is more code than `create`.

**`max_tokens=4096`** is a ceiling on tokens out. The model stops there, even mid-sentence.

**`for ev in stream: ...`** reads the stream, a sequence of events, and prints only the ones that carry text. `hasattr(ev.delta, "text")` is there because other kinds of deltas exist: when a model asks to use a tool, the tool's arguments stream in as JSON, and you don't want to print those as if they were speech.

**`saying = stream.current_message_snapshot`** is the whole reply as data, once the stream ends: its `content` blocks, its `stop_reason`, its `usage`. Printing was for the person. `saying` is for the harness: it's what the output primitive will read to find out what the model asked to do.

## Run it

From the root of the repo:

```bash
uv run lessons/01-model-interface/agent.py
```

You'll see the reply appear word by word. It will probably say something like:

```
I don't have access to your file system, so I can't see what's in your current directory.
You can check by running `ls` (macOS/Linux) or `dir` (Windows)...
```

That's worth sitting with. The model knows the right next step. It just can't take it.

## Recap

**The rule:** the model interface packages tokens in, sends them, and keeps what comes back. It's the only primitive that touches the model.

**What quark chose:** Anthropic's API through the official SDK, streamed, with the whole reply kept as data.

**What else would have worked:**
- **Waiting instead of streaming.** Fewer lines, and fine for short replies or a harness no one watches.
- **Raw HTTP.** One POST with a JSON body. No dependency, but you parse the reply and the stream yourself.
- **A multi-provider library.** Swap models by changing a string, at the cost of a layer between you and each provider's features.
- **A local model.** No API key and no per-token bill, in exchange for your own hardware and usually a smaller model.

**What's missing:** the question is hardcoded, and the reply only goes to the screen. The model said what to do, and nothing could do it. That's input and output.

**→ [Lesson 2: Input and output](../02-input-and-output/)**
