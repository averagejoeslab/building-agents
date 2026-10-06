# Lesson 2: Input and output

> 🎥 **Video:** coming soon

A model only takes tokens in and gives tokens out. It can't read what you type, and it can't run a command. Input and output are how the harness connects it to everything else.

**Input** is how inputs are gathered: from a person, like a message, a question or a correction, or from the world, like what happened when a command ran. **Output** is how the model's outputs are handled: shown to a person, or run as a tool. Input is the harness's afferent pathway, carrying signals in. Output is its efferent pathway, carrying actions out.

They're built independently, but they're two ends of one exchange, so they're taught together. The exchange runs through tools. The model can't act, but it can ask: its response can include a request to use a tool, a name and arguments in a shape the harness described to it. Output runs the request, and what happened comes back as input. The model asks; the harness acts.

You don't strictly need tools to have an agent. A model that can only talk still takes things in and responds. But without tools, the only thing it can change is what a person reads.

Here's where they sit around Lesson 1's call:

```
person or world ─► input ─► request ─► model interface ─► response ─► output ─► person or world
```

In Lesson 1, both ends were stubs: a hardcoded question going in, and a raw dump of the response coming out. This lesson makes each end real on its own, in a small file with nothing else in it: [`input.py`](./input.py) for input, [`output.py`](./output.py) for output. Then it puts them together, the way quark does.

## Input

Here's input with nothing around it: Lesson 1's call, with real input going in. The output is still Lesson 1's stub. It's the whole of [`input.py`](./input.py):

```python
import sys
from anthropic import Anthropic

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def call(each=lambda event: None, **request):            # model interface: the response streams back, and each piece goes to each()
    with client.messages.stream(model=MODEL, **request) as stream:
        for event in stream: each(event)
        return stream.get_final_message()

# ── output: the one tool ────────────────────────────────────────────────────
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

# ── input ───────────────────────────────────────────────────────────────────
def read(prompt):                                        # input: from a person
    while True:
        print(prompt, end="", flush=True)
        line = sys.stdin.readline()
        if not line: return "/q"                         # end of input (Ctrl-D): nothing more is coming
        if line.strip(): return line.rstrip("\n")        # Enter on an empty line: a fresh prompt, as in a terminal
        prompt = "> "
input = " ".join(sys.argv[1:]) or read("> ")
if input == "/q": sys.exit()

output = call(max_tokens=16384, tools=tools, messages=[{"role": "user", "content": input}])
print(output.model_dump_json(indent=2))
```

The model interface section is Lesson 1's, unchanged: the response still streams, and nothing is done with the pieces yet. Two sections are new.

**`# ── input ──`** gathers what goes to the model. `input` is whatever comes in: here, the words on the command line, or a line typed at the `> ` prompt. It isn't assumed to be a task or a question; it's just input, and it goes into the request as the `user` message. `read()` is the afferent pathway from a person: it prints a prompt and reads a line. Press Enter on an empty line and it gives you a fresh `> ` on the next line, as a terminal does, so you can make space as often as you like; nothing is sent. When the input ends (Ctrl-D) it returns `/q`, so the harness can stop.

**`# ── output: the one tool ──`** describes one tool, `bash`, and goes in the request so the model knows it can ask for it. Nothing here can run it yet. Running it is output, which is still the stub: `output` is the whole response, dumped.

From the root of the repo, give it input that needs a tool:

```bash
uv run lessons/02-input-and-output/input.py "how many lines are in README.md?"
```

Here's one run:

```json
{
  "id": "msg_011CfmciMBCLmSLo5sPPnQDJ",
  "container": null,
  "content": [
    {
      "id": "toolu_01HvC7GjvCdrykj9h3xuPkh7",
      "caller": {
        "type": "direct"
      },
      "input": {
        "cmd": "wc -l README.md"
      },
      "name": "bash",
      "type": "tool_use",
      "toolset_name": null
    }
  ],
  "diagnostics": null,
  "model": "claude-sonnet-5-5",
  "role": "assistant",
  "stop_details": null,
  "stop_reason": "tool_use",
  "stop_sequence": null,
  "type": "message",
  "usage": {
    "cache_creation": {
      "ephemeral_1h_input_tokens": 0,
      "ephemeral_5m_input_tokens": 0
    },
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "inference_geo": "global",
    "input_tokens": 382,
    "output_tokens": 54,
    "output_tokens_details": {
      "thinking_tokens": 0
    },
    "server_tool_use": null,
    "service_tier": "standard"
  }
}
```

The input went in, and the model answered it the only way it can: with a `tool_use` block asking to run `wc -l README.md`, and a `stop_reason` of `tool_use`, which means it stopped to wait for the result. The output stub dumps that request to the screen, and nothing runs it. The model asked; nothing acted.

## Output

Here's output with nothing around it: Lesson 1's call, with real output coming out. The input is still Lesson 1's hardcoded question. It's the whole of [`output.py`](./output.py):

