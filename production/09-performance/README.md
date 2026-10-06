# Lesson 9: Performance

> 🎥 **Video:** coming soon

Lesson 8 made the agent keep going when something fails. A run that finishes but takes ten minutes and costs ten dollars is still a run you'll think twice about starting. Over a long task two things add up: the time you wait and the tokens you pay for.

Performance is how fast the agent responds and how much each task costs. Those two are one subject because they come from the same place. Time is spent waiting: on the model to read a request, on the model to write a reply, on a command to finish. Tokens are spent on every request: the more the model reads, the more it costs and the longer it takes. So performance isn't one mechanism. It's a few small ones, spread over the primitives where the time and the tokens go.

This is a production layer, so it adds hardening, not a new primitive. It's **built on context, the model interface and output**. Context decides what the request holds (Lesson 4), the model interface sends it and brings the reply back (Lesson 1), and output runs what the reply asks for (Lesson 2). Everything below happens inside those three. The loop that connects them, the person's input and the sandbox are left as they are.

The mechanism, first in context, because it's where most of the tokens go. Remember what the loop does (Lesson 3): every pass sends the *whole* request again, the instructions, the tools and every message so far. Nothing is remembered on the model's side between calls, so a task of twenty steps makes the model read the same opening twenty times, and each time the conversation is a little longer. The cost of a task isn't the sum of what was said; it's the sum of everything resent.

**Prompt caching** is the fix, and it works because the request is a *prefix*. The model reads the request in a fixed order: the tools, then the instructions, then the messages. The API can remember what it already worked out for the start of a request, and if the next request begins with exactly the same tokens, it picks up from there and only reads the new end. You mark where you want the remembering to end with a `cache_control` block. Reading from the cache costs a fraction of normal input (a tenth, at the time of writing) and is faster, and writing to it costs a little more than normal (a quarter more). So the first call pays slightly extra and every call after it, within five minutes of the last one, gets a discount on the part that hasn't changed. Three consequences follow:

- *The match has to be exact.* One changed character early in the request and everything after it is new. That's why Lesson 4's system prompt has the date and not the time: a timestamp would make every call a miss. Anything that changes goes at the end, never at the start.
- *There's a minimum.* A prefix shorter than a minimum, from 512 to 4,096 tokens depending on the model (512 for this course's Sonnet 5.5, 4,096 for Haiku 4.5), isn't cached, and nothing tells you. quark's system prompt is over five thousand tokens, mostly the copy of its own code, so it qualifies.
- *The cache belongs to one model.* Switch models and you start again.

The system prompt has been marked since Lesson 4. What's new is the other end: the conversation. A second mark on the last message means each call pays full price only for what's new since the previous call: the last reply and the last result.

Context has a second, plainer lever: send less. A command that prints a whole file puts the whole file in the working memory, and from then on it's resent on every call, cached or not. So the harness caps what one tool result may contribute. It keeps the start and the end, which is where headers and errors usually are, and says how much it cut.

