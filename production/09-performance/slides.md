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
| **Control flow** | which model a turn of work goes to (routing) |

Streaming isn't new: `call()` has streamed every response since Lesson 1.

<!-- Performance is how fast the agent responds and how much each task costs. It's a few small mechanisms, spread over context, the model interface and output, with one decision in control flow: choosing a model for each turn. Streaming is the biggest thing for how fast an agent feels, and quark already does it. This lesson is about what's left. -->

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
- **There's a minimum.** 512 to 4,096 tokens depending on the model; quark's system prompt is nine to eleven thousand
- **It belongs to one model.** Switch models and you start again

The system prompt has carried a mark since Lesson 4. New here: a second mark on the **last message**.

<!-- Anything that changes goes at the end, never at the start. A prefix under the minimum isn't cached, and nothing tells you. With the second mark, each call pays full price only for what's new: the last response and the last result. -->

---

# Send less, pick the model, wait together

- **Trim:** cap what one tool result may add, keeping the start and the end
- **Small jobs to the small model:** compaction always goes to a faster, cheaper one
- **Route by the work:** ask Jev how much work a request is, and pick the model from that
- **Run together:** several tool requests in one response run at the same time
- Results still go back in order, with their ids; questions first; one ESC stops all

<!-- A whole file in working memory is resent on every call, cached or not. Which model compaction goes to is a fixed setting, like max_tokens, so it belongs to the model interface. Choosing the model by what the person asked for is a decision about the work: that's routing, control flow. The model asked for those commands together before seeing any result, so it has already decided none needs another's answer. -->

---

# The concept: route, cache, run together (abridged)

```python
TIERS = {"lookup": "claude-haiku-4-5", "edit": "claude-sonnet-5-5", "work": "claude-opus-5-5"}
def route(input):
    try: size = jev.system_one({"input": input}, {"size": SIZE}).choices["size"]
    except Exception: return TIERS["edit"]
    tier = size.choice if size.confidence >= 0.7 else "edit"
    print(f"[Jev: {size.choice}, {size.confidence:.2f}, so {TIERS[tier]}]")
    return TIERS[tier]

notes = [{"type": "text", "text": open("README.md").read(), "cache_control": {"type": "ephemeral"}}]
...
model = route(input)
print(call(model, input))
call(model, input)
...
with ThreadPoolExecutor() as pool: outputs = list(pool.map(run, checks))
```

<!-- performance.py, about forty lines. Jev, the decision model from Lesson 5, answers one Choice: lookup, edit or work. Below 0.7, or no answer, the middle tier. The system prompt is the repo's README with one cache mark; the same request goes twice so you can watch the second find the first one's work. Then three two-second commands, in a loop and then in a thread pool. Asking Jev is model interface; acting on the answer is routing, control flow. -->

---

# The concept, run twice

```
[Jev: lookup, 0.99, so claude-haiku-4-5]
[1.0s: 17 new, 8264 written to the cache, 0 read from it]
[1.1s: 17 new, 0 written to the cache, 8264 read from it]
[one at a time: 6.0s]
lint ok, types ok, tests ok [at the same time: 2.0s]
```

```
[Jev: work, 0.64, so claude-sonnet-5-5]
[4.3s: 41 new, 10695 written to the cache, 0 read from it]
[4.6s: 41 new, 0 written to the cache, 10695 read from it]
```

(shortened: the answers are cut)

<!-- First: a lookup, sure, so Haiku. The first call wrote the README to the cache; the identical second call read all of it back. Six seconds one after another, two together. Second: Jev leaned to work but only at 0.64, under the bar, so the middle tier, not Opus. The same README is 10,695 tokens for Sonnet and 8,264 for Haiku: each model counts its own way and keeps its own cache. -->

---

# Model interface: a list of models (abridged)

```python
MODELS, FAST = ["claude-sonnet-5-5", "claude-opus-5-5"], ["claude-haiku-4-5"]
class Down(Exception): pass
def call(each=lambda event: None, models=MODELS, **request):
    for model in models:
```

Compaction always asks for the small model:

```python
    summary = call(models=FAST, max_tokens=2048, system=system(), messages=keep + [...])
```

<!-- quark.py is Lesson 8's plus performance: 420 lines, 25 more. The rest of call() is Lesson 8's: the same stream, the same stop on ESC, the same retries, and each model in the list backs up the one before it. There's one model in FAST, so no backup for the summary. -->

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
            response = call(unless_esc, models=models, ..., messages=cached(working_memory))
```

<!-- trim() keeps the first and last 10,000 characters of a result over MAX_RESULT, and says how much it cut. cached() puts a cache_control mark on the last block of the last message, on a copy, so the next call reads everything up to there from the cache. The main call sends the marked copy, to the models this turn was routed to. -->

---

# Output: one command becomes a function (abridged)

```python
def execute(cmd):
    if ESC.is_set(): return "[your doing never reached the world]"
    for attempt in (1, 2):
        ...
        doing = subprocess.Popen(["docker", "exec", box, "timeout", ..., cmd], ...)
        ...
        if ESC.is_set(): done.stdout += "\n[your doing stopped before done]"
        ...
        if attempt == 2 or why != "transient" or not reads(cmd): break
        print("[a failure that passes: trying once more]"); time.sleep(1)
    if why == "partial": done.stdout += "\n(it may have partly run: check before repeating it)"
    return trim(done.stdout) or f"(exit {done.returncode})"