```python
import subprocess
from anthropic import Anthropic

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def call(each=lambda event: None, **request):            # model interface: the response streams back, and each piece goes to each()
    with client.messages.stream(model=MODEL, **request) as stream:
        for event in stream: each(event)
        return stream.get_final_message()

# ── output: the one tool ────────────────────────────────────────────────────
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

def show(event):                                         # output: text, shown as it's written
    if event.type == "text": print(event.text, end="", flush=True)
    if event.type == "content_block_stop" and event.content_block.type == "text": print()

output = call(show, max_tokens=16384, tools=tools, messages=[{"role": "user", "content": "What's in this directory?"}]).content

for block in output:                                     # output: run tool requests
    if block.type == "tool_use":
        print(f"$ {block.input['cmd']}")
        done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        print(done.stdout)
```

**`tools`** is what output can do. Each tool has a name, a description the model reads to decide when to use it, and a schema for its arguments. The descriptions travel in the request, `tools=tools`, so the model knows what it can ask for. With `bash`, anything you can do from a command line, the model can ask for, which is why the setup warns you to run it somewhere you can afford to lose.

**`show()`** is output that shows text as it's written. Lesson 1's `call()` hands each piece of the streaming response to `each()`; here `call(show, ...)` makes that `show`. Each piece of text is printed the moment it arrives, so you watch the words appear instead of waiting for the whole response, and when a text block ends, `show()` ends the line. Every other piece, like thinking or a tool request being written, it lets pass.

**`output`** is now the content of the response, `call(...).content`: a list of blocks, the whole response once it's done. Its text has already been shown, so **`for block in output`** only looks for `tool_use` blocks: requests to run something. Thinking blocks go nowhere. `max_tokens` stays at Lesson 1's 16384, to leave room for the model to think before it asks: a response cut off in the middle of a tool request would leave `block.input` without a `cmd`, and this code would crash. quark checks for that in Lesson 8.

**`subprocess.run(...)`** runs the command. `stderr=subprocess.STDOUT` merges errors into the output, in the order they happened. `errors="replace"` turns any bytes that aren't valid text into `�`, so a command that prints half a character can't crash the harness. The command and what it printed go to the person, so they can see what ran.

From the root of the repo:

```bash
uv run lessons/02-input-and-output/output.py
```

Here's one run:

```
$ ls -la
total 192
drwxr-xr-x 11 root root  4096 Oct  6 20:31 .
drwxr-xr-x  5 root root  4096 Oct  5 14:47 ..
-rw-r--r--  1 root root   125 Oct  6 20:27 .env
-rw-r--r--  1 root root   104 Oct  5 22:09 .env.example
drwxr-xr-x  8 root root  4096 Oct  6 20:31 .git
-rw-r--r--  1 root root   113 Oct  6 03:58 .gitignore
drwxr-xr-x  5 root root  4096 Oct  6 20:31 .quark
drwxr-xr-x  4 root root  4096 Oct  5 19:52 .venv
-rw-r--r--  1 root root 21995 Oct  6 19:22 AGENTS.md
-rw-r--r--  1 root root   835 Oct  6 05:44 CITATION.cff
-rw-r--r--  1 root root   316 Oct  6 16:54 CLAUDE.md
-rw-r--r--  1 root root  1086 Oct  6 03:32 LICENSE
-rw-r--r--  1 root root 20045 Oct  6 03:32 LICENSE-CONTENT
-rw-r--r--  1 root root 28138 Oct  6 20:31 README.md
drwxr-xr-x  2 root root  4096 Oct  5 19:53 assets
drwxr-xr-x  3 root root  4096 Oct  5 23:03 docs
drwxr-xr-x  6 root root  4096 Oct  5 19:49 lessons
drwxr-xr-x  4 root root  4096 Oct  6 19:23 paper
drwxr-xr-x  8 root root  4096 Oct  6 18:00 production
-rw-r--r--  1 root root   246 Oct  6 03:33 pyproject.toml
drwxr-xr-x  2 root root  4096 Oct  6 18:34 tools
-rw-r--r--  1 root root 48687 Oct  5 19:52 uv.lock
```

The model asked for `ls -la`, and output ran it. The listing went to the screen, and nowhere else.

## Together

Here's how quark does it: [`input.py`](./input.py) and [`output.py`](./output.py) in one file, input's `read()` and `input` going in, output's tool and handling coming out, plus the one piece that joins them. It's the whole of [`quark.py`](./quark.py):