Then the model interface, where the time goes while you wait. Two things. The first is *streaming*. Lesson 1's `model_interface.py` streamed so that a long reply wouldn't hit a timeout. It also changes what a person experiences. A reply that takes eight seconds to write arrives all at once after eight seconds, or arrives word by word starting after half a second. The total time is the same and the wait feels completely different, so the harness prints the text as it arrives. The second is *which model a kind of request goes to*. Not every request needs the biggest model. Summarizing a working memory to make room (Lesson 4's compaction) is a plain task that a smaller, faster, cheaper model does well, so that one request always goes to one. That's a fixed setting of the request, like `max_tokens`, and it belongs to the model interface, as Lesson 8's backup model does. Deciding the model while the harness runs, per task or per step, is a different thing: that's routing, which Lesson 3 put in control flow, and the fuller example below shows it.

Last, output, where the time goes while a command runs. When the model needs three things, it can ask for all three in one reply: the response has three `tool_use` blocks. The harness has been handling them one at a time, in order. But the model asked for them together, in one reply, before seeing any result, so it has already decided that none of them needs another's answer. Nothing stops the harness running them at the same time, and then the wait is the slowest command and not the sum of all of them. Two details. Every result must still go back, in order, each with the id of the request it answers, because the API checks that. And the questions Lesson 6's gate asks a person are asked first, one at a time, before anything starts, because you can't have three prompts talking over each other.

Nothing here makes the model smarter or the answer better. It makes the same work cheaper and sooner, and the one thing it has to be careful about is not making it different.

## The worked example

Here's Lesson 8's agent with performance added. It's the whole of [`quark.py`](./quark.py), with the system prompt shortened to `...` as before. The new code is the `FAST` model and the `ask()` that streams, `trim()` and `cached()`, `execute()` and the tool section of the loop. The rest is Lesson 8 unchanged, resilience, sandbox, guardrails and tracing included:

```python
import subprocess, sys, os, datetime, json, time, uuid, re, atexit
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic, BadRequestError, APIConnectionError, APIStatusError

client = Anthropic(timeout=300, max_retries=3)
run = uuid.uuid4().hex[:8]
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def trace(**event):
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "run": run, **event}) + "\n")


MODELS, FAST = ["claude-sonnet-5-5", "claude-opus-5-5"], ["claude-haiku-4-5"]
class Down(Exception): pass
def ask(models=MODELS, live=False, **request):
    for model in models:
        try:
            with client.messages.stream(model=model, **request) as stream:
                shown = False
                for text in stream.text_stream:
                    if live: print(text, end="", flush=True); shown = True
                if shown: print()
                return stream.get_final_message()
        except (APIConnectionError, APIStatusError) as e:
            if isinstance(e, APIStatusError) and e.status_code < 500 and e.status_code != 429: raise
            trace(event="model_failed", model=model, error=type(e).__name__)
    raise Down()


MAX_RESULT = 20_000
def trim(text):
    if len(text) <= MAX_RESULT: return text
    return text[:MAX_RESULT // 2] + f"\n[... {len(text) - MAX_RESULT} characters cut ...]\n" + text[-MAX_RESULT // 2:]
def cached(working_memory):
    last = working_memory[-1]
    blocks = [{"type": "text", "text": last["content"]}] if isinstance(last["content"], str) else list(last["content"])
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return working_memory[:-1] + [{"role": last["role"], "content": blocks}]


SESSION = ".quark/session.json"
def save(task, working_memory):
    os.makedirs(".quark", exist_ok=True)
    with open(SESSION + ".tmp", "w") as f: json.dump({"task": task, "working_memory": working_memory}, f, default=lambda b: b.model_dump(exclude_none=True))
    os.replace(SESSION + ".tmp", SESSION)
def unfinished():
    if not os.path.exists(SESSION): return None
    saved = json.load(open(SESSION))
    try: answer = input(f"unfinished run: {saved['task'][:60]!r}. pick it up? [y/N] ").strip().lower()
    except EOFError: answer = ""
    if answer != "y": return None
    working_memory = saved["working_memory"]
    if working_memory[-1]["role"] == "assistant":
        lost = [b for b in working_memory[-1]["content"] if b["type"] == "tool_use"]
        if not lost: return os.remove(SESSION)
        working_memory.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b["id"], "content": "interrupted: the harness stopped before this finished, so it may or may not have run. Check before repeating it.", "is_error": True} for b in lost]})
    return saved["task"], working_memory


IMAGE, TIMEOUT = "python:3.13-slim", 30
box = f"quark-{run}"
def sandbox():
    where = os.getcwd()
    up = subprocess.run(["docker", "run", "-d", "--rm", "--name", box, "--network", "none", "--memory", "512m", "--cpus", "1", "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp", "-e", "HOME=/tmp", "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{where}:{where}", "-w", where, IMAGE, "sleep", "infinity"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if up.returncode: sys.exit(f"[no sandbox, so nothing runs: {up.stdout.strip()}]")
    atexit.register(lambda: subprocess.run(["docker", "rm", "-f", box], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))


def execute(cmd):
    start = time.time()
    done = subprocess.run(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    if done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
    trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
    return trim(done.stdout) or f"(exit {done.returncode})"


MAX_STEPS, MAX_TOKENS = 20, 200_000
SAFE = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "date", "echo", "du", "df", "stat", "file", "uniq"}
DENY = re.compile(r"\bsudo\b|rm\s+-\w*[rf]|mkfs|git\s+push|(curl|wget).*\|\s*(ba)?sh|\.env\b")
def guard(cmd):
    if DENY.search(cmd): return "blocked by policy"
    if not re.search(r"[;&<>$`\n(]", cmd) and all((p.split() or [""])[0] in SAFE for p in cmd.split("|")): return None
    try: answer = input(f"allow `{cmd}`? [y/N] ").strip()
    except EOFError: answer = ""
    return None if answer.lower() == "y" else f"the person said no: {answer or 'no'}"

def mechanics(): return "\n".join('def system(): return "<system prompt redacted so you can see your self mechanics in harness>"' if l.startswith("def system():") else l for l in open(__file__).read().split("\n"))
def system(): return [{"type": "text", "text": f"# Self Model\n\n**Identity:** You are quark ... **Where:** {os.getcwd()}\n**When:** {datetime.date.today()} ... ```python\n{mechanics()}\n```", "cache_control": {"type": "ephemeral"}}]

def compact(working_memory, drop):
    turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
    if drop > len(turns): sys.exit("[working memory can't be summarized small enough]")
    keep = working_memory[turns[drop]:] if drop < len(turns) else [working_memory[turns[-1]]]
    summary = ask(models=FAST, max_tokens=2048, system=system(), messages=keep + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}])
    gist = next((b.text for b in summary.content if b.type == "text"), "")
    return [{"role": "user", "content": f"[your prior working memory, summarized] {gist}"}]


