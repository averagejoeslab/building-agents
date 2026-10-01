# Add a body

> **Harness component: the tool / action layer.** Without tools the harness can only ferry text. With them the model can act on the world and observe the result — and the moment the model, not your code, decides what to do next, the chatbot becomes an agent.

quark has exactly one tool: **bash**. It calls that tool its *body* — the single means through which it acts and observes, the way a person uses one body both to chop wood and to speak. This module gives the Module 3 chatbot that body, and it's the module where the chatbot becomes an agent.

## Why one tool

Most harnesses ship a toolkit — `read`, `write`, `edit`, `grep`, `glob`, `bash`. quark ships one, deliberately:

- **bash already reaches everything.** Anything doable from a command line — any program, any language, any tool you install — is within reach. A `read` tool is `cat`; a `grep` tool is `grep`.
- **Know-how lives in the prompt, not in code.** The rule from the [README](../../README.md): *the model handles what it can; code handles what it must.* How to use bash well — compose pipes, escalate to `python -c`, keep outputs small — is something the model can be *taught* (Module 5). It doesn't need a function per skill.
- **One body means one thing to control.** Interrupts (Module 8) only have to know how to stop one kind of action. And if you sandbox the body, you've sandboxed everything the agent can do.

The cost is precision: a dedicated `edit` tool can enforce "replace exactly this string." With bash, the model writes the `sed` or heredoc itself. For an experienced model, that trade is worth it.

> [!WARNING]
> From this module on, the agent runs whatever bash the model writes — **immediately, with your privileges, no confirmation.** Run it in a container or a directory you can afford to lose. There is no stop button until Module 8; until then, Ctrl+C is your stop button.

## The checkpoint

[`examples/04_body.py`](../../examples/04_body.py):

```python
import subprocess, sys, os, select
from anthropic import Anthropic

client, MODEL, body = Anthropic(), "claude-sonnet-4-5", [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
chat, working_memory = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}]

while True:
    with client.messages.stream(model=MODEL, max_tokens=4096, tools=body, messages=working_memory) as stream:
        for ev in stream:
            if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
        saying = stream.current_message_snapshot
    print()
    working_memory.append({"role": "assistant", "content": saying.content})
    calls = [b for b in saying.content if b.type == "tool_use"]
    if not calls:
        if not chat or (u := next(filter(str.strip, iter(lambda: input("\n> "), None)))) == "/q": break
        working_memory.append({"role": "user", "content": u})
        continue
    results = []
    for c in calls:
        if "cmd" not in (c.input or {}) or (saying.stop_reason == "max_tokens" and c is calls[-1]):
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": "[your doing was cut off before it was fully formed — it never reached the world]"}); continue
        print(f"$ {c.input['cmd']}")
        doing = subprocess.Popen(c.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        chunks = []
        while doing.poll() is None:
            if select.select([doing.stdout], [], [], 0.05)[0]:
                if chunk := os.read(doing.stdout.fileno(), 65536): chunks.append(chunk)
                else: select.select([], [], [], 0.05)
        while select.select([doing.stdout], [], [], 0.1)[0] and (chunk := os.read(doing.stdout.fileno(), 65536)): chunks.append(chunk)
        out = b"".join(chunks).decode(errors="replace")
        if out: print(out, end="")
        results.append({"type": "tool_result", "tool_use_id": c.id, "content": out or f"(exit {doing.returncode})"})
    working_memory.append({"role": "user", "content": results})
```

## Defining the body

```python
body = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
```

