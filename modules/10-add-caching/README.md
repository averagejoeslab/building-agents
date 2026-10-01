# Add caching

> **Harness component: performance.** A harness calls the model over and over with mostly the same input. Prompt caching lets it pay full price for the unchanging part once, then read it back at a fraction of the cost — but only if the harness keeps that part byte-for-byte identical.

After Module 9, every call sends the tool schema, a system prompt of roughly 2,000+ tokens (most of it quark's own source), and the conversation. Inside one turn the agent may call the model a dozen times. Nearly all of that prefix is identical from call to call.

## How prompt caching works

The API renders every request in a fixed order — **tools, then system, then messages** — and lets you mark a point in it with `cache_control: {"type": "ephemeral"}`. Everything *up to and including* that point becomes a cache entry. The next request that starts with exactly the same bytes reads that prefix from the cache instead of processing it again:

- A **cache write** costs about 1.25× the normal input price, once.
- A **cache read** costs about 0.1× — a tenth.
- An entry lives about **5 minutes**, refreshed every time it's hit.
- A prefix must be at least **1,024 tokens** (for Sonnet 4.5) to be cached at all. Shorter prefixes are silently not cached.

"Exactly the same bytes" is the whole game. Change one character anywhere in the prefix and everything after it misses.

## The checkpoint

[`examples/quark.py`](../../examples/quark.py) — and this is quark, byte for byte. Diff it against [`09_self_knowledge.py`](../../examples/09_self_knowledge.py) and exactly one line changes: the `system()` definition.

```python
def system(): return [{"type": "text", "text": f"# Self Model ... {mechanics()}\n```", "cache_control": {"type": "ephemeral"}}]
```

Two changes inside that line:

**1. The prompt becomes a cache-marked content block.** `system` can be a plain string or a list of content blocks; only a block can carry `cache_control`. Marking the end of the system prompt makes *tools + system* one cache entry. After the first call of a session, the tool schema and the whole system prompt — self model, memory recipe, embedded source — are read from cache at a tenth of the price.

**2. The clock is coarsened to the date.**

```markdown
**When:** 2026-10-01 — date only, kept stable so your mind's context can be cached; observe exact time via body: date
```

In Modules 5–9 the World Model said `**When:** 2026-10-01 13:30:42`. Mark *that* prompt for caching and nothing would ever hit: the timestamp changes every second, so the prompt is never the same twice. It's a classic *silent cache invalidator* — no error, just full price on every call. Now the prompt only carries the date, and it tells the model why — and where to get the exact time when it matters: its body. `date` is one bash call away. That's the harness's rules working together: code keeps the prompt stable, and the model handles what it can.

Everything else interpolated into the prompt is already stable for a session: `os.getcwd()` doesn't change, and `mechanics()` only changes if the source file is edited — in which case a cache miss is exactly right. The entry naturally expires during idle gaps and rolls over at midnight when the date changes.

The compaction call (Module 6) sends no `tools`, so its prefix is different from the main call's: it writes its own cache entry, used rarely.

Self-knowledge is also what makes the cache worth having. Before Module 9, the static prefix (tool schema plus a ~3,000-character prompt) sat close to the 1,024-token minimum. With quark's source embedded, it's comfortably above it — and it's the expensive part to re-send.

## Check that it's working

Every response's `usage` reports `cache_creation_input_tokens` and `cache_read_input_tokens`. From the second call of a session onward, `cache_read_input_tokens` should be well above zero. To see it, temporarily add a line after the stream:

```python
        print(f"[cache read: {saying.usage.cache_read_input_tokens} · written: {saying.usage.cache_creation_input_tokens}]")
```

If reads stay at zero across consecutive calls, something in the prefix is changing between calls.

## Going further

quark caches the tools and the system prompt. The conversation itself — which grows with every command in a turn — is re-sent at full price on every call. The API allows up to four breakpoints per request; putting a second one on the last block of `working_memory` would let each call read the previous call's conversation from cache too. It's a good first exercise in modifying quark: one helper, a few lines, and your harness, not mine.

---

## You've built quark

That's the whole harness. Look at it again — [`examples/quark.py`](../../examples/quark.py), 81 lines — and every line is something you've now built and can explain:

| Lines you added | Component | Module |
|---|---|---|
| The streamed call, iterated event by event | Model interface | 2 |
| `while True`, `working_memory`, chat vs one-shot | Control flow | 3 |
| `body`, the tool loop, `Popen` + drain, the cutoff guard | Body | 4 |
| `system()` — self, world, other selves, body operations | Self model | 5 |
| `drop`, turn boundaries, the summary call | Working memory | 6 |
| The memory section of the prompt | Long-term memory | 7 |
| `observe`, terminal modes, the three closures, `killpg` | Interrupts | 8 |
| `mechanics()` | Self-knowledge | 9 |
| `cache_control`, the date-only clock | Caching | 10 |

**Agent = Model + Harness.** You didn't touch the model. Everything quark can do that a raw model can't — act, remember, be stopped, know itself — came from the harness.

## Where to go next

- **Harden it.** quark trusts its model completely. A production harness would run the body in a sandbox (one tool means one thing to contain), ask before destructive commands, trace every call, and run an eval suite against every change. You now know exactly where each of those plugs into the loop.
- **Move it.** Bind the same loop to a different environment — a web socket, a chat app, a game. Only the input and output lines change.
- **Use it.** Point it at a codebase and build something. That's [agentic engineering](../../README.md#after-the-harness-agentic-engineering), the discipline that starts where this one ends.

Back to the [root README](../../README.md).
