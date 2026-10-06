---
marp: true
theme: default
paginate: true
header: "Lesson 9 · Performance"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Performance

### A hands-on course in building agents by building their harness
Lesson 9

---

# A run that finishes can still cost too much

- Lesson 8 made the agent keep going when something fails
- But ten minutes and ten dollars is a run you think twice about starting
- Over a long task two things add up: **the time you wait** and **the tokens you pay for**

<!-- Start from where Lesson 8 left us: the agent is robust now. Robust isn't the same as something you'd happily run all day. -->

---

# Time and tokens come from the same place

| Primitive | Where the time and tokens go |
|---|---|
| **Context** | what the request holds, resent on every pass |
| **Model interface** | which model a kind of request goes to |
| **Output** | waiting on commands to finish |

Streaming isn't new: `call()` has streamed every response since Lesson 1.

<!-- Performance is how fast the agent responds and how much each task costs. It's a few small mechanisms, spread over three primitives; control flow, input and the sandbox are left as they are. Streaming is the biggest thing for how fast an agent feels, and quark already does it. This lesson is about what's left: the tokens resent on every call, the tokens that didn't need sending, the model a plain job goes to, and the commands waiting on each other. -->

---

# The cost of a task is everything resent

- Every pass of the loop sends the **whole** request again: tools, instructions, every message
- Twenty steps means reading the same opening twenty times
- **Prompt caching:** the request is a prefix, read in a fixed order
- Mark where the remembering ends with `cache_control`; a call that starts with the same tokens only reads the new end
- A cache read costs a tenth of normal input; a write, a quarter more; it lasts five minutes since last use

<!-- Nothing is remembered on the model's side between calls. The API can remember what it worked out for the start of a request, though, and pick up from there if the next request begins with exactly the same tokens. -->

---

# A cache has three catches

- **The match has to be exact.** One changed character early and everything after it is new. That's why Lesson 4's prompt has the date, not the time
- **There's a minimum.** 512 to 4,096 tokens depending on the model; quark's system prompt is about nine thousand tokens
- **It belongs to one model.** Switch models and you start again

The system prompt has carried a mark since Lesson 4. New here: a second mark on the **last message**.

<!-- Anything that changes goes at the end, never at the start. A prefix under the minimum isn't cached, and nothing tells you. With the second mark, each call pays full price only for what's new: the last response and the last result. -->

---

# Send less, and wait together

- **Trim:** cap what one tool result may add, keeping the start and the end
- **Small jobs to the small model:** compaction always goes to a faster, cheaper one
- **Run together:** several tool requests in one response run at the same time
- Results still go back in order, each with its id; the guard's questions come first, one at a time
- One ESC has to stop all of them, not just the first

<!-- A whole file in working memory is resent on every call, cached or not. Which model a kind of request goes to is a fixed setting, like max_tokens, so it belongs to the model interface; deciding per task while running is routing, and that's control flow. The model asked for those commands together before seeing any result, so it has already decided none needs another's answer. -->

---

# Model interface: a list of models (abridged)

```python
MODELS, FAST = ["claude-sonnet-5-5", "claude-opus-5-5"], ["claude-haiku-4-5"]
class Down(Exception): pass
def call(each=lambda event: None, models=MODELS, **request):
    for model in models:
```

Only compaction asks for the small model:

```python
    summary = call(models=FAST, max_tokens=2048, system=system(), messages=keep + [...])
```

<!-- The rest of call() is Lesson 8's: the same stream, the same stop on ESC, the same retries. There's one model in FAST, so there's no backup for the summary: if the small model is down, call() raises Down as it would for the main call, and the work so far is in the episode. -->

---

# Context: trim, and cache the end (abridged)

```python
MAX_RESULT = 20_000
def trim(text):
    if len(text) <= MAX_RESULT: return text
    return text[:MAX_RESULT // 2] + f"\n[... {len(text) - MAX_RESULT} characters cut ...]\n" + ...

def cached(working_memory):
    last = working_memory[-1]
    blocks = [{"type": "text", "text": last["content"]}] if isinstance(...) else list(last["content"])
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return working_memory[:-1] + [{"role": last["role"], "content": blocks}]
```

