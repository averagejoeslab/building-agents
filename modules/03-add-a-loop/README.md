# Add a loop

> **Harness component: control flow.** The first real harness piece. A loop turns a single model call into continuous existence — and binds that existence to an environment (here, the terminal).

Module 2 made one LLM call. The model answered, the program ended. Most useful interactions are conversations — questions, follow-ups, clarifications. The fix is a loop around the API call so the program can keep talking.

By the end you have a chatbot. Not an agent yet — the model can only emit text, not act. Tools come next.

## Stateless API, stateful loop

The Messages API is stateless. The server doesn't remember anything between calls. Every `messages.create` is independent — the only context the model has is the `messages` list you send it.

So the *program* keeps the state. You maintain a list of `{role, content}` turns; you append the user's input before the call and the assistant's reply after; you send the whole list every time.

This is the trick that makes a multi-turn conversation possible without any server-side session — the conversation lives in your variable.

## Tie the loop to an environment

A loop on its own is a program running forever in a vacuum. To make it useful you have to **tie it to an environment** — somewhere it reads input from and writes output to. Just as a person is bootstrapped into a body and a world, a loop has to be bootstrapped into an environment. The environment is the agent's world.

We're picking the simplest one available: the **terminal**. `input()` reads a line from stdin, `print()` writes back to stdout, `/q` exits. Zero ceremony, the same bytes you already know.

But the loop itself is environment-agnostic. The same `while True` around the same `messages.create` could just as well bind to:

- A **web socket** — input from a browser, output as streaming SSE.
- A **Slack channel** — input from a slash command, output as a thread reply.
- A **Gameboy emulator** — input from button presses, output as screen state. Give such an agent a "press button" tool later, and it eventually lives and plays inside the console.
- A **Minecraft server** — input from chat or game events, output as block actions.
- A **spreadsheet cell** — input from the formula's arguments, output as the cell's value.

When you decide to wrap an LLM call in a loop, you're also deciding *where* that loop lives. The terminal is just our pick — chosen because it has the least ceremony for a curriculum. The pattern transfers to any environment that can hand you input bytes and accept output bytes; once the loop is wired, the rest of the curriculum is the same.

## The chatbot

A `while True` around the API call, with a list that grows on each turn. Module 2 introduced **async streaming** — we use it here so each reply renders token-by-token instead of as one delayed block. The curriculum uses async streaming for every LLM call from this point forward, so settling into the `async`/`await` pattern early pays off in later modules:

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

Three things to notice:

1. **Every turn sends the full history.** No server-side state — `messages` is the entire conversation each call.
2. **The stream prints text live; `await stream.get_final_message()` returns the structured response** at the end. We append the assistant's text to history from the captured response, not by buffering everything ourselves while streaming.
3. **Both roles get appended.** User input goes in before the call; the assistant's reply goes in after. The next turn sees both.

## Run it

The runnable version is [`examples/stateless_chatbot.py`](../../examples/stateless_chatbot.py).

```bash
cd examples
uv run stateless_chatbot.py
```

```
❯ My name is Sam.
Nice to meet you, Sam.
❯ What's my name?
Your name is Sam.
❯ /q
```

Quit the program and the conversation is gone — `messages` was just an in-memory list. The chatbot is **stateless** across sessions. Making it stateful is Module 4's problem.

## What's missing

- **Nothing survives a restart.** The conversation lives in a process variable; quit the program and it evaporates.
- **The chatbot can only emit text.** It can describe how to read a file, explain what `git status` would output, propose a config change — but it cannot read, run, or write anything.

The first is memory's problem (Module 4). The second is tools' problem (Module 5). Memory comes first because it makes the chatbot useful across sessions even before it can act.

---

**Next:** [Module 4: Add memory](../04-add-memory/)
