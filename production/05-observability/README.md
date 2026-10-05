# Lesson 5: Observability

> 🎥 **Video:** coming soon

You've built a harness that works. Now you're about to run it where you can't watch it, and you'll have questions it can't answer. Why did that take four minutes? Why did it cost that much? What did it run, in what order, and which command failed? The terminal scrolled past and the answers went with it.

Observability is a record of what the harness did, kept as it does it: every call to the model, every tool it ran, how long each took, how many tokens each cost. A harness you can't see into is one you can't trust or fix.

This is a production layer, so it adds hardening, not a new primitive. It's **built on control flow**, and everything it does stays inside it. Control flow is the one primitive that sees the whole sequence. The model interface only knows about one call, and output only knows about one tool, but the loop is where a call, the tool it asked for, and the call after that all happen, in order. So it's the one place a record of the run can be made.

The mechanism is small. Each time around the loop there are things that already exist: the clock, the `usage` that came back with the response, the exit code of the command that ran. Observability reads them off and writes them down.

- **A trace.** One line appended to a file for each thing that happened, in the order it happened. Each line is a JSON object, so you can search it afterwards with the tools you already have.
- **Timing.** Read the clock before and after a model call or a tool, and keep the difference.
- **Token accounting.** Every response says how many tokens went in and came out, and how many were read from or written to the prompt cache. Tokens times your provider's price is cost. The price isn't in the response; you keep the rates yourself.

Observability only watches. It never changes what's sent, what runs, or when the loop stops. If a trace line fails to describe what happened, you've got a wrong record, not a wrong agent.

## The worked example

Here's Lesson 4's agent with quark's observability added. It's the whole of [`quark.py`](./quark.py), with the system prompt shortened to `...` as before. Everything that's new is a line that calls `trace()` or reads the clock for it; the rest is Lesson 4 unchanged:

```python
import subprocess, sys, os, datetime, json, time, uuid
from anthropic import Anthropic, BadRequestError

client = Anthropic()
run = uuid.uuid4().hex[:8]
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def trace(**event):
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "run": run, **event}) + "\n")

def mechanics(): return "\n".join('def system(): return "<system prompt redacted so you can see your self mechanics in harness>"' if l.startswith("def system():") else l for l in open(__file__).read().split("\n"))
def system(): return [{"type": "text", "text": f"# Self Model\n\n**Identity:** You are quark ... **Where:** {os.getcwd()}\n**When:** {datetime.date.today()} ... ```python\n{mechanics()}\n```", "cache_control": {"type": "ephemeral"}}]

def compact(working_memory, drop):
    turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
    if drop > len(turns): sys.exit("[working memory can't be summarized small enough]")
    keep = working_memory[turns[drop]:] if drop < len(turns) else [working_memory[turns[-1]]]
    summary = client.messages.create(model="claude-sonnet-5-5", max_tokens=2048, system=system(), messages=keep + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}])
    gist = next((b.text for b in summary.content if b.type == "text"), "")
    return [{"role": "user", "content": f"[your prior working memory, summarized] {gist}"}]


task = " ".join(sys.argv[1:]) or input("> ")
chat = len(sys.argv) < 2
working_memory, drop = [{"role": "user", "content": task}], 0
trace(event="start", task=task)

while True:
    try:
        if drop:
            working_memory, drop = compact(working_memory, drop), 0
        start = time.time()
        reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, system=system(), tools=tools, messages=working_memory)
        trace(event="model", seconds=round(time.time() - start, 2), stop_reason=reply.stop_reason, input_tokens=reply.usage.input_tokens, output_tokens=reply.usage.output_tokens, cache_read=reply.usage.cache_read_input_tokens, cache_write=reply.usage.cache_creation_input_tokens)
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
        trace(event="too_long", drop=drop)
        continue

    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            start = time.time()
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            trace(event="tool", cmd=block.input["cmd"], seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})

    working_memory.append({"role": "assistant", "content": reply.content})
    if results:
        working_memory.append({"role": "user", "content": results})
        continue
    if not chat or (task := input("\n> ")) == "/q":
        break
    working_memory.append({"role": "user", "content": task})
```

There are four additions, and a function to write them with.

**`trace()`.** It appends one JSON object to `.quark/traces.jsonl`: the time, a `run` id that's the same for everything in one run, and whatever else you pass it. A file that only ever gets appended to is the simplest log there is, and each line stands on its own, so a run that crashes halfway still leaves everything before the crash.

**The start.** `trace(event="start", task=task)` marks where a run begins and what it was asked, so the lines after it have something to belong to.

