# Lesson 9: Performance

> 🎥 **Video:** coming soon

Lesson 8 made the agent keep going when something fails. A run that finishes but takes ten minutes and costs ten dollars is still a run you'll think twice about starting. Over a long task two things add up: the time you wait and the tokens you pay for.

Performance is how fast the agent responds and how much each task costs. Those two are one subject because they come from the same place. Time is spent waiting: on the model to read a request, on the model to write a reply, on a command to finish. Tokens are spent on every request: the more the model reads, the more it costs and the longer it takes. So performance isn't one mechanism. It's a few small ones, spread over the primitives where the time and the tokens go.

This is a production layer, so it adds hardening, not a new primitive. It's **built on context, the model interface and output**. Context decides what the request holds (Lesson 4), the model interface sends it and brings the response back (Lesson 1), and output runs what the response asks for (Lesson 2). Most of what follows happens inside those three. One piece reaches into control flow, choosing a model for each task, and I'll say why when we get there. The person's input and the sandbox are left as they are.

One thing you might expect here isn't new. *Streaming*, getting the response piece by piece as the model writes it, has been there since Lesson 1: `call()` has streamed every response from the start, Lesson 2's `show()` prints the text as it's written, and Lesson 6 stops reading the stream the moment you press ESC. A reply that takes eight seconds to write starts appearing after half a second, and that's the biggest thing you can do for how fast an agent *feels*. quark already does it. This lesson is about what's left: the tokens resent on every call, the tokens that didn't need sending, the model a job goes to, and the commands waiting on each other.

The mechanism, first in context, because it's where most of the tokens go. Remember what the loop does (Lesson 3): every pass sends the *whole* request again, the instructions, the tools and every message so far. Nothing is remembered on the model's side between calls, so a task of twenty steps makes the model read the same opening twenty times, and each time the conversation is a little longer. The cost of a task isn't the sum of what was said; it's the sum of everything resent.

**Prompt caching** is the fix, and it works because the request is a *prefix*. The model reads the request in a fixed order: the tools, then the instructions, then the messages. The API can remember what it already worked out for the start of a request, and if the next request begins with exactly the same tokens, it picks up from there and only reads the new end. You mark where you want the remembering to end with a `cache_control` block. Reading from the cache costs a fraction of normal input (a tenth, at the time of writing) and is faster, and writing to it costs a little more than normal (a quarter more). So the first call pays slightly extra and every call after it, within five minutes of the last one, gets a discount on the part that hasn't changed. Three consequences follow:

- *The match has to be exact.* One changed character early in the request and everything after it is new. That's why Lesson 4's system prompt has the date and not the time: a timestamp would make every call a miss. Anything that changes goes at the end, never at the start.
- *There's a minimum.* A prefix shorter than a minimum, from 512 to 4,096 tokens depending on the model (512 for this course's Sonnet 5.5, 4,096 for Haiku 4.5), isn't cached, and nothing tells you. quark's system prompt is nine to eleven thousand tokens, depending on how the model counts them, mostly the copy of its own code, so it qualifies.
- *The cache belongs to one model.* Switch models and you start again.

Context has a second, plainer lever: send less. A command that prints a whole file puts the whole file in the working memory, and from then on it's resent on every call, cached or not. So the harness caps what one tool result may contribute. It keeps the start and the end, which is where headers and errors usually are, and says how much it cut.

