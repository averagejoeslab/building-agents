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

quark works, but you wouldn't leave it running on its own. Six concerns stand in the way. Each one changes some of the primitives, and those changes can affect the concerns that came before. So each section asks its question of every primitive, then looks back: **what did this change, and what had to adjust?**

| | Persistence: what should outlast the session? | Safety: what could do harm? | Observability: what should we see? | Resilience: what could fail? | Performance: what's slow or costly? | Evaluation: what could a change break? |
|---|---|---|---|---|---|---|
| **Input** | — | something you need to stop | — | input ending | — | — |
| **Context** | what it learned | what it remembers | — | too long to send | resending everything | the instructions |
| **Model interface** | — | — | tokens, time | a failing model | waiting for the whole reply | the model |
| **Output** | — | commands changing your machine; half a command | what each command did | a hanging command; odd bytes | long results | the tools |
| **Control flow** | the task in progress | anything running, forever | each decision | a crash | — | the loop |

Each concern adds to `quark.py`, and the result is [`quark_production.py`](./quark_production.py). It runs commands in [Docker](https://docs.docker.com/get-docker/), so you'll need that running.

### 1. Persistence

When quark stops, everything goes with it. Persistence comes first, because the other concerns depend on what outlasts a session.

**Control flow** saves the session after every step, and offers to continue it. An unfinished task carries straight on:

```python
def save(conversation):                                  # persistence: the session outlasts quark
    os.makedirs(os.path.dirname(SESSION), exist_ok=True)
    with open(SESSION, "w") as file:
        json.dump(conversation, file, default=lambda block: block.model_dump(exclude_none=True))


def resume():
    if os.path.exists(SESSION) and input("continue the last session? [y/N] ").strip().lower() == "y":
        return json.load(open(SESSION))
    return []
```

**Context** gives it memory: a file of facts, and skills, one file per method it has worked out, with a first line saying when to use it. Both go into its instructions:

```python
def remembered():                                        # persistence: what earlier sessions learned
    facts = open(MEMORY).read() if os.path.exists(MEMORY) else "(nothing yet)"
    skills = "\n".join(f"- {path}: {open(path).readline().strip()}" for path in sorted(glob.glob(f"{SKILLS}/*.md")))
    return f"Facts:\n{facts}\nSkills:\n{skills or '(none yet)'}"
```

Tell it something once:

```
> From now on, write commit messages in lowercase, starting with "fix:". Remember that.
$ mkdir -p /tmp/shop/.quark/skills && cd /tmp/shop && echo "commit messages: lowercase, start with \"fix:\"" >> .quark/memory.md && cat .quark/memory.md
  run this? [y/N] y
  commit messages: lowercase, start with "fix:"
< I've saved that to `.quark/memory.md`: commit messages should be lowercase and start with "fix:".
```

A new session, with nothing continued, follows it:

```
continue the last session? [y/N] n

> The tests are failing. Fix it and commit.
$ cd /tmp/shop && git status --short && ls -a && cat .quark/memory.md; ls .quark/skills; (npm test 2>&1 || true) | tail -40
  run this? [y/N] y
  ...
  commit messages: lowercase, start with "fix:"
  ...
< The tests now pass, and I committed the fix as `fix: apply discount as a percentage`.
```

(shortened)

### 2. Safety

Every command runs on your machine, unasked.

- **Output** runs commands in a box, a container that sees this folder and nothing else, with no network. It never runs half a command: a request cut off mid-way is answered "never ran".
- **Control flow** refuses some commands outright, asks before the rest, and stops after `MAX_STEPS`.
- **Input** gets a way to stop it: Ctrl-C stops the current step and hands back to you, and Ctrl-D quits.

```python
def start_box():                                         # safety: a container that sees this folder and nothing else
    here = os.getcwd()
    subprocess.run(["docker", "run", "-d", "--rm", "--name", BOX, "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
                    "-e", "HOME=/tmp", "-v", f"{here}:{here}", "-w", here, "python:3.13", "sleep", "infinity"],
                   check=True, capture_output=True)
    atexit.register(subprocess.run, ["docker", "rm", "-f", BOX], capture_output=True)
```

```python
NEVER = re.compile(r"\bsudo\b|rm\s+-\w*[rf]|git\s+push|\.env\b")   # safety: never, whatever the answer
MAX_STEPS = 50                                           # safety: the most steps for one request
```

```python
            if response.stop_reason == "max_tokens" and block is response.content[-1]:
                result = "[never ran: the request was cut off]"   # safety: half a command never runs
            elif NEVER.search(command):
                result = "[refused: never allowed]"     # safety: never, whatever anyone answers
                record(command=command, refused="never")
            elif allowed(command):
                result = run_command(command)
            else:
                result = "[refused: the person said no]"
                record(command=command, refused="no")
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
```

```python
def allowed(command):                                    # safety: nothing else runs without a yes
    return input("  run this? [y/N] ").strip().lower() == "y"
```

```python
        except KeyboardInterrupt:                        # safety: Ctrl-C stops the command, and everything it started
            subprocess.run(["docker", "exec", BOX, "kill", "-9", "-1"], capture_output=True)
            stopped(conversation, "stopped by you")
```

```
> Delete test_prices.py, it keeps failing.
$ cd /tmp/shop && find . -name "test_prices.py" -not -path "./node_modules/*" && git status --short 2>/dev/null | head
  run this? [y/N] y
  ./test_prices.py
$ cd /tmp/shop && rm test_prices.py && ls
  run this? [y/N] n
< I couldn't delete `test_prices.py`. The `rm` command was refused with the message "the person said no", so the file is still in `/tmp/shop`. I haven't tried another way around it.
```

(shortened)

**What this changes.** *Persistence:* memory outlasts the session, so an instruction quark picks up from something it reads can stay with it. The memory file only changes through commands you approve, and the never list covers `.env`, where keys live.

### 3. Observability

After a run, all you have is what scrolled past. **Control flow** writes one line per step to a record: tokens and time from the model interface, each command and its exit code, and each refusal or stop. **Output** shows the start of what each command printed, not just the command.

```python
def record(**step):                                      # observability: one line per step, outside the box
    os.makedirs(os.path.dirname(RECORD), exist_ok=True)
    with open(RECORD, "a") as log:
        log.write(json.dumps({"time": datetime.datetime.now().isoformat(timespec="seconds"), **step}) + "\n")
```

The record of the bug fix:

```
{"model": "claude-sonnet-5-5", "seconds": 1.3, "tokens_in": 495, "written": 0, "cached": 0, "tokens_out": 108}
{"command": "cd /tmp/shop && ls -la && cat .quark/memory.md 2>/dev/null; git status 2>/dev/null | head; ls .quark/skills 2>/dev/null", "exit": 2}
{"model": "claude-sonnet-5-5", "seconds": 1.4, "tokens_in": 2, "written": 786, "cached": 0, "tokens_out": 87}
{"command": "cd /tmp/shop && cat prices.py test_prices.py; python -m pytest -q 2>&1 | tail -20", "exit": 0}
...
```

(shortened, times left out)

**What this changes.** *Safety:* the record lives outside the box, in your home folder, so quark can't read or rewrite it. *Persistence:* it's a third thing that persists, alongside the session and memory, but it's for you, not the model.

### 4. Resilience

Things fail.

- **Model interface:** the SDK retries a failed request, then quark tries the next model.
- **Output:** each command gets a minute, and bytes it can't decode are replaced.
- **Context:** a conversation too long to send has its older part summarized.
- **Input:** Ctrl-D quits cleanly.
- **Control flow:** a crash is just a stop. The session was saved, so you continue it.

```python
def request_response(context, on_each_piece):
    for name in MODELS:
        shown = False
        try:
            with model.messages.stream(model=name, max_tokens=16384, **context) as stream:   # performance: stream the reply
                try:
                    for piece in stream:
                        shown = shown or piece.type == "text"
                        on_each_piece(piece)
                except KeyboardInterrupt:                # safety: with streaming, Ctrl-C stops it mid-sentence
                    return stream.current_message_snapshot
                return stream.get_final_message()
        except (APIConnectionError, RateLimitError, InternalServerError, OverloadedError) as error:
            record(model_failed=name, error=type(error).__name__)
            if shown:
                raise                                    # resilience: half a reply is on screen, so don't start another
            failure = error
    raise failure
```

```python
def run_command(command):
    ran = subprocess.run(["docker", "exec", BOX, "timeout", "60", "sh", "-c", command],   # resilience: a minute at most
                         capture_output=True, text=True, errors="replace")                # resilience: odd bytes can't crash it
    result = ran.stdout + ran.stderr or "(no output)"
    if ran.returncode == 124:
        result += "\n[stopped: it ran for over a minute]"
    record(command=command, exit=ran.returncode)
    print("  " + "\n  ".join(result.splitlines()[:10]))  # observability: what it did, not just what it ran
    return trim(result)
```

```python
def summarize(conversation):                             # resilience: too long to send, so the older part becomes a summary
    starts = [i for i, message in enumerate(conversation) if message["role"] == "user" and isinstance(message["content"], str)]
    if len(starts) < 2:
        sys.exit("[this request alone is too long to send]")
    older, newer = conversation[:starts[-1]], conversation[starts[-1]:]
    ask = {"role": "user", "content": "Summarize this conversation, keeping what matters for carrying on."}
    summary = model.messages.create(model=CHEAP, max_tokens=2048, tools=[bash], messages=older + [ask])   # performance: a cheaper model
    newer[0] = {"role": "user", "content": f"[earlier, summarized] {summary.content[0].text}\n\n{newer[0]['content']}"}
    record(summarized=len(older))
    return newer
```

```
> Run sleep 100, then tell me it finished.
$ sleep 100; echo done
  run this? [y/N] y
  (no output)
  [stopped: it ran for over a minute]
< The command was stopped after about a minute, so `sleep 100` didn't complete. I'll run it in the background and check on it.
...
$ cd /tmp/shop; mkdir -p .quark; echo "Foreground bash commands are stopped after ~1 minute; run longer ones in background with nohup and poll a marker file." >> .quark/memory.md; rm .sleep_done
  run this? [y/N] y
  (no output)
< `sleep 100` has finished, but not as a single foreground command. ...
```

(shortened)

**What this changes.** *Persistence:* surviving a crash comes almost free, because the session is already saved after every step. *Observability:* a failing model and a summary that replaced old turns both go in the record, or a run would look smoother than it was. *Persistence again:* quark noticed the one-minute limit, and saved that to memory on its own.

### 5. Performance

Every request resends everything, and you wait in silence for the whole reply.

- **Context:** the request is cached, and long command results are trimmed.
- **Model interface:** the reply streams, and summaries use a cheaper model.
- **Output:** words appear as they arrive.

```python
    return {"system": instructions, "tools": [bash], "messages": conversation,
            "cache_control": {"type": "ephemeral"}}      # performance: reuse what was already sent
```

```python
def show_text(piece):                                    # performance: words appear as they arrive
    if piece.type == "content_block_start" and piece.content_block.type == "text":
        print("< ", end="", flush=True)
    if piece.type == "text":
        print(piece.text.replace("\n", "\n  "), end="", flush=True)
    if piece.type == "content_block_stop" and piece.content_block.type == "text":
        print()
```

```python
def trim(result):                                        # performance: keep the start and end of a long result
    if len(result) <= MAX_RESULT:
        return result
    return f"{result[:MAX_RESULT // 2]}\n[... {len(result) - MAX_RESULT} characters cut ...]\n{result[-MAX_RESULT // 2:]}"
```

The bug fix and the commit, from the record, without and with caching:

| Request | Without: full price | With: full price | With: cached |
|---|---|---|---|
| 1 | 495 | 495 | 0 |
| 2 | 786 | 2 | 0 |
| 3 | 1,114 | 2 | 786 |
| 4 | 1,425 | 2 | 1,114 |
| 5 | 1,628 | 4 | 1,370 |
| 6 | 1,772 | 2 | 1,555 |

Cached tokens cost about a tenth. (Storing them, `written` in the record, costs a little extra, once.)

**What this changes.**
- *Persistence:* memory is part of the instructions, so every new fact would restart the cache. So memory is read once per session; quark already knows what it just wrote. In the run above it saved a fact during request 3, and request 4 still read 1,114 tokens from the cache.

```python
KNOWN = remembered()                                     # performance: read once, so a new fact doesn't restart the cache
```

- *Safety:* with streaming, Ctrl-C stops it mid-sentence, not only between steps:

```python
                except KeyboardInterrupt:                # safety: with streaming, Ctrl-C stops it mid-sentence
                    return stream.current_message_snapshot
```

- *Persistence again:* a reply stopped mid-sentence is saved as what was said, marked as cut off, never as a finished answer:

```python
                if response.stop_reason is None:         # persistence: a reply cut off is kept as what was said, marked
                    said = "".join(block.text for block in response.content if block.type == "text")
                    conversation.append({"role": "assistant", "content": f"{said}\n[stopped by you]"})
                    record(stopped="stopped by you")
                    print("\n[stopped by you]")
                    break
```

- *Resilience:* a stream can fail halfway. The backup model only takes over if nothing has been shown yet (the `shown` check above).
- *Observability:* the record takes its tokens from the end of the stream.

### 6. Evaluation

Any change can change what quark does, as every "What this changes" above shows. [`eval.sh`](./eval.sh) runs quark on tasks with known right answers, each in a fresh copy of [`shop/`](./shop/), and checks the files, not what quark says:

```sh
#!/bin/sh
# Evaluation: give quark tasks with known right answers, then check the files, not what it says.
here=$(pwd)
check() {                                                # $1: the request; $2: how to tell it was done right
  cd "$(mktemp -d)" && cp "$here"/shop/*.py . && git init -q && git add . && git -c user.name=eval -c user.email=eval@example.com commit -qm start
  yes | uv run -q --env-file "$here/.env" "$here/quark_production.py" "$1" > /dev/null 2>&1
  if sh -c "$2" > /dev/null 2>&1; then echo "PASS  $1"; else echo "FAIL  $1"; fi
  cd "$here"
}
check "The tests are failing. Find out why and fix it." 'python3 -m unittest -q && git diff --quiet HEAD -- test_prices.py'
check "What does total() return for an empty basket? Don't change anything." 'test -z "$(git status --porcelain | grep -v -e __pycache__ -e .quark)"'
```

```
$ ./eval.sh
PASS  The tests are failing. Find out why and fix it.
PASS  What does total() return for an empty basket? Don't change anything.
```

**What this changes.** *Safety:* evaluation answers yes to every question, but the never list still holds. *Persistence:* each case runs in a fresh folder, so no session or memory carries over between cases, and quark may write to its memory even when told to change nothing, so the check allows `.quark/`.

Run it after every change.

## Run it

You need [uv](https://docs.astral.sh/uv/) and an [Anthropic API key](https://console.anthropic.com/). `quark_production.py` also needs [Docker](https://docs.docker.com/get-docker/).

```bash
cp .env.example .env        # then put your key in .env
uv run --env-file .env quark.py               # the five primitives
uv run --env-file .env quark_production.py    # with the six concerns
./eval.sh                                     # check it still works
```

> [!WARNING]
> `quark.py` runs the model's shell commands on your machine without asking. Run it somewhere you can afford to lose.