**Each model call.** `start = time.time()` before the call and `trace(event="model", ...)` after it. What gets recorded is how long the call took, the `stop_reason` (did it ask for a tool or finish?), and the four token counts from `reply.usage`: `input_tokens` (not cached), `output_tokens`, `cache_read_input_tokens` and `cache_creation_input_tokens`. That's everything you need to work out cost, and the cache counts show whether the `cache_control` from Lesson 4 is doing anything.

**Each tool.** The same pair around `subprocess.run`: the command, how long it took, its exit code and how many characters it printed. A failed command is a line with a non-zero `exit`.

**Each compaction.** When the API says the prompt is too long, `trace(event="too_long", drop=drop)` records it. Lesson 4 said you're unlikely to see this happen. Now, if it does, you'll know.

Nothing else changed. The request is built by the same code and the loop stops for the same reason. The one place the model can notice is `mechanics()`: it puts quark's own file in the system prompt, so the model reads the tracing code too. That's Lesson 4's self-knowledge reading the file, not something this layer does.

## Run it

From the root of the repo, give it a task with a couple of steps:

```bash
uv run production/05-observability/quark.py "which quark.py in the lessons folder is the longest? answer in one sentence"
```

Here's one run:

```
$ cd /home/user/building-agents && find . -path ./node_modules -prune -o -name quark.py -print | xargs wc -l | sort -n | tail -5
   21 ./lessons/02-input-and-output/quark.py
   30 ./lessons/03-control-flow/quark.py
   48 ./lessons/04-context/quark.py
   59 ./production/05-observability/quark.py
  167 total

$ cd /home/user/building-agents && find lessons -name quark.py | xargs wc -lc | sort -n
   9  253 lessons/01-model-interface/quark.py
  21  920 lessons/02-input-and-output/quark.py
  30 1287 lessons/03-control-flow/quark.py
  48 5921 lessons/04-context/quark.py
 108 8381 total

The longest is `lessons/04-context/quark.py`, at 48 lines and 5,921 bytes.
```

The terminal looks the same as it did in Lesson 4. The difference is in the file:

```bash
tail -n 6 .quark/traces.jsonl
```

```
{"ts": "2026-10-05T23:21:13", "run": "b6979eac", "event": "start", "task": "which quark.py in the lessons folder is the longest? answer in one sentence"}
{"ts": "2026-10-05T23:21:15", "run": "b6979eac", "event": "model", "seconds": 1.51, "stop_reason": "tool_use", "input_tokens": 100, "output_tokens": 100, "cache_read": 0, "cache_write": 2766}
{"ts": "2026-10-05T23:21:15", "run": "b6979eac", "event": "tool", "cmd": "cd /home/user/building-agents && find . -path ./node_modules -prune -o -name quark.py -print | xargs wc -l | sort -n | tail -5", "seconds": 0.02, "exit": 0, "chars": 179}
{"ts": "2026-10-05T23:21:17", "run": "b6979eac", "event": "model", "seconds": 1.91, "stop_reason": "tool_use", "input_tokens": 288, "output_tokens": 158, "cache_read": 2766, "cache_write": 0}
{"ts": "2026-10-05T23:21:17", "run": "b6979eac", "event": "tool", "cmd": "cd /home/user/building-agents && find lessons -name quark.py | xargs wc -lc | sort -n", "seconds": 0.01, "exit": 0, "chars": 190}
{"ts": "2026-10-05T23:21:18", "run": "b6979eac", "event": "model", "seconds": 0.95, "stop_reason": "end_turn", "input_tokens": 543, "output_tokens": 37, "cache_read": 2766, "cache_write": 0}
```

Read it as the story of the run. The model was called and asked for a command, which took 0.02 seconds. It was called again with the result and asked for another, and a third call finished. Look at `cache_write` and `cache_read`: the first call wrote 2,766 tokens of system prompt to the cache, and each call after it read them back. That's Lesson 4's `cache_control` working, and you couldn't see it before.

Because it's one JSON object per line, you can ask the file questions with `jq`. quark has bash, so it can ask them too. Add up one run (use the run id from your own file):

```bash
jq -c -s 'map(select(.run=="b6979eac" and .event=="model")) | {calls: length, input: (map(.input_tokens)|add), output: (map(.output_tokens)|add), cache_read: (map(.cache_read)|add), cache_write: (map(.cache_write)|add), seconds: (map(.seconds)|add)}' .quark/traces.jsonl
```

```
{"calls":3,"input":931,"output":295,"cache_read":5532,"cache_write":2766,"seconds":4.37}
```

Three calls and 4.37 seconds waiting on the model. 931 tokens went in fresh, 295 came out, and 5,532 were read from the cache instead of being processed again. Now a run where something goes wrong:

```bash
uv run production/05-observability/quark.py "run ls /nonexistent and tell me in one sentence what happened"
```

```
$ ls /nonexistent
ls: cannot access '/nonexistent': No such file or directory

`ls /nonexistent` failed with "No such file or directory" because no file or directory exists at that path.
```