resumed = unfinished()
task = resumed[0] if resumed else " ".join(sys.argv[1:]) or input("> ")
chat = len(sys.argv) < 2
working_memory, drop, steps, spent = resumed[1] if resumed else [{"role": "user", "content": task}], 0, 0, 0
trace(event="start", task=task, resumed=bool(resumed))
sandbox()

while True:
    save(task, working_memory)
    if steps >= MAX_STEPS or spent >= MAX_TOKENS:
        print(f"[stopped: {steps} steps, {spent} tokens]")
        if not chat or (task := input("\n> ")) == "/q": break
        working_memory.append({"role": "user", "content": task})
        steps, spent = 0, 0
        continue
    try:
        if drop:
            working_memory, drop = compact(working_memory, drop), 0
        start = time.time()
        reply = ask(live=True, max_tokens=16384, system=system(), tools=tools, messages=cached(working_memory))
        trace(event="model", seconds=round(time.time() - start, 2), stop_reason=reply.stop_reason, input_tokens=reply.usage.input_tokens, output_tokens=reply.usage.output_tokens, cache_read=reply.usage.cache_read_input_tokens, cache_write=reply.usage.cache_creation_input_tokens)
        steps += 1
        spent += reply.usage.input_tokens + reply.usage.output_tokens + reply.usage.cache_read_input_tokens + reply.usage.cache_creation_input_tokens
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
        trace(event="too_long", drop=drop)
        continue
    except Down:
        sys.exit("[the model isn't answering. Everything so far is saved; run quark again to pick it up]")

    working_memory.append({"role": "assistant", "content": reply.content})
    save(task, working_memory)
    refused, pending = {}, {}
    for block in reply.content:
        if block.type == "tool_use":
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if not cmd or (reply.stop_reason == "max_tokens" and block is reply.content[-1]):
                refused[block.id] = "your request was cut off at the token limit, so it was not run. Send it again, shorter."
            elif (no := guard(cmd)):
                refused[block.id] = no
            else:
                pending[block.id] = cmd
    with ThreadPoolExecutor() as pool:
        outputs = dict(zip(pending, pool.map(execute, pending.values())))
    results = []
    for block in reply.content:
        if block.type == "tool_use":
            text = refused.get(block.id) or outputs[block.id]
            print(f"[{text}]" if block.id in refused else text)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": text, **({"is_error": True} if block.id in refused else {})})

    if results:
        working_memory.append({"role": "user", "content": results})
        continue
    os.remove(SESSION)
    if not chat or (task := input("\n> ")) == "/q":
        break
    working_memory.append({"role": "user", "content": task})
    steps, spent = 0, 0
