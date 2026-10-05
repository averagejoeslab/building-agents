# Lesson 3: Control flow

> 🎥 **Video:** coming soon

Control flow is how information flows between the other four primitives. They all sit inside it: it decides what runs, in what order, and whether to go again.

How you arrange them decides what you've built. The same four pieces give you:

- **Run once.** Input, call, output, stop. That's Lesson 2.
- **A chat loop.** Call, show the response, hand back to the person, repeat. A chatbot.
- **An agent loop.** Call, and while the model asks for tools, run them, send the results back, and call again. Hand back when it stops asking.
- **A workflow.** Your code decides the steps: call the model to plan, then to write, then to check.

There's no correct one. They differ in who decides what happens next: in an agent loop, the model does; in a workflow, your code does.

Whatever the shape, control flow does two things. It **sequences** the other primitives, passing what one produced to the next. And it **terminates**: it decides when to stop, or when to hand back to a person. A loop with no clear way to end is a bill with no clear way to end.

## The worked example

Here's Lesson 2's input, model interface and output inside quark's loop. It's the whole of [`quark.py`](./quark.py):

```python
import subprocess, sys
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

chat = len(sys.argv) < 2
messages = [{"role": "user", "content": " ".join(sys.argv[1:]) or input("> ")}]

while True:
    reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=4096, tools=tools, messages=messages)

    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})

    messages.append({"role": "assistant", "content": reply.content})
    if results:
        messages.append({"role": "user", "content": results})
        continue
    if not chat or (task := input("\n> ")) == "/q":
        break
    messages.append({"role": "user", "content": task})
```

**`while True:`** means go again. Each pass is one call to the model.

**`messages.append(...)`** is how a result reaches the next call. Sending it back means putting it in the next request, and quark does that the simplest way: it appends the response and the results to `messages`, so each request carries everything so far. That growing list is the simplest form of context, working memory. Deciding what really goes in it is Lesson 4.

**`if results: ... continue`** is the agent loop. If the model asked for anything, the results go back and the loop calls again.

**No results** is termination. The model decides it's done by not asking for a tool. quark doesn't count steps or look for a magic word.

**`chat`** gives one loop two modes. With a task on the command line, quark runs until the model stops asking for tools, then exits. With no task, it's a chat: when the model's turn ends, it hands back to you with `> `, and `/q` quits.

Notice what the loop doesn't have: a step limit. quark trusts the model to finish. That's a choice, and if the model never stops asking, quark never stops.

## Run it

From the root of the repo:

```bash
uv run lessons/03-control-flow/quark.py "which lesson has the longest quark.py? answer in one sentence"
```

Here's one run:

```
$ find / -name quark.py 2>/dev/null | xargs wc -l 2>/dev/null | sort -n | tail -5
   18 /home/user/building-agents/lessons/02-input-and-output/quark.py
   29 /home/user/building-agents/lessons/03-control-flow/quark.py
   40 /home/user/building-agents/lessons/04-context/quark.py
   81 /home/user/quark/quark.py
  177 total

Lesson 04-context has the longest `quark.py` at 40 lines, in `/home/user/building-agents/lessons/04-context/quark.py`. A separate `/home/user/quark/quark.py` is longer at 81 lines, but it isn't inside a lesson.
```

That's two calls. The first asked for a command. Its result went back, and the second call answered from what it found. Run it with no task to chat with it instead.

## What to take away

**The rule:** control flow sequences the other four primitives and decides when to stop. Arranged differently, the same four pieces are a single call, a chatbot, an agent, or a workflow.

**What else control flow can be:** quark runs one agent loop with no limit, one command after another, but this primitive holds more in other harnesses.
- **Its shape.** A single call, a chat loop, an agent loop, a workflow, a planner that hands steps to an executor, agents that hand tasks to other agents, a loop that wakes on a message or a schedule.
- **When it stops.** When the model stops asking, after a number of steps, at a spending limit, when the model declines, when a person says stop.
- **Who it hands back to.** A person, another program, or no one: it runs until the task is done.
- **In what order things run.** Tool requests one after another, or at the same time.

It can be a product on its own. [LangGraph](https://github.com/langchain-ai/langgraph) is built around this primitive: you lay out the steps and the paths between them as a graph, and it runs them.

Here's control flow that does more of that, in [`control_flow.py`](./control_flow.py):

```python
import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS = 10

def run(block):
    done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return {"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"}

messages = [{"role": "user", "content": " ".join(sys.argv[1:]) or input("> ")}]

for step in range(1, MAX_STEPS + 1):
    reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=4096, tools=tools, messages=messages)
    messages.append({"role": "assistant", "content": reply.content})
    for block in reply.content:
        if block.type == "text": print(block.text)
    if reply.stop_reason == "refusal":
        print("[stopped: the model declined]"); break
    calls = [b for b in reply.content if b.type == "tool_use"]
    if not calls:
        print(f"[done in {step} steps]"); break
    print(f"[step {step}: running {len(calls)} command{'s at once' if len(calls) > 1 else ''}]")
    for c in calls: print(f"$ {c.input['cmd']}")
    with ThreadPoolExecutor() as pool:
        messages.append({"role": "user", "content": list(pool.map(run, calls))})
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
```

- **When it stops.** The loop runs at most `MAX_STEPS` calls. It also stops when the model is done, or when it declines with a `refusal`, and it says which.
- **In what order things run.** When the model asks for several commands in one response, they run at the same time instead of one after another.
- **Who it hands back to.** No one. There's no chat mode; it runs the task and exits.

Run it:

```bash
uv run lessons/03-control-flow/control_flow.py "what versions of python3, uv and git are installed? check all three at once, then answer in one line"
```

Here's one run:

```
[step 1: running 3 commands at once]
$ python3 --version 2>&1
$ uv --version 2>&1
$ git --version 2>&1
Python 3.13.14, uv 0.8.17 and git 2.43.0 are installed.
[done in 2 steps]
```

The model asked for three commands in one response, and they ran at the same time. With `MAX_STEPS` set to 1, the same harness stops before the model sees any result:

```
[step 1: running 1 command]
$ git --version
[stopped: hit the 1-step limit]
```

Notice what isn't on that list. Calling the model is the model interface. Bringing things in and carrying them out is input and output. What goes into each request, including that growing `messages` list, is context. Control flow only decides what runs, in what order, and when to stop.

**What's missing:** this is an agent, but it knows nothing. Not where it is, not what day it is, not who it is, not what you told it yesterday. And `messages` grows every pass; in a long session it will outgrow what the model can read. Something has to decide what the model sees. That's context.

**→ [Lesson 4: Context](../04-context/)**
