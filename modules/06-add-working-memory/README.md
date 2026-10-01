# Add working memory

> **Harness component: context management.** The context window is the model's mind, and it's finite. The harness decides what happens when it fills. quark's answer is reactive: wait for the API to say the mind is full, then drop the oldest turns and summarize what's left.

Every call sends all of `working_memory`, and every turn makes it longer. Eventually the conversation no longer fits in the model's context window, and the API rejects the call with `400 prompt is too long`. In the Module 5 checkpoint that exception ends the program. This module catches it and recovers — without losing the thread of the work.

## Two ways to manage a full mind

**Proactive:** count tokens before every call, and trim the conversation to fit a budget. This needs a tokenizer (or an extra API call to count), a budget formula, and care not to split a tool call from its result.

**Reactive:** send the call anyway, and only when the API rejects it, compact. No tokenizer, no estimate — the API's verdict is exact by definition. Most turns cost nothing extra, and the rare overflow is handled by one path.

quark is reactive. It's less code, and it never guesses wrong.

## The checkpoint

[`examples/06_working_memory.py`](../../examples/06_working_memory.py) wraps the body of the loop in `try`, adds a compaction branch at the top, and imports `BadRequestError`:

```python
chat, working_memory, drop = len(sys.argv) < 2, [{"role": "user", "content": next(...)}], 0

while True:
    try:
        if drop > 0:
            turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
            if drop > len(turns): break
            msgs = working_memory[turns[drop]:] if drop < len(turns) else ([working_memory[turns[-1]]] if turns else working_memory)
            while True:
                try:
                    if s := next((b.text for b in client.messages.create(model=MODEL, max_tokens=2048, system=system(), messages=msgs + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}]).content if b.text.strip()), None): break
                except BadRequestError: raise
                except Exception: select.select([], [], [], 1)
            working_memory = [{"role": "user", "content": f"[your prior working memory, summarized] {s}"}]; drop = 0; continue
        # ... the Module 5 turn: stream, act, append — unchanged ...
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
```

The prompt's Mind line gains three words too: *"your context window — where thinking happens. **Summarized when full.**"* The model should know its mind works this way, so a summary appearing at the top of the conversation isn't a surprise.

## Catching the overflow

```python
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
```

Only one kind of `400` is recoverable this way. Any other bad request is a real bug and is re-raised. For an overflow, the harness doesn't fix anything right here — it just bumps a counter, `drop`, and lets the loop come round. The top of the next pass sees `drop > 0` and compacts. `drop` is how many of the oldest turns to drop before summarizing.

## Turn boundaries

```python
            turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
```

A **turn** starts at every user message whose content is a plain string — something the human typed (or, from Module 8, an interrupt notice). Tool results are user messages too, but their content is a *list* of blocks, so they're not boundaries.

This is what makes slicing safe. Cut `working_memory` at a turn boundary and every `tool_use` stays with its `tool_result`: a pair is either entirely in the slice or entirely out. Cut anywhere else and you could keep a result whose call was dropped, which the API rejects.

```python
            msgs = working_memory[turns[drop]:] if drop < len(turns) else ([working_memory[turns[-1]]] if turns else working_memory)
```

Drop the oldest `drop` turns. If that would drop everything, fall back to just the latest user message — the smallest valid conversation there is. And if even that is too long (`drop > len(turns)`), there's nothing left to try, so the loop ends.

## The summary call

```python
                    if s := next((b.text for b in client.messages.create(model=MODEL, max_tokens=2048, system=system(), messages=msgs + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}]).content if b.text.strip()), None): break
```

Ask the model itself to summarize what's left, with the same system prompt, so it summarizes *as quark*. This call uses `create()`, not `stream()`: it's short, and nobody needs to watch it. The `next(... if b.text.strip())` takes the first non-empty text block; if the model returns nothing usable, `s` is `None` and the loop tries again.

```python
                except BadRequestError: raise
                except Exception: select.select([], [], [], 1)
```

The retry loop treats errors in two ways. A `BadRequestError` means even this slice is too long — re-raise it, the outer `except` bumps `drop`, and the next pass slices more aggressively. Anything else (a network blip, an overloaded server) waits a second and retries. (`select.select([], [], [], 1)` is a one-second sleep that needs no extra import.) Because it catches `Exception`, not everything, Ctrl+C still gets through.

```python
            working_memory = [{"role": "user", "content": f"[your prior working memory, summarized] {s}"}]; drop = 0; continue
```

Replace the whole mind with one message: the gist, labeled in the self-to-self voice. Reset `drop`, and loop. The next call carries on from the summary.

## The state machine

| Pass | `drop` | What happens |
|---|---|---|
| 1 | 0 | Normal call → `prompt is too long` → `drop = 1` |
| 2 | 1 | Drop the oldest turn, summarize the rest → `working_memory = [gist]`, `drop = 0` |
| 3 | 0 | Normal call, now on the summary |

If the summary call itself overflows, `drop` climbs to 2, 3, … and each pass drops one more turn, down to the single latest user message.

One consequence worth knowing: the message that triggered the overflow is *inside* what gets summarized. After compaction, the model responds to the gist, which includes your last request — it doesn't see that request on its own any more.

## Run it

```bash
cd examples
uv run 06_working_memory.py
```

Overflowing a 200K-token window by hand takes a while. To watch compaction happen, have the agent read something enormous into its mind — for example, ask it to `cat` a large log file several times — and watch `[your prior working memory, summarized]` take over.

## What's missing

- **It forgets everything when it exits.** Working memory is volatile by design. Nothing survives a restart.

Module 7 gives it a memory that does.

---

**Next:** [Module 7: Add long-term memory](../07-add-long-term-memory/)