```

There are six additions.

**`ask()`.** It gains two arguments and streams. `models` says which models to try, defaulting to the same list as before, so everything Lesson 8 added (the backup, the failure trace, `Down`) still applies. `live=True` prints each piece of text as it arrives, and a newline when the text ends. `client.messages.stream(...)` returns the same final message as `create` did, with `get_final_message()`, so nothing after the call changes. This is why the loop no longer prints text blocks itself: by then they've already been shown.

**`FAST`.** A smaller, quicker model, used by `compact()` and nothing else. That's the whole of per-request choice here: one request, the summary, goes to a different model than the work. One thing to watch is that a smaller model may have a smaller window, so a working memory that was too long for the main model might be too long for this one too. If it is, the call fails with the same "prompt is too long" error, and Lesson 4's mechanism handles it the way it always has: it drops the oldest turns and tries again.

**`cached()`.** It returns the messages with `cache_control` on the last block of the last message, which is always a user message: the task, or the results of the tools. A plain string is turned into a text block first, because a mark has to sit on a block. It builds a copy, so the working memory that `save()` writes to disk has no marks in it. The cache looks back from the mark for the longest prefix it already holds, so the mark from the previous call, two messages back, is found without any bookkeeping.

**`trim()`.** A result over `MAX_RESULT` characters is cut to its first and last halves with a note saying how many characters went. It's applied in `execute()`, before the result is printed or stored, so the person sees what the model sees. The trace still records the full length.

**The tool section.** Lesson 8 handled each tool block from start to finish before looking at the next. Now it's three passes over the blocks. The first goes through them in order, prints each command, and decides what happens to it: cut off, refused by the guard, or approved. The guard's questions are asked here, one at a time. Approved commands go in `pending`. The second pass is the one line that matters: `pool.map(execute, pending.values())` runs them all at the same time on threads, and `map` returns the outputs in the order the commands went in. Threads are enough, because each one is just waiting on a `docker exec`. The third pass prints the results and builds the `tool_result` list, in the order the model asked, with refusals marked as errors exactly as before.

**The system prompt.** One sentence changed. It used to say `One bash invocation per response`, which tells the model *not* to do what this layer is for. It now says commands that don't depend on each other can go in one response and will run at the same time. A harness can only run in parallel what the model asks for in parallel, and the model asks for what it's told it can have.

Everything else is unchanged on purpose. The guard still runs before the box does. The sandbox still holds every command, concurrent or not. Tracing still records each one, and since the tool events are written by the threads, they now appear in the order they finished. Saving still happens before any tool runs.

## Run it

You need what Lesson 8 needed: Docker running, and `uv`. Start in a scratch folder, not in this repo, because the box mounts it and the trace goes in it. Each run below is `uv run --project /path/to/building-agents /path/to/building-agents/production/09-performance/quark.py`, which I'll write as `quark.py`, and the same with `08-resilience` for the one comparison. Answers piped to prompts aren't echoed, so a prompt is followed directly by whatever comes next. The traces are read with [`jq`](https://jqlang.org), one line per event.

**Running at the same time.** Three slow commands that don't depend on each other. `sleep 3` stands in for a lint, a type check and a test run. First Lesson 8's `quark.py`, as a baseline, on this task:

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
[wall: 13.0s]
```

The trace shows that the model asked for all three in one reply, and Lesson 8 ran them one after another:

```
{"event":"model","seconds":1.52,"input_tokens":145,"cache_read":0,"cache_write":4727}
{"event":"tool","seconds":3.08,"cmd":"sleep 3; echo lint ok"}
{"event":"tool","seconds":3.08,"cmd":"sleep 3; echo types ok"}
{"event":"tool","seconds":3.09,"cmd":"sleep 3; echo tests ok"}
{"event":"model","seconds":1.03,"input_tokens":407,"cache_read":4727,"cache_write":0}
```

Three seconds each, nine in total, and a wall time of 13 seconds with two model calls. Now the same task with this lesson's `quark.py`:

```
$ sleep 3; echo lint ok
allow `sleep 3; echo lint ok`? [y/N] $ sleep 3; echo types ok
allow `sleep 3; echo types ok`? [y/N] $ sleep 3; echo tests ok
allow `sleep 3; echo tests ok`? [y/N] lint ok

types ok

tests ok

Lint, types, and tests all passed.
[wall: 6.94s]
```

```
{"event":"model","seconds":1.71,"input_tokens":4,"cache_read":0,"cache_write":5323}
{"event":"tool","seconds":3.08,"cmd":"sleep 3; echo lint ok"}
{"event":"tool","seconds":3.08,"cmd":"sleep 3; echo tests ok"}
{"event":"tool","seconds":3.08,"cmd":"sleep 3; echo types ok"}
{"event":"model","seconds":0.9,"input_tokens":2,"cache_read":5323,"cache_write":264}
```

All three questions come first, then the three commands start together, and the commands' lines in the trace came out in the order they *finished*, which isn't the order they were asked for. The results still went back in the order they were asked, each with its request's id, and the printed output is in that order too. Three seconds of waiting instead of nine, 6.9 seconds against 13.0 for the whole run.