```python
            response = call(unless_esc, max_tokens=16384, ..., messages=cached(working_memory))
```

<!-- trim() keeps the first and last 10,000 characters of a result over MAX_RESULT, and says how much it cut. cached() puts a cache_control mark on the last block of the last message, on a copy, so the next call reads everything up to there from the cache. The main call now sends the marked copy. -->

---

# Output: one command becomes a function (abridged)

```python
def execute(cmd):
    if ESC.is_set(): return "[your doing never reached the world]"
    start = time.time()
    doing = subprocess.Popen(["docker", "exec", box, "timeout", ..., cmd], stdout=subprocess.PIPE, ...)
    while True:
        try: done = subprocess.CompletedProcess(doing.args, 0, doing.communicate(timeout=0.1)[0]); break
        except subprocess.TimeoutExpired:
            if ESC.is_set(): subprocess.run(["docker", "exec", box, "sh", "-c", "kill -9 -1"], ...)
    done.returncode = doing.returncode
    if ESC.is_set(): done.stdout += "\n[your doing stopped before done]"
    elif done.returncode == 137: done.stdout += f"\n(killed: ...)"
    trace(event="tool", cmd=cmd, seconds=..., exit=done.returncode, chars=len(done.stdout))
    return trim(done.stdout) or f"(exit {done.returncode})"
```

<!-- It's Lesson 8's way of running a command, moved: in the box, with a time limit, stopped by ESC with what it had printed kept, and now trimmed. Its first line keeps Lesson 8's promise that after ESC nothing else starts. The pool has a fixed number of threads, so a command still waiting for a thread when ESC comes never runs. -->

---

# Decide each request first, in order (abridged)

```python
    refused, pending = {}, {}
    for block in output:
        if block.type == "tool_use":
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if not cmd or (response.stop_reason == "max_tokens" and block is output[-1]):
                refused[block.id] = "[your doing was cut off before it was fully formed — ...]"
            elif (no := guard(cmd)):
                trace(event="refused", cmd=cmd, why=no)
                refused[block.id] = no
            else:
                pending[block.id] = cmd
```

<!-- The first pass decides each tool request in order. The guard's questions are asked one at a time, before anything starts, because you can't have three prompts talking over each other. -->

---

# Then run everything allowed, at once (abridged)

```python
    with listening(), ThreadPoolExecutor() as pool:
        outputs = dict(zip(pending, pool.map(execute, pending.values())))

    input = []
    for block in output:
        if block.type == "tool_use":
            text = refused.get(block.id) or outputs[block.id]
            print(text if block.id in outputs or text.startswith("[") else f"[{text}]")
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": text, ...})
```

One prompt line changes: *Commands that don't depend on each other can go in the same response: they run at the same time.*

<!-- Everything allowed runs at once in a thread pool, inside listening(), so one ESC reaches every command that's running: kill -9 -1 in the box stops them all at once. The second pass prints the results and sends them back in the order they were asked for, each with its request's id, because the API checks that. Lesson 4 asked for one command per response; now the model is told what the harness will do with several. -->

---

# Three seconds of waiting, not nine

Three `sleep 3` commands that don't depend on each other. This lesson's `quark.py`:

```
$ sleep 3; echo lint ok
allow `sleep 3; echo lint ok`? [y/N] $ sleep 3; echo types ok
allow `sleep 3; echo types ok`? [y/N] $ sleep 3; echo tests ok
allow `sleep 3; echo tests ok`? [y/N] lint ok

types ok

tests ok

Lint, types, and tests all passed.
[wall: 8.0s]
```

Lesson 8's `quark.py` ran them one after another: `[wall: 14.4s]`.

<!-- All three questions come first (piped y's answer them, so the answers don't show), then the three commands run together. 8.0 seconds against 14.4 for the whole run. The wall line is from my shell's clock, not from quark. -->

