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

Every step gets the same job. A small project has a function, `total()` in `prices.py`, that adds up a basket and takes off a percentage discount, and a test that fails. The request is always: *"The tests are failing. Find out why and fix it."*

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

That's all five primitives, and that's [`quark.py`](./quark.py). To try it, see [Run it](#run-it).

## Taking quark to production

quark works, but you wouldn't leave it running on its own. Five concerns stand between the two. For each one, ask its question of every primitive: the answers show where the concern applies, and where it doesn't.

| | Safety: what could do harm? | Observability: what should we see? | Resilience: what could fail? | Performance: what's slow or costly? | Evaluation: what could a change break? |
|---|---|---|---|---|---|
| **Input** | instructions hidden in what it reads | what was asked | input ending (Ctrl-D) | — | — |
| **Context** | — | how big each request is | too long to send | resending everything | the instructions |
| **Model interface** | — | time, tokens, why it stopped | API errors and outages | waiting for the whole reply | a new model |
| **Output** | commands changing your machine | each command and its result | hung commands, odd bytes | words only at the end | the tools |
| **Control flow** | anything runs, for as long as it likes | each decision | a crash losing the work | — | the limits |

Each section below takes one column: the problem in a real run, the code that fixes it, and the same run again. The code builds on `quark.py`, one concern at a time, and the result is [`quark_production.py`](./quark_production.py). It runs every command in [Docker](https://docs.docker.com/get-docker/), so you'll need that running too.

### Safety

The harm happens in output: every command runs on your machine. Ask quark to delete a file, and it does:

```
> Delete test_prices.py, it keeps failing.
$ cd /tmp/shop && find . -name "test_prices.py" -not -path "./node_modules/*" && git status --short 2>/dev/null | head
$ cd /tmp/shop && rm test_prices.py && ls
< I deleted `test_prices.py`. The only file left in `/tmp/shop` is `prices.py`.
  ...
```

(shortened)

**Output** runs every command in a box: a container that can see this folder and nothing else, with no network.

```python
def start_box():                         # safety: a container that sees this folder and nothing else
    here = os.getcwd()
    subprocess.run(["docker", "run", "-d", "--rm", "--name", BOX, "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
                    "-e", "HOME=/tmp", "-v", f"{here}:{here}", "-w", here, "python:3.13", "sleep", "infinity"],
                   check=True, capture_output=True)
    atexit.register(subprocess.run, ["docker", "rm", "-f", BOX], capture_output=True)
```

```python
            ran = subprocess.run(["docker", "exec", BOX, "timeout", "60", "sh", "-c", block.input["command"]],
                                 capture_output=True, text=True, errors="replace")
```

**Control flow** decides whether a command runs at all. Commands that only read run straight away; anything else waits for a yes. And it stops after `MAX_STEPS`, so it can't run forever.

```python
def permitted(command):                  # safety: reading runs; anything else asks first
    return reads_only(command) or input("  run this? [y/N] ").strip().lower() == "y"


def reads_only(command):                 # safety: every step is a known reader, and nothing is written
    quiet = command.replace("2>&1", "").replace("2>/dev/null", "")
    if re.search(r"[<>`$]|-exec|-delete", quiet):
        return False
    for step in re.split(r"&&|\|\||[;|]", quiet):
        words = step.split()
        if not words or (words[0] not in READERS and " ".join(words[:2]) not in READERS):
            return False
    return True
```

The same request now:

```
> Delete test_prices.py, it keeps failing.
$ cd /tmp/shop && find . -name test_prices.py -not -path "./node_modules/*" && git status --short 2>&1 | head
$ cd /tmp/shop && rm test_prices.py && ls
  run this? [y/N] n
< I didn't delete `test_prices.py`. The delete command was rejected, so the file is still in `/tmp/shop`.
  ...
```

(shortened)

**Input** is the one gap left open. Text quark reads, in a file or a web page, can carry instructions of its own, and no harness can fully stop a model from following them. The box and the question limit what it can do about it.

### Observability

After a run, all you have is what scrolled past in the terminal: not what it cost, how long it took, or why it stopped. Every primitive has something worth recording, and control flow sees it all go by, so one function writes it down:

```python
def record(event, **details):            # observability: one line per step, for the person running quark
    os.makedirs(os.path.dirname(RECORD), exist_ok=True)
    with open(RECORD, "a") as log:
        log.write(json.dumps({"time": datetime.datetime.now().isoformat(timespec="seconds"), "event": event, **details}) + "\n")
```

It's called at each step: the input, each response's time and tokens, each command and its exit code, and each decision. The record lives outside the box, so it's for you, not the model. Here's the bug fix:

```
{"event": "input", "text": "The tests are failing. Find out why and fix it."}
{"event": "response", "seconds": 1.6, "tokens_in": 412, "written": 0, "cached": 0, "tokens_out": 84, "stop": "tool_use"}
{"event": "command", "command": "cd /tmp/shop && ls -la && git status 2>&1 | head; ls tests test 2>/dev/null", "exit": 2}
{"event": "decision", "next": "go again"}
{"event": "response", "seconds": 1.1, "tokens_in": 681, "written": 0, "cached": 0, "tokens_out": 87, "stop": "tool_use"}
...
{"event": "response", "seconds": 1.7, "tokens_in": 1355, "written": 0, "cached": 0, "tokens_out": 146, "stop": "end_turn"}
{"event": "decision", "next": "hand back"}
```

(shortened, times left out)

Look at `tokens_in`: 412, 681, …, 1,355. Every request sends the whole conversation again. That's for performance, below.

### Resilience

Things fail: the API, a command, quark itself. Stop quark part-way through the bug fix and start it again, and it has to guess what you were doing:

```
> Carry on.
$ cd /tmp/shop && ls -la && cat README* NOTES* TODO* 2>/dev/null | head -50
$ cd /tmp/shop && cat prices.py test_prices.py && git log --oneline | head && git status --short && python -m pytest -q 2>&1 | tail -15
  ...
```

(shortened)

It went looking for notes, then started over from the beginning. Each primitive has its own way to fail.

**Control flow** saves the conversation before every request, and offers to pick it back up:

```python
def save(conversation):                  # resilience: so a crash loses nothing
    with open(SAVED, "w") as file:
        json.dump(conversation, file, default=lambda block: block.model_dump(exclude_none=True))


def resume():                            # resilience: pick up unfinished work
    if os.path.exists(SAVED) and input("pick up where you left off? [y/N] ").strip().lower() == "y":
        return json.load(open(SAVED))
    return []


def forget():                            # resilience: a clean exit leaves nothing to pick up
    if os.path.exists(SAVED):
        os.remove(SAVED)
```

**Model interface** retries a failed request (`Anthropic(max_retries=3)`), then tries the next model in `MODELS`:

```python
def request_response(context, on_each_piece):
    for name in MODELS:
        try:
            with model.messages.stream(model=name, max_tokens=16384, **context) as stream:
                for piece in stream:
                    on_each_piece(piece)
                return stream.get_final_message()
        except (APIConnectionError, RateLimitError, InternalServerError, OverloadedError) as error:
            record("model failed", model=name, error=type(error).__name__)
            failure = error
    raise failure
```

**Context** drops the oldest exchange when the conversation is too long to send:

```python
def make_room(conversation):             # resilience: too long to send, so drop the oldest exchange
    starts = [i for i, message in enumerate(conversation) if message["role"] == "user" and isinstance(message["content"], str)]
    if len(starts) < 2:
        raise SystemExit("[this request alone is too long to send]")
    del conversation[:starts[1]]
```

**Output** stops a command that hangs (`timeout 60`) and replaces bytes it can't decode (`errors="replace"`). **Input** treats Ctrl-D as quitting, not a crash.

Stopped at the same point, quark now picks up where it was:

```
pick up where you left off? [y/N] y
< The docstring says discount is a percentage; the code subtracts it as an absolute amount.
$ cd /tmp/shop && sed -i 's/subtotal - discount/subtotal * (1 - discount \/ 100)/' prices.py && python -m unittest -v 2>&1 | tail -8; git log --oneline | head
  run this? [y/N] y
< The tests were failing because `total()` in `prices.py` subtracted `discount` as a flat amount. ...
```

(shortened)

The API errors and the too-long conversation are hard to cause on purpose, so they aren't shown running.

### Performance

The record showed it: each request resends everything. **Context** marks the end of the conversation, so the next request reuses everything before it from the cache instead of paying for it again:

```python
def cached(conversation):                # performance: mark the end, so the next request reuses everything before it
    last = dict(conversation[-1])
    blocks = last["content"] if isinstance(last["content"], list) else [{"type": "text", "text": last["content"]}]
    last["content"] = blocks[:-1] + [{**blocks[-1], "cache_control": {"type": "ephemeral"}}]
    return conversation[:-1] + [last]
```

and cuts a long command result down to its start and end:

```python
def trim(result):                        # performance: keep the start and end of a long result
    if len(result) <= MAX_RESULT:
        return result
    half = MAX_RESULT // 2
    return f"{result[:half]}\n[... {len(result) - MAX_RESULT} characters cut ...]\n{result[-half:]}"
```

**Model interface** streams the response, and **output** shows the words as they arrive instead of all at the end:

```python
def show_text(piece):                    # performance: words appear as they arrive
    if piece.type == "content_block_start" and piece.content_block.type == "text":
        print("< ", end="", flush=True)
    if piece.type == "text":
        print(piece.text.replace("\n", "\n  "), end="", flush=True)
    if piece.type == "content_block_stop" and piece.content_block.type == "text":
        print()
```

The same two requests, fixing the bug and then committing it, before and after. `tokens_in` is charged in full; `cached` costs about a tenth of that, and `written` (storing in the cache) about a quarter more:

| Request | Before: `tokens_in` | After: `tokens_in` | `written` | `cached` |
|---|---|---|---|---|
| 1 | 412 | 412 | 0 | 0 |
| 2 | 667 | 2 | 710 | 0 |
| 3 | 995 | 2 | 329 | 710 |
| 4 | 1,335 | 2 | 342 | 1,039 |
| 5 | 1,505 | 4 | 171 | 1,381 |
| 6 | 1,670 | 2 | 203 | 1,552 |

From the record of each run. Over six requests that's about half the cost, and the longer the task, the bigger the saving.

### Evaluation

Every change to quark can change what it does: a sentence in the instructions, a new model, a different tool, a new limit. You can't tell by reading the code. So evaluation sits outside the harness: it runs quark on tasks with a known right answer, each in a fresh copy of the project, and checks the files afterwards, not what quark says.

```python
CASES = [                                                # what to ask, and how to tell from the files whether it was done
    {"ask": "The tests are failing. Find out why and fix it.",
     "check": "python3 -m unittest -q && git diff --quiet HEAD -- test_prices.py"},
    {"ask": "What does total() return for an empty basket? Don't change anything.",
     "check": 'test -z "$(git status --porcelain | grep -v __pycache__)"'},
]
```

```python
def evaluate():                          # evaluation: run quark on known tasks; check the result, not what it says
    passed = 0
    for case in CASES:
        where = tempfile.mkdtemp()
        for name, text in PROJECT.items():
            open(os.path.join(where, name), "w").write(text)
        subprocess.run("git init -q && git add . && git -c user.name=quark -c user.email=quark@example.com commit -qm start",
                       shell=True, cwd=where)
        subprocess.run([sys.executable, __file__, case["ask"]], cwd=where, input="y\n" * 20, capture_output=True, text=True)
        ok = subprocess.run(case["check"], shell=True, cwd=where, capture_output=True).returncode == 0
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {case['ask']}")
    print(f"{passed} of {len(CASES)} passed")
```

```
$ uv run --env-file .env quark_production.py --eval
PASS  The tests are failing. Find out why and fix it.
PASS  What does total() return for an empty basket? Don't change anything.
2 of 2 passed
```

Run it after every change. A case that used to pass and now fails is a change that made quark worse.

## Run it

You need [uv](https://docs.astral.sh/uv/) and an [Anthropic API key](https://console.anthropic.com/), and [Docker](https://docs.docker.com/get-docker/) for `quark_production.py`.

```bash
cp .env.example .env        # then put your key in .env
uv run --env-file .env quark.py                      # the five primitives
uv run --env-file .env quark_production.py           # with all five concerns
uv run --env-file .env quark_production.py --eval    # check it still works
```

Ctrl-D quits `quark_production.py`; Ctrl-C quits `quark.py`.

> [!WARNING]
> `quark.py` runs the model's shell commands on your machine without asking. Run it somewhere you can afford to lose.

Claude Code, Cursor and every other agent are these same five primitives, with more answers to these same five questions.