**Caching.** A task of three steps, in a folder holding a copy of `lessons/`. Each step is one command:

```
Find the quark.py files under lessons/ and count the lines in each. Then grep the import lines of the longest one. Then say in one sentence what those imports tell you. One command per step.
```

```
$ find lessons/ -name quark.py -exec wc -l {} +
allow `find lessons/ -name quark.py -exec wc -l {} +`? [y/N]   30 lessons/03-control-flow/quark.py
  48 lessons/04-context/quark.py
  21 lessons/02-input-and-output/quark.py
   9 lessons/01-model-interface/quark.py
 108 total

$ grep -nE '^\s*(import|from) ' lessons/04-context/quark.py
allow `grep -nE '^\s*(import|from) ' lessons/04-context/quark.py`? [y/N] 1:import subprocess, sys, os, datetime
2:from anthropic import Anthropic, BadRequestError

The longest file is `lessons/04-context/quark.py`, at 48 lines. Its imports show a script that runs shell commands (`subprocess`), reads arguments and exits (`sys`), uses the filesystem (`os`) and timestamps (`datetime`), and calls the Anthropic API. It also handles `BadRequestError`, most likely for prompts that are too long, which fits the "context" lesson.
[wall: 7.91s]
```

```
jq -c 'select(.event=="model") | {seconds,input_tokens,output_tokens,cache_read,cache_write}' .quark/traces.jsonl
```

```
{"seconds":1.58,"input_tokens":4,"output_tokens":69,"cache_read":5182,"cache_write":129}
{"seconds":1.45,"input_tokens":2,"output_tokens":76,"cache_read":5311,"cache_write":155}
{"seconds":3.27,"input_tokens":2,"output_tokens":136,"cache_read":5466,"cache_write":119}
```

Look at the columns. `input_tokens` is what was read at full price, and it's 4, then 2, then 2. Everything else came from the cache or went into it. The first call found about 5,200 tokens of system prompt already cached, because I had run quark in this folder a minute before and the system prompt is the same text from one run to the next. So the cache outlasts a run, as long as the next one starts within five minutes. In the same call, 129 tokens, the task, were written to the cache. Each later call read what the previous one had written, 5,311 and then 5,466 tokens, and wrote only what was new: the last reply and its result, 155 and 119 tokens. The harness resent about 5,500 tokens each time and paid full price for about 150 of them.

**Trimming.** A command that prints a lot. The folder has a copy of `docs/`, and the task is:

```
cat docs/the-model.md, then tell me in one sentence what its first heading says.
```

The file is 25,327 characters, more than `MAX_RESULT`. The output printed 20,000 of them, so I'm showing only its first line, then the lines around the cut (each cut to 100 characters), then the end:

```
$ cat docs/the-model.md
...
- **Attention variants.** Plain multi-head attention (MHA) is legacy at this 
[... 5327 characters cut ...]
ution over the next token, with 'Paris' highlighted at 0.78 as the correct target. A dashed feedback
...
The first heading, "The model: what the harness wraps", introduces the model as the first of an agent's two primitives (TokensOut = Model(TokensIn)), the thing the harness wraps.
[wall: 4.34s]
```

```
{"event":"model","seconds":1.22,"input_tokens":4,"cache_read":0,"cache_write":5281}
{"event":"tool","seconds":0.08,"chars":25327}
{"event":"model","seconds":1.51,"input_tokens":2,"cache_read":5281,"cache_write":6538}
```

The trace's `chars` is the length before trimming, 25,327. The second model call wrote 6,538 tokens to the cache, which is what the trimmed result came to: the 5,327 characters that were cut are 5,327 characters that every later call in this run would otherwise have resent.

Two things from this layer don't show in pasted text. **Streaming** is the text appearing as it's written, and a transcript can't show when it appeared; the fuller example below measures it. And **compaction on the fast model** only runs when the working memory is full, which none of these runs got near. I checked that call separately, by calling `compact()` on a three-message working memory, and the fast model answered it, but I didn't stage a full-window run.

## Going further

