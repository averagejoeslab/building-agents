---
marp: true
theme: default
paginate: true
header: "Lesson 7 · Observability"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Observability

### A hands-on course in building agents by building their harness
Lesson 7

---

# The terminal scrolled past, and the answers went with it

Lessons 5 and 6 made the harness safe to leave running. Now you run it where you can't watch it:

- Why did that take four minutes?
- Why did it cost that much?
- What did it run, and in what order?
- Which command did the guard refuse, and which did the box kill?

<!-- Set this up as the questions you'll have the first time quark runs without you watching. The terminal can't answer any of them once it's scrolled. -->

---

# A record of what the harness did, kept as it does it

- Every call to the model
- Every tool it ran
- How long each took, and how many tokens each cost
- Every time a guardrail said no

A harness you can't see into is one you can't trust or fix.

<!-- That's the whole layer. Keep it as simple as this list: what happened, how long, how much, and every no. -->

---

# Same run, two records, two readers

| | Episode (Lesson 4) | Trace (Lesson 7) |
|---|---|---|
| Written for | the model | you, the person running quark |
| Holds | what working memory would have been | timings, token counts, exit codes, refusals |
| Used to | search its own past | answer your questions afterwards |

A record for the model is context. A record for the operator is observability.

<!-- Someone will say Lesson 4 already did this. The episode has every message, but none of the timings or tokens, and it shouldn't: none of that helps the model think. The paper calls this the rule of who reads it. -->

---

# Built on control flow

- The model interface only knows about one call
- Output only knows about one tool
- The loop is where a call, its tool, the guard's decision and the next call all happen, in order
- So the loop is the one place a record of the run can be made

No new primitive: a production layer adds hardening.

<!-- Control flow is the one primitive that sees the whole sequence. That's why the trace lives there. -->

---

# Read off what's already there, and write it down

- **A trace:** one JSON line per thing that happened, appended in order
- **Timing:** read the clock before and after a model call or a tool
- **Tokens:** every response says tokens in, out, and read from or written to the cache
- **A second opinion:** the exit code is rough, so keep Jev's "did it fail?" beside it

Observability only watches. It never changes what's sent, what runs, or when the loop stops.

<!-- The clock, the usage on the response, the exit code, the reason a command was refused: all of it already exists each time around the loop. grep exits 1 when it finds nothing, and a pipe exits with its last stage, so ls missing.txt | head -1 exits 0. That's why there's a second opinion. Cost is tokens times your provider's price; you keep the rates yourself. -->

---

# The concept: `observability.py` (abridged)

```python
FAILED = Noul(instructions="Does `result` show that the command failed ...?", ...)

def trace(**event):
    with open("traces.jsonl", "a") as f: f.write(json.dumps({...}) + "\n")

def failed(cmd, result):
    try: return round(jev.system_one({...}, {"q": FAILED}).nouls["q"].noul, 2)
    except Exception: return None
```

- `trace()` is the whole layer: append one JSON object per event
- `failed()` asks Jev one yes/no question, and gets a probability back
- No key, wrong key, time-out: `None`, and the line says `null`

<!-- The idea with nothing around it. No agent loop: four fixed commands and one model call at the end. The criteria in FAILED say what counts: failed, errored, crashed, refused or killed, even if it printed something; worked, even if it found nothing or printed a warning. Jev is the decision model from Lesson 5. -->

---

# Around each command, and the one model call (abridged)

```python
for cmd in [...]:
    start = time.time()
    done = subprocess.run(cmd, shell=True, ...)
    trace(event="tool", cmd=cmd, ..., failed=failed(cmd, done.stdout))
```

```python
response = client.messages.create(model=..., messages=[...])
trace(event="model", seconds=..., input_tokens=..., output_tokens=...)
```

- The model is asked which commands failed, so there's something to watch
- Asking Jev is model interface; writing the answer down is observability

<!-- The clock goes on before each command and before the model call. Jev's answer never goes to the model: it only goes in the trace. -->

---

# Run the concept: five lines in `traces.jsonl`

<style scoped>table { font-size: 0.85em; }</style>

| event | cmd | seconds | exit | failed (Jev) |
|---|---|---|---|---|
| tool | `wc -l notes.txt` | 0.0 | 0 | 0.02 |
| tool | `grep -n TODO notes.txt` | 0.0 | 1 | 0.06 |
| tool | `ls missing.txt \| head -1` | 0.0 | 0 | 0.98 |
| tool | `sleep 2` | 2.0 | 0 | 0.03 |
| model | 129 tokens in, 194 out | 2.39 | | |

The trace's fields as a table.

<!-- Run it in a scratch folder with a three-line notes.txt; it writes traces.jsonl where you start it. It only prints the model's answer: ls missing.txt failed, though the pipe masked it, and grep exiting 1 just means no TODO matches. -->

