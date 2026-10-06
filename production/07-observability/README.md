# Lesson 7: Observability

> 🎥 **Video:** coming soon

Lessons 5 and 6 made the harness safe to leave running. Now you're about to run it where you can't watch it, and you'll have questions it can't answer. Why did that take four minutes? Why did it cost that much? What did it run, in what order, which command did the guard refuse, and which did the box kill? The terminal scrolled past and the answers went with it.

Observability is a record of what the harness did, kept as it does it: every call to the model, every tool it ran, how long each took, how many tokens each cost, and every time a guardrail said no. A harness you can't see into is one you can't trust or fix.

You might think Lesson 4 already did this. Every message is in the episode. But the episode is written **for the model**: it's what working memory would have been, so the model can search its own past. It has no timings, no token counts, no exit codes, and it shouldn't, because none of that helps the model think. The trace is written **for you**, the person running quark. Same run, two records, two readers. The paper calls this the rule of who reads it: a record for the model is context; a record for the operator is observability.

This is a production layer, so it adds hardening, not a new primitive. It's **built on control flow**, and everything it does stays inside it. Control flow is the one primitive that sees the whole sequence. The model interface only knows about one call, and output only knows about one tool, but the loop is where a call, the tool it asked for, the guard's decision and the call after that all happen, in order. So it's the one place a record of the run can be made.

The mechanism is small. Each time around the loop there are things that already exist: the clock, the `usage` that came back with the response, the exit code of the command that ran, the reason a command was refused. Observability reads them off and writes them down.

- **A trace.** One line appended to a file for each thing that happened, in the order it happened. Each line is a JSON object, so you can search it afterwards with the tools you already have.
- **Timing.** Read the clock before and after a model call or a tool, and keep the difference.
- **Token accounting.** Every response says how many tokens went in and came out, and how many were read from or written to the prompt cache. Tokens times your provider's price is cost. The price isn't in the response; you keep the rates yourself.

Observability only watches. It never changes what's sent, what runs, or when the loop stops. If a trace line fails to describe what happened, you've got a wrong record, not a wrong agent.

## The worked example

[`quark.py`](./quark.py) is Lesson 6's `quark.py` plus the trace, and nothing else: 14 lines. `time` joins the imports, and at the top of `# ── control flow ──` there's the function that writes the record:

```python
def trace(**event):                                      # observability: one line per step, for whoever runs quark
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "episode": EPISODE, **event}) + "\n")
```

Then one call wherever something happens. Each is a single line next to code that was already there:

```python
trace(event="start", input=input)
        trace(event="stopped", steps=steps, tokens=spent)
        trace(event="model", seconds=round(time.time() - start, 2), stop_reason=response.stop_reason, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens, cache_read=response.usage.cache_read_input_tokens, cache_write=response.usage.cache_creation_input_tokens)
        trace(event="too_long", drop=drop)
        trace(event="interrupted", during="saying")
                trace(event="refused", cmd=block.input["cmd"], why=no)
            trace(event="tool", cmd=block.input["cmd"], seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
        trace(event="interrupted", during="acting")
```

**`trace()`** appends one JSON object to `.quark/traces.jsonl`: the time, the **episode** this run is being written to, and whatever else you pass it. A file that only ever gets appended to is the simplest log there is, and each line stands on its own, so a run that crashes halfway still leaves everything before the crash. The `episode` field ties the two records together: from any trace line you can open the messages of the same run.

**The start** marks where a run begins and what came in.

**Each model call** is timed (`start = time.time()` before the call) and records the `stop_reason` and the four token counts from `response.usage`: new input, output, read from the cache, and written to it. That's everything you need to work out cost, and the cache counts show whether Lesson 4's `cache_control` on the system prompt is doing anything.

**Each tool** records the command, how long it took, its exit code and how many characters it printed. A failed command is a line with a non-zero `exit`; one the box killed is `137`.

**Each refusal** records the command the guard wouldn't run, and why. **Each interrupt** records that you pressed ESC, and whether quark was saying or doing something at the time. **Each limit** records the steps and tokens it stopped at. **Each compaction** records that the API said the prompt was too long.

Nothing else changed. The request is built by the same code, the same commands run in the same box, and the loop stops for the same reasons.

## Run it