---

# The trace shows it, and the cache too

Lesson 8:

```
{"event":"model","seconds":1.97,"input_tokens":145,"cache_read":0,"cache_write":8709}
{"event":"tool","seconds":3.11,"cmd":"sleep 3; echo lint ok"}
{"event":"tool","seconds":3.08,"cmd":"sleep 3; echo types ok"}
{"event":"tool","seconds":3.08,"cmd":"sleep 3; echo tests ok"}
{"event":"model","seconds":1.22,"input_tokens":407,"cache_read":8709,"cache_write":0}
```

This lesson:

```
{"event":"model","seconds":1.84,"input_tokens":4,"cache_read":0,"cache_write":9262}
{"event":"tool","seconds":3.11,"cmd":"sleep 3; echo types ok"}
{"event":"tool","seconds":3.11,"cmd":"sleep 3; echo tests ok"}
{"event":"tool","seconds":3.11,"cmd":"sleep 3; echo lint ok"}
{"event":"model","seconds":1.23,"input_tokens":2,"cache_read":9262,"cache_write":264}
```

<!-- Each trace line is shortened to the fields that matter here. The trace lists them in the order they finished, types first, but the results went back to the model in the order it asked. And look at input_tokens: 145 and 407 at full price for Lesson 8, 4 and 2 here. That's cached(): everything up to the newest message was read from the cache. -->

---

# Pay full price for what's new, and keep it short

A three-step task, one command per step:

```
{"seconds":1.52,"input_tokens":4,"output_tokens":67,"cache_read":0,"cache_write":9250}
{"seconds":1.42,"input_tokens":2,"output_tokens":75,"cache_read":9250,"cache_write":153}
{"seconds":1.77,"input_tokens":2,"output_tokens":111,"cache_read":9403,"cache_write":125}
```

`cat docs/the-model.md`, a file over 25,000 characters:

```
{"event":"model","seconds":1.62,"input_tokens":4,"cache_read":0,"cache_write":9220}
{"event":"tool","seconds":0.1,"chars":25435}
{"event":"model","seconds":2.24,"input_tokens":2,"cache_read":9220,"cache_write":6533}
```

<!-- First run: input_tokens is what was read at full price, 4, then 2, then 2. The first call wrote about 9,250 tokens to the cache, mostly the system prompt; each later call wrote only what was new, 153 and 125 tokens. Second run: chars is the length before trimming, 25,435. The second call cached 6,533 tokens, the trimmed result; the 5,435 characters cut would otherwise be resent on every later call. Compaction on the fast model doesn't show here: it only runs when working memory is full. -->

---

# One ESC stops both commands (shortened)

```
$ for i in 1 2 3 4 5 6 7 8 9; do echo a$i; sleep 1; done
allow `for i in 1 2 3 4 5 6 7 8 9; do echo a$i; sleep 1; done`? [y/N] y
$ for i in 1 2 3 4 5 6 7 8 9; do echo b$i; sleep 1; done
allow `for i in 1 2 3 4 5 6 7 8 9; do echo b$i; sleep 1; done`? [y/N] y
a1
...
a5

[your doing stopped before done]
b1
...
b5

[your doing stopped before done]
```

Then the model: *"You interrupted me with ESC, so I stopped both commands."*

<!-- This ran in a real terminal, driven by a script: both approved with y, ESC four seconds after the second y. The trace has both at 4.22 seconds, exit 137, the code for a process killed by kill -9. Each kept what it had printed, five lines apiece. Run one after the other, as in Lesson 8, the same ESC would have stopped a at its fifth line and b would never have started. -->

---

# What else performance can be

- **What gets cached:** up to four marks; a one-hour lifetime for agents that wait on people
- **What goes in:** clear old tool results; let the model fetch what it needs
- **How much comes back:** "be brief" does more than `max_tokens`; lower thinking effort
- **How many at once:** cap parallel tools; the batch interface at about half the price
- **As a product:** the API's own settings; [LiteLLM](https://www.litellm.ai) and [OpenRouter](https://openrouter.ai) choose models per request

