# Lesson 7: Observability

> 🎥 **Video:** coming soon

Lessons 5 and 6 made the harness safe to leave running. Now you're about to run it where you can't watch it, and you'll have questions it can't answer. Why did that take four minutes? Why did it cost that much? What did it run, in what order, which command did the guard refuse, and which did the box kill? The terminal scrolled past and the answers went with it.

Observability is a record of what the harness did, kept as it does it: every call to the model, every tool it ran, how long each took, how many tokens each cost, and every time a guardrail said no. A harness you can't see into is one you can't trust or fix.

You might think Lesson 4 already did this. Every message is in the episode. But the episode is written **for the model**: it's what working memory would have been, so the model can search its own past. It has no timings, no token counts, no exit codes, and it shouldn't, because none of that helps the model think. The trace is written **for you**, the person running quark. Same run, two records, two readers. The paper calls this the rule of who reads it: a record for the model is context; a record for the operator is observability.

This is a production layer, so it adds hardening, not a new primitive. It's **built on control flow**. Control flow is the one primitive that sees the whole sequence. The model interface only knows about one call, and output only knows about one tool, but the loop is where a call, the tool it asked for, the guard's decision and the call after that all happen, in order. So it's the one place a record of the run can be made.

The mechanism is small. Each time around the loop there are things that already exist: the clock, the `usage` that came back with the response, the exit code of the command that ran, the reason a command was refused. Observability reads them off and writes them down.

- **A trace.** One line appended to a file for each thing that happened, in the order it happened. Each line is a JSON object, so you can search it afterwards with the tools you already have.
- **Timing.** Read the clock before and after a model call or a tool, and keep the difference.
- **Token accounting.** Every response says how many tokens went in and came out, and how many were read from or written to the prompt cache. Tokens times your provider's price is cost. The price isn't in the response; you keep the rates yourself.
- **A second opinion on failure.** The exit code is how a command says it failed, and it's a rough signal. `grep` exits 1 when it finds nothing, which is an answer, not a failure. A pipe exits with its last stage, so `ls missing.txt | head -1` exits 0 even though `ls` failed. So next to each exit code, the record keeps Jev's answer to one question: did this command fail?

Observability only watches. It never changes what's sent, what runs, or when the loop stops. If a trace line fails to describe what happened, you've got a wrong record, not a wrong agent.

## The concept

Here's the idea with nothing around it: run a few commands and one model call, and write down each one as it happens. It's in [`observability.py`](./observability.py):

```python
import subprocess, json, time, datetime
from anthropic import Anthropic

client = Anthropic()

def trace(**event):                                      # one JSON line per event, appended, for whoever runs the agent
    with open("traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), **event}) + "\n")

seen = []
for cmd in ["wc -l notes.txt", "grep -n TODO notes.txt", "ls missing.txt | head -1", "sleep 2"]:
    start = time.time()
    done = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
    seen.append(f"$ {cmd}\n{done.stdout}(exit {done.returncode})")

start = time.time()
response = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, messages=[{"role": "user", "content": "Which of these commands failed? One sentence.\n\n" + "\n\n".join(seen)}])
trace(event="model", seconds=round(time.time() - start, 2), stop_reason=response.stop_reason, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
print("".join(block.text for block in response.content if block.type == "text"))
```

There's no agent loop here. The four commands are fixed, and the model is called once at the end to say which of them failed. That's enough to have something to watch.

**`trace()`** is the whole layer. It appends one JSON object to `traces.jsonl`: the time, and whatever you pass it. A file that only ever gets appended to is the simplest log there is, and each line stands on its own, so a run that crashes halfway still leaves everything before the crash.

**The clock.** `start = time.time()` before each command and before the model call, and the difference goes in the line as `seconds`.

**What's already there.** A command leaves its exit code and what it printed; the trace keeps the code and how many characters. A response comes back with `stop_reason` and `usage`; the trace keeps the token counts. None of this is computed. It's read off and written down.

Run it in a scratch folder, since it writes `traces.jsonl` where you start it:

```bash
mkdir -p /tmp/demo7 && cd /tmp/demo7 && printf 'buy milk\ncall Sam\nfix the bike\n' > notes.txt
uv run --project /path/to/building-agents /path/to/building-agents/production/07-observability/observability.py
```

It prints only the model's answer:

```
The `ls missing.txt | head -1` command failed (the file doesn't exist), but the pipeline's exit status of 0 came from `head` and hid that, while `grep` exiting 1 only means it found no TODO matches, not an error.
```

Everything else is in `traces.jsonl`:

```
{"ts": "2026-10-06T23:58:54", "event": "tool", "cmd": "wc -l notes.txt", "seconds": 0.0, "exit": 0, "chars": 12}
{"ts": "2026-10-06T23:58:54", "event": "tool", "cmd": "grep -n TODO notes.txt", "seconds": 0.0, "exit": 1, "chars": 0}
{"ts": "2026-10-06T23:58:54", "event": "tool", "cmd": "ls missing.txt | head -1", "seconds": 0.0, "exit": 0, "chars": 59}
{"ts": "2026-10-06T23:58:56", "event": "tool", "cmd": "sleep 2", "seconds": 2.0, "exit": 0, "chars": 0}
{"ts": "2026-10-06T23:58:58", "event": "model", "seconds": 2.17, "stop_reason": "end_turn", "input_tokens": 129, "output_tokens": 202}
```

Five lines, one per thing that happened. The `sleep` took its 2 seconds and the model call 2.17, and the model's call cost 129 tokens in and 202 out.

Because each line is one JSON object, you can ask the file questions with `jq`. Here's every command whose exit code says it failed:

```bash
jq -c 'select(.event=="tool" and .exit != 0) | {cmd, exit}' traces.jsonl
```

```
{"cmd":"grep -n TODO notes.txt","exit":1}
```

That's the wrong answer twice over. The `grep` found nothing, which is an answer, not a failure. And the `ls` that did fail isn't there: the pipe exited with `head`'s 0. The model saw both, because it read what the commands printed, but the trace only has the exit code, and the exit code is a rough signal.

## The concept with Jev

So next to each exit code, keep a second opinion. [`jev_observability.py`](./jev_observability.py) is `observability.py` plus Jev, and nothing else:

```bash
diff observability.py jev_observability.py
```

```diff
1c1
< import subprocess, json, time, datetime
---
> import subprocess, os, json, time, datetime
2a3
> from typesafe_sdk import TypeSafeClient, Noul, NoulCriteria
4a6,9
> jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # a second model, asked one question about each command
> FAILED = Noul(instructions="Does `result` show that the command failed or hit an error?",
>     criteria=NoulCriteria(true="The command failed, errored, crashed, was refused or was killed, even if it printed something.",
>                           false="The command worked, even if it found nothing or printed a warning."))
8a14,17
> def failed(cmd, result):                                 # Jev's probability that the command failed; None if it can't answer
>     try: return round(jev.system_one({"command": cmd, "result": result}, {"q": FAILED}).nouls["q"].noul, 2)
>     except Exception: return None
> 
13c22
<     trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
---
>     trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout), failed=failed(cmd, done.stdout))
```

`os` joins the imports to read the key, and Jev's client and yes/no question type come from `typesafe_sdk`. The client is made only when `TYPESAFE_API_KEY` is set.

