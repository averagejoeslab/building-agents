# Add interrupts

> **Harness component: human control.** The human must be able to stop the agent at any moment — mid-sentence or mid-command — without killing it and without corrupting its mind. In quark that's one key: ESC.

Ctrl+C stops the agent by killing it: the process exits and `working_memory` is gone. What you actually want, most of the time, is to say *stop — not that*, and keep going. That's a harness problem with three parts:

1. **Noticing** — reading a keypress while the main thread is busy streaming or running a command.
2. **Stopping** — at whatever point the work is in: the model's reply or a running process tree.
3. **Closing out** — leaving `working_memory` valid for the next call, and telling the model what happened.

This module is the biggest diff in the curriculum (49 → 80 lines), because interruption touches every place the loop can be.

## The checkpoint

[`examples/08_interrupts.py`](../../examples/08_interrupts.py) is quark minus the last two components. Diff it against [`07_long_term_memory.py`](../../examples/07_long_term_memory.py) and every added line is one of the pieces below.

## Noticing: terminal modes and an observer thread

A terminal normally runs in **cooked** mode: it buffers a whole line and only hands it to the program when you press Enter, echoing as you type. That's what `input()` wants. But to catch a single ESC the moment it's pressed, the terminal needs **cbreak** mode: keys are delivered one at a time, unechoed. quark switches modes around the work phase.

```python
_attrs = termios.tcgetattr(sys.stdin); atexit.register(lambda: termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _attrs))
interrupt = threading.Event()
```

At startup, save the terminal's original (cooked) settings, and register an `atexit` hook to restore them however the program exits — a crash or Ctrl+C must never leave your shell in cbreak mode. Then create the one piece of state shared between threads: `interrupt`, an `Event` that's either set or not.

```python
def observe(stop):
    while not stop.is_set():
        if select.select([sys.stdin], [], [], 0.1)[0] and os.read(sys.stdin.fileno(), 1) == b"\x1b":
            if not select.select([sys.stdin], [], [], 0.02)[0]: interrupt.set(); return
            while select.select([sys.stdin], [], [], 0.01)[0]: os.read(sys.stdin.fileno(), 64)
```

`observe` is the loop's *observe* primitive made literal — the harness watching for input from another self. It runs in a background thread, checking stdin every 100ms:

- **`os.read(fd, 1)`, not `sys.stdin.read(1)`.** Python's text layer reads ahead into a buffer, which would hide bytes from the `select` peek below. Raw reads are byte-exact.
- **ESC vs. escape sequences.** The ESC key sends one byte, `\x1b`. But arrow keys and other special keys send *sequences that start with* `\x1b` (up arrow is `\x1b[A`). So after seeing `\x1b`, wait 20ms: if nothing follows, it was a real ESC — set `interrupt` and exit. If more bytes follow, it's a sequence — drain and ignore it. Stray arrow presses don't stop your task.
- Any other key typed during the work phase is read and discarded. ESC is the only thing the observer listens for; type your next message once the `>` prompt is back.

```python
    tty.setcbreak(sys.stdin); stop = threading.Event(); t = threading.Thread(target=observe, args=(stop,), daemon=True); t.start()
```

At the top of every pass of the loop: switch to cbreak, and start a fresh observer thread with its own `stop` event. A new thread per pass is the simplest way to *release* stdin when it's the human's turn to type — which happens in the no-calls branch and in `finally`:

```python
            stop.set(); t.join(timeout=0.2); termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _attrs); interrupt.clear()
```

```python
    finally:
        stop.set(); t.join(timeout=0.2); termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _attrs)
```

Signal the observer to stop, wait for it to exit (it notices within ~100ms), restore cooked mode. In the no-calls branch the flag is also cleared *after* the join, so an ESC pressed in the last instant of a turn can't leak into the next one as a phantom interrupt.

Why a thread and not `asyncio`? Because the rest of the harness stays plain, synchronous Python. The only concurrency quark needs is one loop reading one file descriptor and flipping one bit.

## Stopping and closing out: three places

The main thread checks `interrupt.is_set()` at its **yield points** — the moments it's between units of work. There are three, and each one has its own closure: the exact messages it appends so that `working_memory` stays valid.

### 1. While the model is speaking

```python
            for ev in stream:
                if interrupt.is_set(): break
```

Check before handling each event. `break` leaves the `with` block, which closes the connection; the server stops generating. This is why Module 2 iterated raw events and used `current_message_snapshot` — the snapshot is exactly what had arrived when we stopped.

