---
marp: true
theme: default
paginate: true
header: "Lesson 8 · Resilience"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Resilience

### A hands-on course in building agents by building their harness
Lesson 8

---

# Everything so far assumed the other side answers

Over a long run, this is what breaks first:

- the API drops a call, or the model is overloaded
- a command fails because something else had a file locked
- a response is cut off in the middle of a command
- the process dies halfway through, and the work goes with it
- or you stop it with ESC, and what it had already done goes with it

<!-- Lesson 7 can tell you exactly where a run broke. This lesson is about not breaking, or breaking somewhere you can start again from. Two jobs: get through the failures that pass, and leave a state you can pick up from when one doesn't, so the hour of work before it isn't lost. -->

---

# Built on the model interface and output

- The **model interface** is a service across a network: slow, busy or gone
- **Output** runs the model's words: a command can fail, a request can arrive broken
- Both are where work is in flight when you press ESC
- To pick a run back up, it **reads context's own record**: Lesson 4's episode

A production layer: hardening, not a new primitive.

<!-- These are the two places the harness reaches out of itself and the world gets to say no. The episode already holds every message, written before any tool runs, so resilience needs no save file of its own. -->

---

# Not every failure means the same thing

| Worth trying again | Not worth trying again |
|---|---|
| the network dropped, or a timeout | a bad API key (401) |
| "slow down" (429) | a request the API won't accept (400) |
| any 5xx, and "overloaded" (529) | a model that doesn't exist (404) |

The SDK already retries the left column, with backoff and jitter (`max_retries`). What it can't do is choose a different model.

<!-- On the left, nothing is wrong with the request: send it again a moment later. On the right, retrying only delays the error. Backoff is one second, two, four; jitter is so a thousand clients that failed together don't all come back together. When nothing answers, stop with a sentence, not a stack trace. -->

---

# A failed command: ask what kind of failure

An exit code doesn't say whether to try again. Exit 1 can be a typo, a failing test, a lock held for a second, or a script that did half its work.

- Ask Jev: **transient**, **permanent** or **partial**?
- Sure it's transient, and sure the command only reads: **one more try**
- Sure it's partial: warn the model to **check before repeating it**
- Anything else, or no answer: the failure goes back as it is

<!-- Jev is the decision model from Lesson 5: a choice and a confidence in a fraction of a second. A read is safe to run twice; a write never is, unless doing it twice is the same as doing it once. Asking is a model-interface act; the retry or the warning is output's. -->

---

# When you press ESC, keep what was in flight

Lesson 6 stops at once by throwing the partials away. But the words were written, and the command did its first steps in the world.

- What it had said goes into working memory in **whole blocks**
- Text that had started, and thinking that had finished and been **signed**
- A tool request it had begun: `[your doing never reached the world]`
- A stopped command keeps what it printed, then `[your doing stopped before done]`

<!-- Dropping them leaves the model's record out of step with what happened: the same failure as losing a run to a crash, only smaller. A thinking block's signature comes at its end, and the API won't take thinking back without one. -->

---

# The concept: a call with somewhere else to go

`resilience.py`, `call()` (abridged):

```python
client = Anthropic(max_retries=2)
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]

def call(input):
    for model in MODELS:
        try:
            response = client.messages.create(model=model, ...)
            return f"[{model}] " + ...
        except (APIConnectionError, APIStatusError) as e:
            if ... e.status_code < 500 and e.status_code != 429: raise
            print(f"[{model}: {type(e).__name__}, after the SDK's retries]")
    return "[no model answered]"
```

<!-- The SDK tries each call three times with backoff; call() moves to the next model when what's left is transient. A bad key or a bad request fails the same way on every model, so it's raised. The test is on the status code so 529, overloaded, isn't missed. With Sonnet down through the flaky.py stand-in, three requests failed and Opus answered. -->

---

# The concept: judge a failed command

`run()` (abridged):

```python
for attempt in (1, 2):
    done = subprocess.run(cmd, shell=True, ...)
    if not done.returncode: return "[done]"
    try: answers = jev.system_one({"command": cmd, "result": ...},
                                  {"failure": FAILURE, "kind": KIND}).choices
    except Exception: return "[exit ... Jev: no answer, so no second try]"
    why, kind = answers["failure"], answers["kind"]
    if attempt == 2 or not (sure(why, "transient") and sure(kind, "read")): break
    print("[a failure that passes: trying once more]"); time.sleep(1)
```

<!-- Two questions in one call: FAILURE, the kind of failure, and KIND, whether the command only reads. sure() means that choice at a confidence of at least SURE, 0.9. A sure partial adds the warning. No key, an error or a time-out means no second try. -->

---

# The concept: a locked database

`hold.py` holds `shop.db`'s write lock, and stops when Jev answers:

```
OperationalError (SQLITE_BUSY): database is locked
[exit 1. Jev: transient 1.00, read 0.94]
[a failure that passes: trying once more]
(42,)
[done]
```

- A typo in the query: `permanent 1.00`, no second try
- `migrate.py`, failing at its fourth table: `partial 0.91`, and the warning
- No key: `Jev: no answer, so no second try`