Find every command that failed, in any run:

```bash
jq -c 'select(.event=="tool" and .exit!=0)' .quark/traces.jsonl
```

```
{"ts":"2026-10-05T23:21:25","run":"eed339c8","event":"tool","cmd":"ls /nonexistent","seconds":0.0,"exit":2,"chars":60}
```

The agent shrugged that off and told you what happened. Without the trace, you'd only know if you were watching.

> The trace file only grows. Delete or rotate it when it gets big.

## Going further

**What else observability can be:** quark records one line per event: a flat log, in a file, afterwards. These are the choices you make when you build it.
- **What's recorded.** Events as they happen, or *spans*, which have a start, a duration and a parent, so a run becomes a tree. Or everything: the full request and response of every call. That's the most useful record when something goes wrong, and the biggest, and it will contain whatever the model saw, so decide what to redact.
- **Where it goes.** A file, the terminal, a database, or a collector that speaks a standard like OpenTelemetry.
- **When you see it.** After the fact, as a live line per step, or on a dashboard that alerts you.
- **What's worked out from it.** Tokens, cost, latency, cache hit rate, how often tools fail, steps per task.
- **How you ask it questions.** `grep` and `jq`, SQL, or a UI built for traces.
- **How long it's kept.** Sampling, rotation and deletion.