**`FAILED`** is the question for [Jev](../05-sandboxing/#asking-jev), the decision model from Lesson 5: does `result` show that the command failed or hit an error? The criteria say what counts: failed, errored, crashed, refused or killed, even if it printed something; worked, even if it found nothing or printed a warning.

**`failed()`** asks it about one command, sending the command and what it printed. Jev answers with the probability of yes, rounded to two places. If Jev can't answer (no key, a wrong key, a time-out, any error), `failed()` returns `None`.

**The tool's line** is where the answer is used: it gets `failed` beside `exit`, never instead of it. With no answer, the line says `null`.

Asking Jev is a model-interface act: a second model, called with a request, answering with a response. What happens to the answer is observability's: it's written down, and that's all. It isn't sent to the main model, and it doesn't change what runs next. There's no threshold either, because nothing is decided: the trace keeps the probability as it came, and the person reading it decides.

Run it the same way, in a fresh scratch folder with the same `notes.txt`:

```bash
mkdir -p /tmp/demo7-jev && cd /tmp/demo7-jev && printf 'buy milk\ncall Sam\nfix the bike\n' > notes.txt
uv run --project /path/to/building-agents /path/to/building-agents/production/07-observability/jev_observability.py
```

It prints only the model's answer:

```
`ls missing.txt` is the one that actually failed (the file doesn't exist), though the pipe into `head` masked it with exit 0, while `grep` exiting 1 just means no TODO matches were found, not a real error.
```

Everything else is in `traces.jsonl`:

```
{"ts": "2026-10-06T23:18:22", "event": "tool", "cmd": "wc -l notes.txt", "seconds": 0.0, "exit": 0, "chars": 12, "failed": 0.02}
{"ts": "2026-10-06T23:18:22", "event": "tool", "cmd": "grep -n TODO notes.txt", "seconds": 0.0, "exit": 1, "chars": 0, "failed": 0.06}
{"ts": "2026-10-06T23:18:23", "event": "tool", "cmd": "ls missing.txt | head -1", "seconds": 0.0, "exit": 0, "chars": 59, "failed": 0.98}
{"ts": "2026-10-06T23:18:25", "event": "tool", "cmd": "sleep 2", "seconds": 2.0, "exit": 0, "chars": 0, "failed": 0.03}
{"ts": "2026-10-06T23:18:27", "event": "model", "seconds": 2.39, "stop_reason": "end_turn", "input_tokens": 129, "output_tokens": 194}
```

The same five lines, and each tool's line now has `failed` beside `exit`. Look at the two middle lines. The `grep` exited 1 and Jev gave it 0.06: it found nothing, and that's not a failure. The `ls` exited 0 and Jev gave it 0.98: it failed, and the pipe hid it. The exit code and Jev disagree on both, and Jev is right on both.

Ask the file again, this time for every command that either signal calls a failure, with Jev counted only when it's at least 0.9 sure:

```bash
jq -c 'select(.event=="tool" and (.exit != 0 or .failed >= 0.9)) | {cmd, exit, failed}' traces.jsonl
```

```
{"cmd":"grep -n TODO notes.txt","exit":1,"failed":0.06}
{"cmd":"ls missing.txt | head -1","exit":0,"failed":0.98}
```

One false alarm from the exit code, one real failure only Jev saw. That's why Jev's answer sits next to the exit code and doesn't replace it: you get both, and a person reading the trace decides.

Without Jev, nothing else changes. Here's the same run with a wrong key on purpose, in a fresh folder with the same `notes.txt`:

```bash
TYPESAFE_API_KEY=not-a-key uv run --project /path/to/building-agents /path/to/building-agents/production/07-observability/jev_observability.py
jq -c 'select(.event=="tool") | {cmd, exit, failed}' traces.jsonl
```

```
`ls missing.txt` actually failed (the file doesn't exist), but the pipe to `head` masked it with exit 0, while `grep` exiting 1 only means no TODO matches were found, not a real error.
{"cmd":"wc -l notes.txt","exit":0,"failed":null}
{"cmd":"grep -n TODO notes.txt","exit":1,"failed":null}
{"cmd":"ls missing.txt | head -1","exit":0,"failed":null}
{"cmd":"sleep 2","exit":0,"failed":null}
```

The record is just missing an opinion. The model's answer never depended on Jev: Jev's answer only ever goes in the trace.

## quark's implementation

Here's both built into quark. [`quark.py`](./quark.py) is Lesson 6's `quark.py` plus the trace and Jev's question, and nothing else: 18 lines, 352 in all. `time` joins the imports, and Jev's yes/no question type joins Lesson 5's import from `typesafe_sdk`:

```python
import subprocess, sys, os, re, glob, json, datetime, atexit, termios, tty, threading, select, contextlib, time
from typesafe_sdk import TypeSafeClient, Choice, Noul, NoulCriteria
```

At the top of `# ── control flow ──`, the function that writes the record, and the question:

```python
def trace(**event):                                      # observability: one line per step, for whoever runs quark
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "episode": EPISODE, **event}) + "\n")
FAILED = Noul(instructions="Does `result` show that the command failed or hit an error?", criteria=NoulCriteria(true="The command failed, errored, crashed, was refused or was killed, even if it printed something.", false="The command worked, even if it found nothing or printed a warning."))
def failed(cmd, result):                                 # observability: Jev's second opinion on whether a tool failed, beside its exit code
    judged = ask({"command": cmd, "result": result[-4000:]}, FAILED)
    return judged and round(judged["noul"], 2)
```

Then one call wherever something happens. Each is a single line next to code that was already there:

```python
trace(event="start", input=input)
        trace(event="stopped", steps=steps, tokens=spent)
        trace(event="model", seconds=round(time.time() - start, 2), stop_reason=response.stop_reason, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens, cache_read=response.usage.cache_read_input_tokens, cache_write=response.usage.cache_creation_input_tokens)
        trace(event="too_long", drop=drop)
        trace(event="interrupted", during="saying")
                trace(event="refused", cmd=block.input["cmd"], why=no)
            trace(event="tool", cmd=block.input["cmd"], seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout), failed=failed(block.input["cmd"], done.stdout))
        trace(event="interrupted", during="acting")
```

And `start = time.time()` before the model call and before each command, two more lines.

**`trace()`** is the concept's, with two differences. It writes to `.quark/traces.jsonl`, next to Lesson 4's memory. And every line carries the **episode** this run is being written to. That field ties the two records together: from any trace line you can open the messages of the same run.

**The start** marks where a run begins and what came in.

**Each model call** records the `stop_reason` and the four token counts from `response.usage`: new input, output, read from the cache, and written to it. That's everything you need to work out cost, and the cache counts show whether Lesson 4's `cache_control` on the system prompt is doing anything.

**Each tool** records the command, how long it took, its exit code, how many characters it printed, and `failed`. One thing about the clock: it starts before Lesson 5's question about whether the command needs the network, so a tool's `seconds` include that question (and your answer, if you're asked).

**Each refusal** records the command the guard wouldn't run, and why. **Each interrupt** records that you pressed ESC, and whether quark was saying or doing something at the time. **Each limit** records the steps and tokens it stopped at. **Each compaction** records that the API said the prompt was too long.

**`failed()`** is the same question as in the concept with Jev, asked through Lesson 5's `ask()`, which already handles the key, the time-out and the errors and returns `None` for all of them. It sends the command and the last 4,000 characters of what it printed, since the end of the output is usually where an error is. `judged and round(...)` gives the probability, or `None` when there's no answer. Asking Jev is model interface, as it was in Lessons 5 and 6. What quark does with the answer is observability's, in control flow: it goes in the tool's line, beside `exit`. Unlike Lessons 5 and 6, there's no `SURE` here, because nothing is decided. The trace keeps the probability as it came, sure or not, and the person reading it decides.

Nothing else changed. The request is built by the same code, the same commands run in the same box, and the loop stops for the same reasons. The model never sees `failed`: its tool result is what the command printed, as before.

### Run it

You need Docker running, as in Lessons 5 and 6. Start in a scratch folder with a two-line `small.txt` and a 5,000-line `big.txt`. This time nothing is piped in, so there's no one to answer the guard:

```bash
mkdir /tmp/demo && cd /tmp/demo && printf 'one\ntwo\n' > small.txt && seq 1 5000 | sed 's/^/line /' > big.txt
uv run --project /path/to/building-agents /path/to/building-agents/production/07-observability/quark.py "which file in this folder has the most lines? answer in one sentence" < /dev/null
```

```
$ wc -l * .[!.]* 2>/dev/null | sort -n | tail -5
      0 .quark
      2 small.txt
   5000 big.txt
   5002 total

`big.txt` has the most lines, at 5,000.
```

The command wasn't on the guard's safe list (`2>` redirects, and `sort` isn't a reader it knows), but Jev was sure it only reads, so it ran without asking. Here's what the person running it sees afterwards, in `.quark/traces.jsonl`:

```
{"ts": "2026-10-06T23:18:50", "episode": ".quark/episodes/2026-10-06T23-18-50.jsonl", "event": "start", "input": "which file in this folder has the most lines? answer in one sentence"}
{"ts": "2026-10-06T23:18:52", "episode": ".quark/episodes/2026-10-06T23-18-50.jsonl", "event": "model", "seconds": 1.41, "stop_reason": "tool_use", "input_tokens": 95, "output_tokens": 76, "cache_read": 0, "cache_write": 8941}
{"ts": "2026-10-06T23:18:53", "episode": ".quark/episodes/2026-10-06T23-18-50.jsonl", "event": "tool", "cmd": "wc -l * .[!.]* 2>/dev/null | sort -n | tail -5", "seconds": 0.26, "exit": 0, "chars": 63, "failed": 0.08}
{"ts": "2026-10-06T23:18:54", "episode": ".quark/episodes/2026-10-06T23-18-50.jsonl", "event": "model", "seconds": 0.99, "stop_reason": "end_turn", "input_tokens": 206, "output_tokens": 20, "cache_read": 8941, "cache_write": 0}
```

Every step is there: two calls, the one command between them, how long each took, and Jev's 0.08 that the command failed. Read the cache columns: the first call wrote the 8,941-token system prompt to the cache, and the second read it back instead of paying for it again.

Add up one run, by its episode:

```bash
jq -c -s --arg e ".quark/episodes/2026-10-06T23-18-50.jsonl" 'map(select(.episode==$e and .event=="model")) | {calls: length, input: (map(.input_tokens)|add), output: (map(.output_tokens)|add), cache_read: (map(.cache_read)|add), cache_write: (map(.cache_write)|add), seconds: (map(.seconds)|add)}' .quark/traces.jsonl
```

```
{"calls":2,"input":301,"output":96,"cache_read":8941,"cache_write":8941,"seconds":2.4}
```

Now a run where things go wrong. This uses a copy of `quark.py` with the sandbox's `TIMEOUT` lowered to 5 and `y` piped in for the guard, in a fresh scratch folder with `small.txt`:

```bash
yes y | head -50 | uv run --project /path/to/building-agents /path/to/copy/quark.py "run ls /nonexistent | head -1, then run grep TODO small.txt, then run sleep 60, each as a separate command, then say what happened in one sentence"
```

```
$ ls /nonexistent | head -1
ls: cannot access '/nonexistent': No such file or directory

$ grep TODO small.txt

$ sleep 60
allow `sleep 60`? (Jev: other, 0.81) [y/N] 
(killed: ran over 5 seconds or out of memory)
The `ls /nonexistent | head -1` command printed an error because the path doesn't exist, `grep TODO small.txt` printed nothing and exited 1 (either no TODO lines or no such file), and `sleep 60` was killed at the 5-second sandbox timeout.
```

The agent told you what happened, this time. Without the trace, you'd only know if you were watching. Here are the exit codes and Jev's answers side by side:

```bash
jq -c 'select(.event=="tool") | {cmd, exit, failed}' .quark/traces.jsonl
```

```
{"cmd":"ls /nonexistent | head -1","exit":0,"failed":0.98}
{"cmd":"grep TODO small.txt","exit":1,"failed":0.04}
{"cmd":"sleep 60","exit":137,"failed":0.97}
```

The same split as in the concept with Jev: the pipe hid the `ls` failure behind exit 0, and only Jev saw it; the `grep` that found nothing exited 1, and only the exit code called it a failure. They agree on the kill (`exit` 137). And here's everything that didn't go to plan, by either signal, with the guard's refusals in the same query:

```bash
jq -c 'select((.event=="tool" and (.exit!=0 or .failed>=0.9)) or .event=="refused")' .quark/traces.jsonl
```

```
{"ts":"2026-10-06T23:19:10","episode":".quark/episodes/2026-10-06T23-19-07.jsonl","event":"tool","cmd":"ls /nonexistent | head -1","seconds":0.58,"exit":0,"chars":60,"failed":0.98}
{"ts":"2026-10-06T23:19:11","episode":".quark/episodes/2026-10-06T23-19-07.jsonl","event":"tool","cmd":"grep TODO small.txt","seconds":0.26,"exit":1,"chars":0,"failed":0.04}
{"ts":"2026-10-06T23:19:16","episode":".quark/episodes/2026-10-06T23-19-07.jsonl","event":"tool","cmd":"sleep 60","seconds":5.23,"exit":137,"chars":46,"failed":0.97}
```

Nothing was refused this time, since you said yes. Each line names its episode, so you can go from "what went wrong" to "what the model was thinking" in one step.

And when you break in. In a terminal, I asked for `sleep 30`, said `y`, and pressed ESC three seconds later:

```
> run sleep 30 as one command
$ sleep 30
allow `sleep 30`? (Jev: other, 0.83) [y/N] y
[your doing stopped before done]
You interrupted me, so `sleep 30` was stopped before it finished. It didn't complete.

The sandbox also kills any command that runs 30 seconds or longer. So `sleep 30` might have been killed by that limit even without the interruption. Do you want me to run it again, or run a shorter one such as `sleep 25`?

> /q
```

The trace of that run, without the time and episode:

```bash
jq -c 'del(.ts, .episode)' .quark/traces.jsonl
```

```
{"event":"start","input":"run sleep 30 as one command"}
{"event":"model","seconds":1.81,"stop_reason":"tool_use","input_tokens":86,"output_tokens":109,"cache_read":0,"cache_write":8941}
{"event":"tool","cmd":"sleep 30","seconds":3.16,"exit":137,"chars":32,"failed":0.62}
{"event":"interrupted","during":"acting"}
{"event":"model","seconds":1.91,"stop_reason":"end_turn","input_tokens":233,"output_tokens":108,"cache_read":8941,"cache_write":0}
```

The command was stopped at 3.16 seconds (`exit` 137: ESC's `kill -9 -1` inside the box, which looks the same as a time-out in the exit code), and the next line says why: you interrupted it while it was acting. Then one more call, for the model to acknowledge it. Jev's 0.62 is the in-between case: all it was shown was `[your doing stopped before done]`, which is neither a crash nor a success, and it said so by not being sure. The trace knows more about that command than the model or Jev does.

> The trace file only grows. Delete or rotate it when it gets big.

## Other things we could do

quark records one line per event: a flat log, in a file, read afterwards. These are the choices you make when you build it.
- **What's recorded.** Events as they happen, or *spans*, which have a start, a duration and a parent, so a run becomes a tree. Or everything: the full request and response of every call. That's the most useful record when something goes wrong, and the biggest, and it will contain whatever the model saw, so decide what to redact.
- **Where it goes.** A file, the terminal, a database, or a collector that speaks a standard like OpenTelemetry.
- **When you see it.** After the fact, as a live line per step, or on a dashboard that alerts you.
- **What's worked out from it.** Tokens, cost, latency, cache hit rate, how often tools fail, steps per task.
- **How you ask it questions.** `grep` and `jq`, SQL, or a UI built for traces.
- **How long it's kept.** Sampling, rotation and deletion.

It can be a product on its own. Tracing platforms like [Langfuse](https://github.com/langfuse/langfuse) and LangSmith are this layer: you send them the spans and they store them, price them and show them as a tree.

A few ideas worth knowing if you build more of it yourself:

- **Spans with parents.** Wrap each piece of work so that one record is written when it's over, with an id, the id of the work it belongs to, when it started and how long it took. The run is the parent of every model call and tool, so the log is a tree, not just a list. If the work raises an exception, record the error in the span and let the exception carry on: a crash is in the trace, and still crashes.
- **Jev's answer in a span of its own.** Make the question a child of the tool's span, and the tool's time stays the tool's: Jev's fifth of a second to half a second goes in its own record.
- **Cost.** Multiply the four token counts by your provider's rates per million tokens and keep the result on each model call. The API doesn't tell you what you pay, so the rates are yours to keep up to date, and a cost worked out from example rates tells you which run was expensive, not what you were billed. Jev's questions cost separately.
- **A live line.** After every model call and tool, print one line: the step, how long it took, tokens in and out, cost, the exit code and Jev's answer. You see where the time and money go while it runs.
- **A summary, and a report.** When a run ends, turn its records into one line: how it ended (done, out of steps, declined, or crashed if the run never wrote its end), calls, tools, failures by exit code, failures Jev was sure of, time, tokens, how much came from the cache, cost. Then print that line for every run in the log. A trace of one run tells you what happened; a table of every run tells you what's normal.

## What to take away

**The rule:** record what the harness does as it does it: each model call, each tool, each refusal, how long it took and what it cost, in a log you can search afterwards. Do it where control flow already sees the whole sequence, read from what's already there rather than changing it, and keep it apart from what the model remembers. Where a signal like the exit code is rough, keep a second opinion beside it, not instead of it.

Notice what observability never does. It sits inside control flow's loop, but it never decides what runs next or when to stop. The model interface sends and receives exactly as before; observability only reads `usage` off the response, and its one question to Jev goes through Lesson 5's `ask()`, with the answer going only into the trace. It gathers no input, and it puts nothing in front of the model: the trace is not in the request, which is what makes it observability and not context. Output runs tools the way it always did, only with a clock around them.

**What's missing:** it watches, and that's all it does. It will faithfully record that the API dropped a call halfway through a long run, that the model was cut off in the middle of a command, that you pressed ESC and everything it had said or printed up to then was thrown away, or that the process died and took the work with it. It can tell you exactly where things broke; it can't pick up from there. A harness that runs unattended has to survive a bad day, not just describe one.

**→ [Lesson 8: Resilience](../08-resilience/)**