In a scratch folder with a two-line `small.txt` and a 5,000-line `big.txt`. This time nothing is piped in, so there's no one to answer the guard:

```bash
uv run --project /path/to/building-agents /path/to/building-agents/production/07-observability/quark.py "which file in this folder has the most lines? answer in one sentence" < /dev/null
```

```
$ wc -l * 2>/dev/null | sort -rn | head -5
allow `wc -l * 2>/dev/null | sort -rn | head -5`? [y/N] [the person said no]
$ ls -la
total 36
drwxr-xr-x 3 root root  4096 Oct  6 20:30 .
drwxr-xr-x 3 root root    60 Oct  6 20:30 ..
drwxr-xr-x 3 root root  4096 Oct  6 20:30 .quark
-rw-r--r-- 1 root root 23893 Oct  6 20:30 big.txt
-rw-r--r-- 1 root root     8 Oct  6 20:30 small.txt

$ wc -l big.txt small.txt
 5000 big.txt
    2 small.txt
 5002 total

`big.txt` has the most lines, at 5,000, compared with 2 in `small.txt`.
```

The first command wasn't on the safe list (`2>` redirects, and `sort` isn't a reader the guard knows), so the guard asked, found no one there, and said no. The model switched to commands that were. Here's what the person running it sees afterwards, in `.quark/traces.jsonl`:

```
{"ts": "2026-10-06T20:30:11", "episode": ".quark/episodes/2026-10-06T20-30-11.jsonl", "event": "start", "input": "which file in this folder has the most lines? answer in one sentence"}
{"ts": "2026-10-06T20:30:13", "episode": ".quark/episodes/2026-10-06T20-30-11.jsonl", "event": "model", "seconds": 1.37, "stop_reason": "tool_use", "input_tokens": 95, "output_tokens": 70, "cache_read": 0, "cache_write": 7770}
{"ts": "2026-10-06T20:30:13", "episode": ".quark/episodes/2026-10-06T20-30-11.jsonl", "event": "refused", "cmd": "wc -l * 2>/dev/null | sort -rn | head -5", "why": "the person said no"}
{"ts": "2026-10-06T20:30:14", "episode": ".quark/episodes/2026-10-06T20-30-11.jsonl", "event": "model", "seconds": 1.66, "stop_reason": "tool_use", "input_tokens": 180, "output_tokens": 51, "cache_read": 7770, "cache_write": 0}
{"ts": "2026-10-06T20:30:14", "episode": ".quark/episodes/2026-10-06T20-30-11.jsonl", "event": "tool", "cmd": "ls -la", "seconds": 0.12, "exit": 0, "chars": 249}
{"ts": "2026-10-06T20:30:16", "episode": ".quark/episodes/2026-10-06T20-30-11.jsonl", "event": "model", "seconds": 1.94, "stop_reason": "tool_use", "input_tokens": 397, "output_tokens": 93, "cache_read": 7770, "cache_write": 0}
{"ts": "2026-10-06T20:30:16", "episode": ".quark/episodes/2026-10-06T20-30-11.jsonl", "event": "tool", "cmd": "wc -l big.txt small.txt", "seconds": 0.09, "exit": 0, "chars": 42}
{"ts": "2026-10-06T20:30:18", "episode": ".quark/episodes/2026-10-06T20-30-11.jsonl", "event": "model", "seconds": 1.74, "stop_reason": "end_turn", "input_tokens": 518, "output_tokens": 34, "cache_read": 7770, "cache_write": 0}
```

Every step is there: four calls, the refusal, the two commands that ran, and how long each took. Read the cache columns: the first call wrote the 7,770-token system prompt to the cache, and every call after that read it back instead of paying for it again.

Because it's one JSON object per line, you can ask the file questions with `jq`. Add up one run, by its episode:

```bash
jq -c -s --arg e ".quark/episodes/2026-10-06T20-30-11.jsonl" 'map(select(.episode==$e and .event=="model")) | {calls: length, input: (map(.input_tokens)|add), output: (map(.output_tokens)|add), cache_read: (map(.cache_read)|add), cache_write: (map(.cache_write)|add), seconds: (map(.seconds)|add)}' .quark/traces.jsonl
```

```
{"calls":4,"input":1190,"output":248,"cache_read":23310,"cache_write":7770,"seconds":6.710000000000001}
```