```

<!-- It's Lesson 8's way of running a command, moved: in the box, with a time limit, stopped by ESC with what it had printed kept, with Lesson 8's one retry when Jev is sure a failure will pass and the command only reads. New: the first line keeps the promise that after ESC nothing else starts, and the last line trims. -->

---

# Decide each request first, in order (abridged)

```python
    refused, pending, lent = {}, {}, set()
    for block in output:
        if block.type == "tool_use":
            ...
            if not cmd or (response.stop_reason == "max_tokens" and block is output[-1]):
                refused[block.id] = "[your doing was cut off before it was fully formed — ...]"
            elif (no := guard(cmd)):
                trace(event="refused", cmd=cmd, why=no)
                refused[block.id] = no
            else:
                pending[block.id] = cmd
                if lend(cmd): lent.add(block.id)
```

<!-- The first pass decides each tool request in order. The guard's questions, and Lesson 5's question about the network, are asked one at a time, before anything starts, because you can't have three prompts talking over each other. -->

---

# Then run everything allowed, at once (abridged)

```python
    with listening(), ThreadPoolExecutor() as pool:
        outputs = dict(zip([i for i in pending if i not in lent], pool.map(execute, [...])))
        for i in lent:
            bridge(True); outputs[i] = execute(pending[i]); bridge(False)
```

- One ESC reaches every running command: `kill -9 -1` in the box
- A command lent the network runs on its own, with the way out open just for it
- Results go back in the order asked, each with its id
- New prompt line: *they run at the same time*

<!-- Everything allowed runs at once in a thread pool, inside listening(). Lending opens the box's way out, and while it's open every command in the box could use it, so lent commands run one at a time, after the others. The second pass prints the results and sends them back in order, because the API checks that. -->

---

# Control flow: route each turn (abridged)

```python
TIERS = {"lookup": FAST + MODELS, "edit": MODELS, "work": MODELS[::-1]}
def route(input):
    size = ask({"input": input}, SIZE) if isinstance(input, str) and input else None
    tier = size["choice"] if size and size["confidence"] >= 0.7 else "edit"
    trace(event="routed", to=TIERS[tier][0], size=..., confidence=...)
    return TIERS[tier]
```

```python
    steps, spent, models = 0, 0, route(input)
```

- `SIZE` is the concept's question; lookup → Haiku, edit → Sonnet, work → Opus first
- Unsure, no key, no answer: `edit`, Lesson 8's models
- Once per person turn: switching mid-turn would throw the cache away

<!-- Asking is a model-interface act through Lesson 5's ask(). Acting on it is routing, so it's control flow's. The bar is 0.7, lower than SURE, because a wrong route only spends more or answers worse; nothing runs that wouldn't have run anyway. Each decision goes in the trace as routed. -->

---

# Three seconds of waiting, not nine

```
$ sleep 3; echo lint ok
allow `sleep 3; echo lint ok`? (Jev: read, 0.88) [y/N] $ sleep 3; echo types ok
allow `sleep 3; echo types ok`? (Jev: read, 0.84) [y/N] $ sleep 3; echo tests ok
allow `sleep 3; echo tests ok`? (Jev: read, 0.75) [y/N] lint ok

types ok

tests ok