A tool is a **name**, a **description**, and an **input schema** ([JSON Schema](https://json-schema.org/), the format the whole industry settled on). The model reads all three on every call to decide whether and how to use the tool. The description is short on purpose — "the whole system is in reach" is a nudge at the moment of decision; the real strategy comes from the system prompt in Module 5.

Passing `tools=body` to the stream is all it takes for the model to start asking to act. When it does, the response contains a `tool_use` block: an `id`, the tool `name`, and an `input` like `{"cmd": "ls -la"}`.

## One loop, not two

The usual way to write an agent is two nested loops: an outer one for the conversation, and an inner one that keeps calling the model while it asks for tools. quark has **one**:

```python
    calls = [b for b in saying.content if b.type == "tool_use"]
    if not calls:
        if not chat or (u := next(filter(str.strip, iter(lambda: input("\n> "), None)))) == "/q": break
        working_memory.append({"role": "user", "content": u})
        continue
```

Each pass of the loop is one model call. If the reply asks to act, quark acts, appends the results, and goes round again. Only when a reply asks for **no** actions is the turn over — and only then does the harness turn to the human for more input. That's the definition of an agent in one `if`: the model decides when the work is done, by stopping.

One loop means one place for every error path, one place to check for interrupts, and one place to manage the context window. You'll see all three land here in later modules.

## Acting: the conversation's invariants

Every `tool_use` the model emits must be answered by a `tool_result` with the same `tool_use_id`, in the very next user message. Miss one and the next API call is rejected. So the loop builds exactly one result per call, collects them all in `results`, and appends them as a single user message:

```python
    working_memory.append({"role": "user", "content": results})
```

Before running anything, there's a guard:

```python
        if "cmd" not in (c.input or {}) or (saying.stop_reason == "max_tokens" and c is calls[-1]):
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": "[your doing was cut off before it was fully formed — it never reached the world]"}); continue
```

**Never execute a truncated act.** If the response hit `max_tokens`, the last tool call may have been cut off mid-JSON. The SDK parses partial JSON leniently, so a truncated command can still come out *parseable* — imagine `rm -rf /tmp/build` cut off after `rm -rf /`. quark refuses to run it and answers with a placeholder that tells the model what happened. The same guard covers a call with no `cmd` at all. Either way the pairing invariant holds: the call still gets its result.

Notice the voice of that string: *your doing … never reached the world.* The harness talks to the model in the same vocabulary the system prompt will teach it (Module 5) — self, world, doing. That's rule 4 from the README, cognitive alignment.

## Running a command without wedging

The obvious way to run a command is `subprocess.run(cmd, capture_output=True)`. quark doesn't, because that blocks until the command finishes — and in Module 8 the harness needs to be able to stop a command partway. So quark starts the process and then watches it:

```python
        doing = subprocess.Popen(c.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
```

`shell=True` runs the string through `/bin/sh`, so pipes, redirects, and `&&` all work. `stderr=STDOUT` merges both streams into one pipe, so the model reads errors and output the way you would in a terminal.

```python
        chunks = []
        while doing.poll() is None:
            if select.select([doing.stdout], [], [], 0.05)[0]:
                if chunk := os.read(doing.stdout.fileno(), 65536): chunks.append(chunk)
                else: select.select([], [], [], 0.05)
```

While the process is alive, wake every 50ms and **drain the pipe** of whatever has arrived. This isn't optional. A pipe holds about 64KB; a child that writes more than that blocks until someone reads it. If the parent just waited for the child to exit, a command with a lot of output would hang forever — each side waiting on the other. Reading as it goes means output of any size flows through. (If the read returns nothing while the process is still alive, it closed its own stdout; the `else` sleeps 50ms instead of spinning.)

```python
        while select.select([doing.stdout], [], [], 0.1)[0] and (chunk := os.read(doing.stdout.fileno(), 65536)): chunks.append(chunk)
```

After the process exits, collect what's left — but only while more keeps arriving, giving up after 0.1s of silence. That bound matters: a command like `npm run dev &` starts a background process that inherits the pipe and can hold it open forever. An unbounded read would hang the agent until that server died.

```python
        out = b"".join(chunks).decode(errors="replace")
        if out: print(out, end="")
        results.append({"type": "tool_result", "tool_use_id": c.id, "content": out or f"(exit {doing.returncode})"})
```

Decode once, at the end, with `errors="replace"`, so a binary or malformed byte can't crash the turn. Print the output so the human sees what the body did. And if a command printed nothing, the model still gets a real observation: its exit code.

`select` is a POSIX call. It's why quark runs on macOS and Linux (and WSL), not native Windows.

## Run it

```bash
cd examples
uv run 04_body.py "what's the largest file in this directory?"
```

You'll see the model's narration, then a `$ ...` line for each command it runs, then the command's output, then the model's answer once it's done acting. In chat mode (`uv run 04_body.py`), each of your messages can set off any number of commands before the agent hands control back to you.

## What's missing

- **It doesn't know what it is.** No identity, no sense of where it's running or what time it is, no guidance on how to use its body well.
- **Its mind fills up.** A long session eventually exceeds the context window, the API rejects the call, and the program dies.
- **You can't stop it** except with Ctrl+C, which kills the whole agent.

Module 5 gives it a self model.

---

**Next:** [Module 5: Add a self model](../05-add-a-self-model/)
