# Lesson 1: Model interface

> 🎥 **Video:** coming soon

**You build:** how the harness interfaces with the model: one call, and its reply.
**You end with:** [`agent.py`](./agent.py), 11 lines.

---

## Explain

The model is a function: **TokensOut = Model(TokensIn)**. The model interface is the part of the harness that calls it. It's the only primitive that touches the model directly, which is why we start here: until you can call the model, there's nothing for the other four to wrap.

Strip away the provider and every model interface does the same three things:

1. **Package** the tokens in, in the shape the model expects.
2. **Send** them, and wait for tokens to come out.
3. **Receive** the reply, and keep what the rest of the harness will need.

Those are the mechanisms. Everything else is a choice:

- **Where the model lives.** A hosted API, a model on your own machine, a model behind your company's gateway.
- **How you reach it.** An official SDK, raw HTTP, a library that wraps many providers.
- **Wait or stream.** Get the whole reply at once, or receive it piece by piece as it's produced.
- **What you keep.** The reply is more than text. It says *why* the model stopped, how many tokens went in and out, and, once there are tools, what the model asked to do.

Here's the smallest model interface there is:

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

Run it and the model answers. It will probably tell you it can't see your files and suggest you run `ls`. That's worth sitting with. The model knows the right next step. It just can't take it. The question was hardcoded, the answer was only printed, and nothing happens next. Every one of those is a different primitive, and each of the next three lessons fills one.

## Show

Here's quark's model interface, with everything else removed:

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

**`client, MODEL = Anthropic(), "claude-sonnet-4-5"`**. Where the model lives and how quark reaches it: Anthropic's hosted API, through the official SDK. The client reads your key from `ANTHROPIC_API_KEY`. The model name is a constant because the harness calls the model from more than one place later on, and they should all agree.

**`working_memory = [...]`**. The tokens in, as a list of messages. Each message has a `role` (`user` or `assistant`) and `content`. It's called working memory because that's what it becomes: everything that has happened in this session. Right now it holds one message. You'll see it grow in Lesson 3 and understand why it's named that way in Lesson 4.

**`client.messages.stream(...)`**. quark streams instead of waiting. Two reasons. You see words as they're produced, so a long answer doesn't look like a hang. And a long reply can take long enough that a request waiting for the whole thing times out; a stream doesn't. The cost is more code than `create`.

**`max_tokens=4096`**. A ceiling on tokens out. The model stops there even mid-sentence. You'll handle what that means for tools in Lesson 2.

**`for ev in stream: ...`**. The stream is a sequence of events. quark only prints the ones that carry text. `hasattr(ev.delta, "text")` is there because other kinds of deltas exist: when the model asks to use a tool, its arguments stream in as JSON, and you don't want to print those as if they were speech.

**`saying = stream.current_message_snapshot`**. When the stream ends, this is the whole reply as data: its `content` blocks, its `stop_reason`, its `usage`. Printing was for the person. `saying` is for the harness. Nothing uses it yet. Lesson 2 does.

## Do

1. **Type it.** Create `agent.py` in the root of your copy of this repo and type the code above. Don't paste it; typing is how you notice what each part does. Then run it:

   ```bash
   uv run agent.py
   ```

   You should see the reply appear word by word.

2. **Make one change of your own.** Pick one, or invent your own:
   - Print `saying.usage.input_tokens` and `saying.usage.output_tokens` after the reply. Those are TokensIn and TokensOut, counted.
   - Print `saying.stop_reason`. Then set `max_tokens=20` and run it again. What changed?
   - Swap streaming for `client.messages.create(...)`. What did you gain? What did you lose?
   - Point it at a different model or provider. What had to change, and what didn't?

3. **Check yourself.** If you're stuck, compare against [`agent.py`](./agent.py) in this folder.

## Recap

**The rule:** the model interface packages tokens in, sends them, and keeps what comes back. It's the only primitive that touches the model.

**Questions to check yourself:**
- What are the tokens in, in your code? What are the tokens out?
- What does the reply contain besides text?
- Why would a harness need to know *why* the model stopped?

**What else would have worked:**
- **Waiting instead of streaming.** Fewer lines, and fine for short replies or for a harness no person watches.
- **Raw HTTP.** One POST with a JSON body. No dependency, but you parse the reply and the stream yourself.
- **A multi-provider library.** Swap models by changing a string, at the cost of a layer between you and each provider's features.
- **A local model.** No API key and no per-token bill. You trade them for your own hardware and, usually, a smaller model.

**What's missing:** the question is hardcoded, and the reply only goes to the screen. The model said what to do, and nothing could do it. That's input and output.

**→ [Lesson 2: Input and output](../02-input-and-output/)**
