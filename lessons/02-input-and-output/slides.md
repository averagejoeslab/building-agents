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

### A hands-on course in building agents by building their harness
Lesson 2

<!-- Welcome. This lesson makes both ends of the model call real: how inputs are gathered, and how outputs are handled. -->

---

# Where we left off: both ends were stubs

- Going in: a hardcoded question no one typed
- Coming out: a raw dump of the response
- The model said to run `ls`, and nothing could do it
- A model only takes tokens in and gives tokens out: it can't read what you type or run a command

<!-- Input and output are how the harness connects the model to everything else. This lesson makes each end real on its own, then puts them together. -->

---

# Two pathways around the call

```
person or world ─► input ─► request ─► model interface ─► response ─► output ─► person or world
```

- **Input** gathers inputs: from a person (a message, a question, a correction) or from the world (what happened when a command ran)
- **Output** handles the model's outputs: shown to a person, or run as a tool
- Input is afferent, carrying signals in; output is efferent, carrying actions out

<!-- They're built independently, but they're two ends of one exchange, so we teach them together. -->

---

# The model asks; the harness acts

- The exchange runs through **tools**
- The model can't act, but its response can include a **request** to use a tool: a name and arguments, in a shape the harness described
- Output runs the request; what happened comes back as input
- Without tools, the only thing a model can change is what a person reads

<!-- You don't strictly need tools to have an agent. A model that can only talk still takes things in and responds. But tools are how it reaches the world. -->

---

# Input: input.py adds read() (abridged)

```python
# ── input ───────────────────────────────────────────────────────────────────
def read(prompt):                                        # input: from a person
    while True:
        print(prompt, end="", flush=True)
        line = sys.stdin.readline()
        if not line: return "/q"                         # ...
        if line.strip(): return line.rstrip("\n")        # ...
        prompt = "> "
input = " ".join(sys.argv[1:]) or read("> ")
if input == "/q": sys.exit()
```

Comments cut. The output is still Lesson 1's stub: the whole response, dumped.

<!-- This is Lesson 1's harness with real input. input is the words on the command line, or a line typed at the prompt. -->

---

# Input is whatever comes in

- `input` isn't assumed to be a task or a question; it goes in as the `user` message
- `read()` prints a prompt and reads a line: the afferent pathway from a person
- Enter on an empty line gives a fresh `> `, as a terminal does; nothing is sent
- End of input (Ctrl-D) returns `/q`, so the harness can stop
- The new `# ── output: the one tool ──` section describes `bash` in the request; nothing can run it yet

<!-- The model interface section is Lesson 1's, unchanged. Two sections are new: input, and the description of the one tool. -->

---

# Run it: the model asks, nothing acts

```bash
uv run lessons/02-input-and-output/input.py "how many lines are in README.md?"
```

```json
      "input": {
        "cmd": "wc -l README.md"
      },
      "name": "bash",
      "type": "tool_use",
  "stop_reason": "tool_use",
```

One real run (shortened)

<!-- The input went in, and the model answered the only way it can: a tool_use block asking to run wc -l README.md. stop_reason tool_use means it stopped to wait for the result. The stub dumps that request to the screen, and nothing runs it. -->

---

# Output: output.py runs the request (abridged)

```python
output = call(max_tokens=16384, tools=tools, messages=[...]).content

for block in output:                                     # output: show text, run tool requests
    if block.type == "text":
        print(block.text)
    if block.type == "tool_use":
        print(f"$ {block.input['cmd']}")
        done = subprocess.run(block.input["cmd"], shell=True, ...)
        print(done.stdout)
```

The input is still Lesson 1's hardcoded question.

<!-- This is Lesson 1's harness with real output. The messages list is the same hardcoded question, and the subprocess line also merges stderr into stdout; I've cut both on the slide. -->

---

# Each block goes where it belongs

- **`tools`** is what output can do: a name, a description the model reads, a schema for arguments
- **`output`** is now `call(...).content`: a list of blocks
- A `text` block is printed; a `tool_use` block is run; thinking goes nowhere
- `stderr=subprocess.STDOUT` merges errors in, in the order they happened
- `max_tokens` is 16384 from now on, so a response that thinks first has room to finish a tool request

<!-- With bash, anything you can do from a command line, the model can ask for. That's why the setup warns you to run it somewhere you can afford to lose. A response cut off mid-request would leave no cmd, and this code would crash. -->

---

# Run it: output runs the command

```bash
uv run lessons/02-input-and-output/output.py
```

