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

<!-- The model interface section is Lesson 1's, unchanged: the response still streams, and nothing is done with the pieces yet. Two sections are new: input, and the description of the one tool. -->

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

# Output: output.py shows and runs (abridged)

```python
def show(event):                                         # output: text, shown as it's written
    if event.type == "text": print(event.text, end="", flush=True)
    if event.type == "content_block_stop" and event.content_block.type == "text": print()

output = call(show, max_tokens=16384, tools=tools, messages=[...]).content

for block in output:                                     # output: run tool requests
    if block.type == "tool_use":
        print(f"$ {block.input['cmd']}")
        done = subprocess.run(block.input["cmd"], shell=True, ...)
        print(done.stdout)
```

<!-- This is Lesson 1's harness with real output. The input is still Lesson 1's hardcoded question; the messages list is cut on the slide, and the subprocess line also merges stderr into stdout. -->

---

# Each block goes where it belongs

- **`tools`** is what output can do: a name, a description the model reads, a schema for arguments
- **`show()`**: `call(show, ...)` hands it each streamed piece; text is printed the moment it arrives
- **`output`** is now `call(...).content`, the whole response once it's done
- Its text has already been shown, so the loop only runs `tool_use` blocks; thinking goes nowhere
- `max_tokens` is 16384 from now on, so a response that thinks first has room to finish a tool request

<!-- You watch the words appear instead of waiting for the whole response, and when a text block ends, show ends the line. Every other piece, like thinking or a tool request being written, it lets pass. stderr=subprocess.STDOUT merges errors in, in the order they happened. With bash, anything you can do from a command line, the model can ask for. That's why the setup warns you to run it somewhere you can afford to lose. A response cut off mid-request would leave no cmd, and this code would crash. -->

---

# Run it: output runs the command

```bash
uv run lessons/02-input-and-output/output.py
```

```
$ ls -la
total 192
-rw-r--r--  1 root root 28138 Oct  6 20:31 README.md
drwxr-xr-x  6 root root  4096 Oct  5 19:49 lessons
-rw-r--r--  1 root root   246 Oct  6 03:33 pyproject.toml
```

One real run (shortened). The listing went to the screen, and nowhere else.

<!-- The model asked for ls -la, and output ran it. -->

---

# Together: quark.py (abridged)

```python
output = call(show, max_tokens=16384, tools=tools, messages=[...]).content

input = []
for block in output:                                     # output: run tool requests
    if block.type == "tool_use":
        print(f"$ {block.input['cmd']}")
        done = subprocess.run(block.input["cmd"], shell=True, ...)
        print(done.stdout)
        input.append({"type": "tool_result", ..., "content": ...})  # input: from the world
```

Before these lines, quark.py is input.py plus output.py's `show()`. Lesson 1's dump is gone.

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
301 README.md
```

- Same input as input.py, same `wc -l`. This time output ran it
- The model never sees the 301. It's sitting in `input`, and nothing sends it

<!-- The model didn't say anything before asking; sometimes it does. Run it with no input on the command line and it prompts you with > instead. -->

---

# Other things we could do

- **Input from a person:** command line, a prompt, a pipe, a chat app, a webhook, a schedule; text, images, files
- **Input from the world:** what a tool printed, its exit code, whether it failed
- **Output:** a terminal, a file, a chat message, a pull request; all at once or as produced
- **Tools:** one general tool or many routed by name; run here, in a container, remotely; one by one or all at once
- **A product:** [MCP](https://modelcontextprotocol.io) servers package tools behind one protocol, output you plug in

<!-- quark gathers input from a terminal and runs one tool on the same machine. Other harnesses hold more. MCP lets a harness run tools someone else built without writing them. -->

---

# A few worth picturing

- **A chat app as both ends:** messages come in from Telegram, words and results go back to the same chat
- **Tools routed by name:** `bash` and `read_file`; an unknown name gets an error back, not a crash
- **Every request at once:** three two-second commands take two seconds, not six
- **Don't run what was cut off:** if the response hit `max_tokens`, its last request may be half-written
- **Stop what hangs:** kill a command after 30 seconds; failures come back marked `is_error`

<!-- A chat app is for when the person isn't at your machine. Taking one message is input; answering message after message would be control flow. Narrow tools are easier for the model to use well and easier for you to limit. Each result still names the request it answers. -->

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
