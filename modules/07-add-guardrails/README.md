# Add guardrails

> **Harness component: safety constraints.** What the harness allows, what it asks the human about, what it refuses, and how long it's willing to run. The harness's policy layer.

Module 6 contained *where* the agent can do damage. Guardrails constrain *whether* it gets to act at all — and what happens when the world misbehaves around it. Three complementary controls, none of them about the sandbox:

1. **Approval gates** — pause before any destructive action and let the human say yes or no.
2. **Loop bounds** — cap how long a single user turn is allowed to run.
3. **Retry / backoff** — survive transient API errors without crashing.

By the end you have [`examples/safe_agent.py`](../../examples/safe_agent.py).

## Where each control sits

```mermaid
flowchart LR
    User[User] --input--> Loop[TAO loop<br/><i>bounded</i>]
    Loop --> LLM[LLM call<br/><i>retry/backoff</i>]
    LLM --> Loop
    Loop --> Gate{Dangerous<br/>tool?}
    Gate -- yes --> Approve[Approval<br/>gate]
    Approve --> Tool[Execute]
    Gate -- no --> Tool
    Tool --> Loop
    Loop --output--> User
```

The three controls live in three different places:

- The **LLM call** itself gets retry/backoff (handled by the SDK).
- The **TAO loop** gets an iteration cap.
- The **tool dispatch** gets an approval gate for dangerous tools.

Each is independent; together they form the policy layer around the work the model wants to do.

## Approval gates

The simplest control: before running a tool that mutates state, ask the human.

### Which tools are dangerous?

Of the six tools, three change state in ways the user cares about:

```python
DANGEROUS_TOOLS = {"write", "edit", "bash"}
```

`read`, `grep`, and `glob` are observation only — no approval needed, run them as fast as you can. `write`, `edit`, and `bash` actually change something — files, the filesystem, the world outside the agent. These get gated.

This is a deliberately small set. You could add more (e.g. a future `git_commit` tool, anything that hits an API), but the principle stays: gate the tools whose effects you can't undo.

### The interactive y/N prompt

```python
async def request_approval(name: str, input: dict) -> bool:
    print(f"\n⚠ Tool '{name}' wants to run with: {input}")
    answer = input_(f"approve? [y/N] ").strip().lower()
    return answer in ("y", "yes")


# alias to avoid colliding with input dict param name in execute_tool
input_ = input
```

The model proposed a tool call. Print the tool name and the arguments. Ask the user. Anything other than `y`/`yes` is a no.

The `input_ = input` alias is a small Python gotcha: the next function (`execute_tool`) takes an argument called `input` because that's what the Anthropic API calls the tool's input dict. Shadowing the builtin `input()` inside that scope would break the prompt; so we keep a top-level alias `input_` to use for stdin reading.

### Wiring the gate into `execute_tool`

```python
async def execute_tool(name: str, input: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"
    if name in DANGEROUS_TOOLS:
        if not await request_approval(name, input):
            return "error: user denied approval"
    try:
        result = await tool["fn"](**input)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        return f"error: {e}"
```

Two new lines compared to Module 5/6: if the tool is in `DANGEROUS_TOOLS`, prompt for approval first. If the user says no, return the string `"error: user denied approval"` instead of running the tool. The model sees that as a tool error and can adjust — explain itself, propose a different command, or just ask the user what they meant.

Returning the rejection *as a tool result* (rather than raising or aborting) is what keeps the agent loop alive. The model gets feedback, the conversation continues, the user stays in charge.

### Approval-aware dispatch

There's a subtle interaction with Module 5's parallel dispatch:

```python
def has_dangerous(tool_calls) -> bool:
    return any(c.name in DANGEROUS_TOOLS for c in tool_calls)
```

If the model emits five `read` calls and two `bash` calls in one turn, Module 5 would `asyncio.gather` all seven. With approvals, that means the user gets two interleaved y/N prompts in the middle of five concurrent `read` results streaming back — chaotic. So if *any* tool call in the batch is dangerous, fall back to serial execution:

```python
if has_dangerous(tool_calls):
    outputs = []
    for c in tool_calls:
        outputs.append(await execute_tool(c.name, c.input))
else:
    outputs = await asyncio.gather(*(execute_tool(c.name, c.input) for c in tool_calls))
```