<!-- And never edit the middle of the conversation: that invalidates everything after it, which is why compaction is paid for with a full-price call. Providers also compete on speed alone. The usual trade-off: the more of the layer you hand to a product, the less of your own agent you can see. -->

---

# `performance.py`: Jev routes

Lesson 3's loop, async, measuring itself. Jev sizes each task: `lookup` → Haiku, `edit` → Sonnet, `work` → Opus (abridged):

```python
DEFAULT, SURE = "edit", 0.7
async def size(input):
    try:
        answer = (await jev.system_one({"input": input}, {"size": SIZE})).choices["size"]
    except Exception as e:
        return DEFAULT, f"no answer from Jev ({type(e).__name__})"
    if answer.confidence < SURE: return DEFAULT, f"Jev: {answer.choice}, {answer.confidence:.2f}, not sure enough"
    return answer.choice, f"Jev: {answer.choice}, {answer.confidence:.2f}"
```

- Asking is model interface; acting on the answer is routing, control flow
- Not sure, or no answer: the middle tier

<!-- Jev is the decision model from Lesson 5: it writes no text, answers typed questions in about a fifth of a second, with a confidence. The answer says what; the confidence says whether to act on it. It's decided once per task, not per step, because the cache belongs to one model. Every call prints time to first output and how input splits: new, from cache, written. Its prompt holds the project's README and docs, so there's something to cache. -->

---

# Warm cache, cheaper bill; a guess, caught

```
[routed to lookup: claude-haiku-4-5 (Jev: lookup, 0.99)]
[done in 2 steps, 2.1s, 50% of input tokens read from the cache]
[done in 3 steps, 2.8s, 99% of input tokens read from the cache]
```

Same task twice (shortened): cold, then warm. The saving was in the bill, not the clock.

```
[routed to edit: claude-sonnet-5-5 (Jev: work, 0.49, not sure enough)]
[3 commands: 3.0s together, 9.0s one after another]
[routed to work: claude-opus-5-5 (Jev: work, 0.94)]
```

Three `echo`s: not sure, so the middle tier. Making `slow.py` fast: sure, so Opus.

<!-- Three echos: Jev leaned towards work but wasn't sure, so the bar sent them to the middle tier, not to Opus. A real performance fix in slow.py: work, 0.94, Opus, 4.2 seconds down to 0.03. With a key Jev doesn't accept, the task still ran, on the middle tier. Jev reads literally: adding "Answer in two sentences; don't edit anything." to a question pulled its confidence from 0.94 to 0.63. -->

---

# The rule

Don't resend what hasn't changed, don't send what isn't needed, and don't wait for things one at a time that could be waiting together.

<!-- Mark the stable start of the request, and the end of the conversation, so the model only reads what's new. Cut what a tool returns to the part that matters. Send the small jobs to the small model. And when the model has asked for several things at once, run them at once. -->

---

# Performance changes how, never what

- **Control flow:** the same loop, the same stops, the same number of calls
- **Input:** the person's task is read the way it always was
- **Context** still decides what the request holds, only marked for reuse
- **Model interface** still sends a request and gets a response, only to a smaller model for a summary
- **Output** still runs what the response asks for, only together, and stopped together

<!-- Nothing here makes the model smarter or the answer better. It makes the same work cheaper and sooner, and the one thing it has to be careful about is not making it different. -->

---

# Faster and cheaper, but as good?

- A trimmed result might have cut the line that mattered
- A summary from the small model might have lost a fact
- The router might send a hard task to a weak model
- Parallel commands can quietly depend on each other
- The trace shows a faster, cheaper run, and not whether it did the job

<!-- Every saving here is a bet. What's missing is a way to measure whether the agent still does its job, on tasks with known answers, every time you change anything, this lesson's changes included. That's evaluation. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Next: Evaluation

Lesson 10