---

# Where the exit code and Jev disagree

```bash
jq -c 'select(.event=="tool" and (.exit != 0 or .failed >= 0.9)) | {cmd, exit, failed}' traces.jsonl
```

```
{"cmd":"grep -n TODO notes.txt","exit":1,"failed":0.06}
{"cmd":"ls missing.txt | head -1","exit":0,"failed":0.98}
```

- The `grep` found nothing: exit 1, but not a failure
- The `ls` failed, and the pipe hid it behind exit 0
- One false alarm from the exit code, one real failure only Jev saw

<!-- That's why Jev's answer sits next to the exit code and doesn't replace it: you get both, and a person reading the trace decides. With a wrong key, every failed is null and nothing else changes. -->

---

# quark: `trace()` and `failed()`, in control flow (abridged)

Lesson 6's `quark.py` plus 18 lines, 352 in all:

```python
def trace(**event):
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({...}) + "\n")
def failed(cmd, result):
    judged = ask({"command": cmd, "result": result[-4000:]}, FAILED)
    return judged and round(judged["noul"], 2)
```

- Each line also carries `episode`: it ties the trace to the model's record of the same run
- `failed()` asks through Lesson 5's `ask()`: the last 4,000 characters, or `None`
- No `SURE` here: nothing is decided, so the probability is kept as it came

<!-- FAILED is the concept's question, word for word. ask() already handles the key, the time-out and errors. The end of the output is usually where an error is. In Lessons 5 and 6, quark acted only on a sure answer; here it just writes it down, and the person reading decides. -->

---

# Then one call wherever something happens

```python
trace(event="start", input=input)
        trace(event="stopped", steps=steps, tokens=spent)
        trace(event="too_long", drop=drop)
        trace(event="interrupted", during="saying")
                trace(event="refused", cmd=block.input["cmd"], why=no)
        trace(event="interrupted", during="acting")
```

- **start:** where a run begins and what came in
- **stopped:** the steps and tokens a limit stopped at
- **too_long:** the API said the prompt was too long, so compaction runs
- **refused:** the command the guard wouldn't run, and why
- **interrupted:** you pressed ESC, and whether quark was saying or doing something

<!-- Each is a single line next to code that was already there. The indentation is the indentation in the file: each call sits next to the line it describes. -->

---

# The model and the tool lines (abridged)

```python
start = time.time()
trace(event="model", seconds=..., stop_reason=..., input_tokens=..., ...)
```

```python
start = time.time()
trace(event="tool", ..., failed=failed(block.input["cmd"], done.stdout))
```

- **model:** `stop_reason` and four counts from `usage`: input, output, cache read, cache write
- **tool:** the command, seconds, `exit`, characters printed, and Jev's `failed`
- The model never sees `failed`: its tool result is what the command printed

<!-- The four token counts are everything you need to work out cost, and the cache counts show whether Lesson 4's cache_control is doing anything. One thing about the clock: it starts before Lesson 5's network question, so a tool's seconds include that question. Nothing else changed: same request, same box, same reasons to stop. -->

---

# Run it: nobody there to answer the guard

`quark.py "which file in this folder has the most lines? answer in one sentence" < /dev/null`

```
$ wc -l * .[!.]* 2>/dev/null | sort -n | tail -5
      0 .quark
      2 small.txt
   5000 big.txt
   5002 total

`big.txt` has the most lines, at 5,000.
```

Not on the safe list, but Jev was sure it only reads, so it ran without asking.

<!-- A scratch folder with a two-line small.txt and a 5,000-line big.txt, and Docker running. 2> redirects, and sort isn't a reader the guard knows. That's Lesson 6's Jev question at work. -->

---

# What you see afterwards, in `.quark/traces.jsonl`

<style scoped>table, pre { font-size: 0.8em; }</style>

| event | seconds | stop / exit | in | out | cache_read | cache_write | failed |
|---|---|---|---|---|---|---|---|
| model | 1.41 | tool_use | 95 | 76 | 0 | 8941 | |
| tool | 0.26 | exit 0 | | | | | 0.08 |
| model | 0.99 | end_turn | 206 | 20 | 8941 | 0 | |

The trace's fields as a table; the `start` line is left out. Summed with `jq`, by episode:

```
{"calls":2,"input":301,"output":96,"cache_read":8941,"cache_write":8941,"seconds":2.4}
```

<!-- Every step is there: two calls, the one command between them, how long each took, and Jev's 0.08 that the command failed. Point at the cache columns: the first call wrote the 8,941-token system prompt to the cache, and the second read it back instead of paying again. -->

---

# A run where things go wrong

A copy with `TIMEOUT` lowered to 5, and `y` piped in for the guard (shortened):