```python
import subprocess, sys
from anthropic import Anthropic

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def call(each=lambda event: None, **request):            # model interface: the response streams back, and each piece goes to each()
    with client.messages.stream(model=MODEL, **request) as stream:
        for event in stream: each(event)
        return stream.get_final_message()

# ── output: the one tool ────────────────────────────────────────────────────
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

def show(event):                                         # output: text, shown as it's written
    if event.type == "text": print(event.text, end="", flush=True)
    if event.type == "content_block_stop" and event.content_block.type == "text": print()

# ── input ───────────────────────────────────────────────────────────────────
def read(prompt):                                        # input: from a person
    while True:
        print(prompt, end="", flush=True)
        line = sys.stdin.readline()
        if not line: return "/q"                         # end of input (Ctrl-D): nothing more is coming
        if line.strip(): return line.rstrip("\n")        # Enter on an empty line: a fresh prompt, as in a terminal
        prompt = "> "
input = " ".join(sys.argv[1:]) or read("> ")
if input == "/q": sys.exit()

output = call(show, max_tokens=16384, tools=tools, messages=[{"role": "user", "content": input}]).content

input = []
for block in output:                                     # output: run tool requests
    if block.type == "tool_use":
        print(f"$ {block.input['cmd']}")
        done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        print(done.stdout)
        input.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})  # input: from the world
```

Lesson 1's dump is gone, because output now handles the response. And there's one piece neither file could have on its own:

**`input = []`** is input again, this time from the world. Once output runs a tool, what the tool printed is something the model should know about. Each `tool_result` puts it in the shape the model reads, naming the `tool_use_id` it answers, and a command that prints nothing still reports its exit code. It's the same name as the input from a person, on purpose: input is whatever comes in, from a person or from the world. That's the exchange: the model asks, output acts, input brings back what happened.

### Run it

From the root of the repo:

```bash
uv run lessons/02-input-and-output/quark.py "how many lines are in README.md?"
```

Here's one run:

```
$ wc -l README.md
301 README.md
```

It's the same input as `input.py`, and the model asked for the same `wc -l README.md`. This time output ran it. The model didn't say anything before asking; sometimes it does. Run it with no input on the command line and it prompts you with `> ` instead.

(README.md has grown since this run, so you'll see a bigger number.)

Notice what never happens: the model never sees the 301. It's sitting in `input`, and nothing sends it.

## Other things we could do

quark gathers input from a terminal and runs one tool on the same machine. Input and output can hold a lot more than that in other harnesses.

Input:
- **Where a person's input comes from.** Command-line arguments, a prompt, a pipe, a chat app, a webhook, a schedule.
- **What it can be.** Text, images, files.
- **What happens to bad input.** A blank message can be asked for again instead of sent.
- **What comes back from the world.** What a tool printed, its exit code, and whether it failed.

Output:
- **Where it goes.** A terminal, a file, a chat message, a pull request.
- **How it reaches a person.** All at once, or as it's produced, the way `show()` does it.
- **Which tools exist.** One general tool, or many specific ones, each request routed by name.
- **Where tools run.** This machine, a container, a remote machine, or a tool the provider hosts.
- **How tool requests run.** One after another, or all at the same time.
- **When not to run.** A tool request the model was cut off in the middle of is incomplete, and running half a command is worse than running none.
- **What happens when a tool fails or hangs.** Stop it after a timeout, and report the failure instead of crashing.

Some of this is a product on its own. [MCP](https://modelcontextprotocol.io) servers package tools behind one protocol, so a harness can run tools someone else built without writing them. That part of MCP is output you plug in.

A few of these are worth picturing in a real harness.

**A chat app as both ends.** Swap the terminal for a Telegram bot and nothing else about the model changes. Input asks Telegram for new messages and waits until one arrives, then hands back its text and which chat it came from. Output posts the model's words, and each tool's result, back to that same chat. You'd want this when the person isn't sitting at your machine: they message the agent from their phone. Taking one message is still input; answering message after message would be control flow.

**Several tools, routed by name.** Instead of one `bash` that can do anything, you could give the model a `bash` and a `read_file`, and keep a table from each tool's name to the code that runs it. A request for a tool that isn't in the table gets an error back instead of crashing the harness. Narrow tools are easier for the model to use well and easier for you to limit.

**Every request at once.** A response can ask for more than one tool. Run them one after another and three commands that each take two seconds take six. Start them all together and wait for all of them, with something like `asyncio.gather`, and they take two. Each result still has to name the request it answers.

**A request that was cut off.** If the response hit `max_tokens`, its last tool request may be half-written. Output can check `stop_reason == "max_tokens"` and send back "cut off before it was finished, so it was not run" instead of running it.

**A tool that hangs or fails.** A command that never ends would hang the harness forever. Output can stop it after, say, 30 seconds and say so. And a failure, a timeout, a missing file, a non-zero exit code, can come back as a result marked `is_error`, so the model knows it didn't work.

## What to take away

**The rule:** input gathers what goes to the model, from a person or from the world. Output handles what comes back, shown to a person or run as a tool. A tool is the model asking and the harness acting.

Notice what input and output never do. Getting the request to the model and the response back is the model interface. When to call, and whether a result goes back around, is control flow. How what input gathers is presented in the request is context. Input only gathers what goes in, from a person or the world, and output only handles the response, showing it to a person or running a tool.

**What's missing:** the model asked for `wc -l`, it ran, and the model never saw what it found. The path ends at output. Something has to send the result back to the start and decide to go again. That's control flow.

**→ [Lesson 3: Control flow](../03-control-flow/)**