<!-- The first try waited SQLite's five seconds for the lock and failed. Jev was sure it would pass and sure the select only reads, so it ran once more and got the count. migrate.py had written three files before it failed: the warning was true. -->

---

# quark: `call()` grows a backup

Lesson 7's `quark.py` plus 43 lines, 395 in all (abridged):

```python
client = Anthropic(timeout=300, max_retries=3)
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]
class Down(Exception): pass
def call(each=lambda event: None, **request):
    for model in MODELS:
        try:
            with client.messages.stream(model=model, **request) as stream:
                ...
        except (APIConnectionError, APIStatusError) as e:
            if ... e.status_code < 500 and e.status_code != 429: raise
            trace(event="model_failed", model=model, error=type(e).__name__)
    raise Down()
```

<!-- The concept's loop, around Lesson 1's stream. Everything else is raised, including "prompt is too long", which compaction is waiting for. timeout=300 is five minutes, because a reply of 16,000 tokens takes minutes to write. If every model fails, Down ends the run with a sentence. -->

---

# quark: Jev's question

After Lesson 5's `ask()` (abridged):

```python
FAILURE = Choice(instructions="... What kind of failure is it?", criteria=...)
def failure(cmd, result):
    why = ask({"command": cmd, "result": result[-4000:]}, FAILURE)
    return why["choice"] if why and why["confidence"] >= SURE else None
def reads(cmd):
    kind = ask({"command": cmd}, KIND)
    return bool(kind and kind["choice"] == "read" and kind["confidence"] >= SURE)
```

- `failure()`: the kind of failure, only when Jev is sure
- `reads()`: Lesson 6's `KIND` again, yes only to a sure `read`

<!-- FAILURE is the concept's question, word for word. ask() already turns no key, an error or a time-out into None. reads() needs no new question: the guard already asks KIND before every command that isn't on its safe list. -->

---

# quark: one more try

The command now runs in a loop of at most two tries (abridged):

```python
for attempt in (1, 2):
    ...
    trace(event="tool", ..., failed=failed(cmd, done.stdout))
    why = failure(cmd, done.stdout) if done.returncode and not ESC.is_set() else None
    if attempt == 2 or why != "transient" or not reads(cmd): break
    print("[a failure that passes: trying once more]"); time.sleep(1)
...
if why == "partial": done.stdout += "\n(it may have partly run: ...)"
```

<!-- A command you stopped with ESC isn't asked about. The model only sees the second try's result; the trace gets a tool line for each try. Asking Jev is model interface; another try or a line on the result is output's. -->

---

# Picking up an unfinished session

In `# ── input ──` (abridged):

```python
resumed = None if sys.argv[1:] else unfinished()
```

- `unfinished()` reads the newest episode; if it ends mid-task, it asks: *pick it up? [y/N]*
- `EPISODE` points at the old file, so the session continues in it
- A request with no result gets: *"interrupted: ... it may or may not have run. Check before repeating it."*
- The harness doesn't run it again: it might have been `git push`

<!-- If the newest episode ends with the model's answer and no tool request, that session finished. A new task on the command line starts fresh, so it's never swallowed by an old one. The API won't accept a tool request with no result, and the harness can't know whether it ran, so it says so. The model, which knows what the command was for, looks and decides. -->

---

# ESC, `Down`, and half a command

While it thinks or says, what it had produced is kept (abridged):

```python
kept = [b for b in output if (b.type != "text" or b.text)
        and (b.type != "thinking" or b.signature)]
```

- While it acts, Lesson 6's `=` becomes `+=`: a stopped command keeps what it printed
- `except Down:` ends the run with a sentence: *run quark again to pick it up*
- No `cmd`, or cut off by `max_tokens`: `[cut off, not run]`, and the model is told it *never reached the world*

<!-- Every block is kept unless it's empty text or thinking with no signature. Then your interruption, and an answer for each tool request it had begun. block.input.get("cmd") means a request with no command is answered, not a KeyError. -->

---

# Run it: the preferred model is down

`flaky.py` answers "529 overloaded" to every request for `claude-sonnet-5-5`:

```
$ wc -c notes.txt
6 notes.txt

notes.txt is 6 bytes.
```

The output looks like any other run. The trace doesn't (shortened):

```
{"event":"model_failed","model":"claude-sonnet-5-5","error":"OverloadedError"}
{"event":"model","seconds":4.91,"stop_reason":"tool_use"}
```

<!-- Both calls had four failed requests to Sonnet, the first try and three retries, then one to Opus that worked: ten requests for two calls. The seconds, 4.91 and 4.26, are mostly the backoff. Every call tries the preferred model again from scratch. -->

---

# Run it: nothing answers, then the API comes back

Every request fails, for every model:

```
[the model isn't answering. Everything so far is in the episode; run quark again to pick it up]
```

Run `quark.py` again with no input, and answer `y` to *unfinished session: 'How many bytes is notes.txt? Answer in one line.'. pick it up?* (shortened):

```
6 notes.txt

notes.txt is 6 bytes.
```

<!-- It tried both models, four requests each, and said so. There's no save file: the episode is the record. The second run picked the session up and finished in it: that one file now holds all four messages, and the trace marks the second start as resumed. -->

