# Lesson 2: Input and output

> 🎥 **Video:** coming soon

A model only takes tokens in and gives tokens out. It can't read what you type, and it can't run a command. Input and output are how the harness connects it to everything else.

**Input** is how inputs are gathered: from a person, like a task or a question, or from the world, like what happened when a command ran. **Output** is how the model's outputs are handled: shown to a person, or run as a tool. Input is the harness's afferent pathway, carrying signals in. Output is its efferent pathway, carrying actions out.

They're built independently, but they're two ends of one exchange, so they're taught together. The exchange runs through tools. The model can't act, but it can ask: its response can include a request to use a tool, a name and arguments in a shape the harness described to it. Output runs the request, and what happened comes back as input. The model asks; the harness acts.

You don't strictly need tools to have an agent. A model that can only talk still takes things in and responds. But without tools, the only thing it can change is what a person reads.

## The worked example

Here's Lesson 1's call with quark's input and output around it. It's the whole of [`quark.py`](./quark.py):

```python
import subprocess, sys
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

messages = [{"role": "user", "content": " ".join(sys.argv[1:]) or input("> ")}]
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
```

**`tools`** is what quark's output can do: one tool, `bash`. Each tool has a name, a description the model reads to decide when to use it, and a schema for its arguments. The descriptions travel in the request so the model knows what it can ask for. With `bash`, anything you can do from a command line, quark can do, which is why the setup warns you to run it somewhere you can afford to lose.

**`messages = [...]`** is input from a person: the task from the command line, or typed at a `> ` prompt.

**`client.messages.create(..., tools=tools)`** is Lesson 1's model interface, with the tools added to the request.

**`for block in reply.content`** is output. The response is a list of blocks, and each one goes where it belongs: a `text` block is printed for the person, and a `tool_use` block is a request to run something. Thinking blocks go nowhere.

**`subprocess.run(...)`** runs the command. `stderr=subprocess.STDOUT` merges errors into the output, in the order they happened, so the model would see what you'd see. The command and what it printed go to the person too, so they can see what ran.

**`results`** is input from the world: what the command printed, in the shape the model reads. A `tool_result` names the `tool_use_id` it answers, and a command that prints nothing still reports its exit code.

## Run it

From the root of the repo:

```bash
uv run lessons/02-input-and-output/quark.py "what's in this directory?"
```

Here's one run:

```
$ ls -la
total 104
drwxr-xr-x 7 root root  4096 Oct  5 20:26 .
drwxr-xr-x 5 root root  4096 Oct  5 14:47 ..
-rw-r--r-- 1 root root   125 Oct  5 20:26 .env
-rw-r--r-- 1 root root    29 Oct  5 20:24 .env.example
drwxr-xr-x 8 root root  4096 Oct  5 21:13 .git
-rw-r--r-- 1 root root    41 Oct  5 20:24 .gitignore
drwxr-xr-x 4 root root  4096 Oct  5 19:52 .venv
-rw-r--r-- 1 root root  1071 Oct  5 14:47 LICENSE
-rw-r--r-- 1 root root  4691 Oct  5 20:24 README.md
drwxr-xr-x 2 root root  4096 Oct  5 19:53 assets
drwxr-xr-x 2 root root  4096 Oct  5 19:53 docs
drwxr-xr-x 6 root root  4096 Oct  5 19:49 lessons
-rw-r--r-- 1 root root   193 Oct  5 19:49 pyproject.toml
-rw-r--r-- 1 root root 48687 Oct  5 19:52 uv.lock
```

The model asked for `ls -la`, and quark ran it. This time the model didn't say anything before asking; sometimes it does. Run it without the task and it prompts you for one instead.

Notice what never happens: the model never sees the listing. It's sitting in `results`, and nothing sends it.

## What to take away

**The rule:** input gathers what goes to the model, from a person or from the world. Output handles what comes back, shown to a person or run as a tool. A tool is the model asking and the harness acting.

**What else input and output can be:** quark gathers one task from a terminal and runs one tool on the same machine, but these primitives hold more in other harnesses.

