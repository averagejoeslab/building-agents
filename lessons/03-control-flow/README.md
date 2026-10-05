# Lesson 3: Control flow

> 🎥 **Video:** coming soon

Control flow is how information flows between the other four primitives. By the end of this lesson you'll have [`agent.py`](./agent.py), 28 lines that loop: run the command the model asked for, send the result back, and go again until the model is done. It's the first version that's an agent.

## What it is

Control flow is one of the five primitives, and the other four sit inside it. It decides what runs, in what order, and whether to go again.

## Why a harness needs it

Input, a model interface and output on their own run once and stop. Something has to arrange them. And the arrangement is what decides what you've built. The same four pieces give you:

- **Run once.** Input, call, output, stop. A single call.
- **A chat loop.** Call, show the reply, hand back to the person, repeat. A chatbot.
- **An agent loop.** Call, and while the model asks for tools, run them, send the results back, and call again. Hand back when it stops asking.
- **A workflow.** Your code decides the steps: call the model to plan, then to write, then to check. The model fills in each step.

There's no correct one. An agent loop isn't better than a workflow; it's a different answer to who decides what happens next. In an agent loop, the model decides. In a workflow, your code does.

## How it works

Whatever you pick, control flow comes down to two mechanisms:

- **Sequence:** run the other primitives in some order, passing what one produced to the next.
- **Termination:** decide when to stop, or when to hand back to a person.

Termination is the one people forget. A loop with no clear way to end is a bill with no clear way to end.

## Show: quark's control flow

Here's [`agent.py`](./agent.py). The model interface, input and output are the ones from [Lesson 1](../01-model-interface/) and [Lesson 2](../02-input-and-output/), indented into a loop:

```python
import subprocess, sys
from anthropic import Anthropic

client, MODEL, body = Anthropic(), "claude-sonnet-5-5", [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
chat, working_memory = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}]

while True:
    with client.messages.stream(model=MODEL, max_tokens=4096, tools=body, messages=working_memory) as stream:
        for ev in stream:
            if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
        saying = stream.current_message_snapshot
    print()
    working_memory.append({"role": "assistant", "content": saying.content})
    calls = [b for b in saying.content if b.type == "tool_use"]
    if not calls:
        if not chat or (u := next(filter(str.strip, iter(lambda: input("\n> "), None)))) == "/q": break
        working_memory.append({"role": "user", "content": u})
        continue
    results = []
    for c in calls:
        if "cmd" not in (c.input or {}) or (saying.stop_reason == "max_tokens" and c is calls[-1]):
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": "[your doing was cut off before it was fully formed — it never reached the world]"}); continue
        print(f"$ {c.input['cmd']}")
        doing = subprocess.run(c.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = doing.stdout.decode(errors="replace")
        if out: print(out, end="")
        results.append({"type": "tool_result", "tool_use_id": c.id, "content": out or f"(exit {doing.returncode})"})
    working_memory.append({"role": "user", "content": results})
```

quark is an agent loop that's also a chat loop. Here's what makes it one:

**`while True:`** means go again. Each pass is one call to the model.

**The last line** appends the tool results to `working_memory`, and because there's a next pass, they get sent. That's the whole difference between running once and an agent: the result goes back. And because each pass appends to `working_memory`, the model sees everything that has happened so far, every request and every result.

**`if not calls:`** is termination. The model decides when it's done by not asking for a tool. quark doesn't count steps or look for a magic word. When the model replies with only words, its turn is over.

**`chat = len(sys.argv) < 2`** gives one loop two modes. Give quark a task on the command line and it's one-shot: it works until the model stops asking for tools, then exits. Give it nothing and it's chat: when the model's turn ends, it hands back to you with `> `, adds what you type, and goes again. `/q` quits.

**`continue`** after you type goes straight to the next call. There's no tool result to send, just your message.

Notice what the loop doesn't have: a step limit. quark trusts the model to finish. That's a choice with a cost: if the model never stops asking for tools, quark never stops. A step limit is a guardrail, and guardrails are hardening.

## Run it

From the root of the repo, give it a task that takes more than one command:

```bash
uv run lessons/03-control-flow/agent.py "find the largest file in this directory and tell me what it is"
```

You'll see the model run a command, read the result, maybe run another, and then answer, something like:

```
I'll find the largest file in this directory.
$ find . -type f -not -path './.git/*' -not -path './.venv/*' -exec ls -s {} + | sort -rn | head -5
...
$ head -20 ./assets/04c-attention-variants.svg
...
The largest file is ./assets/04c-attention-variants.svg, an SVG diagram comparing...
```

Then run it with no argument, have a conversation, and quit with `/q`.

## Recap

**The rule:** control flow sequences the other four and decides when to stop. Change it and the same four pieces become a single call, a chatbot, an agent, or a workflow.

**What quark chose:** an agent loop that hands back to a person when the model stops asking for tools, with one-shot and chat as two modes of the same loop, and no step limit.

**What else would have worked:**
- **A step limit or a budget.** Stops a runaway loop, and sometimes stops a task that was about to finish.
- **A workflow.** Predictable and easy to test, but only handles the tasks you designed it for.
- **A planner and an executor.** One loop decides what to do, another does it.
- **More than one agent.** One loop hands a task to another and waits for the result.
- **An event loop.** Wake on a message, a schedule, or a file change instead of a person typing.

**What's missing:** this is an agent, but it doesn't know anything. Not where it is, not what day it is, not who it is, not what you told it yesterday. And `working_memory` grows on every pass; in a long session it will outgrow what the model can read. Something has to decide what the model sees. That's context.

**→ [Lesson 4: Context](../04-context/)**
