# Add a loop

> **Harness component: control flow.** The first real piece of harness we build. A loop is what turns a single model call into something that can actually keep going — and it also binds that "going" to an environment (in our case, the terminal).

Module 2 made one LLM call. The model answered, the program ended, that was it. But most useful interactions aren't single shots — they're conversations, with follow-ups, clarifications, and back-and-forth. So in this module we wrap that single call in a loop, and that gives us a chatbot that can keep talking.

It's still not an agent yet — the model can only emit text, not act on anything. That comes in Module 5 when we add tools. But for now we're focused on the loop itself.

## Stateless API, stateful loop

One thing worth understanding up front: the Messages API itself is **stateless**. The server doesn't remember anything between calls. Every `messages.create` is completely independent — the only context the model has access to is whatever's in the `messages` list you send on that specific call.

So the *program* is the thing that has to keep the state. You maintain a list of `{role, content}` turns yourself, you append the user's input before each call and the assistant's reply after each call, and you send the whole list every single time.

In my opinion this is one of those tricks that's worth pausing on. It's what makes a multi-turn conversation possible without any server-side session at all — the conversation literally lives in your variable, and the server's role is just to take whatever you send and complete it.

## Tie the loop to an environment

A loop on its own is just a program running forever in a vacuum. To actually make it useful you have to **tie it to an environment** — somewhere it reads input from and somewhere it writes output to. The way I think about it is just like a person being bootstrapped into a body and a world: a loop has to be bootstrapped into an environment, and that environment is the agent's world.

For this curriculum we're picking the simplest environment available: the **terminal**. `input()` reads a line from stdin, `print()` writes back to stdout, and `/q` exits the loop. Zero ceremony, just the same bytes you already know how to work with.

But here's the thing — the loop itself is environment-agnostic. The exact same `while True` around the exact same `messages.create` could just as well be bound to:

- A **web socket**, with input coming from a browser and output sent back as streaming SSE.
- A **Slack channel**, with input from a slash command and output as a thread reply.
- A **Gameboy emulator**, with input from button presses and output as screen state. Give that kind of agent a "press button" tool later and it eventually lives and plays inside the console.
- A **Minecraft server**, with input from chat or game events and output as block actions.
- A **spreadsheet cell**, with input from the formula's arguments and output as the cell's value.
- A **humanoid robot**, with input from on-board cameras, microphones, and joint sensors, and output as motor torques sent to the limbs. The loop in this case literally walks around in the physical world. It hasn't been done a ton yet, but there's some genuinely exciting work happening in this space — and in my opinion that's the most exciting environment you can put one in.

When you decide to wrap an LLM call in a loop, you're also deciding *where* that loop lives. The terminal is just our pick because it has the least ceremony for a curriculum. The pattern transfers to any environment that can hand you input bytes and accept output bytes back — once the loop is wired up, the rest of the curriculum is the same.

## The chatbot

The loop itself is just a `while True` around the API call, with a list that grows on each turn. We're using async streaming here — which we introduced back in Module 2 — so that each reply renders token-by-token instead of arriving as one delayed block of text. The curriculum uses async streaming for every LLM call from this point forward, so settling into the `async` / `await` pattern early pays off in the later modules:

```python
import os
import asyncio
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


async def main():
    messages = []

    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        messages.append({"role": "user", "content": user_input})

        async with client.messages.stream(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system="You are a helpful assistant.",
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                print(text, end="", flush=True)
            print()
            response = await stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content[0].text})


asyncio.run(main())
```

Three things in there worth calling out specifically:

1. **Every turn sends the full history.** There's no server-side state — `messages` is the entire conversation, sent fresh on every call.
2. **The stream prints text live; `await stream.get_final_message()` returns the structured response** at the end. We append the assistant's text to history from that captured response rather than buffering everything ourselves while the stream is happening.
3. **Both roles get appended.** User input goes in before the call, the assistant's reply goes in after. The next iteration of the loop sees both.

## Run it

The runnable version lives at [`examples/stateless_chatbot.py`](../../examples/stateless_chatbot.py):

```bash
cd examples
uv run stateless_chatbot.py
```

```
❯ My name is Chase.
Nice to meet you, Chase.
❯ What's my name?
Your name is Chase.
❯ /q
```

Quit the program and the conversation is gone, because `messages` was just an in-memory list that disappears with the process. So the chatbot is **stateless** across sessions even though it's stateful within a single session. Making it stateful across sessions is Module 4's problem.

## What's missing

By the end of this module we've got a working chatbot, but two specific things still aren't there:

- **Nothing survives a restart.** The conversation lives in a process variable, so quitting the program evaporates everything that just happened.
- **The chatbot can only emit text.** It can describe how to read a file, or explain what `git status` would do, or propose what a config change might look like — but it cannot actually read, run, or write anything on its own.

The first is memory's problem and we solve it in Module 4. The second is tools' problem and we solve it in Module 5. We do memory first because it makes the chatbot useful across sessions even before it can act.

---

**Next:** [Module 4: Add memory](../04-add-memory/)