Then the model interface: *which model a request goes to*. Not every request needs the biggest model. Summarizing a working memory to make room (Lesson 4's compaction) is a plain job that a smaller, faster, cheaper model does well, so that one request always goes to one. That's a fixed setting of the request, like `max_tokens`, and it belongs to the model interface, as Lesson 8's backup model does. Choosing the model by *what the person asked for*, a quick lookup to the small model and real work to the big one, is a different thing. That's a decision about the work, and deciding which path the work takes is control flow's (Lesson 3 called it routing). To make it, quark asks a second model how much work the request is.

Last, output, where the time goes while a command runs. When the model needs three things, it can ask for all three in one response: the response has three `tool_use` blocks. The harness has been handling them one at a time, in order. But the model asked for them together, in one response, before seeing any result, so it has already decided that none of them needs another's answer. Nothing stops the harness running them at the same time, and then the wait is the slowest command and not the sum of all of them. Three details. Every result must still go back, in order, each with the id of the request it answers, because the API checks that. The questions Lesson 6's gate asks a person are asked first, one at a time, before anything starts, because you can't have three prompts talking over each other. And one ESC has to stop all of them, not just the first.

Nothing here makes the model smarter or the answer better. It makes the same work cheaper and sooner, and the one thing it has to be careful about is not making it different.

## The concept

Here are three of those ideas with nothing around them, in [`performance.py`](./performance.py): a model picked for the request, the same request sent twice so the second reads its start from the cache, and three commands run one at a time and then all at once:

```python
import subprocess, sys, os, time
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic
from typesafe_sdk import TypeSafeClient, Choice

client = Anthropic()
jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # Jev: a second model that answers typed questions and writes no text

SIZE = Choice(instructions="How much work does the request in `input` need from an agent that works through a shell?", criteria={"lookup": "one quick fact or one command: count, list, show, check a version", "edit": "a small, clear change to one or two files", "work": "several steps of reading, reasoning and changing things, or a design question"})
TIERS = {"lookup": "claude-haiku-4-5", "edit": "claude-sonnet-5-5", "work": "claude-opus-5-5"}
def route(input):                                        # the smallest model that can do it; unsure means the usual one
    try: size = jev.system_one({"input": input}, {"size": SIZE}).choices["size"]
    except Exception: return TIERS["edit"]
    tier = size.choice if size.confidence >= 0.7 else "edit"
    print(f"[Jev: {size.choice}, {size.confidence:.2f}, so {TIERS[tier]}]")
    return TIERS[tier]

notes = [{"type": "text", "text": open("README.md").read(), "cache_control": {"type": "ephemeral"}}]   # the same long start, marked
def call(model, input):                                  # one call, and where its input tokens came from
    start = time.time()
    output = client.messages.create(model=model, max_tokens=16384, system=notes, messages=[{"role": "user", "content": input}])
    u = output.usage
    print(f"[{time.time() - start:.1f}s: {u.input_tokens} new, {u.cache_creation_input_tokens} written to the cache, {u.cache_read_input_tokens} read from it]")
    return "".join(block.text for block in output.content if block.type == "text")

def run(cmd):                                            # one command, and what it printed
    return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace").stdout.strip()

input = " ".join(sys.argv[1:])
model = route(input)
print(call(model, input))
call(model, input)                                       # the same request again: its start comes from the cache

checks = ["sleep 2; echo lint ok", "sleep 2; echo types ok", "sleep 2; echo tests ok"]
start = time.time()
for cmd in checks: run(cmd)
print(f"[one at a time: {time.time() - start:.1f}s]")
start = time.time()
with ThreadPoolExecutor() as pool: outputs = list(pool.map(run, checks))
print(", ".join(outputs), f"[at the same time: {time.time() - start:.1f}s]")
```

**`route()`** asks Jev, the decision model from [Lesson 5](../05-sandboxing/#asking-jev), one question, a `Choice`: how much work does this request need, `lookup`, `edit` or `work`? Each option has a line saying what it covers, because Jev reads literally. `TIERS` turns the answer into a model: a lookup goes to `claude-haiku-4-5`, an edit to `claude-sonnet-5-5`, work to `claude-opus-5-5`. The answer says *what*; the confidence says whether to act on it. Below 0.7 the request goes to the middle, and so does every request when Jev can't be reached: any exception is caught, so a broken router costs you the right model, never the answer. Asking is a model-interface act. Acting on the answer, sending the work down a different path, is control flow.

**`notes` and `call()`.** The system prompt is this repo's `README.md`, thousands of tokens, the same every time, with one `cache_control` mark on it. `call()` sends one request and prints where its input tokens came from: new, written to the cache, or read from it. The file sends the same request twice, on purpose, so you can watch the second one find the first one's work.

**`run()` and the pool.** Three commands that each take two seconds, run in a plain loop and then through a `ThreadPoolExecutor`, which starts them all and hands back what they printed in the order they were given.

Run it from the root of the repo (it reads `README.md` from where it runs, and it needs `TYPESAFE_API_KEY` as well as the Anthropic key):

```bash
uv run production/09-performance/performance.py "how many lessons are in this course? answer in one sentence"
```

```
[Jev: lookup, 0.99, so claude-haiku-4-5]
[1.0s: 17 new, 8264 written to the cache, 0 read from it]
The course has 10 lessons total: 4 primitive lessons (model interface, input and output, control flow, and context) followed by 6 production layers (sandboxing, guardrails, observability, resilience, performance, and evaluation).
[1.1s: 17 new, 0 written to the cache, 8264 read from it]
[one at a time: 6.0s]
lint ok, types ok, tests ok [at the same time: 2.0s]
```

Jev called it a `lookup` with 0.99 confidence, so it went to Haiku. The first call wrote the whole README to the cache, 8,264 tokens, and paid full price for only the 17 tokens of the question. The second call, identical, read all 8,264 back. Then the commands: six seconds one after another, two seconds together.

A question that needs more thought:

```bash
uv run production/09-performance/performance.py "Which lesson of this course should I teach first to a room of backend engineers, and why? Answer in three sentences."
```

```
[Jev: work, 0.64, so claude-sonnet-5-5]
[4.3s: 41 new, 10695 written to the cache, 0 read from it]
Teach Lesson 1 (Model interface) first, because the course is cumulative: each lesson's `quark.py` is the previous one's plus one primitive, so you can't skip ahead without losing the thread. It's also familiar ground for backend engineers, since it's just one API call and a streamed reply, which lets you establish "Agent = Harness(Model)" and the five primitives without fighting unfamiliar material. Because they'll find it easy, you can move through it quickly and spend your time on Lesson 3 (Control flow), where a plain request/response call becomes an agent loop and the real "aha" lands.
[4.6s: 41 new, 0 written to the cache, 10695 read from it]
[one at a time: 6.0s]
lint ok, types ok, tests ok [at the same time: 2.0s]
```

Jev leaned towards `work`, but with 0.64 confidence, under the bar, so it went to the middle tier, Sonnet, and not to Opus. A router with no bar would have sent it to the biggest model on a guess. Look at the cache line too: the same README is 10,695 tokens here and 8,264 for Haiku. Each model counts tokens its own way and keeps its own cache, so the Haiku run's cache was no use to this one: it wrote the README again.

## quark's implementation

[`quark.py`](./quark.py) is Lesson 8's `quark.py` plus performance, and nothing else: 420 lines, 25 more than Lesson 8's. In `# ── model interface ──`, `call()` takes a list of models, which is Lesson 8's list unless you say otherwise:

```python
MODELS, FAST = ["claude-sonnet-5-5", "claude-opus-5-5"], ["claude-haiku-4-5"]
class Down(Exception): pass
def call(each=lambda event: None, models=MODELS, **request):   # model interface: the response streams back, and each piece goes to each()
    for model in models:                                 # resilience: retries, then a backup model, then give up cleanly
```

The rest of `call()` is Lesson 8's: the same stream, the same stop on ESC, the same retries, and each model in the list is the backup for the one before it. `models=FAST` sends a request to the small model, and compaction always asks for it:

```python
    summary = call(models=FAST, max_tokens=2048, system=system(), messages=keep + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}])
```

There's one model in `FAST`, so there's no backup for the summary: if the small model is down, `call()` raises `Down` as it would for the main call, and the work so far is in the episode.

In `# ── context ──`, two ways to send less, and to pay less for what's sent again:

```python
MAX_RESULT = 20_000
def trim(text):                                          # performance: keep the start and end of a long result
    if len(text) <= MAX_RESULT: return text
    return text[:MAX_RESULT // 2] + f"\n[... {len(text) - MAX_RESULT} characters cut ...]\n" + text[-MAX_RESULT // 2:]

def cached(working_memory):                              # performance: cache everything up to the newest message
    last = working_memory[-1]
    blocks = [{"type": "text", "text": last["content"]}] if isinstance(last["content"], str) else list(last["content"])
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return working_memory[:-1] + [{"role": last["role"], "content": blocks}]
```

**`trim()`** keeps the first and last 10,000 characters of a result over `MAX_RESULT`, and says how much it cut. **`cached()`** puts a `cache_control` mark on the last block of the last message, on a copy, so the next call reads everything up to there from the cache. The system prompt has carried its own mark since Lesson 4. The main call now sends the marked copy, to the models this turn was routed to:

```python
            response = call(unless_esc, models=models, max_tokens=16384, system=system(), tools=tools, messages=cached(working_memory))
```

One line of the system prompt changes too. Lesson 4 asked for one command per response; now the model is told what the harness will do with several:

```
Prefer focused actions to keep results small. Commands that don't depend on each other can go in the same response: they run at the same time.
```

In `# ── output: the one tool ──`, running one command becomes a function, so several can run at once. It's Lesson 8's way of running a command, moved: in the box, with a time limit, stopped by ESC with what it had printed kept, traced with Jev's opinion on whether it failed, and given one more try when Jev is sure a failure will pass and the command only reads. What's new is the first line, which keeps Lesson 6's promise that after ESC nothing else starts, and the last, which trims:

```python
from concurrent.futures import ThreadPoolExecutor
```

```python
def execute(cmd):                                        # performance: one command in the box, so several can run at once
    if ESC.is_set(): return "[your doing never reached the world]"   # guardrails: after ESC, nothing else starts
    for attempt in (1, 2):                               # resilience: a failure that will pass gets one more try, if it only reads
        start = time.time()
        doing = subprocess.Popen(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        while True:
            try: done = subprocess.CompletedProcess(doing.args, 0, doing.communicate(timeout=0.1)[0]); break
            except subprocess.TimeoutExpired:
                if ESC.is_set(): subprocess.run(["docker", "exec", box, "sh", "-c", "kill -9 -1"], capture_output=True)   # every command in the box, not the box
        done.returncode = doing.returncode
        if ESC.is_set(): done.stdout += "\n[your doing stopped before done]"
        elif done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
        trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout), failed=failed(cmd, done.stdout))
        why = failure(cmd, done.stdout) if done.returncode and not ESC.is_set() else None
        if attempt == 2 or why != "transient" or not reads(cmd): break
        print("[a failure that passes: trying once more]"); time.sleep(1)
    if why == "partial": done.stdout += "\n(it may have partly run: check before repeating it)"
    return trim(done.stdout) or f"(exit {done.returncode})"

```

The pool has a fixed number of threads, so when the model asks for more commands than that, the extra ones wait for a free thread, and if ESC came while they waited, the first line answers for them.

In the loop, the tool requests are handled in two passes. The first decides each one in order, asking the guard's questions one at a time, and Lesson 5's question about the network, before anything starts. Then everything allowed runs at once in a thread pool, inside `listening()`, so one ESC reaches every command that's running: `kill -9 -1` in the box stops them all at once. A command lent the network is the exception. Lending opens the box's way out, and while it's open every command in the box could use it, so each lent command runs on its own, after the others, with the way out opened just for it. The second pass prints the results and sends them back in the order they were asked for, each with its request's id:

```python
    refused, pending, lent = {}, {}, set()
    for block in output:                                 # output: decide each tool request, in order
        if block.type == "tool_use":
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if not cmd or (response.stop_reason == "max_tokens" and block is output[-1]):   # resilience: never run half a command
                refused[block.id] = "[your doing was cut off before it was fully formed — it never reached the world]"
            elif (no := guard(cmd)):
                trace(event="refused", cmd=cmd, why=no)
                refused[block.id] = no
            else:
                pending[block.id] = cmd
                if lend(cmd): lent.add(block.id)
    with listening(), ThreadPoolExecutor() as pool:      # performance: everything allowed runs at the same time
        outputs = dict(zip([i for i in pending if i not in lent], pool.map(execute, [c for i, c in pending.items() if i not in lent])))
        for i in lent:                                   # sandboxing: a command lent the network runs on its own
            bridge(True); outputs[i] = execute(pending[i]); bridge(False)

    input = []
    for block in output:
        if block.type == "tool_use":
            text = refused.get(block.id) or outputs[block.id]
            print(text if block.id in outputs or text.startswith("[") else f"[{text}]")
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": text, **({"is_error": True} if block.id in refused and not text.startswith("[your doing") else {})})  # input: from the world
```

Then routing. These lines are in `# ── control flow ──`, next to the loop that uses them:

```python
SIZE = Choice(instructions="How much work does the request in `input` need from an agent that works through a shell?", criteria={"lookup": "one quick fact or one command: count, list, show, check a version", "edit": "a small, clear change to one or two files", "work": "several steps of reading, reasoning and changing things, or a design question"})
TIERS = {"lookup": FAST + MODELS, "edit": MODELS, "work": MODELS[::-1]}
def route(input):                                        # performance: the smallest model that can do it; unsure means the usual one
    size = ask({"input": input}, SIZE) if isinstance(input, str) and input else None
    tier = size["choice"] if size and size["confidence"] >= 0.7 else "edit"
    trace(event="routed", to=TIERS[tier][0], size=size and size["choice"], confidence=size and size["confidence"])
    return TIERS[tier]
```

`SIZE` is the concept's question, word for word. `TIERS` maps each answer to a list of models for `call()`: a lookup goes to Haiku, with Lesson 8's two models behind it as backups; an edit goes to Lesson 8's list, Sonnet then Opus; work goes to the same list reversed, Opus first. **`route()`** asks Jev about the person's request through Lesson 5's `ask()`. It acts on the answer only when the confidence is at least 0.7, lower than the 0.9 `SURE` the other layers use, because the worst a wrong route can do is spend more or answer worse, and the next lesson measures that; whatever a smaller model asks for still goes through the same guard and the same box. Unsure, no key, no answer, or a turn with no new request (a resumed session) all mean `edit`, Lesson 8's models, as if nothing had been asked. Every decision goes in the trace as a `routed` record, so you can see where each turn went.

Asking is a model-interface act, as in every lesson since Lesson 5. What's done with the answer is routing, so it's control flow's: it decides which path a turn of work takes, unlike Lesson 8's backup model, which steps in only when the first model fails. It's decided once per person turn, when the request arrives, not once per step, for the reason from the start of the lesson: the cache belongs to a model, and a turn that changed model at every step would never read what it wrote. The loop asks at the start, and again with each new turn from the person:

```python
models = route(input)
```

```python
    steps, spent, models = 0, 0, route(input)
```

Lesson 8's loop gave a command that hadn't started yet `[your doing never reached the world]` after ESC. That check now lives in `execute()`. Usually everything allowed starts together, so ESC finds them all running, and each one gets what it had printed and `[your doing stopped before done]`; only a command still waiting for a thread gets the other result.

Two small things look different on screen: a cut-off request now prints its whole result, where Lesson 8 printed `[cut off, not run]`, and a refusal is printed with the other results, after the allowed commands have run. Everything else is unchanged. The guard still decides before anything runs, the box still holds every command, the trace still records each call and command, and resilience's backup model, resume and kept partials work through the same `call()` and episode.

### Run it

You need Docker running, as in Lesson 5, and both keys. Start in a scratch folder, not in this repo:

```bash
mkdir -p /tmp/demo && cd /tmp/demo
uv run --project /path/to/building-agents /path/to/building-agents/production/09-performance/quark.py "..."
```

I'll write that as `quark.py`. Where the guard might ask, I piped in `y`s. The `[wall: …]` line at the end of a run is from my shell's clock, not from quark. Each trace below is shortened: I left out the `start` line, and the `ts`, `episode`, `stop_reason` and `output_tokens` fields of every line.

**Running at the same time.** Three slow commands that don't depend on each other; `sleep 3` stands in for a lint, a type check and a test run. First Lesson 8's `quark.py`, as a baseline:

```
Run these three commands as three separate commands: 'sleep 3; echo lint ok', 'sleep 3; echo types ok', 'sleep 3; echo tests ok'. Then say what passed, in one line.
```

```
$ sleep 3; echo lint ok
allow `sleep 3; echo lint ok`? (Jev: read, 0.86) [y/N] lint ok

$ sleep 3; echo types ok
allow `sleep 3; echo types ok`? (Jev: read, 0.82) [y/N] types ok

$ sleep 3; echo tests ok
allow `sleep 3; echo tests ok`? (Jev: read, 0.81) [y/N] tests ok

Lint, types and tests all passed.
[wall: 16.5s]
```

The guard asked about each one (Jev thought each only reads, but not with the 0.9 it takes to skip the question). Lesson 8's trace shows the model asked for all three in one response, and they ran one after another:

```
{"event":"model","seconds":1.74,"input_tokens":145,"cache_read":0,"cache_write":10391}
{"event":"tool","cmd":"sleep 3; echo lint ok","seconds":3.1,"exit":0,"chars":8,"failed":0.03}
{"event":"tool","cmd":"sleep 3; echo types ok","seconds":3.08,"exit":0,"chars":9,"failed":0.02}
{"event":"tool","cmd":"sleep 3; echo tests ok","seconds":3.09,"exit":0,"chars":9,"failed":0.02}
{"event":"model","seconds":0.93,"input_tokens":407,"cache_read":10391,"cache_write":0}
```

Three seconds each, nine in total. Now the same task with this lesson's `quark.py`:

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

```
{"event":"routed","to":"claude-sonnet-5-5","size":"work","confidence":0.51}
{"event":"model","seconds":1.8,"input_tokens":4,"cache_read":0,"cache_write":11342}
{"event":"tool","cmd":"sleep 3; echo lint ok","seconds":3.1,"exit":0,"chars":8,"failed":0.03}
{"event":"tool","cmd":"sleep 3; echo types ok","seconds":3.11,"exit":0,"chars":9,"failed":0.02}
{"event":"tool","cmd":"sleep 3; echo tests ok","seconds":3.11,"exit":0,"chars":9,"failed":0.02}
{"event":"model","seconds":1.47,"input_tokens":2,"cache_read":11342,"cache_write":264}
```

All three questions come first (the piped `y`s answer them, so the answers don't show), then the three commands run together: three seconds of waiting instead of nine, 10.6 seconds against 16.5 for the whole run. The rest of each run is the model, and Jev's questions about each command (the guard's, the network's, and whether it failed). The results went back to the model in the order it asked. Look at `input_tokens` too: 145 and 407 at full price for Lesson 8, 4 and 2 here. That's `cached()`: with a mark on the newest message, the first call wrote the whole request to the cache instead of paying full price for its end, and the second read all of that back and paid full price for only 2.

The `routed` line is the new decision. Jev leaned towards `work`, at 0.51, which is too unsure to act on, so the turn went to `edit`'s models, starting with `claude-sonnet-5-5`, Lesson 8's.

**Caching.** A task of three steps, in a folder holding a copy of `lessons/`, one command per step:

```
Find the quark.py files under lessons/ and count the lines in each. Then grep the import lines of the longest one. Then say in one sentence what those imports tell you. One command per step.
```

````
$ find lessons/ -name quark.py | xargs wc -l | sort -n
   12 lessons/01-model-interface/quark.py
   38 lessons/02-input-and-output/quark.py
   51 lessons/03-control-flow/quark.py
  239 lessons/04-context/quark.py
  340 total

$ grep -nE "^\s*(import|from) " lessons/04-context/quark.py
1:import subprocess, sys, os, re, glob, json, datetime
2:from anthropic import Anthropic, BadRequestError

I found four quark.py files under lessons/. The longest is `04-context`, with 239 lines:

| File | Lines |
|---|---|
| lessons/01-model-interface/quark.py | 12 |
| lessons/02-input-and-output/quark.py | 38 |
| lessons/03-control-flow/quark.py | 51 |
| lessons/04-context/quark.py | 239 |

Its imports are just two lines:
```
1:import subprocess, sys, os, re, glob, json, datetime
2:from anthropic import Anthropic, BadRequestError
```

**In one sentence:** The imports suggest this lesson adds memory on disk (timestamped JSON files found with `glob`, and maybe a skills index parsed with `re`) and catches `BadRequestError` to shrink the conversation when the prompt gets too long, all on top of a basic Anthropic client that runs shell commands through `subprocess`.

That reading is based only on the imports and how they match my own harness; I didn't read the rest of the file.
[wall: 12.9s]
````

```
{"event":"routed","to":"claude-opus-5-5","size":"work","confidence":0.83}
{"event":"model","seconds":2.04,"input_tokens":4,"cache_read":0,"cache_write":11330}
{"event":"tool","cmd":"find lessons/ -name quark.py | xargs wc -l | sort -n","seconds":0.1,"exit":0,"chars":170,"failed":0.03}
{"event":"model","seconds":1.84,"input_tokens":2,"cache_read":11330,"cache_write":158}
{"event":"tool","cmd":"grep -nE \"^\\s*(import|from) \" lessons/04-context/quark.py","seconds":0.09,"exit":0,"chars":106,"failed":0.03}
{"event":"model","seconds":5.08,"input_tokens":2,"cache_read":11488,"cache_write":125}
```

This time Jev was sure enough, `work` at 0.83, so the turn went to `claude-opus-5-5`. Neither command was on the guard's safe list, and Jev was sure both only read, so nothing was asked. `input_tokens` is what was read at full price: 4, then 2, then 2. The first call wrote 11,330 tokens to the cache, mostly the system prompt with quark's own code in it. Each later call read what the previous one had written and wrote only what was new: the last response and its result, 158 and 125 tokens. The harness resent over eleven thousand tokens each time and paid full price for a handful of them.

**Trimming.** A command that prints a lot. The folder has a copy of `docs/`, and the task is:

```
cat docs/the-model.md, then tell me in one sentence what its first heading says.
```

The file is over 25,000 characters, more than `MAX_RESULT`, and `cat` is on the guard's safe list, so nothing is asked. The output printed 20,000 of them, so here are its first lines, the lines around the cut, and the answer (shortened, with the file's long lines cut to 100 characters):

```
$ cat docs/the-model.md
> Optional background for [harness-engineering](../README.md): enough about model development to kno

...
- **Attention variants.** Plain multi-head attention (MHA) is legacy at this 
[... 5435 characters cut ...]
oops the loss back to the model with the annotation 'gradient → tweak weights → repeat'." width=
...
The first heading says a modern LLM is a probabilistic next-token predictor that generates text by producing probability distributions over what word should come next.
```

```
{"event":"routed","to":"claude-haiku-4-5","size":"lookup","confidence":0.89}
{"event":"model","seconds":0.88,"input_tokens":3,"cache_read":0,"cache_write":9051}
{"event":"tool","cmd":"cat docs/the-model.md","seconds":0.11,"exit":0,"chars":25435,"failed":0.03}
{"event":"model","seconds":0.83,"input_tokens":6,"cache_read":9051,"cache_write":4936}
```

The trace's `chars` is the length before trimming, 25,435. The second call wrote 4,936 tokens to the cache, which is what the trimmed result came to; the 5,435 characters that were cut are characters that every later call would otherwise have resent. Jev called the request a `lookup`, 0.89, so it went to Haiku, and Haiku's answer is not quite right: the first heading is "The model: what the harness wraps", and what it describes is the paragraph under the *second* heading. Remember that one at the end of the lesson.

**One ESC, every command.** This ran in a real terminal, driven by a script, in chat mode ending with `/q`: two commands that print a line a second for nine seconds, and ESC four seconds after the second one was printed. Jev was sure both only read, so the guard didn't ask:

```
> Run these two as separate commands, at the same time: for i in 1 2 3 4 5 6 7 8 9; do echo a$i; sleep 1; done   and   for i in 1 2 3 4 5 6 7 8 9; do echo b$i; sleep 1; done
$ for i in 1 2 3 4 5 6 7 8 9; do echo a$i; sleep 1; done
$ for i in 1 2 3 4 5 6 7 8 9; do echo b$i; sleep 1; done
a1
a2
a3
a4

[your doing stopped before done]
b1
b2
b3
b4

[your doing stopped before done]
You interrupted me, so both commands stopped early. They did run at the same time, and each got through four iterations (`a1`–`a4` and `b1`–`b4`) before the stop. Neither loop finished its nine counts.

Do you want me to run both again from the start, or leave it?

> /q
```

```
{"event":"routed","to":"claude-sonnet-5-5","size":"lookup","confidence":0.35}
{"event":"model","seconds":2.11,"input_tokens":4,"cache_read":0,"cache_write":11363}
{"event":"tool","cmd":"for i in 1 2 3 4 5 6 7 8 9; do echo b$i; sleep 1; done","seconds":3.93,"exit":137,"chars":45,"failed":0.66}
{"event":"tool","cmd":"for i in 1 2 3 4 5 6 7 8 9; do echo a$i; sleep 1; done","seconds":3.93,"exit":137,"chars":45,"failed":0.72}
{"event":"interrupted","during":"acting"}
{"event":"model","seconds":2.01,"input_tokens":4,"cache_read":11363,"cache_write":284}
```

One ESC stopped both, at the same moment: 3.93 seconds each, exit 137, the code for a process killed by `kill -9`. Each kept what it had printed, four lines apiece, and the model knew how far each had got. Run one after the other, as in Lesson 8, the same ESC would have stopped `a` at its fourth line and `b` would never have started. (Jev's `failed`, 0.66 and 0.72, is its read of a result that ends in `[your doing stopped before done]`.)

**Routing, turn by turn.** A chat with two turns, piped in, in a folder holding only a `slow.py` that takes a few seconds to print `1000`. First a lookup, then a question that takes thought:

```
how many lines is slow.py?
slow.py takes seconds to run. Read it and tell me why, and what you would change to make it fast with the same output. Do not change anything yet.
/q
```

```
> I'll check the line count for slow.py.
$ wc -l slow.py
8 slow.py

**slow.py has 8 lines.**

> $ cat -n slow.py
     1	seen = []
     2	for n in range(50_000):
     3	    if n % 1000 not in seen:
     4	        seen.append(n % 1000)
     5	for n in range(50_000):
     6	    if str(n) not in [str(s) for s in seen]:
     7	        pass
     8	print(len(seen))

**Why it's slow:** almost all the time goes to the second loop, which does nothing.

- **Lines 5–7 (the main cost):** on every one of 50,000 passes, `[str(s) for s in seen]` builds a new list of 1,000 strings and then searches it. That's about 50 million string conversions plus about 50 million comparisons. The body is `pass`, so the loop has no effect on anything.
- **Lines 1–4 (smaller cost):** `seen` is a list, so `not in seen` checks it item by item, up to 1,000 items each time. That's tens of millions more comparisons. It always ends up holding 0 to 999.
- **Output:** `print(len(seen))` always prints `1000`.

**What I'd change, keeping the output the same:**
1. **Delete lines 5–7.** They print nothing and change nothing, so removing them can't change the output. This alone makes the script run almost instantly.
...

If the second loop is a placeholder for real work, I'd build `{str(s) for s in seen}` once before the loop and check against that set. That avoids rebuilding the list 50,000 times.

As you asked, I haven't changed anything and haven't timed it.

> 
```

The second answer is shortened (I cut its code). The trace has a `routed` line for each turn:

```
{"event":"routed","to":"claude-haiku-4-5","size":"lookup","confidence":1.0}
{"event":"model","seconds":0.93,"input_tokens":3,"cache_read":0,"cache_write":9038}
{"event":"tool","cmd":"wc -l slow.py","seconds":0.1,"exit":0,"chars":10,"failed":0.02}
{"event":"model","seconds":0.45,"input_tokens":6,"cache_read":9038,"cache_write":84}
{"event":"routed","to":"claude-opus-5-5","size":"work","confidence":0.9}
{"event":"model","seconds":1.72,"input_tokens":4,"cache_read":0,"cache_write":11427}
{"event":"tool","cmd":"cat -n slow.py","seconds":0.08,"exit":0,"chars":248,"failed":0.04}
{"event":"model","seconds":8.53,"input_tokens":2,"cache_read":11427,"cache_write":171}
```

The first turn was a `lookup` at 1.00, so it went to `claude-haiku-4-5`: under a second for each call. The second was `work` at 0.90, so `claude-opus-5-5`, which read the file and explained the list rebuilt on every pass. Look at its first call: `cache_read` 0 and `cache_write` 11,427. The system prompt was the same as in the first turn, but the first turn's cache was Haiku's, and Opus has its own. Switching models costs a full write, which is why quark switches only when a new turn starts, never in the middle of one.

One thing from this layer doesn't show here. **Compaction on the fast model** only runs when working memory is full, which none of these runs got near.

## Other things we could do

quark has one cache mark on the conversation, one trim, one fast model for summaries, one routing question per turn and one thread pool. These are the choices you make when you build this layer.
- **What gets cached, and for how long.** quark marks two places: the system prompt and the end of the conversation. You can mark up to four, for instance after the tools, which rarely change, so that a change to the instructions doesn't throw them away. The default lifetime is five minutes since the cache was last used; there's a longer, one-hour option, which costs more to write and suits an agent that waits on people. And whatever you do, don't edit the middle of the conversation: changing an early message invalidates everything after it, which is why compaction, which rewrites the history, is paid for with a full-price call.
- **What goes in the request.** Cutting a tool result to its start and end, as quark does. Clearing *old* tool results once the model has acted on them. Summarizing, as in Lesson 4. Or not loading things up front at all: put a short list of what's available in the request, and let the model fetch the one it needs (that's how Lesson 4's skills index works). The cheapest token is the one that was never sent.
- **How much comes back.** Output tokens cost more than input tokens and take longer to produce, so a short answer is faster and cheaper than a long one. `max_tokens` is a cap and not a goal; the instruction "be brief" does more. A lower thinking effort for simple tasks saves the time spent thinking before the first word.
- **Which model, and when.** quark sends the summary to a faster model, and routes each turn by asking Jev how much work it is. You could instead switch by step (a cheap model for reading files, a strong one for deciding what to change), at the price of the cache restarting each time you switch, as the last run showed.
- **How the reply arrives.** Streamed to the person, as quark has done since Lesson 1. Or streamed so a tool can start as soon as the block that asks for it is complete, before the model has finished writing the rest of its reply. Or not streamed at all, when nobody is waiting.
- **How many at once.** Tools at the same time, as in quark, with a cap on how many so that twenty requests don't start twenty heavy processes. Whole model calls in parallel is a different thing, a way of arranging the work, and that's control flow (Lesson 3's parallelization workflows). For work nobody is waiting on, there's the batch interface: many requests handed over together, answered within a day, at about half the price.
- **When the work is done.** A cache can be warmed before it's needed: send the long opening of a task while the person is still typing the question, and the first real call finds it ready.

It can be a product on its own. The caching, the model choice and the batch interface are features of the API itself, so you use them by sending the right settings, and the Lesson 1 gateways, [LiteLLM](https://www.litellm.ai) and [OpenRouter](https://openrouter.ai), can choose a model per request, or cache whole responses, for you. And providers compete on speed alone, serving models on hardware built for it, which makes every call faster without the harness changing at all. The trade-off is the usual one: the more of the layer you hand to a product, the less of your own agent you can see.

A few of those choices are worth spelling out, because quark could have gone the other way on each.

**Measure what a person feels.** quark's trace records how long each call took in all. What a person waiting at the keyboard feels is the time until *anything* appears. A streamed call can note when its first content block starts, and print that beside the total: the gap between the two is what streaming buys you. Add up, over a task, the tokens read from the cache against all the input tokens, and you have one number that says whether your caching is working.

**Give the cache something worth caching.** A system prompt under the model's minimum is never cached, and nothing tells you. quark's is long enough because it carries its own code. An agent with a short prompt can put the project's notes in it, its README and docs, the same text on every task with no date or clock in it, so the cache has a long, stable start to recognize, and the agent starts every task knowing the project.

**Route the effort as well as the model.** The tier a router picks can carry more than a model name: a thinking effort too, none for a lookup, medium for an edit, high for real work, so the small jobs don't spend time thinking before the first word.

**Cap what runs at once.** quark's thread pool has a fixed number of threads. With async code, a semaphore does the same job more plainly: each command waits for a slot, so no more than, say, four run together, however many the model asks for. And timing each command lets you print the time they took together against the time they'd have taken one after another, which is the saving in one line.

## What to take away

**The rule:** don't resend what hasn't changed, don't send what isn't needed, and don't wait for things one at a time that could be waiting together. Mark the stable start of the request, and the end of the conversation, so the model only reads what's new. Cut what a tool returns to the part that matters. Send the small jobs to the small model, and let the size of the work pick the model only when you're sure of the size. And when the model has asked for several things at once, run them at once.

Notice what performance never does. It sits in context, the model interface and output, with one decision in control flow, and it leaves the rest alone. Control flow is the same loop with the same stops: the number of calls and steps is what it was, and routing only chooses which models a turn's calls go to, once per turn. Asking Jev is a model-interface act, and it changes nothing until control flow acts on a confident answer. Input is untouched: the person's request is read the way it always was. And inside each of the three it changes how, not what: context still decides what the request holds, only marked so that it can be reused and with long results cut, the model interface still sends a request and gets a response, only to a smaller model when the job is a summary, and output still runs what the response asks for, only together, and stopped together.

**What's missing:** performance makes a run faster and cheaper, and it doesn't tell you the run was *as good*. Every saving here is a bet. A trimmed result might have cut the line that mattered, a summary from the small model might have lost a fact, the router might send a request to a model too weak for it (the trimming run above did: Haiku described the wrong heading), and parallel commands can quietly depend on each other in a way the model didn't notice. Nothing in the harness would show it. The trace would show a faster, cheaper run, and you'd have no way to know whether it did the job. What's missing is a way to measure whether the agent still does its job, on tasks with known answers, every time you change anything, this lesson's changes included. That's evaluation.

**→ [Lesson 10: Evaluation](../10-evaluation/)**