Input:
- **Where a person's input comes from.** Command-line arguments, a prompt, a pipe, a chat app, a webhook, a schedule.
- **What it can be.** Text, images, files.
- **What happens to bad input.** A blank message can be asked for again instead of sent.
- **What comes back from the world.** What a tool printed, its exit code, and whether it failed.

Output:
- **Where it goes.** A terminal, a file, a chat message, a pull request.
- **How it reaches a person.** All at once, or as it's produced.
- **Which tools exist.** One general tool, or many specific ones, each request routed by name.
- **Where tools run.** This machine, a container, a remote machine, or a tool the provider hosts.
- **When not to run.** A tool request the model was cut off in the middle of is incomplete, and running half a command is worse than running none.
- **What happens when a tool fails or hangs.** Stop it after a timeout, and report the failure instead of crashing.

Some of this is a product on its own. [MCP](https://modelcontextprotocol.io) servers package tools behind one protocol, so a harness can run tools someone else built without writing them. That part of MCP is output you plug in.

Here's input and output that do more of that, in [`input_output.py`](./input_output.py):

```python
import subprocess, sys, pathlib
from anthropic import Anthropic

client = Anthropic()
tools = [
    {"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}},
    {"name": "read_file", "description": "Read a text file", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
]

def gather():
    if len(sys.argv) > 1: return " ".join(sys.argv[1:])
    if not sys.stdin.isatty(): return sys.stdin.read()
    while not (task := input("> ").strip()): pass
    return task

def run(block):
    try:
        if block.name == "bash":
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            return done.stdout + (f"\n(exit {done.returncode})" if done.returncode else ""), False
        if block.name == "read_file":
            return pathlib.Path(block.input["path"]).read_text(), False
        return f"no tool named {block.name}", True
    except subprocess.TimeoutExpired:
        return "stopped after 30 seconds", True
    except OSError as e:
        return str(e), True

messages = [{"role": "user", "content": gather()}]
with client.messages.stream(model="claude-sonnet-5-5", max_tokens=4096, tools=tools, messages=messages) as stream:
    for text in stream.text_stream: print(text, end="", flush=True)
    reply = stream.get_final_message()
print()

results = []
for block in reply.content:
    if block.type != "tool_use": continue
    if reply.stop_reason == "max_tokens" and block is reply.content[-1]:
        results.append({"type": "tool_result", "tool_use_id": block.id, "content": "cut off before it was finished, so it was not run", "is_error": True}); continue
    print(f"→ {block.name} {block.input}")
    out, failed = run(block)
    print(out)
    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out, "is_error": failed})
```

- **Where a person's input comes from.** `gather()` takes the task from the command line, then from a pipe, then from a prompt that asks again if you type nothing.
- **Which tools exist.** Two, `bash` and `read_file`, and `run()` routes each request by its name. A request for a tool that doesn't exist gets an error back instead of crashing the harness.
- **How it reaches a person.** The text is printed as it's produced, using the streamed response from Lesson 1's `model_interface.py`.
- **When not to run.** If the response hit `max_tokens`, its last tool request may be incomplete, so it isn't run.
- **What happens when a tool fails or hangs.** `bash` stops after 30 seconds. Failures come back as results with `is_error` set, and a non-zero exit code is added to the output.

Run it with the task piped in:

```bash
echo "Which Python version does this project need? Check pyproject.toml." | uv run lessons/02-input-and-output/input_output.py
```

Here's one run:

```

→ read_file {'path': 'pyproject.toml'}
[project]
name = "harness-engineering"
version = "0.1.0"
description = "A hands-on course in building agents by building their harness."
requires-python = ">=3.13"
dependencies = ["anthropic"]
```

The task came in through the pipe, and the model used `read_file` instead of `bash`. The blank first line is where its text would have streamed; it didn't say anything before asking. As with `quark.py`, the answer is in `results`, and the model never sees it.

Notice what isn't on those lists. Calling the model is the model interface. Sending the result back and going again is control flow. Deciding what else the model sees is context. Input and output only bring things in and carry things out.

**What's missing:** the model asked for `ls`, `ls` ran, and the model never saw what it found. Something has to send the result back and decide to go again. That's control flow.

**→ [Lesson 3: Control flow](../03-control-flow/)**
