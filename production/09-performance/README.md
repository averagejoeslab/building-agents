# Lesson 9: Performance

> 🎥 **Video:** coming soon

Lesson 8 made the agent keep going when something fails. A run that finishes but takes ten minutes and costs ten dollars is still a run you'll think twice about starting. Over a long task two things add up: the time you wait and the tokens you pay for.

Performance is how fast the agent responds and how much each task costs. Those two are one subject because they come from the same place. Time is spent waiting: on the model to read a request, on the model to write a reply, on a command to finish. Tokens are spent on every request: the more the model reads, the more it costs and the longer it takes. So performance isn't one mechanism. It's a few small ones, spread over the primitives where the time and the tokens go.

This is a production layer, so it adds hardening, not a new primitive. It's **built on context, the model interface and output**. Context decides what the request holds (Lesson 4), the model interface sends it and brings the response back (Lesson 1), and output runs what the response asks for (Lesson 2). Everything below happens inside those three. The loop that connects them, the person's input and the sandbox are left as they are.

One thing you might expect here isn't new. *Streaming*, getting the response piece by piece as the model writes it, has been there since Lesson 1: `call()` has streamed every response from the start, Lesson 2's `show()` prints the text as it's written, and Lesson 6 stops reading the stream the moment you press ESC. A reply that takes eight seconds to write starts appearing after half a second, and that's the biggest thing you can do for how fast an agent *feels*. quark already does it. This lesson is about what's left: the tokens resent on every call, the tokens that didn't need sending, the model a plain job goes to, and the commands waiting on each other.

The mechanism, first in context, because it's where most of the tokens go. Remember what the loop does (Lesson 3): every pass sends the *whole* request again, the instructions, the tools and every message so far. Nothing is remembered on the model's side between calls, so a task of twenty steps makes the model read the same opening twenty times, and each time the conversation is a little longer. The cost of a task isn't the sum of what was said; it's the sum of everything resent.

**Prompt caching** is the fix, and it works because the request is a *prefix*. The model reads the request in a fixed order: the tools, then the instructions, then the messages. The API can remember what it already worked out for the start of a request, and if the next request begins with exactly the same tokens, it picks up from there and only reads the new end. You mark where you want the remembering to end with a `cache_control` block. Reading from the cache costs a fraction of normal input (a tenth, at the time of writing) and is faster, and writing to it costs a little more than normal (a quarter more). So the first call pays slightly extra and every call after it, within five minutes of the last one, gets a discount on the part that hasn't changed. Three consequences follow:

- *The match has to be exact.* One changed character early in the request and everything after it is new. That's why Lesson 4's system prompt has the date and not the time: a timestamp would make every call a miss. Anything that changes goes at the end, never at the start.
- *There's a minimum.* A prefix shorter than a minimum, from 512 to 4,096 tokens depending on the model (512 for this course's Sonnet 5.5, 4,096 for Haiku 4.5), isn't cached, and nothing tells you. quark's system prompt is about nine thousand tokens, mostly the copy of its own code, so it qualifies.
- *The cache belongs to one model.* Switch models and you start again.

The system prompt has been marked since Lesson 4. What's new is the other end: the conversation. A second mark on the last message means each call pays full price only for what's new since the previous call: the last response and the last result.

Context has a second, plainer lever: send less. A command that prints a whole file puts the whole file in the working memory, and from then on it's resent on every call, cached or not. So the harness caps what one tool result may contribute. It keeps the start and the end, which is where headers and errors usually are, and says how much it cut.