**What else performance can be:** quark has one cache mark on the conversation, one trim, one fast model and one thread pool. These are the choices you make when you build it.
- **What gets cached, and for how long.** quark marks two places: the system prompt and the end of the conversation. You can mark up to four, for instance after the tools, which rarely change, so that a change to the instructions doesn't throw them away. The default lifetime is five minutes since the cache was last used; there's a longer, one-hour option, which costs more to write and suits an agent that waits on people. And whatever you do, don't edit the middle of the conversation: changing an early message invalidates everything after it, which is why compaction, which rewrites the history, is paid for with a full-price call.
- **What goes in the request.** Cutting a tool result to its start and end, as quark does. Clearing *old* tool results once the model has acted on them. Summarizing, as in Lesson 4. Or not loading things up front at all: put a short list of what's available in the request, and let the model fetch the one it needs (that's how the skills in Lesson 4's fuller example work). The cheapest token is the one that was never sent.
- **How much comes back.** Output tokens cost more than input tokens and take longer to produce, so a short answer is faster and cheaper than a long one. `max_tokens` is a cap and not a goal; the instruction "be brief" does more. A lower thinking effort for simple tasks saves the time spent thinking before the first word.
- **Which model, and when.** quark sends one request, the summary, to a faster model. The fuller example sends a whole task to one by asking a small model how hard it is. You could instead switch by step (a cheap model for reading files, a strong one for deciding what to change), at the price of the cache restarting each time you switch. Deciding per task or per step is routing, so that part is control flow.
- **How the reply arrives.** Streamed to the person, as in quark. Or streamed so a tool can start as soon as the block that asks for it is complete, before the model has finished writing the rest of its reply. Or not streamed at all, when nobody is waiting.
- **How many at once.** Tools at the same time, as in quark, with a cap on how many so that twenty requests don't start twenty heavy processes. Whole model calls in parallel is a different thing, a way of arranging the work, and that's control flow (Lesson 3's parallelization workflows). For work nobody is waiting on, there's the batch interface: many requests handed over together, answered within a day, at about half the price.
- **When the work is done.** A cache can be warmed before it's needed: send the long opening of a task while the person is still typing the question, and the first real call finds it ready.

It can be a product on its own. The caching, the model choice and the batch interface are features of the API itself, so you use them by sending the right settings, and the Lesson 1 gateways, [LiteLLM](https://www.litellm.ai) and [OpenRouter](https://openrouter.ai), can choose a model per request, or cache whole responses, for you. And providers compete on speed alone, serving models on hardware built for it, which makes every call faster without the harness changing at all. The trade-off is the usual one: the more of the layer you hand to a product, the less of your own agent you can see.

The fuller example, [`performance.py`](./performance.py), shows more of that list. It's Lesson 3's agent loop (no memory, no tracing, no guardrails, no sandbox, no resilience), written with the async client, so performance is all there is to look at. It does everything quark does, and it measures itself: every call prints how long until the first output arrived, how long it took, and how its input tokens split into new, read from the cache and written to it. It asks a small model how hard the task is and picks the model and thinking effort from a table. Its system prompt holds the project's README and `docs/`, about ten thousand tokens, so there's something worth caching. And its commands run together, up to four at a time, and it prints how long that took against how long running them in turn would have. Here it is, all of it:

```python
import asyncio, glob, os, sys, time
from anthropic import AsyncAnthropic

client = AsyncAnthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

# Control flow: which model answers is chosen per task, by a small fast model. That's routing (Lesson 3). (The cache belongs to one model, so
# this is decided once per task, not once per step: switching mid-task would start the cache over.)
ROUTER = "claude-haiku-4-5"
TIERS = {                                    # tier -> (model, effort)
    "quick":    ("claude-haiku-4-5", None),
    "standard": ("claude-sonnet-5-5", "medium"),
    "deep":     ("claude-opus-5-5", "high"),
}
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

async def route(task):
    reply = await client.messages.create(model=ROUTER, max_tokens=10, messages=[{"role": "user", "content":
        "How much model does this task need? quick: one lookup or one simple command. standard: a few steps. "
        "deep: hard reasoning, debugging, or code that must be right. Reply with one word: quick, standard or deep.\n\nTask: " + task}])
    word = next((b.text.strip().lower() for b in reply.content if b.type == "text"), "")
    return word if word in TIERS else "standard"

async def call(messages, tier):
    # Model interface: streamed, so the person reads the answer as it is written, and timed, so you can see it.
    model, effort = TIERS[tier]
    settings = {"output_config": {"effort": effort}} if effort else {}
    start, first = time.time(), None
    async with client.messages.stream(model=model, max_tokens=16384, system=SYSTEM, tools=tools, messages=cached(messages), **settings) as stream:
        async for event in stream:
            if first is None and event.type == "content_block_start": first = time.time() - start
            if event.type == "text": print(event.text, end="", flush=True)
        reply = await stream.get_final_message()
    u = reply.usage
    print(f"\n[{model}: first output after {first or 0:.1f}s, finished after {time.time() - start:.1f}s; "
          f"input {u.input_tokens} new + {u.cache_read_input_tokens} from cache + {u.cache_creation_input_tokens} written to it; output {u.output_tokens}]")
    return reply

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
    task = " ".join(sys.argv[1:]) or input("> ")
    tier = await route(task)
    print(f"[routed to {tier}: {TIERS[tier][0]}]")
    messages, start, seen = [{"role": "user", "content": task}], time.time(), [0, 0]
    for step in range(1, MAX_STEPS + 1):
        reply = await call(messages, tier)
        seen[0] += reply.usage.cache_read_input_tokens
        seen[1] += reply.usage.input_tokens + reply.usage.cache_read_input_tokens + reply.usage.cache_creation_input_tokens
        messages.append({"role": "assistant", "content": reply.content})
        calls = [b for b in reply.content if b.type == "tool_use"]
        if not calls:
            print(f"[done in {step} steps, {time.time() - start:.1f}s, {seen[0] / max(seen[1], 1):.0%} of input tokens read from the cache]")
            return
        for b in calls: print(f"$ {b.input.get('cmd')}")
        began = time.time()
        done = await asyncio.gather(*(bash(b.input["cmd"]) for b in calls if b.input.get("cmd")))
        together, alone = time.time() - began, sum(took for _, took in done)
        if len(calls) > 1: print(f"[{len(calls)} commands: {together:.1f}s together, {alone:.1f}s one after another]")
        outputs = iter(done)
        results = []
        for b in calls:
            if b.input.get("cmd"): text, failed = next(outputs)[0], False
            else: text, failed = "your request was cut off at the token limit, so it was not run. Send it again, shorter.", True
            print(text)
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": text, "is_error": failed})
        messages.append({"role": "user", "content": results})
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")

asyncio.run(main())
```

There's a lot of it that's the same as quark, so here is what's different.

**`notes()` and `SYSTEM`.** The agent starts every task knowing the project's `README.md` and `docs/*.md`, whatever is in the folder it's run from. It's the same text every time, with no date or clock in it, which is what lets the cache recognize it. It's also what makes the prompt long enough to be cached at all: without it, the cache mark would silently do nothing.

**`route()` and `TIERS`.** This is routing, which Lesson 3 put in control flow: sending a task down a different path, here a different model, is a decision about the work, unlike Lesson 8's backup model, which only steps in when the first is down. It's in this lesson because it's one of the biggest levers on cost, so this fuller example reaches into control flow where `quark.py` doesn't. One call to the small model, with a ten-token limit and a prompt that asks for one word, decides how much model the task needs. The table turns that word into a model and a thinking effort, and a bad answer falls back to `standard`. It's done once per task, not once per step, for the reason from the start of the lesson: the cache belongs to a model, and a task that changes model at each step would never read what it wrote. It's a guess made by a small model, and guesses can be wrong, as the third run below shows.

**`call()`.** The streamed call. It goes through the stream's events: the first `content_block_start` is when the model began producing something, which is the number a person feels as *how long until anything happens*; `text` events are printed as they come. The line after it says which model answered and splits the input tokens. `cached()` and `trim()` are the same as quark's.

**`bash()`.** An async command with a time limit, behind a semaphore, `gate`, so that no more than `AT_ONCE` run together, and it returns how long it took.

**`main()`.** Route, then loop. After each step it adds up the tokens read from the cache against all the input tokens, and prints that share when the task is done. When there are several commands in a reply, `asyncio.gather` starts them all and returns the results in order, and a line compares the time they took together with the sum of their times alone.

Two runs on the same task, first with nothing cached and then with the cache warm. Both were run in a folder holding a copy of this repo's `README.md` and `docs/`, one I'd never run it in before so that its system prompt was new to the cache:

```
python performance.py "how many lessons are in this course? answer in one sentence"
```

```
[routed to quick: claude-haiku-4-5]

[claude-haiku-4-5: first output after 0.6s, finished after 1.0s; input 3 new + 0 from cache + 10601 written to it; output 73]
$ grep -c "^| [0-9]" /tmp/pd/f/README.md
10

There are 10 lessons in this course: 4 core lessons on the primitives and 6 production lessons (coming soon).
[claude-haiku-4-5: first output after 0.4s, finished after 0.7s; input 6 new + 10601 from cache + 84 written to it; output 32]
[done in 2 steps, 1.7s, 50% of input tokens read from the cache]
```

The router sent a one-command lookup to the quick tier, `claude-haiku-4-5`. The first output arrived after 0.6 seconds, and the whole first reply was done after 1.0. The first call wrote the whole 10,601-token prompt to the cache (`0 from cache + 10601 written to it`), which is the premium you pay once. The second call read all of it back, and wrote only what was new, 84 tokens. The task is two calls and the first one carried the premium, so over the whole task only 50% of the input came from the cache. Run it again straight away:

```
[routed to quick: claude-haiku-4-5]

[claude-haiku-4-5: first output after 0.5s, finished after 0.9s; input 3 new + 10601 from cache + 0 written to it; output 74]
$ grep -E "^\| [0-9]+ \|" README.md | wc -l
10

The harness-engineering course has 10 lessons: 4 on the core primitives and 6 on production layers.
[claude-haiku-4-5: first output after 0.8s, finished after 1.1s; input 6 new + 10601 from cache + 85 written to it; output 31]
[done in 2 steps, 1.9s, 100% of input tokens read from the cache]
```

Now the first call read all 10,601 tokens from the cache and wrote nothing, and the second call wrote only 85 new tokens, so the share of input read from the cache came out at 100% (rounded: 9 tokens were new, out of about 21,000). The times are about the same, as they should be for a reply this short. The saving here was in the bill, not the clock, though on a long prompt a cache read is faster too.

Now three slow checks in one reply, run from this repo's root:

```
python performance.py "Simulate three slow checks, as three separate commands in one response: 'sleep 3; echo lint ok', 'sleep 3; echo types ok', 'sleep 3; echo tests ok'. Then summarize in one line."
```

```
[routed to deep: claude-opus-5-5]

[claude-opus-5-5: first output after 0.7s, finished after 2.1s; input 4 new + 13541 from cache + 0 written to it; output 170]
$ sleep 3; echo lint ok
$ sleep 3; echo types ok
$ sleep 3; echo tests ok
[3 commands: 3.0s together, 9.0s one after another]
lint ok

types ok

tests ok

I ran the three simulated checks as separate commands in one response, and all three passed: lint ok, types ok, tests ok.
[claude-opus-5-5: first output after 0.9s, finished after 0.9s; input 2 new + 13805 from cache + 0 written to it; output 41]
[done in 2 steps, 6.0s, 100% of input tokens read from the cache]
```

The router called this `deep` and sent it to `claude-opus-5-5`, which is more model than three `echo`s need. That's the guess I mentioned, and I can't see why it went that way. You'd tune the router's prompt, or the table, until its mistakes cost less than it saves, and you'd want a way to know that, which is where this course is going. The commands did what they should: `3 commands: 3.0s together, 9.0s one after another`. This file runs commands on this machine with no sandbox, as Lesson 3's does, so run it somewhere you can afford to.

## What to take away

**The rule:** don't resend what hasn't changed, don't send what isn't needed, and don't wait for things one at a time that could be waiting together. Mark the stable start of the request, and the end of the conversation, so the model only reads what's new. Cut what a tool returns to the part that matters. Show the reply as it's written. Send the small jobs to the small model. And when the model has asked for several things at once, run them at once.

Notice what Performance never does. It sits in context, the model interface and output, and it leaves the other primitives alone. Control flow is the same loop with the same stops: the number of calls and steps is exactly what it was, and the loop doesn't know that some of them were cheaper. Input is untouched: the person's task is read the way it always was. And inside each of the three it changes how, not what: context still decides what the request holds, only marked so that it can be reused, the model interface still sends a request and gets a reply, only streamed, and output still runs what the reply asks for, only together.

**What's missing:** performance makes a run faster and cheaper, and it doesn't tell you the run was *as good*. Every saving here is a bet. A trimmed result might have cut the line that mattered, a summary from the small model might have lost a fact, the router might send a hard task to a weak model, and parallel commands can quietly depend on each other in a way the model didn't notice. Nothing in the harness would show it. The trace would show a faster, cheaper run, and you'd have no way to know whether it did the job. What's missing is a way to measure whether the agent still does its job, on tasks with known answers, every time you change anything, this lesson's changes included. That's evaluation.

**→ [Lesson 10: Evaluation](../10-evaluation/)**