```
$ ls /nonexistent | head -1
ls: cannot access '/nonexistent': No such file or directory

$ grep TODO small.txt

$ sleep 60
allow `sleep 60`? (Jev: other, 0.81) [y/N] 
(killed: ran over 5 seconds or out of memory)
```

The agent told you what happened, this time. Without the trace, you'd only know if you were watching.

<!-- A pipe that hides a failure, a grep that finds nothing, and a command the box kills. The model's answer said so, but you can't count on that. -->

---

# Exit codes and Jev, side by side

```bash
jq -c 'select(.event=="tool") | {cmd, exit, failed}' .quark/traces.jsonl
```

```
{"cmd":"ls /nonexistent | head -1","exit":0,"failed":0.98}
{"cmd":"grep TODO small.txt","exit":1,"failed":0.04}
{"cmd":"sleep 60","exit":137,"failed":0.97}
```

- The same split as the concept's: Jev saw the hidden `ls`; the exit code flagged the `grep`
- They agree on the kill: `exit` 137
- Each line names its episode: from "what went wrong" to "what the model was thinking"

<!-- The README also has the query for everything that didn't go to plan by either signal, with the guard's refusals in the same query. Nothing was refused this time, since y was piped in. The trace file only grows: delete or rotate it when it gets big. -->

---

# Press ESC, and the trace says why it stopped

In a terminal: `sleep 30`, `y` to the guard, ESC three seconds later (shortened):

```
{"event":"tool","cmd":"sleep 30","seconds":3.16,"exit":137,"chars":32,"failed":0.62}
{"event":"interrupted","during":"acting"}
```

- Stopped at 3.16 seconds: `exit` 137, ESC's kill inside the box
- The next line says why: you interrupted it while it was acting
- Jev's 0.62: all it saw was `[your doing stopped before done]`
- The trace knows more about that command than the model or Jev does

<!-- Without the interrupted line, this would look exactly like a time-out kill: same exit code. Then one more call, for the model to acknowledge it. Jev's 0.62 is the in-between case: neither a crash nor a success, and it said so by not being sure. -->

---

# Other things we could do

- **What's recorded:** events, *spans* with a parent (a tree), or every full request and response
- **Where it goes:** a file, the terminal, a database, an OpenTelemetry collector
- **When you see it:** afterwards, a live line per step, or a dashboard that alerts you
- **What's worked out:** tokens, cost, latency, cache hit rate, tool failures, steps per task
- **How you ask and how long it's kept:** `grep` and `jq`, SQL or a trace UI; sampling, rotation, deletion

<!-- quark records a flat log, in a file, read afterwards. These are the choices you make when you build it. If you record the full requests, they contain whatever the model saw, so decide what to redact. -->

---

# A product on its own, and ideas worth knowing

Tracing platforms like Langfuse and LangSmith are this layer: you send them spans, they store them, price them and show them as a tree.

- **Spans with parents:** the run is the parent of every call and tool; a crash is recorded and still crashes
- **Jev in its own span**, a child of the tool's, so the tool's time stays the tool's
- **Cost:** token counts times your provider's rates, kept on each model call
- **A live line** per step, **a summary** per run, **a report** across every run

<!-- A trace of one run tells you what happened; a table of every run tells you what's normal. The API doesn't tell you what you pay, so a cost from example rates tells you which run was expensive, not what you were billed. -->

---

# The rule

Record what the harness does as it does it: each model call, each tool, each refusal, how long it took and what it cost, in a log you can search afterwards.

Do it where control flow already sees the whole sequence, read from what's already there, and keep it apart from what the model remembers. Keep a second opinion beside a rough signal, not instead of it.

<!-- Record everything as it happens, read rather than change, keep it separate from context, and keep Jev beside the exit code. -->

---

# What observability never does

- **Control flow:** it sits in the loop, but never decides what runs next or when to stop
- **Model interface:** sends and receives as before; Jev's answer goes only into the trace
- **Input:** it gathers none
- **Context:** the trace is not in the request; that's what makes it observability
- **Output:** runs tools the way it always did, only with a clock around them

<!-- Walk the five primitives. It only reads usage off the response, and its one question to Jev goes through Lesson 5's ask(). The context line is the one people trip on: the moment the trace goes into the request, it's context. -->

---

# What's missing: it watches, and that's all

It will faithfully record that:

- the API dropped a call halfway through a long run
- the model was cut off in the middle of a command
- you pressed ESC, and everything it had said or printed up to then was thrown away
- the process died and took the work with it

It can tell you exactly where things broke; it can't pick up from there. A harness that runs unattended has to survive a bad day, not just describe one.

<!-- That's the bridge to resilience: same failures, but now the harness has to get through them or stop somewhere it can start again. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Next: Resilience

Lesson 8