Now a run where things go wrong: a command that fails, and one the box kills. This uses a copy with the sandbox's `TIMEOUT` lowered to 5, `y` piped in for the guard, and the input "run ls /nonexistent, then run sleep 60 as a separate command, then say what happened in one sentence":

```
$ ls /nonexistent
ls: cannot access '/nonexistent': No such file or directory

$ sleep 60
allow `sleep 60`? [y/N] 
(killed: ran over 5 seconds or out of memory)
`ls /nonexistent` failed because the path doesn't exist, and `sleep 60` was killed after the sandbox's 5-second time limit.
```

The agent told you what happened, this time. Without the trace, you'd only know if you were watching. Here's everything that didn't go to plan, across both runs:

```bash
jq -c 'select((.event=="tool" and .exit!=0) or .event=="refused")' .quark/traces.jsonl
```

```
{"ts":"2026-10-06T20:30:13","episode":".quark/episodes/2026-10-06T20-30-11.jsonl","event":"refused","cmd":"wc -l * 2>/dev/null | sort -rn | head -5","why":"the person said no"}
{"ts":"2026-10-06T20:30:32","episode":".quark/episodes/2026-10-06T20-30-30.jsonl","event":"tool","cmd":"ls /nonexistent","seconds":0.12,"exit":2,"chars":60}
{"ts":"2026-10-06T20:30:37","episode":".quark/episodes/2026-10-06T20-30-30.jsonl","event":"tool","cmd":"sleep 60","seconds":5.1,"exit":137,"chars":46}
```

A refusal, a failure (`exit` 2) and a kill (`exit` 137, after 5.1 seconds). Each line names its episode, so you can go from "what went wrong" to "what the model was thinking" in one step.

And when you break in. In a terminal, I asked for `sleep 30`, said `y`, and pressed ESC three seconds later:

```
> run sleep 30 as one command
$ sleep 30
allow `sleep 30`? [y/N] y
[your doing stopped before done]
You interrupted me, so `sleep 30` was stopped before it finished. I didn't get an exit status. Do you want me to run it again?

The sandbox kills any command that runs past 30 seconds. A bare `sleep 30` would probably hit that limit and be killed (exit 137). If you want it to complete, I can run `sleep 25` instead.

> /q
```

The trace of that run, with only the fields that matter here:

```
{"event":"start"}
{"event":"model","seconds":1.72}
{"event":"tool","cmd":"sleep 30","seconds":3.23,"exit":137}
{"event":"interrupted","during":"acting"}
{"event":"model","seconds":2.01}
```