Lint, types and tests all passed.
[wall: 10.6s]
```

Lesson 8's `quark.py` ran them one after another: `[wall: 16.5s]`.

<!-- All three questions come first (piped y's answer them, so the answers don't show), then the three commands run together. 10.6 seconds against 16.5 for the whole run. The wall line is from my shell's clock, not from quark. -->

---

# The trace shows it, and the cache too (shortened)

Lesson 8:

```
{"event":"model","seconds":1.74,"input_tokens":145,"cache_read":0,"cache_write":10391}
{"event":"model","seconds":0.93,"input_tokens":407,"cache_read":10391,"cache_write":0}
```

This lesson:

```
{"event":"routed","to":"claude-sonnet-5-5","size":"work","confidence":0.51}
{"event":"model","seconds":1.8,"input_tokens":4,"cache_read":0,"cache_write":11342}
{"event":"model","seconds":1.47,"input_tokens":2,"cache_read":11342,"cache_write":264}
```

<!-- input_tokens: 145 and 407 at full price for Lesson 8, 4 and 2 here. That's cached(): everything up to the newest message came from the cache. And the routed line: Jev leaned towards work at 0.51, too unsure, so the turn went to edit's models, Sonnet first. -->

---

# Pay full price for what's new, and keep it short (shortened)

A three-step task, one command per step:

```
{"event":"routed","to":"claude-opus-5-5","size":"work","confidence":0.83}
{"event":"model","seconds":2.04,"input_tokens":4,"cache_read":0,"cache_write":11330}
{"event":"model","seconds":1.84,"input_tokens":2,"cache_read":11330,"cache_write":158}
{"event":"model","seconds":5.08,"input_tokens":2,"cache_read":11488,"cache_write":125}
```

`cat docs/the-model.md`, over 25,000 characters:

```
{"event":"tool","cmd":"cat docs/the-model.md","seconds":0.11,"exit":0,"chars":25435,"failed":0.03}
{"event":"model","seconds":0.83,"input_tokens":6,"cache_read":9051,"cache_write":4936}
```

<!-- First run: sure enough, so Opus. input_tokens is what was read at full price, 4, then 2, then 2; each later call wrote only what was new, 158 and 125 tokens. Second run: chars is the length before trimming, 25,435; the second call cached 4,936 tokens, the trimmed result. Jev called it a lookup, so Haiku, and Haiku described the wrong heading. Remember that for the end. -->

---

# One ESC stops both commands (shortened)

```
$ for i in 1 2 3 4 5 6 7 8 9; do echo a$i; sleep 1; done
$ for i in 1 2 3 4 5 6 7 8 9; do echo b$i; sleep 1; done
a1
...
a4

[your doing stopped before done]
b1
...
b4

[your doing stopped before done]
```

Then the model: *"You interrupted me, so both commands stopped early."*

<!-- This ran in a real terminal, driven by a script; Jev was sure both only read, so nothing was asked. ESC four seconds after the second was printed. The trace has both at 3.93 seconds, exit 137, the code for a process killed by kill -9. Each kept what it had printed. One after the other, as in Lesson 8, b would never have started. -->

---

# Routing, turn by turn (shortened)

A chat: *how many lines is slow.py?*, then *why is it slow, and what would you change?*

```
{"event":"routed","to":"claude-haiku-4-5","size":"lookup","confidence":1.0}
{"event":"model","seconds":0.93,"input_tokens":3,"cache_read":0,"cache_write":9038}
{"event":"model","seconds":0.45,"input_tokens":6,"cache_read":9038,"cache_write":84}
{"event":"routed","to":"claude-opus-5-5","size":"work","confidence":0.9}
{"event":"model","seconds":1.72,"input_tokens":4,"cache_read":0,"cache_write":11427}
```

The switch to Opus started its cache over: `cache_read` 0.

<!-- The first turn was a lookup at 1.00, so Haiku, under a second a call. The second was work at 0.90, so Opus, which read the file and explained the list rebuilt on every pass. The system prompt was the same, but the first turn's cache was Haiku's. That's why quark switches only when a new turn starts. -->

---

# Other things we could do

- **What gets cached:** up to four marks; a one-hour lifetime for agents that wait on people
- **What goes in, and comes back:** clear old results; fetch on demand; "be brief"; less thinking
- **How many at once:** cap parallel tools; the batch interface at about half the price
- **Measure what a person feels:** time to first output, and the share read from the cache
- **As a product:** the API's own settings; [LiteLLM](https://www.litellm.ai) and [OpenRouter](https://openrouter.ai) choose models per request

<!-- Never edit the middle of the conversation: that invalidates everything after it. You could switch models by step instead of by turn, at the price of the cache. A tier can carry a thinking effort as well as a model. An agent with a short prompt can put the project's notes in it so there's something to cache. Providers also compete on speed alone. The more of the layer you hand to a product, the less of your own agent you can see. -->

---

# The rule

Don't resend what hasn't changed, don't send what isn't needed, and don't wait for things one at a time that could be waiting together.

<!-- Mark the stable start of the request, and the end of the conversation, so the model only reads what's new. Cut what a tool returns to the part that matters. Send the small jobs to the small model, and let the size of the work pick the model only when you're sure of the size. And when the model has asked for several things at once, run them at once. -->

---

# Performance changes how, never what

- **Control flow:** the same loop and stops; routing only picks a turn's models
- **Input:** the person's request is read the way it always was
- **Context** still decides what the request holds, only marked for reuse
- **Model interface** still sends a request and gets a response; asking Jev changes nothing on its own
- **Output** still runs what the response asks for, only together, and stopped together

<!-- Nothing here makes the model smarter or the answer better. It makes the same work cheaper and sooner, and the one thing it has to be careful about is not making it different. -->

---

# Faster and cheaper, but as good?

- A trimmed result might have cut the line that mattered
- A summary from the small model might have lost a fact
- The router might send a request to a model too weak for it: Haiku described the wrong heading
- Parallel commands can quietly depend on each other
- The trace shows a faster, cheaper run, and not whether it did the job

<!-- Every saving here is a bet. What's missing is a way to measure whether the agent still does its job, on tasks with known answers, every time you change anything, this lesson's changes included. That's evaluation. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Next: Evaluation

Lesson 10