Pure-read batches still run in parallel (fast). Anything with a dangerous call runs serially (so approvals are sequential and the user can reason about what they're approving). Cost is a few extra seconds per turn; benefit is the user always sees one prompt at a time.

### The tradeoff: always-ask vs. never-ask vs. remembered

The interactive y/N is the safest default but also the most annoying. Real harnesses pick from a small menu:

| Policy | When to use |
|---|---|
| **Always ask** | First-time use; high-stakes codebases; running unfamiliar agents. The default here. |
| **Never ask** | CI / automated runs where the agent is sandboxed enough that any action is acceptable, or where a separate review step gates the output. |
| **Remembered per session** | A "yes to this exact tool with this exact input, for this conversation" answer that caches approvals. Saves prompts on repeated calls but loses the per-call audit. |
| **Pattern-based allowlist** | "Yes to `bash` running anything matching `pytest *`; ask for everything else." More config than this module wants but useful in production. |

The module ships with always-ask. Switching policies is a one-function change in `request_approval`.

## Loop bounds

The other open-ended risk: a pathological turn that never produces a final answer. The model could:

- Loop on a tool error it can't fix (`bash`: command not found → tries again → fails → tries again).
- Get stuck in a "let me read one more file" spiral.
- Hit an actual logic bug in the harness and keep emitting tool calls forever.

Each iteration costs an LLM call (tokens, money, time). Without a bound, a stuck turn can eat your budget before you notice.

### The cap

```python
MAX_ITERATIONS = 30
```

30 is generous — most real tasks finish in 3–10 iterations. The cap is there to stop the worst case, not to constrain normal work.

### The for-else pattern

Module 5's TAO loop was `while True:` with a `break` when the model stopped requesting tools. Module 7 swaps the unbounded while for a bounded for:

```python
for iteration in range(MAX_ITERATIONS):
    messages, turn_start = enforce_budget(messages, turn_start, system)
    async with client.messages.stream(...) as stream:
        ...
    messages.append({"role": "assistant", "content": ...})

    tool_calls = [b for b in response.content if b.type == "tool_use"]
    if not tool_calls:
        break

    # dispatch and append tool_result ...
else:
    print(f"\n⚠ Reached {MAX_ITERATIONS} iterations without completion. Aborting turn.")
```

The Python `for ... else:` clause fires only when the loop exhausts without hitting `break`. If the model finishes naturally (`if not tool_calls: break`), the `else:` doesn't run. If we run out of iterations, the `else:` fires and prints a warning before the turn ends.

The agent stops cleanly. The user sees what happened. The conversation state is still saved. The next user input starts a fresh turn.

### What to feed back to the model

This module aborts the turn silently to the model — the loop just stops and the user sees the warning. A more sophisticated harness could push a synthetic tool_result back to the model on the last iteration, saying *"iteration cap reached; summarize what you've done and stop calling tools."* That gives the model one final shot to produce a clean answer. The trade-off: more code, occasional ugly output. Not in this module's baseline.

## Retry and backoff

Anthropic's API is reliable but not infallible. Real failure modes:

- **429 / 529** — rate limited. Surge in usage, retry after a short wait.
- **503** — temporary service unavailability.
- **Connection reset / timeout** — network blips, especially on long-running calls.

In Module 5/6, any of these crashes the agent mid-turn. The conversation state up to that point is lost (or worse, half-saved).

### Let the SDK handle it

The Anthropic Python SDK has retry and timeout built in. Configure them at client construction:

```python
client = AsyncAnthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=4,
    timeout=60.0,
)
```

- `max_retries=4` — retry transient errors up to 4 times before giving up.
- `timeout=60.0` — per-request timeout. If the API doesn't respond in 60 seconds, the request fails (and the retry logic catches it).

The SDK uses exponential backoff between retries: 0.5s, 1s, 2s, 4s. By the time the agent gives up, the network has had ~7.5 seconds to recover. Empirically that's enough for almost every transient blip.

### Why the harness doesn't retry tool errors

Tool errors are a different shape. When `bash` returns `"error: command not found"`, the right response isn't to retry the same command — it's to let the model see the error, think, and try something different. The model already does this naturally: it reads the `tool_result` string, decides to use a different tool or adjust the command, and continues.

So the rule is:

- **API errors → SDK retries with backoff.** The harness doesn't see them.
- **Tool errors → returned as `tool_result` strings.** The model handles them.
- **Hard failures (auth, quota exhausted, 4 retries used up) → exception propagates, agent crashes.** This is the right behaviour — you want to know.

## What the safe agent does, end to end

Compared to Module 6, three things changed in `main()`:

1. Client built with retries + timeout (top of the file, not in `main`).
2. The inner loop runs `for iteration in range(MAX_ITERATIONS):` instead of `while True:`, with an `else:` clause warning when the cap is hit.
3. Tool dispatch branches: serial if any call is dangerous, parallel otherwise.

Everything else from Module 6 is preserved unchanged: the sandboxed `bash`, the host-side `read`/`write`/`edit`/`grep`/`glob`, the persistence, budget eviction, semantic recall. Guardrails sit *around* the existing machinery — they don't replace any of it.

## Run it

The end state lives at [`examples/safe_agent.py`](../../examples/safe_agent.py).

Requires Docker to be running (carries forward the Module 6 sandbox).

```bash
cd examples
uv run safe_agent.py
```

Try a write call:

```
❯ create a file called notes.txt with the text "hello"

⏺ I'll create that file for you.

⚠ Tool 'write' wants to run with: {'path': 'notes.txt', 'content': 'hello'}
approve? [y/N]
```

Type `y` and it runs. Type `n` (or just Enter) and the model sees `"error: user denied approval"` as the tool result, typically responds with an acknowledgement, and waits for your next input.

Try a bash call:

```
❯ run pwd

⚠ Tool 'bash' wants to run with: {'cmd': 'pwd'}
approve? [y/N] y
/workspace
```

`pwd` runs in the sandbox container (Module 6), then prints `/workspace` — the bind-mount root, not your host path.

Try something that would loop:

Force the model into a stuck pattern with something like *"keep listing files until you find one named `does-not-exist-anywhere.zzz`"*. The agent will try, fail, try, fail. At iteration 30 the loop bound kicks in:

```
⚠ Reached 30 iterations without completion. Aborting turn.
```

State directory: `~/.safe-agent/` — same `messages.json` and `recall.json` shape as Module 6.

## What's missing

- **No visibility into what happened.** Approvals, retries, loop-bound trips — they all print to the terminal and disappear with the scrollback. If the agent did the wrong thing yesterday, there's no record of which tools ran, which were denied, which got retried.
- **No structured record of LLM calls.** Tokens consumed, latency, the actual content of each prompt and response — all ephemeral.
- **No way to feed any of this into evals.** You can't ask "did the agent take more tool calls than necessary?" if you didn't log the tool calls.

The harness needs to start watching itself. That's observability — the next module.

---

**Next:** [Module 8: Add observability](../08-add-observability/)