It can be a product on its own. Tracing platforms like [Langfuse](https://github.com/langfuse/langfuse) and LangSmith are this layer: you send them the spans and they store them, price them and show them as a tree.

Here's observability that does more of that, in [`observability.py`](./observability.py). It's built on Lesson 3's `control_flow.py`, so it has the step limit, and it has no system prompt, so its requests are just the task:

```python
import subprocess, sys, os, json, time, uuid, datetime
from collections import defaultdict
from contextlib import contextmanager
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS = 10
LOG = ".quark/spans.jsonl"
PRICE = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75}  # dollars per million tokens: example rates, use your provider's
RUN, SPANS = uuid.uuid4().hex[:8], []

@contextmanager
def span(kind, parent=None, **attrs):
    s = {"run": RUN, "span": uuid.uuid4().hex[:6], "parent": parent, "kind": kind, "start": datetime.datetime.now().isoformat(timespec="seconds"), **attrs}
    began = time.time()
    try:
        yield s
    except BaseException as e:
        s["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        s["seconds"] = round(time.time() - began, 2)
        SPANS.append(s)
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f: f.write(json.dumps(s) + "\n")

def cost(usage):
    return round(sum(usage[k] * PRICE[k] for k in PRICE) / 1_000_000, 6)

def row(spans):
    run = next((s for s in spans if s["kind"] == "run"), {})
    calls = [s for s in spans if s["kind"] == "model" and "cost" in s]
    ran = [s for s in spans if s["kind"] == "tool"]
    sent = sum(c["input"] + c["cache_read"] + c["cache_write"] for c in calls)
    problems = sum(t.get("exit") != 0 for t in ran) + sum("error" in s for s in spans)
    return f"{spans[0]['run']}  {run.get('status', 'crashed'):<10} {len(calls):>5} {len(ran):>5} {problems:>5} {sum(s['seconds'] for s in calls + ran):>6.1f}s {sent:>8} {sum(c['output'] for c in calls):>6} {sum(c['cache_read'] for c in calls) / max(sent, 1):>6.0%} ${sum(c['cost'] for c in calls):>8.4f}  {run.get('task', '')[:40]}"

HEADER = "run       status     calls tools  prob.   time     in    out  cached     cost  task"

if sys.argv[1:2] == ["report"]:
    runs = defaultdict(list)
    for line in open(LOG):
        runs[json.loads(line)["run"]].append(json.loads(line))
    print(HEADER)
    for spans in runs.values(): print(row(spans))
    sys.exit()

task = " ".join(sys.argv[1:]) or input("> ")
messages = [{"role": "user", "content": task}]

with span("run", task=task) as run:
    for step in range(1, MAX_STEPS + 1):
        with span("model", run["span"], step=step) as m:
            reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)
            u = reply.usage
            m.update(stop_reason=reply.stop_reason, input=u.input_tokens, output=u.output_tokens, cache_read=u.cache_read_input_tokens, cache_write=u.cache_creation_input_tokens)
            m["cost"] = cost(m)
        print(f"[step {step}: model {m['seconds']}s, {m['input'] + m['cache_read'] + m['cache_write']} tokens in, {m['output']} out, ${m['cost']:.4f}]")
        messages.append({"role": "assistant", "content": reply.content})
        if reply.stop_reason == "refusal":
            run["status"] = "declined"
            break
        results = []
        for block in reply.content:
            if block.type == "text":
                print(block.text)
            if block.type == "tool_use":
                print(f"$ {block.input['cmd']}")
                with span("tool", run["span"], step=step, cmd=block.input["cmd"]) as t:
                    done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    t.update(exit=done.returncode, chars=len(done.stdout))
                print(done.stdout)
                print(f"[step {step}: tool {t['seconds']}s, exit {t['exit']}]")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})
        if not results:
            run["status"] = "done"
            break
        messages.append({"role": "user", "content": results})
    else:
        run["status"] = "step limit"

print(HEADER)
print(row(SPANS))
```

- **Spans.** `span()` wraps a piece of work and writes one record when it's over: an id, the `parent` it belongs to, when it `start`ed and how many `seconds` it took. The run is the parent of every model call and tool, so the file is a tree, not just a list. If the work raises, the span records the `error` and lets the exception carry on, so a crash is in the trace and still crashes.
- **Cost.** `cost()` multiplies the four token counts by `PRICE`. The rates there are examples; the API doesn't tell you what you pay, so put in your provider's. Each model span carries its cost, and so each task has one.
- **A live line.** After every model call and tool, it prints one line: the step, how long it took, tokens in and out, cost, exit code. You see where the time and money go while it runs.
- **A summary.** When the run ends, `row()` turns its spans into one line: how it ended (`done`, `step limit`, `declined`, or `crashed` if no run span was written), calls, tools, problems, time, tokens, how much was read from the cache, cost.
- **A report.** `observability.py report` reads the whole log and prints that same line for every run. This is the part that works across runs. A trace of one run tells you what happened; a table of every run tells you what's normal.

Try it on a task with a failure and a slow step:

```bash
uv run production/05-observability/observability.py "run ls /nonexistent, then run sleep 3 as a separate command, then say what happened in one sentence"
```

Here's one run:

```
[step 1: model 1.96s, 397 tokens in, 166 out, $0.0037]
$ ls /nonexistent
ls: cannot access '/nonexistent': No such file or directory

[step 1: tool 0.0s, exit 2]
$ sleep 3

[step 1: tool 3.0s, exit 0]
[step 2: model 1.35s, 645 tokens in, 71 out, $0.0030]
`ls /nonexistent` failed with "No such file or directory" because that path doesn't exist, and `sleep 3` then ran as its own command and exited successfully (exit 0) after pausing 3 seconds.
run       status     calls tools  prob.   time     in    out  cached     cost  task
47a469d6  done           2     2     1    6.3s     1042    237     0% $  0.0067  run ls /nonexistent, then run sleep 3 as
```

The `prob.` column is 1: one tool exited non-zero. Of the 6.3 seconds, 3.0 were the `sleep`. `cached` is 0% because this agent has no system prompt to cache; quark's does, as you saw above. After a few runs, ask for the report:

```bash
uv run production/05-observability/observability.py report
```

```
run       status     calls tools  prob.   time     in    out  cached     cost  task
7941924a  done           2     1     0    2.2s      948    111     0% $  0.0045  which quark.py in the lessons folder is 
98bab13a  done           4     3     0    5.3s     5150    377     0% $  0.0211  read the file docs/the-models.md and tel
47a469d6  done           2     2     1    6.3s     1042    237     0% $  0.0067  run ls /nonexistent, then run sleep 3 as
```

One line per run. The run that went looking for a file with the wrong name took four calls and cost nearly five times the first. The spans are in `.quark/spans.jsonl`, and the slowest tool in the log is one query away:

```bash
jq -s -c 'map(select(.kind=="tool")) | sort_by(-.seconds) | .[0] | {run, step, seconds, exit, cmd}' .quark/spans.jsonl
```

```
{"run":"47a469d6","step":1,"seconds":3.0,"exit":0,"cmd":"sleep 3"}
```

The costs are computed at the example rates in `PRICE`, so they show you which run was expensive, not what you were billed.

## What to take away

**The rule:** record what the harness does as it does it: each model call, each tool, how long it took and what it cost, in a log you can search afterwards. Do it where control flow already sees the whole sequence, and read from what's already there rather than changing it.

Notice what Observability never does. It sits inside control flow's loop, but it never decides what runs next or when to stop. It leaves the other four alone. The request goes to the model and the response comes back through the model interface exactly as before; observability only reads `usage` off the response. It gathers no input, decides nothing about what the request holds (context), and runs tools the way output always did, only with a clock around them.

**What's missing:** it watches, and that's all it does. It will faithfully record a run that deleted the wrong directory, or one that looped for an hour, after it happened. The agent runs whatever the model asks, as before, and the only thing that changes is that you can see it. To act on what you see, to ask first, or to stop a run that's spending too much, the harness needs rules about what it's allowed to do.

**→ [Lesson 6: Guardrails](../06-guardrails/)**