---

# Run it: killed mid-command, then resumed

`sleep 15 && echo finished > flag.txt`, killed with `kill -9` on its PID eight seconds in. The container wasn't, so the command finished. Resumed (shortened):

```
$ ls -l flag.txt; cat flag.txt
-rw-rw-rw- 1 root root 9 Oct  6 23:21 flag.txt
finished
```

> The harness said my first run was interrupted, so I checked the file before running the command again. The file already existed with that content, which means the command had finished. I didn't run it a second time.

<!-- atexit can't run after kill -9, so the box kept going: the command did run, and the harness didn't know. That's exactly the case the interrupted result is for. Kill by PID, not pkill, which matches on names and can match far more than you meant. -->

---

# Run it: a failure that passes

The locked `shop.db`, through quark:

```
$ python3 -m sqlite3 shop.db "select count(*) from orders"
[a failure that passes: trying once more]
(42,)

There are 42 orders in shop.db.
```

```
{"event":"tool","seconds":5.4,"exit":1,"failed":0.99}
{"event":"tool","seconds":0.32,"exit":0,"failed":0.03}
```

<!-- No question from the guard: Jev was sure the select only reads. The first try's database-is-locked never reached the screen or the model: Jev was sure it was transient, reads() was sure, and quark tried once more. The trace has both tries. migrate.py through quark came back partial, with the warning, and the model didn't run it again. -->

---

# Run it: ESC, and the model knows how far it got

While saying, the screen stopped at (shortened):

> ... Likewise 19 × 52631 = 999,989, which leaves

After ESC (shortened):

> Understood, I'll stop there. ... The hand checks I did cover 2, 3, 5, 7, 11, 13, 17, 19 and 37, and none of them divides it.

While doing, a line a second, ESC after about three: the model saw `step 1` to `step 3` and `[your doing stopped before done]`.

<!-- The episode shows the signed thinking and the text kept, which ends a little later than the screen: "which leaves 14." So the second answer counts 19 among the primes it checked. In Lesson 6 it would have been told only that you interrupted it. In the second, the result held step 1 to step 3 and the note, where Lesson 6 gave only the note. -->

---

# Run it: every request cut off, nothing run

A copy with `max_tokens` lowered to 400, and a 40-line poem to write in one command (shortened):

```
$ None
[cut off, not run]
$ None
[cut off, not run]
```

- Each request arrived with no `cmd` at all, so the line says `$ None`
- Each was answered with the cut-off result; none of them ran
- After the tenth, the model stopped and said what was happening, with nothing half-written on disk

<!-- Every response hit the limit while the model was writing its command. Its guess about the 400-token limit came from its own file, which it reads as its mechanics. With the real limit of 16,384, the same rule catches the rare command that's too long to finish. -->

---

# Other things we could do

- **Waiting and the backup:** backoff with a cap, `Retry-After`, a limiter; another model, provider or region
- **Remembering a failure:** a *bench* or *circuit breaker* leaves a failed model alone for a minute
- **Commands:** kill the whole process group, cap output, a hand-written list of reads
- **State:** a checkpoint file written whole or not at all; restart by hand or by a supervisor
- **Products:** gateways (LiteLLM, OpenRouter); durable execution (Temporal), checkpointing (LangGraph)

<!-- quark has one retry setting, one backup model, one question for a failed command, and no file of its own. A switch of model pays full price for the prompt once, since the cache is per model. A hand-written list of reads is stricter than Jev, but the line is drawn by code you can read. And Jev can only judge what a command printed: a curl -sf that hides its error gave it nothing to go on. -->

---

# The rule

Assume the call can fail, and make failure something the harness handles instead of something that ends the run.

- Retry what passes, a bounded number of times; have somewhere else to go
- Run a failed command again only when it's sure to pass and sure to only read
- Answer every tool request, even a broken one, with a result the model can read
- When you stop it, keep what it had already said and done
- Keep a record written before each step, so what was in flight is reported as *unknown*

<!-- Stop with a sentence when everywhere is out. What was in flight is not guessed at, and not lost. -->

---

# What resilience never does

- **Context:** it reads the record context already keeps; it adds no store of its own
- **Control flow:** same loop, same stops; a retry is inside one call or one command, and the only new way out is `Down`
- **Input:** untouched, apart from one question at startup, asked with the same `read()`
- **What the model sees:** only what it's told about its own work: interrupted, cut off, partial, and the partials ESC used to throw away

<!-- It sits in the model interface and output, and its question to Jev goes through Lesson 5's ask(). The system prompt doesn't tell the model that the harness retries or that it may have been resumed: that would be a decision about context, and this layer doesn't make it. -->

---

# What's missing: alive, but not fast or cheap

- Every call re-sends the whole conversation; only the system prompt is cached
- A command that prints a megabyte puts a megabyte in the next request
- Three commands that could run side by side wait for each other
- The summary is written by the same big model as everything else

Making each step smaller, faster and cheaper is its own layer.

<!-- Resilience keeps a run alive and recoverable; it doesn't make it fast or cheap. That's the bridge to performance. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Next: Performance

Lesson 9