```python
        if interrupt.is_set():
            if spoken := [b for b in saying.content if b.type != "text" or b.text]:
                working_memory.append({"role": "assistant", "content": spoken})
                if tu := [b for b in spoken if b.type == "tool_use"]:
                    working_memory.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b.id, "content": "[your doing never reached the world]"} for b in tu]})
            working_memory.append({"role": "user", "content": ESC_SAYING}); interrupt.clear(); continue
```

- **`spoken`** — the snapshot minus empty text blocks. A stream cut between a block's start and its first word leaves an empty text block, and the API rejects empty content.
- If anything was said, keep it — the model should know what it got out before being stopped.
- Any `tool_use` blocks in it never ran, but each still needs its paired result. Answer them: *your doing never reached the world*.
- Then tell the model what happened, in a message of its own: `ESC_SAYING = "[other self interrupted what you were saying — acknowledge]"`. On the next pass, the model acknowledges and yields back to you.

### 2. Between commands

```python
        for i, c in enumerate(calls):
            if interrupt.is_set():
                results += [{"type": "tool_result", "tool_use_id": calls[j].id, "content": "[your doing never reached the world]"} for j in range(i, len(calls))]; break
```

If the model asked for several commands and ESC lands between them, every remaining call gets a placeholder result and the loop stops. No call is left unanswered.

### 3. While a command is running

```python
            doing = subprocess.Popen(c.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            killed, chunks = False, []
            while doing.poll() is None:
                if interrupt.is_set():
                    try: os.killpg(doing.pid, 9)
                    except OSError: pass
                    killed = True; break
```

This is why Module 4 used `Popen` and a polling loop instead of `subprocess.run`: there's a moment every 50ms to check the flag.

- **`start_new_session=True`** puts the command in its own **process group**. `shell=True` means the process you started is `/bin/sh`, and the real work — every stage of a pipeline, every child — runs under it. Killing just the shell would leave `sleep 30 | cat` running.
- **`os.killpg(doing.pid, 9)`** sends SIGKILL to the whole group: the shell, pipeline stages, and grandchildren. The `except OSError` covers the race where the command exits just as you press ESC.

```python
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": (out + "\n[your doing stopped before done]") if killed else (out or f"(exit {doing.returncode})")})
            if killed:
                results += [{"type": "tool_result", "tool_use_id": calls[j].id, "content": "[your doing never reached the world]"} for j in range(i + 1, len(calls))]; break
```

The killed command's result is whatever output it produced, plus *your doing stopped before done*. Any calls after it get placeholders. Then, after the results are appended:

```python
        if interrupt.is_set(): working_memory.append({"role": "user", "content": ESC_DOING}); interrupt.clear()
```

`ESC_DOING = "[other self interrupted what you were doing — acknowledge]"`.

### And one place ESC is ignored

Compaction (Module 6) runs a single non-streamed call. It isn't interruptible — an ESC pressed during it is simply cleared when it finishes (`drop = 0; interrupt.clear(); continue`). Ctrl+C still works.

## The invariants

After every possible interrupt, `working_memory` ends in a state the API accepts:

| ESC during… | `working_memory` ends with |
|---|---|
| the model's reply | `assistant(partial)` · `user(placeholder results, if any tool calls)` · `user(ESC_SAYING)` |
| a running command | `assistant(tool calls)` · `user(real + partial + placeholder results)` · `user(ESC_DOING)` |
| compaction | the summary, as usual |

Two user messages in a row is fine — the API accepts it. And the interrupt notices are plain-string user messages, so they become new turn boundaries for compaction automatically.

Read the harness strings together and you'll hear three voices, all in the prompt's vocabulary: the **world** (*your doing never reached the world*, *stopped before done*), the **self** (*your prior working memory, summarized*), and **other selves** (*other self interrupted what you were saying*).

## Run it

```bash
cd examples
uv run 08_interrupts.py
> run sleep 30 | cat and then tell me when it's done
```

Press ESC while the `$ sleep 30 | cat` line is up. The command dies at once (check `ps` — no `sleep` survives), and the agent acknowledges the interrupt and hands control back. Try ESC while it's mid-sentence, too, and try the arrow keys during a long command — they're ignored.

## What's missing

The harness is now functionally complete. Two finishing components remain, and both are about the system prompt:

- **The model doesn't know how it works.** It can't explain what happens when you press ESC, or why its memory got summarized.
- **The prompt is re-billed in full on every call.**

Module 9 handles the first.

---

**Next:** [Module 9: Add self-knowledge](../09-add-self-knowledge/)
