# Lesson 2: Input and output

> 🎥 **Video:** coming soon

Input is how inputs are gathered. Output is how the model's outputs are handled: shown to a person, or run as a tool. By the end of this lesson you'll have [`agent.py`](./agent.py), 23 lines that take a task from you, call the model once, and run any command the model asks for.

## What they are

Input and output are two primitives, built independently. They're taught together because they're the two ends of one exchange: output is how the model reaches the world, and input is how the world reaches the model.

**Input** gathers what goes in, from two sources:

- **A person.** Someone types a message, asks a question, gives a task.
- **The world.** The result of something the harness did: a command's output, a file's contents, an error.

**Output** handles what comes out, to two destinations:

- **A person.** The model's words are shown to someone.
- **The world.** The model asks for a tool, and the harness runs it.

## Why a harness needs them

A model can only take in tokens and produce tokens. It can't read what you type, and it can't run a command. Without input, the only question it ever answers is one you hardcoded. Without output, the only thing it can change is what's printed on a screen.

That second point is what tools are for. The model can't act, but it can produce tokens that *ask* for an action: a tool name and arguments, in a shape the harness agreed on. The harness reads the request, runs it, and the result comes back as input. The model asks, the harness acts.

You don't strictly need tools to have an agent. A model that can only talk still perceives and responds. But most of what we want from an agent needs it to act.

## How they work

- **Input:** receive something, and put it in a form the model interface can send.
- **Output:** look at what came back, route each part to its destination, and capture what happened.

How you do each one is a choice. Where input comes from: a terminal, a chat app, a webhook, a file, a schedule. Where output goes. Which tools exist, and how many: one general tool or many specific ones. What a tool's result looks like when it fails or is cut off.

## Show: quark's input and output

Here's [`agent.py`](./agent.py). The model interface in the middle is the one from [Lesson 1](../01-model-interface/), now with `tools=body`. What's around it is new:

```python
import subprocess, sys
from anthropic import Anthropic

client, MODEL, body = Anthropic(), "claude-sonnet-4-5", [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
working_memory = [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}]

with client.messages.stream(model=MODEL, max_tokens=4096, tools=body, messages=working_memory) as stream:
    for ev in stream:
        if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
    saying = stream.current_message_snapshot
print()
working_memory.append({"role": "assistant", "content": saying.content})
calls = [b for b in saying.content if b.type == "tool_use"]
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

### Input from a person

```python
working_memory = [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}]
```

quark reads the task from the command line if you gave one. Otherwise it prompts you with `> `, and keeps prompting until you type something that isn't blank. A blank message would be a wasted call.

### The tool

```python
client, MODEL, body = Anthropic(), "claude-sonnet-4-5", [{"name": "bash", ...}]
```

A tool definition is a name, a description the model reads to decide when to use it, and a JSON schema for its arguments. quark calls the list `body`, because it's how quark acts on the world, and gives it exactly one tool: `bash`. Anything you can do from a command line, quark can do: read files, write files, run programs, install more tools. One general tool instead of twenty specific ones. The cost is that nothing narrows what the model can do, which is why the setup warns you to run this somewhere you can afford to lose.

### Output to a person and to the world

The words were already shown to the person while they streamed. What's left is output to the world:

```python
working_memory.append({"role": "assistant", "content": saying.content})
calls = [b for b in saying.content if b.type == "tool_use"]
```

The reply is kept, and every `tool_use` block in it is a request to run something. Each one has an `id` and an `input`. Then quark runs each request:

- **The cutoff guard.** If the model hit `max_tokens` while writing a command, the command is incomplete, and running half a command is worse than running none. So quark skips it and tells the model why. This is what `stop_reason` is for.
- **`print(f"$ {c.input['cmd']}")`.** The person sees what's about to run. Output goes to both destinations.
- **`stderr=subprocess.STDOUT`.** Errors and normal output arrive as one stream, in the order they happened. The model sees what you would have seen.
- **`out or f"(exit {doing.returncode})"`.** A command that prints nothing still tells the model something: whether it worked.

### Input from the world

```python
results.append({"type": "tool_result", "tool_use_id": c.id, "content": ...})
working_memory.append({"role": "user", "content": results})
```

Each result names the `tool_use_id` it answers, and all of them go back in one `user` message, which is the shape the model expects. This is input again, this time from the world.

> quark's own version reads command output in chunks instead of all at once, so pressing ESC can stop a command partway through. That's hardening, so it's left out here. What's above is the primitive.

## Run it

From the root of the repo:

```bash
uv run lessons/02-input-and-output/agent.py "what's in this directory?"
```

You'll see the model say what it's going to do, the command it asked for, and the command's output, something like:

```
I'll check what's in the current directory.
$ ls -la
total 24
drwxr-xr-x  7 you  staff  224 Oct  5 10:12 .
...
```

And then it stops. Run it without an argument and it will prompt you for the task instead.

## Recap

**The rule:** input puts the world into tokens; output puts tokens into the world. A tool is the model asking and the harness acting.

**What quark chose:** a task from the command line or a prompt, one `bash` tool that can reach the whole system, and command output returned exactly as it printed.

**What else would have worked:**
- **Many specific tools** (`read_file`, `write_file`, `search`). Easier to check and limit, more to build, and the model can only do what you anticipated.
- **A different input.** A chat app, an issue tracker, a webhook, a voice transcript.
- **A different output.** Write to a file, post a message, open a pull request.
- **A confirmation step.** Ask the person before each command runs.
- **Tools that run somewhere else.** A container, a remote machine, a tool the provider hosts.

**What's missing:** the result went into `working_memory`, and nobody sent it. The model asked for `ls`, `ls` ran, and the model never saw what it found. Something has to send the result back and decide to go again. That's control flow.

**→ [Lesson 3: Control flow](../03-control-flow/)**