The command was stopped at 3.23 seconds (`exit` 137: ESC's `kill -9 -1` inside the box, which looks the same as a time-out in the trace), and the next line says why: you interrupted it while it was acting. Then one more call, for the model to acknowledge it. Its answer says it "didn't get an exit status": since Lesson 6, a stopped command's result is just `[your doing stopped before done]`, so the trace knows more about that command than the model does.

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

Here's observability that does more of that, in [`observability.py`](./observability.py). It's built on Lesson 3's `control_flow.py`, so it has the step limit, and it has no system prompt, so its requests are just the task. It also asks a second model one question about every tool result:

```python
import subprocess, sys, os, json, time, uuid, datetime
from collections import defaultdict
from contextlib import contextmanager
from anthropic import Anthropic
from typesafe_sdk import TypeSafeClient, Noul, NoulCriteria
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic()
jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # a second model, asked one question about each tool result
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS = 10
LOG = ".quark/spans.jsonl"
PRICE = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75}  # dollars per million tokens: example rates, use your provider's
RUN, SPANS = uuid.uuid4().hex[:8], []
SURE = 0.9                                               # count a tool as failed when Jev is this sure
ERROR = {"error": Noul(instructions="Does `result` show that the command failed or hit an error?",
    criteria=NoulCriteria(true="The command failed, errored, crashed, was refused or was killed, even if it printed something.",
                          false="The command worked, even if it found nothing or printed a warning."))}

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

def failed(cmd, result):
    try:
        return round(jev.system_one({"command": cmd, "result": result}, ERROR).nouls["error"].noul, 2)
    except Exception:
        return None                                      # no verdict: the span just says so

def cost(usage):
    return round(sum(usage[k] * PRICE[k] for k in PRICE) / 1_000_000, 6)

def row(spans):
    run = next((s for s in spans if s["kind"] == "run"), {})
    calls = [s for s in spans if s["kind"] == "model" and "cost" in s]
    ran = [s for s in spans if s["kind"] == "tool"]
    sent = sum(c["input"] + c["cache_read"] + c["cache_write"] for c in calls)
    problems = sum(t.get("exit") != 0 for t in ran) + sum("error" in s for s in spans)
    flagged = sum((s.get("failed") or 0) >= SURE for s in spans if s["kind"] == "jev")
    return f"{spans[0]['run']}  {run.get('status', 'crashed'):<10} {len(calls):>5} {len(ran):>5} {problems:>5} {flagged:>4} {sum(s['seconds'] for s in calls + ran):>6.1f}s {sent:>8} {sum(c['output'] for c in calls):>6} {sum(c['cache_read'] for c in calls) / max(sent, 1):>6.0%} ${sum(c['cost'] for c in calls):>8.4f}  {run.get('task', '')[:40]}"

HEADER = "run       status     calls tools  prob.  jev   time     in    out  cached     cost  task"

if sys.argv[1:2] == ["report"]:
    runs = defaultdict(list)
    for line in open(LOG):
        runs[json.loads(line)["run"]].append(json.loads(line))
    print(HEADER)
    for spans in runs.values(): print(row(spans))
    sys.exit()

input = " ".join(sys.argv[1:]) or read("> ")
messages = [{"role": "user", "content": input}]

with span("run", task=input) as run:
    for step in range(1, MAX_STEPS + 1):
        with span("model", run["span"], step=step) as m:
            output = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)
            u = output.usage
            m.update(stop_reason=output.stop_reason, input=u.input_tokens, output=u.output_tokens, cache_read=u.cache_read_input_tokens, cache_write=u.cache_creation_input_tokens)
            m["cost"] = cost(m)
        print(f"[step {step}: model {m['seconds']}s, {m['input'] + m['cache_read'] + m['cache_write']} tokens in, {m['output']} out, ${m['cost']:.4f}]")
        messages.append({"role": "assistant", "content": output.content})
        if output.stop_reason == "refusal":
            run["status"] = "declined"
            break
        input = []
        for block in output.content:
            if block.type == "text":
                print(block.text)
            if block.type == "tool_use":
                print(f"$ {block.input['cmd']}")
                with span("tool", run["span"], step=step, cmd=block.input["cmd"]) as t:
                    done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
                    t.update(exit=done.returncode, chars=len(done.stdout))
                result = done.stdout or f"(exit {done.returncode})"
                with span("jev", t["span"], step=step) as j:     # its own span, so the tool's seconds stay the tool's
                    j["failed"] = failed(block.input["cmd"], result)
                print(done.stdout)
                print(f"[step {step}: tool {t['seconds']}s, exit {t['exit']}, Jev: failed {j['failed']}]")
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        if not input:
            run["status"] = "done"
            break
        messages.append({"role": "user", "content": input})
    else:
        run["status"] = "step limit"

print(HEADER)
print(row(SPANS))
```

- **Spans.** `span()` wraps a piece of work and writes one record when it's over: an id, the `parent` it belongs to, when it `start`ed and how many `seconds` it took. The run is the parent of every model call and tool, so the file is a tree, not just a list. If the work raises, the span records the `error` and lets the exception carry on, so a crash is in the trace and still crashes.
- **Cost.** `cost()` multiplies the four token counts by `PRICE`. The rates there are examples; the API doesn't tell you what you pay, so put in your provider's. Each model span carries its cost, and so each task has one.
- **A live line.** After every model call and tool, it prints one line: the step, how long it took, tokens in and out, cost, exit code, and what Jev said. You see where the time and money go while it runs.
- **A summary.** When the run ends, `row()` turns its spans into one line: how it ended (`done`, `step limit`, `declined`, or `crashed` if no run span was written), calls, tools, problems, how many tools Jev called failed, time, tokens, how much was read from the cache, cost.
- **A report.** `observability.py report` reads the whole log and prints that same line for every run. This is the part that works across runs. A trace of one run tells you what happened; a table of every run tells you what's normal.

### A second opinion on every tool

The exit code is how a command says it failed, and it's a rough signal. `grep` exits 1 when it finds nothing, which is an answer, not a failure. A pipe exits with its last stage, so `ls /nonexistent | head -1` exits 0 even though `ls` failed. So I ask [Jev](../05-sandboxing/#asking-jev), the small decision model from Lesson 5 (it needs `TYPESAFE_API_KEY`), one yes/no question about each tool's result: does `result` show that the command failed or hit an error? The criteria say what counts: failed, errored, crashed, refused or killed, even if it printed something; worked, even if it found nothing or printed a warning. Jev answers with the probability of yes.

`failed()` asks it. The answer goes in a span of its own, kind `jev`, whose parent is the tool's span, so the tool's `seconds` stay the tool's. The live line shows it next to the exit code, and the summary gets a `jev` column next to `prob.`: the tools Jev was at least `SURE` (0.9) sure had failed. Next to the exit code, not instead of it. If Jev doesn't answer (it's down, it times out, the key is wrong), the span says `None` and nothing is counted.

Asking Jev is a model-interface act: a second model, called with a request, answering with a response. What happens to the answer is observability's, inside control flow: it's written down and counted, and that's all. It never goes to the model doing the work, and it never changes what runs next. A probability isn't a fact, either. Jev reads only what the command printed, so it can be fooled by output that looks like an error, and it isn't sure about the in-between cases, as you'll see.

Try it on a task with a failure and a slow step:

```bash
uv run production/07-observability/observability.py "run ls /nonexistent, then run sleep 3 as a separate command, then say what happened in one sentence"
```

Here's one run:

```
[step 1: model 2.76s, 397 tokens in, 233 out, $0.0047]
$ ls /nonexistent
ls: cannot access '/nonexistent': No such file or directory

[step 1: tool 0.0s, exit 2, Jev: failed 0.98]
$ sleep 3

[step 1: tool 3.0s, exit 0, Jev: failed 0.02]
[step 2: model 0.97s, 712 tokens in, 52 out, $0.0029]
`ls /nonexistent` failed because that directory doesn't exist, and the separate `sleep 3` command then ran and exited successfully (exit 0).
run       status     calls tools  prob.  jev   time     in    out  cached     cost  task
6dae6b62  done           2     2     1    1    6.7s     1109    285     0% $  0.0076  run ls /nonexistent, then run sleep 3 as
```

The `prob.` column is 1: one tool exited non-zero. The `jev` column is 1 too: Jev was 0.98 sure `ls` failed and 0.02 sure `sleep` did. Of the 6.7 seconds, 3.0 were the `sleep`. (Jev's own time, about a fifth to half a second a question here, is in its spans, not in `time`.) `cached` is 0% because this agent has no system prompt to cache; quark's does, as you saw above.

Here's where the two disagree:

```bash
uv run production/07-observability/observability.py "run grep -rn FIXME production/07-observability, then run ls /nonexistent | head -1, each as a separate command, then say what happened in one sentence"
```

```
[step 1: model 1.5s, 412 tokens in, 118 out, $0.0030]
$ grep -rn FIXME production/07-observability

[step 1: tool 0.0s, exit 1, Jev: failed 0.76]
$ ls /nonexistent | head -1
ls: cannot access '/nonexistent': No such file or directory

[step 1: tool 0.0s, exit 0, Jev: failed 0.97]
[step 2: model 1.11s, 612 tokens in, 62 out, $0.0028]
The grep for FIXME in `production/07-observability` found no matches (exit code 1), and `ls /nonexistent` failed with "No such file or directory" because that path doesn't exist.
run       status     calls tools  prob.  jev   time     in    out  cached     cost  task
c0808f2d  done           2     2     1    1    2.6s     1024    180     0% $  0.0058  run grep -rn FIXME production/07-observa
```

Both columns say 1, but they're counting different tools. The exit code counts the `grep` that found nothing, which wasn't a problem. Jev counts the `ls` whose error the pipe hid behind exit 0, which was. Jev wasn't clean on the `grep`, though: 0.76 that it failed. "Exit 1, nothing printed" looks like a failure more often than not, and only `SURE` keeps it out of the count. That's why the answer sits beside the exit code.

If Jev can't answer, the run goes on as if it weren't there. Here the key is wrong on purpose:

```bash
TYPESAFE_API_KEY=not-a-key uv run production/07-observability/observability.py "run ls /nonexistent and say what happened in one sentence"
```

```
[step 1: model 0.92s, 382 tokens in, 55 out, $0.0020]
$ ls /nonexistent
ls: cannot access '/nonexistent': No such file or directory

[step 1: tool 0.0s, exit 2, Jev: failed None]
[step 2: model 0.97s, 464 tokens in, 38 out, $0.0020]
The `ls /nonexistent` command failed with "No such file or directory" because that path doesn't exist on the system.
run       status     calls tools  prob.  jev   time     in    out  cached     cost  task
79a51a22  done           2     1     1    0    1.9s      846     93     0% $  0.0039  run ls /nonexistent and say what happene
```

After a few runs, ask for the report (I took this one before the run with the wrong key, so that run isn't in it):

```bash
uv run production/07-observability/observability.py report
```

```
run       status     calls tools  prob.  jev   time     in    out  cached     cost  task
0348969a  done           2     1     0    0    2.2s      948    111     0% $  0.0045  which quark.py in the lessons folder is 
ff40e40a  done           4     3     0    0    7.4s     5613    397     0% $  0.0228  read the file docs/the-models.md and tel
6dae6b62  done           2     2     1    1    6.7s     1109    285     0% $  0.0076  run ls /nonexistent, then run sleep 3 as
c0808f2d  done           2     2     1    1    2.6s     1024    180     0% $  0.0058  run grep -rn FIXME production/07-observa
```

One line per run. The run that went looking for a file with the wrong name took four calls and cost about five times the first. The spans are in `.quark/spans.jsonl`, and the slowest tool in the log is one query away:

```bash
jq -s -c 'map(select(.kind=="tool")) | sort_by(-.seconds) | .[0] | {run, step, seconds, exit, cmd}' .quark/spans.jsonl
```

```
{"run":"6dae6b62","step":1,"seconds":3.0,"exit":0,"cmd":"sleep 3"}
```

So is every exit code next to Jev's answer, by joining each `jev` span to its parent tool:

```bash
jq -s -c '(map(select(.kind=="tool")) | INDEX(.span)) as $t | .[] | select(.kind=="jev") | {exit: $t[.parent].exit, failed, cmd: $t[.parent].cmd[:40]}' .quark/spans.jsonl
```

```
{"exit":0,"failed":0.03,"cmd":"find . -path '*lessons*' -name 'quark.py"}
{"exit":0,"failed":0.63,"cmd":"grep -m1 -n '^#' docs/the-models.md || ("}
{"exit":0,"failed":0.08,"cmd":"find . -iname '*.md' -not -path './.venv"}
{"exit":0,"failed":0.03,"cmd":"grep -m1 -n '^#' docs/the-model.md"}
{"exit":2,"failed":0.98,"cmd":"ls /nonexistent"}
{"exit":0,"failed":0.02,"cmd":"sleep 3"}
{"exit":1,"failed":0.76,"cmd":"grep -rn FIXME production/07-observabili"}
{"exit":0,"failed":0.97,"cmd":"ls /nonexistent | head -1"}
```

The 0.63 is the in-between case: that command's `grep` failed on the missing file, printed its error, and the `||` went on to search for the right one and exit 0. Part of it failed and the whole of it worked, and Jev said so by not being sure.

The costs are computed at the example rates in `PRICE`, so they show you which run was expensive, not what you were billed. Jev's questions aren't in them.

## What to take away

**The rule:** record what the harness does as it does it: each model call, each tool, each refusal, how long it took and what it cost, in a log you can search afterwards. Do it where control flow already sees the whole sequence, read from what's already there rather than changing it, and keep it apart from what the model remembers.

Notice what observability never does. It sits inside control flow's loop, but it never decides what runs next or when to stop. The model interface sends and receives exactly as before; observability only reads `usage` off the response. It gathers no input, and it puts nothing in front of the model: the trace is not in the request, which is what makes it observability and not context. Output runs tools the way it always did, only with a clock around them.

**What's missing:** it watches, and that's all it does. It will faithfully record that the API dropped a call halfway through a long run, that the model was cut off in the middle of a command, that you pressed ESC and everything it had said or printed up to then was thrown away, or that the process died and took the work with it. It can tell you exactly where things broke; it can't pick up from there. A harness that runs unattended has to survive a bad day, not just describe one.

**→ [Lesson 8: Resilience](../08-resilience/)**
