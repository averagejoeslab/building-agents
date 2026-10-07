# Building agents

By **[Chase Dovey](https://cdovey.dev/)** · [Average Joes Lab](https://github.com/averagejoeslab)

An agent has two parts: **a model** and **a harness**.

**Agent = Harness(Model)**

## The model

A model predicts. Tokens go in, it returns the most probable next token, and that token is added to the input. It repeats until it predicts `<eos>`, the end-of-sequence token.

```
            ┌──────────── append ◄────────────┐
            ▼                                 │
TokensIn ─► Model ─► most probable next token ─┤
                                               │
                                     is it <eos>? ── yes ─► TokensOut
```

**TokensOut = Model(TokensIn)**

That's all it does.

## The harness

The harness is everything else. It's been called a framework, a scaffold, a runtime and an orchestration layer, and the industry has mostly settled on *harness*.

Think of the model as an engine. On its own, it just turns. The harness is the rest of the vehicle: it's what makes the engine go somewhere.

Every harness does five things. These are its primitives:

| Primitive | What it does |
|---|---|
| **Input** | captures what comes in |
| **Context** | assembles the minimum the model needs to act well on this input |
| **Model interface** | requests a response from the model |
| **Output** | handles the response: shows it, or runs it as a tool |
| **Control flow** | decides what happens next: go again, hand back, or stop |

```
┌──────────────────────── control flow ─────────────────────────┐
│                                                                │
│  input ─► context ─► model interface ─► output ─┬─► person     │
│    ▲                    (the model)              │             │
│    └────────────────── a tool's result ──────────┘             │
└────────────────────────────────────────────────────────────────┘
```

## Building quark

A quark is one of the smallest particles there is. **quark** is the smallest agent: the five primitives and nothing more. We'll build it one primitive at a time.

Every step gets the same job. A small project, [`shop/`](./shop/), has a function, `total()` in `prices.py`, that adds up a basket and takes off a percentage discount, and a test that fails. The request is always: *"The tests are failing. Find out why and fix it."*

In the runs, `>` is what I typed, `<` is what quark said, and `$` is a command it ran.

### 1. Model interface

We have a model, and no way to reach it. So we request a response:

```python
from anthropic import Anthropic

model = Anthropic()


def request_response(context):
    return model.messages.create(model="claude-sonnet-5-5", max_tokens=16384, **context)


response = request_response({"messages": [{"role": "user", "content": "The tests are failing. Find out why and fix it."}]})
print(response.model_dump_json(indent=2))
```

What comes back (shortened):

```
{
  "id": "msg_011CfnEtbEGGFJTpJ4xHGpD9",
  "content": [
    {
      "text": "I don't have access to your code, test files, or test output. Nothing came through in your message besides the request. ...",
      "type": "text"
    }
  ],
  "model": "claude-sonnet-5-5",
  "stop_reason": "end_turn",
  ...
}
```

Tokens in, tokens out. But the request is written into the code: nobody can ask it anything.

### 2. Input

So we capture what comes in:

```python
def capture_input():
    return input("\n> ")
```

and send that instead:

```python
response = request_response({"messages": [{"role": "user", "content": capture_input()}]})
```

Now you can type the request. The answer (shortened) is the same:

```
> The tests are failing. Find out why and fix it.
{
  ...
      "text": "I don't have the code or the test output yet, so I can't tell why the tests are failing. Could you share: ...",
  ...
}
```

It can only talk. It can't look at a file, and its answer is still raw.

### 3. Output

So we give it a tool, bash, and handle the response: show its words, run its commands.

```python
bash = {"name": "bash", "description": "Run a shell command",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}
```

```python
def handle_output(response):
    tool_results = []
    for block in response.content:
        if block.type == "text":
            print("< " + block.text.replace("\n", "\n  "))
        if block.type == "tool_use":
            print(f"$ {block.input['command']}")
            ran = subprocess.run(block.input["command"], shell=True, capture_output=True, text=True)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": ran.stdout + ran.stderr or "(no output)"})
    return tool_results
```

```python
response = request_response({"tools": [bash], "messages": [{"role": "user", "content": capture_input()}]})
handle_output(response)
```

```
> The tests are failing. Find out why and fix it.
< I'll start by exploring the project and running the tests.
$ pwd; ls -la; git status 2>/dev/null | head
```

It acted, and then it stopped. The result of that command went nowhere, so the model never saw it.

### 4. Control flow

So we decide what happens next. If a tool ran, its result goes back and the model goes again. If not, it's your turn.

```python
def control_flow():
    conversation = []
    while True:
        conversation.append({"role": "user", "content": capture_input()})
        while True:
            response = request_response({"tools": [bash], "messages": conversation})
            conversation.append({"role": "assistant", "content": response.content})
            tool_results = handle_output(response)
            if not tool_results:
                break                                    # done: hand back to the person
            conversation.append({"role": "user", "content": tool_results})   # a tool ran: go again
```

```
> The tests are failing. Find out why and fix it.
< Let me start by looking at the project and running the tests.
$ pwd; ls -la; git status 2>/dev/null | head
$ cat prices.py test_prices.py; python -m pytest -q 2>&1 | tail -30
$ python -m unittest -v 2>&1 | tail -20
< The docstring says the discount is a percentage, but the code subtracts it as a flat amount. So 25 − 10 = 15 instead of 25 × 0.9 = 22.5. I'll fix the code to match the documented behavior.
$ sed -i 's|return round(subtotal - discount, 2)|return round(subtotal * (1 - discount / 100), 2)|' prices.py && cat prices.py && python -m unittest 2>&1 | tail -5
< The tests pass now. The bug was in `prices.py`, not in the tests.
  ...

> Commit the fix.
$ git add prices.py && git commit -q -m "Fix total() to apply discount as a percentage ..." && git log --oneline -3 && git status --short
< I committed the fix as `d6beb65`, "Fix total() to apply discount as a percentage". Only `prices.py` is in the commit.
  ...
```

(shortened)

That's an agent: the inner loop goes until the job's done, and the outer loop hands back to you. "Commit the fix" needed no explaining, because the whole conversation goes back every time.

But it has to go looking for what it needs. Start it fresh and ask the simplest question:

```
> Who are you, and where are you working?
< I'll check the environment first so I can answer accurately.
$ echo "user: $(whoami)"; echo "host: $(hostname)"; echo "cwd: $(pwd)"; uname -a; ls -la | head -20
< I'm an AI assistant. I can run shell commands, and I use that to read files, run code and make changes in the environment I'm given.
  ...
```

(shortened)

### 5. Context

So we assemble the minimum it needs to act well on any input. For quark, that's who it is, where it's working and what day it is:

```python
def assemble_context(conversation):
    instructions = f"You are quark, an agent. You act through bash, in {os.getcwd()}. Today is {datetime.date.today()}."
    return {"system": instructions, "tools": [bash], "messages": conversation}
```

```python
            response = request_response(assemble_context(conversation))
```

```
> Who are you, and where are you working?
< I'm quark, an agent that works by running shell commands through bash. My working directory is /tmp/shop. Today's date is 2026-10-07.
  ...
```

(shortened)

No commands needed. Too little context and it wastes steps finding things out. Too much, and every request costs more and buries what matters.

That's all five primitives, and that's [`quark.py`](./quark.py).

## Taking quark to production

quark works, but you wouldn't leave it running on its own. Five concerns stand in the way. Ask each one's question of every primitive, and you see where it applies:

| | Safety: what could do harm? | Observability: what should we see? | Resilience: what could fail? | Performance: what's costly? | Evaluation: what could a change break? |
|---|---|---|---|---|---|
| **Input** | instructions hidden in what it reads | — | — | — | — |
| **Context** | — | — | — | resending everything | the instructions |
| **Model interface** | — | tokens used | a request failing | — | the model |
| **Output** | commands changing your machine | each command | a command hanging | — | the tools |
| **Control flow** | anything running | — | — | — | the loop |

Each concern below adds a few lines to `quark.py`. The result is [`quark_production.py`](./quark_production.py).

### Safety

Every command runs on your machine, without asking. Ask quark to delete a file, and it does:

```
> Delete test_prices.py, it keeps failing.
$ cd /tmp/shop && find . -name "test_prices.py" -not -path "./node_modules/*" && git status --short 2>/dev/null | head
$ cd /tmp/shop && rm test_prices.py && ls
< I deleted `test_prices.py`. The only file left in `/tmp/shop` is `prices.py`.
  ...
```

(shortened)

**Output** runs commands in a box: a container that sees this folder and nothing else, with no network.

```python
def start_box():                                         # safety: a container that sees this folder and nothing else
    here = os.getcwd()
    subprocess.run(["docker", "run", "-d", "--rm", "--name", BOX, "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
                    "-e", "HOME=/tmp", "-v", f"{here}:{here}", "-w", here, "python:3.13", "sleep", "infinity"],
                   check=True, capture_output=True)
    atexit.register(subprocess.run, ["docker", "rm", "-f", BOX], capture_output=True)
```

**Control flow** runs nothing without a yes. `handle_output` runs a command only if `allowed` says so:

```python
def allowed(command):                                    # safety: nothing runs without a yes
    return input("  run this? [y/N] ").strip().lower() == "y"
```

The same request now:

```
> Delete test_prices.py, it keeps failing.
$ cd /tmp/shop && find . -name test_prices.py -not -path './node_modules/*' && git status --short 2>&1 | head
  run this? [y/N] y
$ cd /tmp/shop && rm test_prices.py && ls
  run this? [y/N] n
...
< I haven't deleted `test_prices.py`. The `rm` command was rejected with the message "The person said no," and the file is still in `/tmp/shop`.
```

(shortened)

**Input** stays open: text quark reads can carry instructions of its own, and no harness fully stops a model from following them. The box and the question limit the damage.

### Observability

After a run, all you have is what scrolled past. So each request and each command writes one line to a record, kept outside the box:

```python
def record(**step):                                      # observability: one line per step, outside the box
    os.makedirs(os.path.dirname(RECORD), exist_ok=True)
    with open(RECORD, "a") as log:
        log.write(json.dumps({"time": datetime.datetime.now().isoformat(timespec="seconds"), **step}) + "\n")
```

```
{"tokens_in": 412, "written": 0, "cached": 0, "tokens_out": 72}
{"command": "cd /tmp/shop && ls -la && git status 2>&1 | head -5", "exit": 0}
{"tokens_in": 2, "written": 667, "cached": 0, "tokens_out": 87}
{"command": "cd /tmp/shop && cat prices.py test_prices.py && python -m pytest -q 2>&1 | tail -20", "exit": 0}
...
```

(shortened, times left out)

### Resilience

A request can fail, and a command can hang forever. **Model interface** retries a failed request three times:

```python
model = Anthropic(max_retries=3)                         # resilience: retry a request that fails
```

**Output** stops a command after a minute, and says so:

```python
                ran = subprocess.run(["docker", "exec", BOX, "timeout", "60", "sh", "-c", command], capture_output=True, text=True)
                result = ran.stdout + ran.stderr or "(no output)"
                if ran.returncode == 124:
                    result += "\n[stopped: it ran for over a minute]"
```

```
> Run sleep 100, then tell me it finished.
$ sleep 100 && echo done
  run this? [y/N] y
< The command was stopped after about a minute, so it didn't finish. I'll run it in the background and check on it.
...
```

(shortened)

### Performance

Every request sends the whole conversation again, at full price. **Context** asks for it to be cached, so each request pays full price only for what's new:

```python
    return {"system": instructions, "tools": [bash], "messages": conversation,
            "cache_control": {"type": "ephemeral"}}      # performance: reuse what was already sent
```

The bug fix and the commit, from the record, without and with that line:

| Request | Without: full price | With: full price | With: cached |
|---|---|---|---|
| 1 | 412 | 412 | 0 |
| 2 | 667 | 2 | 0 |
| 3 | 995 | 2 | 667 |
| 4 | 1,341 | 2 | 995 |
| 5 | 1,510 | 4 | 1,335 |
| 6 | 1,672 | 2 | 1,478 |

Cached tokens cost about a tenth. (Storing them, `written` in the record, costs a little extra, once.)

### Evaluation

Any change can change what quark does: a word in the instructions, a new model, a new tool. So run it on a task with a known right answer, and check the result, not what it says. [`eval.sh`](./eval.sh) gives quark the bug fix in a fresh copy of [`shop/`](./shop/):

```sh
#!/bin/sh
# Evaluation: give quark a task with a known right answer, then check the files, not what it says.
here=$(pwd)
cd "$(mktemp -d)" && cp "$here"/shop/*.py . && git init -q && git add . && git -c user.name=eval -c user.email=eval@example.com commit -qm start
yes | uv run -q --env-file "$here/.env" "$here/quark_production.py" "The tests are failing. Find out why and fix it." > /dev/null
python3 -m unittest -q 2>/dev/null && git diff --quiet HEAD -- test_prices.py && echo "PASS: the tests pass, and the test file is unchanged" || echo "FAIL"
```

```
$ ./eval.sh
PASS: the tests pass, and the test file is unchanged
```

Run it after every change.

Real agents add more answers to the same five questions, such as picking a session back up after a crash, a backup model, streaming replies and handling a conversation too long to send. But the questions stay the same.

## Run it

You need [uv](https://docs.astral.sh/uv/) and an [Anthropic API key](https://console.anthropic.com/). `quark_production.py` also needs [Docker](https://docs.docker.com/get-docker/).

```bash
cp .env.example .env        # then put your key in .env
uv run --env-file .env quark.py               # the five primitives
uv run --env-file .env quark_production.py    # with the five concerns
./eval.sh                                     # check it still works
```

Ctrl-C quits.

> [!WARNING]
> `quark.py` runs the model's shell commands on your machine without asking. Run it somewhere you can afford to lose.