```
$ ls -la
total 156
-rw-r--r-- 1 root root 30846 Oct  6 05:44 README.md
drwxr-xr-x 6 root root  4096 Oct  5 19:49 lessons
-rw-r--r-- 1 root root   246 Oct  6 03:33 pyproject.toml
```

One real run (shortened). The listing went to the screen, and nowhere else.

<!-- The model asked for ls -la, and output ran it. -->

---

# Together: quark.py (abridged)

```python
output = call(max_tokens=16384, tools=tools, messages=[...]).content

input = []
for block in output:                                     # output: show text, run tool requests
    if block.type == "text":
        print(block.text)
    if block.type == "tool_use":
        print(f"$ {block.input['cmd']}")
        done = subprocess.run(block.input["cmd"], shell=True, ...)
        print(done.stdout)
        input.append({"type": "tool_result", ..., "content": ...})  # input: from the world
```

Before these lines, quark.py is input.py. Lesson 1's dump is gone.

<!-- quark.py is input.py and output.py in one file. The request carries input as the user message. And there's one piece neither file could have on its own: the last line. -->

---

# input = [] is input from the world

- What a tool printed is something the model should know about
- Each `tool_result` names the `tool_use_id` it answers
- A command that prints nothing still reports its exit code
- Same name as input from a person, on purpose: input is whatever comes in

<!-- That's the exchange: the model asks, output acts, input brings back what happened. -->

---

# Run it: the exchange, one way

```bash
uv run lessons/02-input-and-output/quark.py "how many lines are in README.md?"
```

```
$ wc -l README.md
333 README.md
```

- Same input as input.py, same `wc -l`. This time output ran it
- The model never sees the 333. It's sitting in `input`, and nothing sends it

<!-- The model didn't say anything before asking; sometimes it does. Run it with no input on the command line and it prompts you with > instead. -->

---

# What else input and output can be

- **Input from a person:** command line, a prompt, a pipe, a chat app, a webhook, a schedule; text, images, files
- **Input from the world:** what a tool printed, its exit code, whether it failed
- **Output:** a terminal, a file, a chat message, a pull request; all at once or as produced
- **Tools:** one general tool or many routed by name; run here, in a container, remotely; one by one or all at once
- **A product:** [MCP](https://modelcontextprotocol.io) servers package tools behind one protocol, output you plug in

<!-- quark gathers input from a terminal and runs one tool on the same machine. Other harnesses hold more: asking again for a blank message, not running a tool request that was cut off, stopping a tool that hangs. MCP lets a harness run tools someone else built without writing them. -->

---

# input_output.py: Telegram, tools at once (abridged)

```python
async def execute(block, cut_off):
    if cut_off:
        out, failed = "cut off before it was finished, so it was not run", True
    elif block.name not in executors:
        out, failed = f"no tool named {block.name}", True
    else:
        out, failed = await executors[block.name](block.input)
    return {"type": "tool_result", "tool_use_id": block.id, ...}
```

- `receive()` takes a Telegram message; `send()` posts back to the chat
- `executors` routes `bash` and `read_file` by name
- `asyncio.gather` runs every tool request at once

<!-- Three commands that each take two seconds finish in two seconds, not six. If the response hit max_tokens, its last tool request may be incomplete, so it isn't run. bash is stopped after 30 seconds, and failures come back with is_error set. -->

---

# One message, three tools, run together

Sent: "check the python3 version, the git version and the first line of pyproject.toml, all three at once"

```
[bot → telegram] → bash {"cmd": "python3 --version"}
Python 3.13.14
[bot → telegram] → bash {"cmd": "git --version"}
git version 2.43.0
[bot → telegram] → bash {"cmd": "head -n 1 pyproject.toml"}
[project]
```

One real run (shortened), Telegram swapped for a stand-in that prints each message; the model and tools were real

<!-- One message asked for three things, the model asked for three tools in one response, and the executor ran them together. As with quark.py, the model never sees the results. -->

---

# The rule

- **Input** gathers what goes to the model, from a person or from the world
- **Output** handles what comes back, shown to a person or run as a tool
- A tool is the model asking and the harness acting

<!-- That's the whole lesson in three lines. -->

---

# What they never do

- Getting the request there and the response back is the **model interface**
- When to call, and whether a result goes back around, is **control flow**
- How what input gathers is presented in the request is **context**
- Input only gathers; output only handles the response

<!-- Each primitive is defined by what it does and by what it never does. -->

---

# The path ends at output

- The model asked for `wc -l`, it ran, and the model never saw what it found
- Something has to send the result back to the start and decide to go again
- That's **control flow**

<!-- That's the next lesson. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Next: Control flow

### A hands-on course in building agents by building their harness
Lesson 3

<!-- Next lesson, we close the loop. -->