Then the model interface: *which model a kind of request goes to*. Not every request needs the biggest model. Summarizing a working memory to make room (Lesson 4's compaction) is a plain job that a smaller, faster, cheaper model does well, so that one request always goes to one. That's a fixed setting of the request, like `max_tokens`, and it belongs to the model interface, as Lesson 8's backup model does. Deciding the model while the harness runs, per task or per step, is a different thing: that's routing, which Lesson 3 put in control flow, and the fuller example below shows it.

Last, output, where the time goes while a command runs. When the model needs three things, it can ask for all three in one response: the response has three `tool_use` blocks. The harness has been handling them one at a time, in order. But the model asked for them together, in one response, before seeing any result, so it has already decided that none of them needs another's answer. Nothing stops the harness running them at the same time, and then the wait is the slowest command and not the sum of all of them. Three details. Every result must still go back, in order, each with the id of the request it answers, because the API checks that. The questions Lesson 6's gate asks a person are asked first, one at a time, before anything starts, because you can't have three prompts talking over each other. And one ESC has to stop all of them, not just the first.

Nothing here makes the model smarter or the answer better. It makes the same work cheaper and sooner, and the one thing it has to be careful about is not making it different.

## The worked example

[`quark.py`](./quark.py) is Lesson 8's `quark.py` plus performance, and nothing else: 373 lines, 17 more than Lesson 8's. In `# ── model interface ──`, `call()` takes a list of models, which is Lesson 8's list unless you say otherwise:

```python
MODELS, FAST = ["claude-sonnet-5-5", "claude-opus-5-5"], ["claude-haiku-4-5"]
class Down(Exception): pass
def call(each=lambda event: None, models=MODELS, **request):   # model interface: the response streams back, and each piece goes to each()
    for model in models:                                 # resilience: retries, then a backup model, then give up cleanly
```

The rest of `call()` is Lesson 8's: the same stream, the same stop on ESC, the same retries. `models=FAST` sends a request to the small model, and only compaction asks for it:

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

**`trim()`** keeps the first and last 10,000 characters of a result over `MAX_RESULT`, and says how much it cut. **`cached()`** puts a `cache_control` mark on the last block of the last message, on a copy, so the next call reads everything up to there from the cache. The system prompt has carried its own mark since Lesson 4. The main call now sends the marked copy:

```python
            response = call(unless_esc, max_tokens=16384, system=system(), tools=tools, messages=cached(working_memory))
```

One line of the system prompt changes too. Lesson 4 asked for one command per response; now the model is told what the harness will do with several:

```
Prefer focused actions to keep results small. Commands that don't depend on each other can go in the same response: they run at the same time.
```

In `# ── output ──`, running one command becomes a function, so several can run at once. It's Lesson 8's way of running a command, moved: in the box, with a time limit, stopped by ESC with what it had printed kept, and now trimmed. Its first line keeps Lesson 8's promise that after ESC nothing else starts. The pool has a fixed number of threads, so when the model asks for more commands than that, the extra ones wait for a free thread, and if ESC came while they waited, they never run:

```python
from concurrent.futures import ThreadPoolExecutor
```

```python
def execute(cmd):                                        # performance: one command in the box, so several can run at once
    if ESC.is_set(): return "[your doing never reached the world]"   # guardrails: after ESC, nothing else starts
    start = time.time()
    doing = subprocess.Popen(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    while True:
        try: done = subprocess.CompletedProcess(doing.args, 0, doing.communicate(timeout=0.1)[0]); break
        except subprocess.TimeoutExpired:
            if ESC.is_set(): subprocess.run(["docker", "exec", box, "sh", "-c", "kill -9 -1"], capture_output=True)   # every command in the box, not the box
    done.returncode = doing.returncode
    if ESC.is_set(): done.stdout += "\n[your doing stopped before done]"
    elif done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
    trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
    return trim(done.stdout) or f"(exit {done.returncode})"
```

And in the loop, the tool requests are handled in two passes. The first decides each one in order, asking the guard's questions one at a time, before anything starts. Then everything allowed runs at once in a thread pool, inside `listening()`, so one ESC reaches every command that's running: `kill -9 -1` in the box stops them all at once. The second pass prints the results and sends them back in the order they were asked for, each with its request's id:

```python
    refused, pending = {}, {}
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
    with listening(), ThreadPoolExecutor() as pool:      # performance: everything allowed runs at the same time
        outputs = dict(zip(pending, pool.map(execute, pending.values())))

    input = []
    for block in output:
        if block.type == "tool_use":
            text = refused.get(block.id) or outputs[block.id]
            print(text if block.id in outputs or text.startswith("[") else f"[{text}]")
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": text, **({"is_error": True} if block.id in refused and not text.startswith("[your doing") else {})})  # input: from the world
```

Lesson 8's loop gave a command that hadn't started yet `[your doing never reached the world]` after ESC. That check now lives in `execute()`. Usually everything allowed starts together, so ESC finds them all running, and each one gets what it had printed and `[your doing stopped before done]`; only a command still waiting for a thread gets the other result.

Everything else is unchanged. The guard still decides before anything runs, the box still holds every command, the trace still records each call and command, and resilience's backup model, resume and kept partials work through the same `call()` and episode.

## Run it

You need Docker running, as in Lesson 5. Start in a scratch folder. Each run below is `uv run --project /path/to/building-agents /path/to/building-agents/production/09-performance/quark.py`, which I'll write as `quark.py`, with `y` piped in for the guard. The `[wall: …]` line at the end of a run is from my shell's clock, not from quark.

**Running at the same time.** Three slow commands that don't depend on each other; `sleep 3` stands in for a lint, a type check and a test run. First Lesson 8's `quark.py`, as a baseline:

```
Run these three commands as three separate commands: 'sleep 3; echo lint ok', 'sleep 3; echo types ok', 'sleep 3; echo tests ok'. Then say what passed, in one line.
```

```
$ sleep 3; echo lint ok
allow `sleep 3; echo lint ok`? [y/N] lint ok

$ sleep 3; echo types ok
allow `sleep 3; echo types ok`? [y/N] types ok

$ sleep 3; echo tests ok
allow `sleep 3; echo tests ok`? [y/N] tests ok

Lint, types, and tests all passed.
[wall: 14.4s]
```

The trace shows the model asked for all three in one response, and Lesson 8 ran them one after another (each line shortened to the fields that matter here):

```
{"event":"model","seconds":1.97,"input_tokens":145,"cache_read":0,"cache_write":8709}
{"event":"tool","seconds":3.11,"cmd":"sleep 3; echo lint ok"}
{"event":"tool","seconds":3.08,"cmd":"sleep 3; echo types ok"}
{"event":"tool","seconds":3.08,"cmd":"sleep 3; echo tests ok"}
{"event":"model","seconds":1.22,"input_tokens":407,"cache_read":8709,"cache_write":0}
```

Three seconds each, nine in total. Now the same task with this lesson's `quark.py`, and its trace shortened the same way:

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

```
{"event":"model","seconds":1.84,"input_tokens":4,"cache_read":0,"cache_write":9262}
{"event":"tool","seconds":3.11,"cmd":"sleep 3; echo types ok"}
{"event":"tool","seconds":3.11,"cmd":"sleep 3; echo tests ok"}
{"event":"tool","seconds":3.11,"cmd":"sleep 3; echo lint ok"}
{"event":"model","seconds":1.23,"input_tokens":2,"cache_read":9262,"cache_write":264}
```

All three questions come first (piped `y`s answer them, so the answers don't show), then the three commands run together: three seconds of waiting instead of nine, 8.0 seconds against 14.4 for the whole run. The trace lists them in the order they finished, `types` first, but the results went back to the model in the order it asked. Look at `input_tokens` too: 145 and 407 at full price for Lesson 8, 4 and 2 here. That's `cached()`: everything up to the newest message was read from the cache.

**Caching.** A task of three steps, in a folder holding a copy of `lessons/`, one command per step:

```
Find the quark.py files under lessons/ and count the lines in each. Then grep the import lines of the longest one. Then say in one sentence what those imports tell you. One command per step.
```

```
$ find lessons -name quark.py -exec wc -l {} +
allow `find lessons -name quark.py -exec wc -l {} +`? [y/N]    51 lessons/03-control-flow/quark.py
  239 lessons/04-context/quark.py
   38 lessons/02-input-and-output/quark.py
   12 lessons/01-model-interface/quark.py
  340 total

$ grep -nE "^\s*(import|from) " lessons/04-context/quark.py
allow `grep -nE "^\s*(import|from) " lessons/04-context/quark.py`? [y/N] 1:import subprocess, sys, os, re, glob, json, datetime
2:from anthropic import Anthropic, BadRequestError

The longest file, `lessons/04-context/quark.py` (239 lines), imports only the standard library (subprocess, os, re, glob, json and similar) plus the `anthropic` SDK. That means it's a self-contained agent that runs shell commands, handles files and JSON, and talks to Claude, with no other third-party dependencies.
[wall: 6.7s]
```

```
jq -c 'select(.event=="model") | {seconds,input_tokens,output_tokens,cache_read,cache_write}' .quark/traces.jsonl
```

```
{"seconds":1.52,"input_tokens":4,"output_tokens":67,"cache_read":0,"cache_write":9250}
{"seconds":1.42,"input_tokens":2,"output_tokens":75,"cache_read":9250,"cache_write":153}
{"seconds":1.77,"input_tokens":2,"output_tokens":111,"cache_read":9403,"cache_write":125}
```

`input_tokens` is what was read at full price: 4, then 2, then 2. The first call wrote about 9,250 tokens to the cache, mostly the system prompt with quark's own code in it. Each later call read what the previous one had written and wrote only what was new: the last response and its result, 153 and 125 tokens. The harness resent about 9,250 to 9,400 tokens each time and paid full price for a handful of them.

**Trimming.** A command that prints a lot. The folder has a copy of `docs/`, and the task is:

```
cat docs/the-model.md, then tell me in one sentence what its first heading says.
```

The file is over 25,000 characters, more than `MAX_RESULT`. `cat` is on the guard's safe list, so nothing is asked. The output printed 20,000 of them, so here is its first line, the lines around the cut (each cut to 100 characters), and the answer:

```
$ cat docs/the-model.md
...
- **Attention variants.** Plain multi-head attention (MHA) is legacy at this 
[... 5435 characters cut ...]
oops the loss back to the model with the annotation 'gradient → tweak weights → repeat'." width=
...
The first heading is "The model: what the harness wraps", and the section under it says the model is the first of an agent's two primitives (TokensOut = Model(TokensIn)). It then gives a short tour of what an LLM is made of, how it's trained, and how it generates output, so you know what your harness is wrapping.
```

```
{"event":"model","seconds":1.62,"input_tokens":4,"cache_read":0,"cache_write":9220}
{"event":"tool","seconds":0.1,"chars":25435}
{"event":"model","seconds":2.24,"input_tokens":2,"cache_read":9220,"cache_write":6533}
```

(The trace is shortened as before.) The trace's `chars` is the length before trimming, 25,435. The second call wrote 6,533 tokens to the cache, which is what the trimmed result came to: the 5,435 characters that were cut are characters that every later call would otherwise have resent.

**One ESC, every command.** This ran in a real terminal, driven by a script, in chat mode ending with `/q`: two commands that print a line a second for nine seconds, both approved with `y`, and ESC four seconds after the second `y`:

```
> Run these two as separate commands, at the same time: for i in 1 2 3 4 5 6 7 8 9; do echo a$i; sleep 1; done   and   for i in 1 2 3 4 5 6 7 8 9; do echo b$i; sleep 1; done
$ for i in 1 2 3 4 5 6 7 8 9; do echo a$i; sleep 1; done
allow `for i in 1 2 3 4 5 6 7 8 9; do echo a$i; sleep 1; done`? [y/N] y
$ for i in 1 2 3 4 5 6 7 8 9; do echo b$i; sleep 1; done
allow `for i in 1 2 3 4 5 6 7 8 9; do echo b$i; sleep 1; done`? [y/N] y
a1
a2
a3
a4
a5

[your doing stopped before done]
b1
b2
b3
b4
b5

[your doing stopped before done]
You interrupted me with ESC, so I stopped both commands. I had started them at the same time as separate commands. Each one got through 5 of its 9 iterations before it was killed:

- The first printed a1 to a5.
- The second printed b1 to b5.

Neither loop finished. Do you want me to rerun them, or do something different?

> /q
```

The trace, cut to those three lines and their fields that matter:

```
{"event":"tool","cmd":"for i in 1 2 3 4 5 6 7 8 9; do echo b$i; sleep 1; done","seconds":4.22,"exit":137,"chars":48}
{"event":"tool","cmd":"for i in 1 2 3 4 5 6 7 8 9; do echo a$i; sleep 1; done","seconds":4.22,"exit":137,"chars":48}
{"event":"interrupted","during":"acting"}
```

One ESC stopped both, at the same moment: 4.22 seconds each, exit 137, the code for a process killed by `kill -9`. Each kept what it had printed, five lines apiece, and the model knew how far each had got. Run one after the other, as in Lesson 8, the same ESC would have stopped `a` at its fifth line and `b` would never have started.

One thing from this layer doesn't show here. **Compaction on the fast model** only runs when working memory is full, which none of these runs got near.

## Going further

**What else performance can be:** quark has one cache mark on the conversation, one trim, one fast model and one thread pool. These are the choices you make when you build it.
- **What gets cached, and for how long.** quark marks two places: the system prompt and the end of the conversation. You can mark up to four, for instance after the tools, which rarely change, so that a change to the instructions doesn't throw them away. The default lifetime is five minutes since the cache was last used; there's a longer, one-hour option, which costs more to write and suits an agent that waits on people. And whatever you do, don't edit the middle of the conversation: changing an early message invalidates everything after it, which is why compaction, which rewrites the history, is paid for with a full-price call.
- **What goes in the request.** Cutting a tool result to its start and end, as quark does. Clearing *old* tool results once the model has acted on them. Summarizing, as in Lesson 4. Or not loading things up front at all: put a short list of what's available in the request, and let the model fetch the one it needs (that's how the skills in Lesson 4's fuller example work). The cheapest token is the one that was never sent.
- **How much comes back.** Output tokens cost more than input tokens and take longer to produce, so a short answer is faster and cheaper than a long one. `max_tokens` is a cap and not a goal; the instruction "be brief" does more. A lower thinking effort for simple tasks saves the time spent thinking before the first word.
- **Which model, and when.** quark sends one request, the summary, to a faster model. The fuller example sends a whole task to one by asking a second model, Jev, how much work it is. You could instead switch by step (a cheap model for reading files, a strong one for deciding what to change), at the price of the cache restarting each time you switch. Deciding per task or per step is routing, so that part is control flow.
- **How the reply arrives.** Streamed to the person, as quark has done since Lesson 1. Or streamed so a tool can start as soon as the block that asks for it is complete, before the model has finished writing the rest of its reply. Or not streamed at all, when nobody is waiting.
- **How many at once.** Tools at the same time, as in quark, with a cap on how many so that twenty requests don't start twenty heavy processes. Whole model calls in parallel is a different thing, a way of arranging the work, and that's control flow (Lesson 3's parallelization workflows). For work nobody is waiting on, there's the batch interface: many requests handed over together, answered within a day, at about half the price.
- **When the work is done.** A cache can be warmed before it's needed: send the long opening of a task while the person is still typing the question, and the first real call finds it ready.

It can be a product on its own. The caching, the model choice and the batch interface are features of the API itself, so you use them by sending the right settings, and the Lesson 1 gateways, [LiteLLM](https://www.litellm.ai) and [OpenRouter](https://openrouter.ai), can choose a model per request, or cache whole responses, for you. And providers compete on speed alone, serving models on hardware built for it, which makes every call faster without the harness changing at all. The trade-off is the usual one: the more of the layer you hand to a product, the less of your own agent you can see.

The fuller example, [`performance.py`](./performance.py), shows more of that list. It's Lesson 3's agent loop (no memory, no tracing, no guardrails, no sandbox, no resilience), written with the async client, so performance is all there is to look at. It does everything quark does, and it measures itself: every call prints how long until the first output arrived, how long it took, and how its input tokens split into new, read from the cache and written to it. It asks Jev how much work the task is and picks the model and thinking effort from a table. Its system prompt holds the project's README and `docs/`, about fifteen thousand tokens, so there's something worth caching. And its commands run together, up to four at a time, and it prints how long that took against how long running them in turn would have. Here it is, all of it:

```python
import asyncio, glob, os, sys, time
from anthropic import AsyncAnthropic
from typesafe_sdk import AsyncTypeSafeClient, Choice
read = input                                             # a person's input; the name input is for whatever comes in

client = AsyncAnthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

# Control flow: which model answers is chosen per task, by asking Jev how much work it is. That's routing (Lesson 3). (The cache belongs to
# one model, so this is decided once per task, not once per step: switching mid-task would start the cache over.)
jev = AsyncTypeSafeClient(timeout=5)         # Jev, a decision model: answers typed questions, writes no text (reads TYPESAFE_API_KEY)
TIERS = {                                    # how much work -> (model, effort)
    "lookup": ("claude-haiku-4-5", None),
    "edit":   ("claude-sonnet-5-5", "medium"),
    "work":   ("claude-opus-5-5", "high"),
}
DEFAULT, SURE = "edit", 0.7                  # the tier when Jev can't say, and how confident it must be to choose another
SIZE = Choice(instructions="How much work does the request in `input` need from an agent that works through a shell?", criteria={
    "lookup": "one quick fact or one command: count, list, show, check a version",
    "edit": "a small, clear change to one or two files",
    "work": "several steps of reading, reasoning and changing things, or a design question"})
MAX_STEPS, MAX_RESULT = 10, 20_000
TOOL_TIMEOUT, AT_ONCE = 30, 4                # seconds a command may run, commands that may run together

def notes():
    # Context: what the agent starts every task knowing. It's the same text every time, which is what lets it be cached.
    files = [f for pattern in ("README.md", "docs/*.md") for f in sorted(glob.glob(pattern))]
    return "\n\n".join(f"## {f}\n\n{open(f).read()}" for f in files) or "(none)"
SYSTEM = [{"type": "text", "text": f"You are quark, an agent whose body is bash. You work in {os.getcwd()}. Be brief.\n\n# Project notes\n\n{notes()}", "cache_control": {"type": "ephemeral"}}]

def cached(messages):
    # A second cache breakpoint, on the end of the conversation: each call pays full price only for what is new since the last one.
    last = messages[-1]
    blocks = [{"type": "text", "text": last["content"]}] if isinstance(last["content"], str) else list(last["content"])
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return messages[:-1] + [{"role": last["role"], "content": blocks}]

def trim(text):
    if len(text) <= MAX_RESULT: return text
    return text[:MAX_RESULT // 2] + f"\n[... {len(text) - MAX_RESULT} characters cut ...]\n" + text[-MAX_RESULT // 2:]

async def size(input):
    # Model interface: one question to a second model. What's done with the answer is control flow's.
    try:
        answer = (await jev.system_one({"input": input}, {"size": SIZE})).choices["size"]
    except Exception as e:                   # TypeSafeError, or anything else the call raises: never stop the task for it
        return DEFAULT, f"no answer from Jev ({type(e).__name__})"
    if answer.confidence < SURE: return DEFAULT, f"Jev: {answer.choice}, {answer.confidence:.2f}, not sure enough"
    return answer.choice, f"Jev: {answer.choice}, {answer.confidence:.2f}"

async def call(messages, tier):
    # Model interface: streamed, so the person reads the answer as it is written, and timed, so you can see it.
    model, effort = TIERS[tier]
    settings = {"output_config": {"effort": effort}} if effort else {}
    start, first = time.time(), None
    async with client.messages.stream(model=model, max_tokens=16384, system=SYSTEM, tools=tools, messages=cached(messages), **settings) as stream:
        async for event in stream:
            if first is None and event.type == "content_block_start": first = time.time() - start
            if event.type == "text": print(event.text, end="", flush=True)
        output = await stream.get_final_message()
    u = output.usage
    print(f"\n[{model}: first output after {first or 0:.1f}s, finished after {time.time() - start:.1f}s; "
          f"input {u.input_tokens} new + {u.cache_read_input_tokens} from cache + {u.cache_creation_input_tokens} written to it; output {u.output_tokens}]")
    return output

gate = asyncio.Semaphore(AT_ONCE)
async def bash(cmd):
    # Output: one command. Many of these run at once; each reports how long it took.
    async with gate:
        start = time.time()
        p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            out, _ = await asyncio.wait_for(p.communicate(), TOOL_TIMEOUT)
            text = out.decode(errors="replace") + (f"\n(exit {p.returncode})" if p.returncode else "")
        except TimeoutError:
            p.kill()
            text = f"stopped after {TOOL_TIMEOUT} seconds"
        return trim(text) or "(no output)", time.time() - start

async def main():
    input = " ".join(sys.argv[1:]) or read("> ")
    tier, why = await size(input)
    print(f"[routed to {tier}: {TIERS[tier][0]} ({why})]")
    messages, start, seen = [{"role": "user", "content": input}], time.time(), [0, 0]
    for step in range(1, MAX_STEPS + 1):
        output = await call(messages, tier)
        seen[0] += output.usage.cache_read_input_tokens
        seen[1] += output.usage.input_tokens + output.usage.cache_read_input_tokens + output.usage.cache_creation_input_tokens
        messages.append({"role": "assistant", "content": output.content})
        calls = [b for b in output.content if b.type == "tool_use"]
        if not calls:
            print(f"[done in {step} steps, {time.time() - start:.1f}s, {seen[0] / max(seen[1], 1):.0%} of input tokens read from the cache]")
            return
        for b in calls: print(f"$ {b.input.get('cmd')}")
        began = time.time()
        done = await asyncio.gather(*(bash(b.input["cmd"]) for b in calls if b.input.get("cmd")))
        together, alone = time.time() - began, sum(took for _, took in done)
        if len(calls) > 1: print(f"[{len(calls)} commands: {together:.1f}s together, {alone:.1f}s one after another]")
        outputs = iter(done)
        input = []
        for b in calls:
            if b.input.get("cmd"): text, failed = next(outputs)[0], False
            else: text, failed = "your request was cut off at the token limit, so it was not run. Send it again, shorter.", True
            print(text)
            input.append({"type": "tool_result", "tool_use_id": b.id, "content": text, "is_error": failed})
        messages.append({"role": "user", "content": input})
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")

asyncio.run(main())
```

There's a lot of it that's the same as quark, so here is what's different.

**`notes()` and `SYSTEM`.** The agent starts every task knowing the project's `README.md` and `docs/*.md`, whatever is in the folder it's run from. It's the same text every time, with no date or clock in it, which is what lets the cache recognize it. It's also what makes the prompt long enough to be cached at all: without it, the cache mark would silently do nothing.

**`size()`, `TIERS` and Jev.** Jev is the decision model I introduced in [Lesson 5](../05-sandboxing/#asking-jev): it writes no text, it answers typed questions in about a fifth of a second, and each answer comes with a confidence. Here it gets one question, a `Choice`: how much work does this request need, `lookup`, `edit` or `work`? Each option has a line saying what it means, because Jev reads them literally. What comes back is the option it picked and how confident it is. The table turns the option into a model and a thinking effort: a lookup goes to `claude-haiku-4-5`, an edit to `claude-sonnet-5-5`, work to `claude-opus-5-5`. The answer says *what*; the confidence says whether to act on it. Below `SURE`, 0.7, the task goes to `DEFAULT`, the middle tier, and so does every task when Jev can't be reached: any exception from the call, `TypeSafeError` or otherwise, is caught, so a broken router costs you the right model, never the task. The line after the route says which of those happened.

Asking is a model-interface act, a request to a second model. Acting on the answer is routing, which Lesson 3 put in control flow: sending a task down a different path, here a different model, is a decision about the work, unlike Lesson 8's backup model, which only steps in when the first is down. It's in this lesson because it's one of the biggest levers on cost, so this fuller example reaches into control flow where `quark.py` doesn't. It's done once per task, not once per step, for the reason from the start of the lesson: the cache belongs to a model, and a task that changes model at each step would never read what it wrote.

It's still a guess, and Jev has known weak spots: it reads the words you wrote, not what you meant, so a request that says the same thing differently can come out a different size. I asked it "why is slow.py slow, and what would you change?" and it said `work`, 0.94. With "Answer in two sentences; don't edit anything." on the end it still said `work`, but at 0.63, under the bar. That's why the bar is there: a guess it isn't sure of goes to the middle, not to either end.

**`call()`.** The streamed call. It goes through the stream's events: the first `content_block_start` is when the model began producing something, which is the number a person feels as *how long until anything happens*; `text` events are printed as they come. The line after it says which model answered and splits the input tokens. `cached()` and `trim()` are the same as quark's.

**`bash()`.** An async command with a time limit, behind a semaphore, `gate`, so that no more than `AT_ONCE` run together, and it returns how long it took.

**`main()`.** Route, then loop. After each step it adds up the tokens read from the cache against all the input tokens, and prints that share when the task is done. When there are several commands in a reply, `asyncio.gather` starts them all and returns the results in order, and a line compares the time they took together with the sum of their times alone.

Running it needs `TYPESAFE_API_KEY` as well as the Anthropic key; without it, every task goes to the middle tier, as the last run below shows.

Two runs on the same task, first with nothing cached and then with the cache warm. Both were run in a folder holding a copy of this repo's `README.md` and `docs/`, one I'd never run it in before so that its system prompt was new to the cache:

```
python performance.py "how many lessons are in this course? answer in one sentence"
```

```
[routed to lookup: claude-haiku-4-5 (Jev: lookup, 0.99)]

[claude-haiku-4-5: first output after 0.9s, finished after 1.3s; input 3 new + 0 from cache + 14918 written to it; output 86]
$ grep -E "^\| [0-9]+ \|" /tmp/pc/fx09/f9a/README.md | wc -l
14

The course has 10 lessons: 4 primitives (Lessons 1–4) and 6 production layers (Lessons 5–10).
[claude-haiku-4-5: first output after 0.4s, finished after 0.7s; input 6 new + 14918 from cache + 97 written to it; output 38]
[done in 2 steps, 2.1s, 50% of input tokens read from the cache]
```

Jev called this a `lookup` with 0.99 confidence, so it went to `claude-haiku-4-5`. The first output arrived after 0.9 seconds, and the whole first reply was done after 1.3. The first call wrote the whole 14,918-token prompt to the cache (`0 from cache + 14918 written to it`), which is the premium you pay once. The second call read all of it back, and wrote only what was new, 97 tokens. The task is two calls and the first one carried the premium, so over the whole task only 50% of the input came from the cache. (Its `grep` counted 14 table rows, not 10; it answered from the notes it already had.) Run it again straight away:

```
[routed to lookup: claude-haiku-4-5 (Jev: lookup, 0.99)]

[claude-haiku-4-5: first output after 0.6s, finished after 1.0s; input 3 new + 14918 from cache + 0 written to it; output 82]
$ cd /tmp/pc/fx09/f9a && find lessons production -type f -name "README.md" | wc -l
find: ‘lessons’: No such file or directory
find: ‘production’: No such file or directory
0

Let me check what's in the current directory:
[claude-haiku-4-5: first output after 0.4s, finished after 0.7s; input 6 new + 14918 from cache + 117 written to it; output 66]
$ pwd && ls -la
/tmp/pc/fx09/f9a
total 44
drwxr-xr-x 3 root root  4096 Oct  6 22:41 .
drwxr-xr-x 4 root root  4096 Oct  6 22:41 ..
-rw-r--r-- 1 root root 30016 Oct  6 22:41 README.md
drwxr-xr-x 3 root root  4096 Oct  6 22:41 docs

The course has 10 lessons total: 4 primitive lessons (model interface, input/output, control flow, and context) plus 6 production layers (sandboxing, guardrails, observability, resilience, performance, and evaluation).
[claude-haiku-4-5: first output after 0.5s, finished after 1.1s; input 6 new + 15035 from cache + 206 written to it; output 57]
[done in 3 steps, 2.8s, 99% of input tokens read from the cache]
```

Now the first call read all 14,918 tokens from the cache and wrote nothing. This time the model went looking for lesson folders that aren't in this folder, took a step to look around, and answered from its notes, so the task took three calls instead of two, and 99% of the input across them came from the cache. The times are about the same, as they should be for replies this short. The saving here was in the bill, not the clock, though on a long prompt a cache read is faster too.

Now three slow checks in one reply, run from this repo's root:

```
python performance.py "Simulate three slow checks, as three separate commands in one response: 'sleep 3; echo lint ok', 'sleep 3; echo types ok', 'sleep 3; echo tests ok'. Then summarize in one line."
```

```
[routed to edit: claude-sonnet-5-5 (Jev: work, 0.49, not sure enough)]

[claude-sonnet-5-5: first output after 0.7s, finished after 1.8s; input 4 new + 0 from cache + 19199 written to it; output 170]
$ sleep 3; echo lint ok
$ sleep 3; echo types ok
$ sleep 3; echo tests ok
[3 commands: 3.0s together, 9.0s one after another]
lint ok

types ok

tests ok

All three checks passed: lint, types and tests each reported ok.
[claude-sonnet-5-5: first output after 0.8s, finished after 0.8s; input 2 new + 19199 from cache + 264 written to it; output 22]
[done in 2 steps, 5.7s, 50% of input tokens read from the cache]
```

Jev leaned towards `work`, with 0.49 confidence, which is more model than three `echo`s need, and it wasn't sure, so the bar sent the task to the middle tier, `claude-sonnet-5-5`, instead. A router with no bar would have sent it to Opus. The commands did what they should: `3 commands: 3.0s together, 9.0s one after another`.

When Jev is sure, the bar doesn't get in the way. A task that is real work, in a folder holding only a `slow.py` that takes a few seconds to print `1000` (so there are no notes, and a prompt too short to cache until the conversation grows):

```
python performance.py "slow.py takes seconds to run. Find out why and make it fast, keeping its output the same."
```

```
[routed to work: claude-opus-5-5 (Jev: work, 0.94)]

[claude-opus-5-5: first output after 1.0s, finished after 1.2s; input 443 new + 0 from cache + 0 written to it; output 76]
$ cd /tmp/pc/fx09/f9b; ls -la; cat slow.py
total 12
drwxr-xr-x 2 root root 4096 Oct  6 22:42 .
drwxr-xr-x 5 root root 4096 Oct  6 22:42 ..
-rw-r--r-- 1 root root  192 Oct  6 22:42 slow.py
seen = []
for n in range(50_000):
    if n % 1000 not in seen:
        seen.append(n % 1000)
for n in range(50_000):
    if str(n) not in [str(s) for s in seen]:
        pass
print(len(seen))

The second loop rebuilds a 1,000-item string list on each of its 50,000 passes (~50M operations). The first loop also does list membership checks.
[claude-opus-5-5: first output after 1.6s, finished after 4.9s; input 2 new + 0 from cache + 704 written to it; output 382]
$ cd /tmp/pc/fx09/f9b; cp slow.py /tmp/slow_orig.py; cat > slow.py <<'EOF'
seen = []
seen_set = set()
for n in range(50_000):
    m = n % 1000
    if m not in seen_set:
        seen_set.add(m)
        seen.append(m)
seen_strs = {str(s) for s in seen}
for n in range(50_000):
    if str(n) not in seen_strs:
        pass
print(len(seen))
EOF
time python3 /tmp/slow_orig.py; time python3 slow.py
/bin/sh: 15: time: not found
/bin/sh: 15: time: not found

(exit 127)

[claude-opus-5-5: first output after 4.4s, finished after 5.6s; input 2 new + 704 from cache + 423 written to it; output 141]
$ cd /tmp/pc/fx09/f9b; for f in /tmp/slow_orig.py slow.py; do s=$(date +%s.%N); python3 $f; e=$(date +%s.%N); echo "$f: $(echo "$e - $s" | bc)s"; done
1000
/tmp/slow_orig.py: 4.157177278s
1000
slow.py: .034694657s

slow.py now runs in about 0.03s instead of 4.2s, and still prints `1000`. I ran both versions and compared the output.

**Why it was slow:** the second loop rebuilt `[str(s) for s in seen]`, a list of 1,000 strings, on every one of its 50,000 passes, then searched that list one item at a time. That's about 50 million operations. The first loop had a smaller version of the same problem: checking `in seen` on a list scans the whole list each time.

**Fix:**
- The first loop now tracks seen values in a set, which checks membership in one step. It still fills the `seen` list in the same order.
- The second loop now builds the strings once, before the loop, as a set.

The second loop has no effect on the output (its body is just `pass`), so it could be deleted entirely. I kept it in case it stands in for real work. The original is backed up at `/tmp/slow_orig.py`.
[claude-opus-5-5: first output after 1.4s, finished after 4.3s; input 2 new + 1127 from cache + 184 written to it; output 310]
[done in 4 steps, 20.8s, 51% of input tokens read from the cache]
```

`work`, 0.94, so `claude-opus-5-5`, with high effort. It read the file, found the list rebuilt on every pass, rewrote it, and timed both versions (once `time` turned out not to be there): 4.2 seconds down to 0.03, same output. It backed up the original in `/tmp`, which I deleted afterwards. This file runs commands on this machine with no sandbox, as Lesson 3's does, so run it somewhere you can afford to.

And the fallback. The first task again, with a key Jev doesn't accept:

```
TYPESAFE_API_KEY=not-a-key python performance.py "how many lessons are in this course? answer in one sentence"
```

```
[routed to edit: claude-sonnet-5-5 (no answer from Jev (TypeSafeAuthenticationError))]
The course has ten lessons: four primitive lessons (model interface, input and output, control flow, context) and six production layers (sandboxing, guardrails, observability, resilience, performance, evaluation).
[claude-sonnet-5-5: first output after 0.7s, finished after 1.4s; input 4 new + 0 from cache + 19141 written to it; output 65]
[done in 1 steps, 1.4s, 0% of input tokens read from the cache]
```

The call to Jev failed, the failure was caught, and the task went to the middle tier and was answered. Nothing stopped; the only cost was a bigger model than a lookup needed.

## What to take away

**The rule:** don't resend what hasn't changed, don't send what isn't needed, and don't wait for things one at a time that could be waiting together. Mark the stable start of the request, and the end of the conversation, so the model only reads what's new. Cut what a tool returns to the part that matters. Send the small jobs to the small model. And when the model has asked for several things at once, run them at once.

Notice what Performance never does. It sits in context, the model interface and output, and it leaves the other primitives alone. Control flow is the same loop with the same stops: the number of calls and steps is exactly what it was, and the loop doesn't know that some of them were cheaper. Input is untouched: the person's task is read the way it always was. And inside each of the three it changes how, not what: context still decides what the request holds, only marked so that it can be reused, the model interface still sends a request and gets a response, only to a smaller model when the job is a summary, and output still runs what the response asks for, only together, and stopped together.

**What's missing:** performance makes a run faster and cheaper, and it doesn't tell you the run was *as good*. Every saving here is a bet. A trimmed result might have cut the line that mattered, a summary from the small model might have lost a fact, the router might send a hard task to a weak model, and parallel commands can quietly depend on each other in a way the model didn't notice. Nothing in the harness would show it. The trace would show a faster, cheaper run, and you'd have no way to know whether it did the job. What's missing is a way to measure whether the agent still does its job, on tasks with known answers, every time you change anything, this lesson's changes included. That's evaluation.

**→ [Lesson 10: Evaluation](../10-evaluation/)**
