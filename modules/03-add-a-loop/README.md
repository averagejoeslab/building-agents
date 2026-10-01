# Add a loop

> **Harness component: control flow.** The first real piece of harness. A loop turns a single model call into something that keeps going — and binding that loop to an environment gives the agent somewhere to live.

Module 2 made one call and exited. Useful interactions are conversations: follow-ups, corrections, back-and-forth. So we wrap the call in a loop. By the end of this module we have a chatbot. It still can't *do* anything — that's Module 4 — but the loop we write here is the exact loop quark runs. Every later module adds to it; none of them replace it.

## Stateless API, stateful loop

The Messages API is **stateless**. The server remembers nothing between calls; the only context the model has is whatever is in the `messages` list on that call. So the *harness* holds the state. It keeps the conversation in a list, appends the human's message before each call and the model's reply after it, and sends the whole list every time.

That list is `working_memory`. It is, quite literally, everything the model knows in the moment — which is why quark calls it the agent's mind.

## Bind the loop to an environment

A loop on its own runs in a vacuum. To be useful it has to be **bound to an environment** — somewhere it reads input from and writes output to. The way I think about it is like a person being bootstrapped into a body and a world: a loop has to be bootstrapped into an environment, and that environment is the agent's world.

quark's environment is the **terminal**: `input()` reads from the human, `sys.stdout` writes back. Zero ceremony. But the loop is environment-agnostic — the same `while True` around the same streaming call could just as well be bound to:

- A **web socket**, with input from a browser and output streamed back to it.
- A **Slack channel** or **Telegram chat**, with messages in and replies out. (quark itself has an experimental branch that does exactly this: the same loop, with Telegram as its ear and voice.)
- A **Gameboy emulator**, with screen state in and button presses out.
- A **humanoid robot**, with cameras, microphones, and joint sensors in, and motor torques out. In my opinion that's the most exciting environment you can put a loop in.

When you wrap a model in a loop, you're also deciding *where* that loop lives. The rest of the curriculum is the same wherever it is.

## The checkpoint

[`examples/03_loop.py`](../../examples/03_loop.py):

```python
import sys
from anthropic import Anthropic

client, MODEL = Anthropic(), "claude-sonnet-4-5"
chat, working_memory = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}]

while True:
    with client.messages.stream(model=MODEL, max_tokens=4096, messages=working_memory) as stream:
        for ev in stream:
            if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
        saying = stream.current_message_snapshot
    print()
    working_memory.append({"role": "assistant", "content": saying.content})
    if not chat or (u := next(filter(str.strip, iter(lambda: input("\n> "), None)))) == "/q": break
    working_memory.append({"role": "user", "content": u})
```

The streaming block is Module 2's, unchanged. What's new is the line that seeds the conversation, and the three lines at the bottom of the loop.

### Two modes: one-shot and chat

```python
chat, working_memory = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}]
```

This line is dense, so take it apart:

- **`chat = len(sys.argv) < 2`** — if you passed a task on the command line, quark runs **one-shot**: it works on that task and exits. With no arguments it runs in **chat** mode and keeps prompting you.
- **`iter(lambda: ..., None)`** — the two-argument form of `iter` calls the function over and over until it returns the sentinel (`None`, which it never does). So this is an endless stream of attempts to get input: the command-line args if there are any, otherwise `input("> ")`.
- **`next(u for u in ... if u.strip())`** — take the first attempt that isn't blank. Hit Enter on an empty line and you're simply prompted again. That matters more than it looks: an empty message is an API error, and an API error would end the program. The harness never sends one.

### The bottom of the loop

```python
    working_memory.append({"role": "assistant", "content": saying.content})
    if not chat or (u := next(filter(str.strip, iter(lambda: input("\n> "), None)))) == "/q": break
    working_memory.append({"role": "user", "content": u})
```

1. **Append the model's reply** — the full list of content blocks, not just the text. Today that's one text block; from Module 4 on it will include `tool_use` blocks, and the API needs to see them again on the next call.
2. **Decide whether to continue.** In one-shot mode, the turn is over, so break. In chat mode, read the next non-blank line from the human (same `iter`-until-non-blank idiom); if it's `/q`, break.
3. **Append the human's message**, and loop — the next call sends the whole conversation again.

Every turn adds two entries to `working_memory`, and every call sends all of them. That's the whole trick behind multi-turn conversation: no server-side session, just a list that grows.

## Run it

```bash
cd examples
uv run 03_loop.py
```

```
> My name is Chase.
Nice to meet you, Chase!

> What's my name?
Your name is Chase.

> /q
```

Or one-shot: `uv run 03_loop.py "give me a haiku about loops"`.

Quit and restart, and it has no idea who you are — `working_memory` lived in a variable that died with the process. Persistence comes in Module 7.

## What's missing

- **No body.** The chatbot can explain how to list a directory, but it can't list one.
- **No sense of self or place.** It doesn't know what it is, where it's running, or what day it is.

Module 4 gives it a body.

---

**Next:** [Module 4: Add a body](../04-add-a-body/)
