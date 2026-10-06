---
marp: true
theme: default
paginate: true
header: "Lesson 2 · Input and output"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Input and output

### Building agents by building their harness
Lesson 2 of 4

---

# Where we left off

Lesson 1 had both ends stubbed:

- the input was a hardcoded string
- the output was a JSON dump

The model knew to run `ls` and couldn't.

---

# The model only takes and gives tokens

It can't read what you type.

It can't run a command.

Something on each side has to do that.

---

# Input

**How inputs are gathered.**

From a person: a task or a question.

From the world: what happened when a command ran.

The **afferent** pathway.

---

# Output

**How the model's outputs are handled.**

Shown to a person, or run as a tool.

The **efferent** pathway.

---

# Two primitives, taught together

Built independently, but they are two ends of one exchange.

What connects them is **tools**.

---

# The path so far

```
person/world → input → request → model interface
                                       ↓
person/world ← output ← response ←─────┘
```

---

# What is a tool?

The model can't act, **but it can ask**.

It emits a `tool_use` block: a name and arguments, in the shape the harness described.

---

# The model asks, the harness acts

1. The model asks for a tool
2. **Output** runs it
3. The result comes back as **input**

---

# Tools aren't strictly required

An agent can work without them.

Without tools, the only thing the model changes is **what a person reads**.

---

# Describing a tool

```python
tools = [{
  "name": "bash",
  "description": "Run shell command — the whole system is in reach",
  "input_schema": {
    "type": "object",
    "properties": {"cmd": {"type": "string"}},
    "required": ["cmd"],
  },
}]
```

---

# Three parts of a tool definition

- **name**: what the model calls it
- **description**: what the model reads to decide
- **input_schema**: a JSON schema for the arguments

Passed in the request as `tools=tools`.

---

# Input first: `input.py`

Real input, stub output.

```python
task = " ".join(sys.argv[1:]) or input("> ")
```

Replaces the hardcoded question.

---

# Run `input.py`

```bash
uv run lessons/02-input-and-output/input.py \
  "how many lines are in README.md?"
```

---

# The model asks

The response now has a `tool_use` block:

```json
{"type": "tool_use", "id": "toolu_...",
 "name": "bash", "input": {"cmd": "wc -l README.md"}}
```

`stop_reason` is `"tool_use"`: it stopped, waiting for a result.

---

# Nothing acted

The model asked. Nothing ran the command.

That is the missing half: **output**.

---

# Output next: `output.py`

Real output, hardcoded input: "What's in this directory?"

```python
for block in reply.content:
    ...
```

---

# Output: text blocks

```python
if block.type == "text":
    print(block.text)
```

Showing the model's words to a person.

---

# Output: tool requests

```python
if block.type == "tool_use":
    print(f"$ {block.input['cmd']}")
    done = subprocess.run(block.input["cmd"], shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    print(done.stdout)
```

Running the command. Thinking blocks are ignored.

---

# Why merge stderr

`stderr=subprocess.STDOUT`

Errors and output arrive **in order**, as one stream.

---

# Why `max_tokens` is 16384 from here on

Room for thinking.

A tool request cut off at the limit lacks `block.input['cmd']`.

That would crash.

---

# Warning: bash is everything

Anything on the command line can run.

**Run this somewhere disposable.**

Nothing asks before a command runs.

---

# Run `output.py`

The model asks for `ls -la`.

The listing prints.

---

# Together: `quark.py`

`input.py` plus `output.py`.

New: collect the tool results.

---

# The tool result

```python
results.append({
  "type": "tool_result",
  "tool_use_id": block.id,
  "content": done.stdout or f"(exit {done.returncode})",
})
```

This is **input from the world**.

---

# Matching result to request

`tool_use_id` names the request this answers.

A silent command still reports its exit code.

---

# Run `quark.py`

```bash
uv run lessons/02-input-and-output/quark.py \
  "how many lines are in README.md?"
```

```
$ wc -l README.md
71 README.md
```

---

# The key gap

`results` is built.

**Nothing sends it back.**

The model never sees the 71.

---

# Going further: input

- **Where** a person's input comes from: CLI args, prompt, pipe, chat app, webhook, schedule
- **What** it can be: text, images, files
- **Bad input**: re-ask on blank
- **From the world**: printed output, exit code, failure

---

# Going further: output

- **Where** it goes: terminal, file, chat message, PR
- **Reaching a person**: all at once or streamed
- **Which tools**: one general or many specific, routed by name
- **Where tools run**: this machine, container, remote, provider-hosted
- **How they run**: one at a time or concurrently

---

# Going further: when not to run

A tool request cut off at `max_tokens` is incomplete.

Half a command is worse than none.

Also handle hangs: time out, and report failure instead of crashing.

---

# MCP servers

They package tools behind one protocol.

That is **output you plug in**.

---

# A richer example: `input_output.py`

A Telegram bot.

Needs `TELEGRAM_BOT_TOKEN` from @BotFather.

Two tools: `bash` and `read_file`.

---

# Richer input and output: Telegram

```python
def telegram(method, **params): ...   # urllib POST
async def receive(): ...              # input: long-poll getUpdates
async def send(chat, text): ...       # output: sendMessage
```

`receive()` takes **one** message and stops. Repeating is control flow.

`send()` posts the words and each result back to the chat.

---

# Richer output: time limit

```python
except asyncio.TimeoutError:
    proc.kill()
    return "stopped after 30 seconds", True
```

A hung command is killed and reported as an error.

---

# Richer output: errors as results

`execute(block, cut_off)` always returns a tool result.

Marked `is_error`:
- cut off: "cut off before it was finished, so it was not run"
- unknown tool: "no tool named X"
- a file that can't be read, or a timeout

A non-zero exit code is added to the output.

---

# Richer output: concurrent tools

```python
results = await asyncio.gather(*(execute(b, ...) for b in calls))
```

(shortened)

Three 2-second tasks take **2 seconds**, not 6.

---

# Demo

One message asks for three things. (For the README's run, Telegram was a stand-in that prints each message.)

Three concurrent bash calls.

The model still never sees the results.

---

# What to take away

**Rule:** input gathers what goes to the model. Output handles what comes back. A tool is the model asking and the harness acting.

They never get the request to the model (model interface), decide when to call or send a result back (control flow), or decide how it's presented in the request (context).

---

# What's missing

The result never reaches the model.

We need to send it back and go again.

---

<!-- _class: title -->

# Next: Control flow

Lesson 3 closes the loop.
