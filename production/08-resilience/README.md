# Lesson 8: Resilience

> 🎥 **Video:** coming soon

Lesson 7 can tell you exactly where a run broke. This lesson is about not breaking, or breaking somewhere you can start again from. Everything so far assumed that the thing on the other side of a call answers, and answers sensibly. Over a long run that's the assumption that fails first: the API drops a call, the model is overloaded, a command fails because something else had the file locked, a response is cut off in the middle of a command, the process dies halfway through and the work goes with it. Or you stop it yourself, with Lesson 6's ESC, and what it had already done goes with it.

Resilience is how the harness keeps going, or stops cleanly, when something doesn't answer. It has two jobs. The first is to get through the failures that pass. The second is to leave things in a state you can pick up from when a failure doesn't pass, so that the hour of work before it isn't lost.

This is a production layer, so it adds hardening, not a new primitive. It's **built on the model interface and output**, the two places where the harness reaches out of itself and the world gets to say no. The model interface is the call to the API (Lesson 1), a service across a network, so it can be slow, busy or gone. Output runs the model's words (Lesson 2), so what it runs can fail, and what it's handed can be broken. They're also the two places where work is in flight when you press ESC: a response half streamed, a command half run. And to pick a run back up it **reads context's own record**: Lesson 4's episode already holds every message, written before any tool runs, so resilience doesn't need a save file of its own.

The mechanism, first in the model interface. Not every failure means the same thing, so the first step is to sort them:

- **Worth trying again.** The network dropped, the request timed out, the server said slow down (429), or the server itself had trouble (any 5xx, and Anthropic's "overloaded", 529). Nothing is wrong with the request. Send the same one a moment later and it will probably work.
- **Not worth trying again.** A bad API key (401), a request the API won't accept (400), a model that doesn't exist (404). Sending it again gets the same answer, so retrying only delays the error. These go up to the code that can do something about them, or to you.

For the first kind, the way to retry matters. Wait longer after each failure (*exponential backoff*: one second, two, four), so a service that's struggling isn't hit at full speed. Add a little randomness (*jitter*), so a thousand clients that failed together don't all come back together. If the server said how long to wait, wait that long. And put a limit on it: a few tries, not forever. The Anthropic SDK already does all of this for you: it retries connection errors, 408, 409, 429 and 5xx with backoff, and the number of tries is the `max_retries` setting. What the SDK can't do is choose a different model. That's the one thing the harness adds here: when the preferred model is still failing after the SDK has given up, try a backup, and when nothing answers, stop with a message instead of a stack trace.

Then output. A command fails too, and it's harder to sort. The API's failures come with a status code that says whether to try again. A command's come with an exit code, and exit 1 can be a missing file, a typo, a failing test, a database another program had locked for a second, or a script that did half its work and then fell over. Only the first kind of thing, the lock, will work if you simply run it again, and even then only if running it twice can't do harm, which is true of a command that only reads and never of one that writes. Telling those apart means reading what the command printed, and that's a judgment. So the harness asks Jev, the decision model from [Lesson 5](../05-sandboxing/#asking-jev): what kind of failure is this, *transient*, *permanent* or *partial*? A sure *transient* failure of a command that only reads gets one more try. A sure *partial* one is flagged to the model, so it checks before repeating it. Anything else goes back as it is.

And a command's request can arrive broken: cut off in the middle by the token limit, half a sentence. The rule for that is the one Lesson 2 started with: every request gets an answer the model can read. A result that says *this was cut off before it was whole, and it never reached the world* is something the model can act on. A crash isn't.

Then the failure that's yours: you press ESC. Lesson 6 made that stop at once, and it stops cleanly by throwing away whatever was in flight. Whatever the model had already said, it's told only that you interrupted it. Whatever the command had printed, the model gets only `[your doing stopped before done]`. But both of those happened. The words were written, and the command did its first steps in the world. Dropping them leaves the model's record out of step with what happened, which is the same failure as losing a run to a crash, only smaller. So resilience keeps the partials, the way upstream quark does.

Last, picking a task back up. If the harness is killed during a long task, working memory dies with the process. But since Lesson 4, every message has also been written to the session's episode, by the harness, as it happens, and the model's request is on disk *before* the command it asks for runs. So the record already exists. Resilience only has to notice, at startup, that the last episode ended mid-task, and offer to continue it. There's one trap: if the harness died while a command was running, the record ends with a request and no result, and the command may or may not have run. The harness can't know, so it says so, and the model, which knows what the command was for, looks before it repeats anything.

None of this makes the model right, and it doesn't make a failed run succeed. It makes a run that hits trouble end up either finished or somewhere you can start again from.

## The concept

Here are the two ideas with nothing around them: a call with somewhere else to go, and a failed command that's judged before it's tried again. They're in [`resilience.py`](./resilience.py):

```python
import subprocess, sys, os, time
from anthropic import Anthropic, APIConnectionError, APIStatusError
from typesafe_sdk import TypeSafeClient, Choice

client = Anthropic(max_retries=2)                        # the SDK tries a failed call twice more, waiting longer each time
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]        # the model you want, then the backup
jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # Jev answers typed questions (Lesson 5)
SURE = 0.9                                               # how sure Jev must be before its answer changes anything

def call(input):                                         # model interface: when the SDK gives up on a model, try the next one
    for model in MODELS:
        try:
            response = client.messages.create(model=model, max_tokens=1024, messages=[{"role": "user", "content": input}])
            return f"[{model}] " + "".join(block.text for block in response.content if block.type == "text")
        except (APIConnectionError, APIStatusError) as e:
            if isinstance(e, APIStatusError) and e.status_code < 500 and e.status_code != 429: raise   # a bad key or a bad request fails on every model
            print(f"[{model}: {type(e).__name__}, after the SDK's retries]")
    return "[no model answered]"

FAILURE = Choice(instructions="The command in `command` failed with `result`. What kind of failure is it?",
    criteria={"transient": "likely to work if run again unchanged: a network blip, a timeout, a lock held, a rate limit, a busy resource",
              "permanent": "will fail again unchanged: a missing file, a syntax error, a wrong argument, permission denied, a failing test",
              "partial": "it got part of the way: some of its changes may have happened before it failed"})
KIND = Choice(instructions="Does the shell command in `command` only read?",
    criteria={"read": "only reads, lists, searches, queries or prints; changes nothing", "change": "creates, changes or removes something, or its effect can't be told from the command"})
def sure(answer, choice): return answer.choice == choice and answer.confidence >= SURE

def run(cmd):                                            # output: run a command; when it fails, ask Jev whether trying again can help
    for attempt in (1, 2):
        done = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        print(done.stdout, end="")
        if not done.returncode: return "[done]"
        try: answers = jev.system_one({"command": cmd, "result": done.stdout[-4000:]}, {"failure": FAILURE, "kind": KIND}).choices
        except Exception: return f"[exit {done.returncode}. Jev: no answer, so no second try]"   # no key, an error or a time-out
        why, kind = answers["failure"], answers["kind"]
        print(f"[exit {done.returncode}. Jev: {why.choice} {why.confidence:.2f}, {kind.choice} {kind.confidence:.2f}]")
        if attempt == 2 or not (sure(why, "transient") and sure(kind, "read")): break   # only a read is safe to run twice
        print("[a failure that passes: trying once more]"); time.sleep(1)
    return "(it may have partly run: check before repeating it)" if sure(why, "partial") else "[failed]"

mode, input = sys.argv[1], " ".join(sys.argv[2:])
print(call(input) if mode == "ask" else run(input))
```

There's no agent loop. `resilience.py ask "..."` sends one question to the model; `resilience.py run "..."` runs one command.

**`call()`** is the model interface's half. The client is made with `max_retries=2`, so the SDK tries each call up to three times, with backoff, before it raises. `call()` wraps that in a loop over `MODELS`: if what's raised is transient (a lost connection or timeout, 429, or any 5xx), it says so and moves to the next model. Anything else is raised at once: a bad key or a bad request will fail the same way on every model. The test is on the status code, not a list of exception classes, because the SDK has a class for each and it's easy to miss 529, the overloaded error, which is the one you most want to catch. If every model fails, it says so.

**`run()`** is output's half. It runs the command, and if it fails it asks Jev two questions in one call, about the command and the last 4,000 characters of what it printed. `FAILURE` is the kind of failure: `transient` (likely to work if run again unchanged), `permanent` (will fail the same way) or `partial` (it got part of the way, so some of its changes may have happened). `KIND` is whether the command only reads. Each option has a sentence saying exactly what it covers, because Jev reads literally; "queries" is in the `read` option because a `select` is a query, and with the word there Jev was surer of it. Then: (Its `KIND` is simpler than Lesson 6's, with two options; quark reuses Lesson 6's.)

- **Sure it's transient, and sure it only reads:** run it once more, a second later. A read is safe to run twice; a write never is, unless doing it twice is the same as doing it once, and nobody can promise that from outside.
- **Sure it's partial:** say so, with the warning "it may have partly run: check before repeating it".
- **Anything else,** including an answer under `SURE` (0.9) and no answer at all: it failed, and that's what comes back.

Asking Jev is a model-interface act: a second model, called with a request, read back. What's done with its answer, a second try or a warning on the result, is output's, because it changes how the tool runs and what its result says.

### Running it

Failures that actually happen are hard to schedule, so for the model's half I used a stand-in for the API that fails on purpose and passes everything else through to the real one. It's about 30 lines of Python, built on the standard library, and it never prints headers, so your key doesn't appear anywhere. Save it as `flaky.py`:

```python
# A stand-in for the Anthropic API that fails on purpose. Everything else it passes through.
#   python flaky.py PORT all          every request gets "529 overloaded"
#   python flaky.py PORT MODEL        requests for that model get "529 overloaded"
#   python flaky.py PORT first:N      the first N requests get "429 slow down" (retry-after: 1)
import json, sys, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT, MODE = int(sys.argv[1]), sys.argv[2]
seen = 0

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        global seen
        seen += 1
        body = self.rfile.read(int(self.headers["content-length"]))
        model = json.loads(body)["model"]
        headers = {"content-type": "application/json"}
        if MODE.startswith("first:") and seen <= int(MODE[6:]):
            code, out, headers["retry-after"] = 429, b'{"type":"error","error":{"type":"rate_limit_error","message":"Slow down"}}', "1"
        elif MODE in ("all", model):
            code, out = 529, b'{"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}'
        else:
            keep = ("x-api-key", "anthropic-version", "content-type", "anthropic-beta")
            req = urllib.request.Request("https://api.anthropic.com" + self.path, body, {k: v for k, v in self.headers.items() if k.lower() in keep})
            try: r = urllib.request.urlopen(req, timeout=300); code, out = r.status, r.read()
            except urllib.error.HTTPError as e: code, out = e.code, e.read()
        print(f"request {seen}: {model} -> {code}", flush=True)
        self.send_response(code)
        for k, v in headers.items(): self.send_header(k, v)
        self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)
    def log_message(self, *args): pass

HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
```

The SDK reads `ANTHROPIC_BASE_URL`, so that's how the call reaches it; nothing in `resilience.py` knows about it. Everything below runs in a scratch folder, as `uv run --project /path/to/building-agents /path/to/building-agents/production/08-resilience/resilience.py`, which I'll write as `resilience.py`. First, the preferred model is down:

```bash
python3 flaky.py 8205 claude-sonnet-5-5 &
ANTHROPIC_BASE_URL=http://127.0.0.1:8205 resilience.py ask "In one sentence: why does a harness need a backup model?"
```

```
[claude-sonnet-5-5: OverloadedError, after the SDK's retries]
[claude-opus-5-5] A harness needs a backup model so it can keep working when the primary model fails, whether from outages, rate limits, timeouts, errors, or unusable output, by automatically switching to an alternative instead of crashing or stalling the whole task.
```

The stand-in's log has four requests: three to `claude-sonnet-5-5` (the first try and the SDK's two retries), all 529, then one to `claude-opus-5-5`, which answered. With every model down (`flaky.py 8206 all`), the same question:

```
[claude-sonnet-5-5: OverloadedError, after the SDK's retries]
[claude-opus-5-5: OverloadedError, after the SDK's retries]
[no model answered]
```

Six requests, three per model, then a sentence instead of a stack trace.

For the command's half, I need a failure that passes. A database is a good one: while another program is writing to it, it's locked, and a read has to wait. `makedb.py` makes `shop.db` with 42 orders, and `hold.py` plays the other program:

```
import sqlite3
db = sqlite3.connect("shop.db")
db.execute("create table orders (id integer, total integer)")
db.executemany("insert into orders values (?, ?)", [(i, i * 3) for i in range(1, 43)])
db.commit()
```

```
# Another program writing to shop.db: it holds the database's write lock until it's stopped.
import sqlite3, time
db = sqlite3.connect("shop.db", isolation_level=None)
db.execute("begin exclusive")
print("holding the lock", flush=True)
time.sleep(3600)
```

I start the holder, and stop it (by its process ID) as soon as `resilience.py` prints Jev's answer, the way the other program would finish its write while you waited:

```bash
python3 makedb.py
python3 hold.py & HOLDER=$!
(until grep -q "Jev:" out.txt; do sleep 0.05; done; kill $HOLDER) &
PYTHONUNBUFFERED=1 resilience.py run 'python3 -m sqlite3 shop.db "select count(*) from orders"' > out.txt; cat out.txt
```

```
OperationalError (SQLITE_BUSY): database is locked
[exit 1. Jev: transient 1.00, read 0.94]
[a failure that passes: trying once more]
(42,)
[done]
```

The first try waited the five seconds SQLite waits for a lock and failed. Jev was sure it was a lock that would pass (1.00) and sure the `select` only reads (0.94), so `run()` tried once more and got the count. The same query with a typo in it fails the other way:

```
OperationalError (SQLITE_ERROR): near "order": syntax error
[exit 1. Jev: permanent 1.00, read 0.99]
[failed]
```

Permanent, at 1.00: running it again would give the same syntax error, so it doesn't. The third kind needs a command that does part of its work and then fails. `migrate.py` writes one file per table and stops at the fourth:

```
import os
os.makedirs("out", exist_ok=True)
for table in ["users", "orders", "items", "payments", "audit"]:
    if table == "payments": raise SystemExit("error: payments: no column named email")
    open(f"out/{table}.csv", "w").write("id\n")
    print(f"migrated {table}")
```

```
migrated users
migrated orders
migrated items
error: payments: no column named email
[exit 1. Jev: partial 0.91, change 1.00]
(it may have partly run: check before repeating it)
```

Partial, at 0.91, and the warning goes on the result. `out/` has `users.csv`, `orders.csv` and `items.csv`: the warning is true. Jev also called it a change (1.00), so even a confident "transient" wouldn't have run it twice.

And with no Jev, the locked database again, with `TYPESAFE_API_KEY=` and the holder left running:

```
OperationalError (SQLITE_BUSY): database is locked
[exit 1. Jev: no answer, so no second try]
```

No answer means no second try: a failure is a failure, as it was before Jev.

## quark's implementation

[`quark.py`](./quark.py) is Lesson 7's `quark.py` plus resilience and its question for Jev, and nothing else: 43 lines, 395 in all.

The import grows two exception classes, and in `# ── model interface ──` Lesson 1's `call()` grows a backup:

```python
from anthropic import Anthropic, BadRequestError, APIConnectionError, APIStatusError
```

```python
client = Anthropic(timeout=300, max_retries=3)
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]
class Down(Exception): pass
def call(each=lambda event: None, **request):            # model interface: the response streams back, and each piece goes to each()
    for model in MODELS:                                 # resilience: retries, then a backup model, then give up cleanly
        try:
            with client.messages.stream(model=model, **request) as stream:
                for event in stream:
                    if each(event): return stream.current_message_snapshot   # guardrails: told to stop, so stop reading
                return stream.get_final_message()
        except (APIConnectionError, APIStatusError) as e:
            if isinstance(e, APIStatusError) and e.status_code < 500 and e.status_code != 429: raise
            trace(event="model_failed", model=model, error=type(e).__name__)
    raise Down()
```

**The client.** `Anthropic(timeout=300, max_retries=3)`. The SDK does the retrying, with backoff, and honors the server's `Retry-After`. `timeout` is how long to wait on a single request; it's five minutes because a reply of 16,000 tokens takes minutes to write. `max_retries=3` is one more than the SDK's default, written out so you can see it's a choice.

**`call()`.** It's the concept's loop over models, around Lesson 1's stream. Every call to the model already went through it, the main one and the summary in `compact()`, so this is the one place to change. A transient failure is traced as `model_failed` and the next model is tried. Everything else is raised, and in particular "prompt is too long", which Lesson 4's compaction is waiting for. If every model fails, `call()` raises `Down`.

After Lesson 5's `ask()`, Jev's question:

```python
FAILURE = Choice(instructions="The command in `command` failed with `result`. What kind of failure is it?", criteria={"transient": "likely to work if run again unchanged: a network blip, a timeout, a lock held, a rate limit, a busy resource", "permanent": "will fail again unchanged: a missing file, a syntax error, a wrong argument, permission denied, a failing test", "partial": "it got part of the way: some of its changes may have happened before it failed"})
def failure(cmd, result):                                # resilience: Jev says what kind of failure it is, when it's sure
    why = ask({"command": cmd, "result": result[-4000:]}, FAILURE)
    return why["choice"] if why and why["confidence"] >= SURE else None
def reads(cmd):                                          # resilience: only a command that only reads is safe to run twice
    kind = ask({"command": cmd}, KIND)
    return bool(kind and kind["choice"] == "read" and kind["confidence"] >= SURE)
```

**`failure()`** asks the concept's question through Lesson 5's `ask()`, which already turns no key, an error or a time-out into `None`. It hands back the kind of failure only when Jev is sure of it, and `None` otherwise. **`reads()`** doesn't need a new question: Lesson 6's `KIND` already asks whether a command reads, writes, deletes or does something else, and the guard asks it before every command that isn't on its list. `reads()` asks it again and says yes only to a sure `read`.

In `# ── context ──`, after `add()`, a function that reads the last episode back:

```python
def unfinished():                                        # resilience: the last session's episode, if it ended mid-task
    episodes = sorted(glob.glob(".quark/episodes/*.jsonl"))
    if not episodes: return None
    messages = [json.loads(line) for line in open(episodes[-1])]
    last = messages[-1]
    if last["role"] == "assistant" and not any(b["type"] == "tool_use" for b in last["content"]): return None
    if read(f"unfinished session: {messages[0]['content'][:60]!r}. pick it up? [y/N] ").lower() != "y": return None
    return episodes[-1], messages
```

**`unfinished()`** looks at the newest episode. If it ends with the model's answer and no tool request, that session finished, and there's nothing to do. Otherwise it shows you the input that opened it and asks, with Lesson 2's `read()`. On a `y`, it hands back the episode's path and its messages.

In `# ── input ──`, it's asked before anything else is read, but only when quark starts with no input: a new task on the command line starts a new session, so it's never swallowed by an old one.

```python
resumed = None if sys.argv[1:] else unfinished()   # resilience: a new task on the command line starts fresh
input = "" if resumed else " ".join(sys.argv[1:]) or read("> ")
```

In `# ── control flow ──`, a resumed session continues in its own episode, and an unanswered tool request gets the "interrupted" result:

```python
if resumed:                                              # resilience: pick up where the episode ends
    EPISODE, working_memory = resumed
    if working_memory[-1]["role"] == "assistant":
        add(working_memory, {"role": "user", "content": [{"type": "tool_result", "tool_use_id": b["id"], "content": "interrupted: the harness stopped before this finished, so it may or may not have run. Check before repeating it.", "is_error": True} for b in working_memory[-1]["content"] if b["type"] == "tool_use"]})
else:
    add(working_memory, {"role": "user", "content": input})
trace(event="start", input=input, resumed=bool(resumed))
```

`EPISODE` is pointed at the old file, so everything from here on is appended to the same session. If the record ends with the model asking for tools, each request is answered with the "interrupted" result, through `add()`, so the episode records that too. The harness doesn't run the command again, because it may already have run: it might have been `git push`, or sent an email, or appended a line to a file. The trace marks the start as `resumed`.

When no model answers, the run ends with a sentence, not a stack trace:

```python
    except Down:
        sys.exit("[the model isn't answering. Everything so far is in the episode; run quark again to pick it up]")
```

When you press ESC while it's thinking or saying something, what it had produced is kept:

```python
    if response.stop_reason is None:                     # guardrails: ESC stopped it while it thought or said
        trace(event="interrupted", during="saying")
        print()
        kept = [b for b in output if (b.type != "text" or b.text) and (b.type != "thinking" or b.signature)]   # resilience: keep what it had said, in whole blocks
        if kept: add(working_memory, {"role": "assistant", "content": kept})
        add(working_memory, {"role": "user", "content": [{"type": "tool_result", "tool_use_id": b.id, "content": "[your doing never reached the world]"} for b in kept if b.type == "tool_use"] + [{"type": "text", "text": SAYING}]})
        continue
```

`output` is what had arrived when the stream stopped: Lesson 6's `call()` hands back the message as far as it got. Lesson 6 dropped it. Now every block in it is kept unless it's empty text or thinking with no signature, which is thinking that was cut off before it finished (a thinking block's signature comes at its end, and the API won't take thinking back without one). The kept blocks go into working memory, and so into the episode, as the model's message. Then comes your interruption, as before, and in the same message an answer for each tool request it had begun: `[your doing never reached the world]`, because none of them ran.

In the output loop, a cut-off request is never run:

```python
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if ESC.is_set():                             # guardrails: after ESC, nothing else starts
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": "[your doing never reached the world]"})
                continue
            if not cmd or (response.stop_reason == "max_tokens" and block is output[-1]):   # resilience: never run half a command
                print("[cut off, not run]")
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": "[your doing was cut off before it was fully formed — it never reached the world]"})
                continue
```

`block.input.get("cmd")` means a request with no command is answered and not a `KeyError`. If the response was cut off by `max_tokens` and this is its last block, the command may be half a command, so it isn't run, and the model is told so in the same words as everything else that didn't happen: it never reached the world. The other uses of `block.input["cmd"]` become `cmd`.

And the command itself now runs inside a loop of at most two tries:

```python
            for attempt in (1, 2):                       # resilience: a failure that will pass gets one more try, if it only reads
                start = time.time()
                with listening():                            # guardrails: ESC stops the command
                    doing = subprocess.Popen(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")   # sandboxing: in the box, with a time limit
                    while True:
                        try: done = subprocess.CompletedProcess(doing.args, 0, doing.communicate(timeout=0.1)[0]); break
                        except subprocess.TimeoutExpired:
                            if ESC.is_set(): subprocess.run(["docker", "exec", box, "sh", "-c", "kill -9 -1"], capture_output=True)   # every command in the box, not the box
                done.returncode = doing.returncode
                if ESC.is_set(): done.stdout += "\n[your doing stopped before done]"   # resilience: keep what it had printed
                elif done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
                trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout), failed=failed(cmd, done.stdout))
                why = failure(cmd, done.stdout) if done.returncode and not ESC.is_set() else None
                if attempt == 2 or why != "transient" or not reads(cmd): break
                print("[a failure that passes: trying once more]"); time.sleep(1)
            if lent: bridge(False)
            if why == "partial": done.stdout += "\n(it may have partly run: check before repeating it)"
```

The clock now starts inside the loop, after Lesson 5's network question, so each try's `seconds` in the trace is the command's own.

Most of that is Lesson 6's, moved in one level. What's new:

**`+=`** on the ESC line. In Lesson 6 it was `=`; now a stopped command keeps what it had printed, with `[your doing stopped before done]` after it. One character, and the model sees what its command did before you stopped it.

**`why`.** When the command failed, and not because you pressed ESC, `failure()` asks Jev what kind of failure it was. A command that succeeded, or that you stopped, isn't asked about.

**The second try.** The loop breaks unless this was the first try, Jev was sure the failure is transient, and `reads()` is sure the command only reads. Otherwise quark says so, waits a second and runs it again. The model only sees the second try's result; the first is in the trace, which gets a `tool` line for each try.

**The warning.** If Jev was sure the failure was partial, the result gets "(it may have partly run: check before repeating it)", the same advice the "interrupted" result gives after a crash.

Asking Jev is model interface, through Lesson 5's `ask()`. What quark does with the answer, another try or a line on the result, is output's: it's how the tool runs and what its result says. As everywhere Jev appears, when it isn't sure or doesn't answer, quark does what it did before: the result goes back as it came.

Everything else is unchanged on purpose. ESC still stops the stream and kills the commands exactly as in Lesson 6; this layer only decides what's kept afterwards. The guard still runs before the box. The trace now records failed models, and a `model` event's `seconds` includes the retries, so a flaky API shows up as slow calls next to `model_failed` events. The system prompt doesn't tell the model that the harness retries or that it may have been resumed; that would be a decision about context, and this layer doesn't make it. (It can read `call()` and `unfinished()` in its own file, as it always could.)

### Run it

You need Docker running, as in Lesson 5. Start each run in a fresh scratch folder. Each is `uv run --project /path/to/building-agents /path/to/building-agents/production/08-resilience/quark.py`, which I'll write as `quark.py`. Answers piped to prompts aren't echoed. The stand-in is the concept's `flaky.py`, with one more thing to know: it reads each response whole before passing it on, so through it the stream arrives all at once. That doesn't matter for these runs.

**The preferred model is down.** The stand-in answers "529 overloaded" to every request for `claude-sonnet-5-5`, and forwards the rest:

```bash
mkdir /tmp/demo && cd /tmp/demo && echo "notes" > notes.txt
python3 flaky.py 8105 claude-sonnet-5-5 &
ANTHROPIC_BASE_URL=http://127.0.0.1:8105 quark.py "How many bytes is notes.txt? Answer in one line."
```

```
$ wc -c notes.txt
6 notes.txt

notes.txt is 6 bytes.
```

You don't see the failures in the output: the run looks like any other. The trace does (shown with only the fields that matter here):

```
{"event":"start"}
{"event":"model_failed","model":"claude-sonnet-5-5","error":"OverloadedError"}
{"event":"model","seconds":4.91,"stop_reason":"tool_use"}
{"event":"tool","seconds":0.09}
{"event":"model_failed","model":"claude-sonnet-5-5","error":"OverloadedError"}
{"event":"model","seconds":4.26,"stop_reason":"end_turn"}
```

Both calls had four failed requests to `claude-sonnet-5-5` (the first try and the SDK's three retries), then one to `claude-opus-5-5` that worked; the stand-in's log shows ten requests for two calls. The `seconds` of the two `model` events, 4.91 and 4.26, are mostly the backoff. Every call tries the preferred model again from scratch: a few seconds a call while it's down, and quark is back on it the moment it recovers.

**Nothing answers.** Now the stand-in fails every request, for every model:

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:8106 quark.py "How many bytes is notes.txt? Answer in one line."
```

```
[the model isn't answering. Everything so far is in the episode; run quark again to pick it up]
$ ls .quark .quark/episodes
.quark:
episodes
traces.jsonl

.quark/episodes:
2026-10-06T23-21-04.jsonl
```

It tried both models, four requests each, gave up and said so. There's no save file: the episode is the record. Then the API comes back (no `ANTHROPIC_BASE_URL`) and I run `quark.py` again with no input, answering `y` when asked, and `/q` when it finished:

```
unfinished session: 'How many bytes is notes.txt? Answer in one line.'. pick it up? [y/N] $ wc -c notes.txt
6 notes.txt

notes.txt is 6 bytes.

>
```

The session was picked up from its episode, and finished in it: that one file now holds all four messages. The trace shows the second `start` as resumed, with no new input:

```
{"event":"start","input":"How many bytes is notes.txt? Answer in one line.","resumed":false}
{"event":"model_failed","model":"claude-sonnet-5-5","error":"OverloadedError"}
{"event":"model_failed","model":"claude-opus-5-5","error":"OverloadedError"}
{"event":"start","input":"","resumed":true}
{"event":"model","stop_reason":"tool_use"}
{"event":"tool"}
{"event":"model","stop_reason":"end_turn"}
```

**The harness is killed.** This is the one that matters most. The task is one slow command, started in the background with `y` piped in for the guard, and killed with `kill -9` on its process ID eight seconds after the guard's question appeared, in the middle of the command. I ran the repo's own Python directly, so `$!` is the harness itself (`uv run` puts a wrapper in between). That's `kill` on a PID, not `pkill`, which matches on names and can match far more than you meant:

```bash
(yes y | /path/to/building-agents/.venv/bin/python /path/to/building-agents/production/08-resilience/quark.py "Run exactly this one command: sleep 15 && echo finished > flag.txt   (it is slow on purpose). Then tell me what flag.txt contains." > out1.txt 2>&1 & echo $! > pid)
until grep -q allow out1.txt; do sleep 0.25; done; sleep 8; kill -9 $(cat pid)
cat out1.txt
```

```
$ sleep 15 && echo finished > flag.txt
allow `sleep 15 && echo finished > flag.txt`? (Jev: delete, 0.61) [y/N]
```

That's all it printed before it died. (Jev called the command a delete, unsure at 0.61: `>` replaces whatever `flag.txt` held, so that's a fair reading.) What it left, and then the same folder a few seconds later:

```
$ ls -a . .quark
.:
.
..
.quark
out1.txt
pid

.quark:
.
..
episodes
traces.jsonl

$ ls
flag.txt
out1.txt
pid
```

The episode was written when the model asked for the command, before it ran. `flag.txt` isn't there, and then it is: the harness was killed, but its container wasn't (`atexit` can't run after `kill -9`), so the command finished in it. (I removed the leftover container and its network with `docker rm -f` and `docker network rm` afterwards.) That's exactly the case the "interrupted" result is for: the command did run, and the harness doesn't know. Now `quark.py` again, answering `y` to resume and `/q` at the end:

```
unfinished session: 'Run exactly this one command: sleep 15 && echo finished > fl'. pick it up? [y/N] The harness reported that the command was interrupted. I'll check whether it ran before repeating it.
$ ls -l flag.txt; cat flag.txt
-rw-rw-rw- 1 root root 9 Oct  6 23:21 flag.txt
finished

`flag.txt` contains `finished`.

The harness said my first run was interrupted, so I checked the file before running the command again. The file already existed with that content, which means the command had finished. I didn't run it a second time.

>
```

The model was told the command was interrupted and may or may not have run, and it did what that wording asks: it looked, found the file, and didn't run the command again. If `flag.txt` hadn't been there, the same sentence would have led it to run the command once. It's the model's call, made with the facts. (The guard didn't ask about `ls -l flag.txt; cat flag.txt`: Jev was sure it only reads.)

**A failure that passes.** The concept's locked database, through quark. `shop.db` and `hold.py` are the ones from the concept. This time I stop the holder as soon as quark's trace has the first try's `tool` line:

```bash
python3 makedb.py
python3 hold.py & HOLDER=$!
(until grep -qs '"event": "tool"' .quark/traces.jsonl; do sleep 0.05; done; kill $HOLDER) &
quark.py 'How many orders are in shop.db? Run exactly this command: python3 -m sqlite3 shop.db "select count(*) from orders"'
```

```
$ python3 -m sqlite3 shop.db "select count(*) from orders"
[a failure that passes: trying once more]
(42,)

There are 42 orders in shop.db.
```

There was no question from the guard (Jev was sure the `select` only reads), and the first try's `database is locked` never reached the screen or the model: Jev was sure it was transient, `reads()` was sure the command only reads, and quark tried once more. The trace has both tries:

```
{"event":"tool","seconds":5.4,"exit":1,"failed":0.99}
{"event":"tool","seconds":0.32,"exit":0,"failed":0.03}
```

The first took 5.4 seconds, SQLite's wait for the lock, and exited 1; Lesson 7's `failed` gave it 0.99. The second, about a second later, took a third of a second and worked.

**A failure that half happened.** The concept's `migrate.py`, with `y` for the guard:

```bash
quark.py "Run python3 migrate.py once and tell me how it went. Don't fix anything."
```

```
$ python3 migrate.py
allow `python3 migrate.py`? (Jev: other, 1.00) [y/N] error: payments: no column named email
migrated users
migrated orders
migrated items

(it may have partly run: check before repeating it)
The migration only partly succeeded. I ran `python3 migrate.py` once, as you asked.

- **Failed:** `payments` stopped with `error: payments: no column named email`.
- **Succeeded:** `users`, `orders` and `items` each printed "migrated".

The harness flagged that the script may have partly run, so some changes may already be applied. Re-running it blindly could repeat them. I didn't check the exit code, the database or the script, and I changed nothing, as you asked.

The error suggests the script expects an `email` column in `payments` that isn't there. That is a guess from the message alone, since I haven't read `migrate.py`.
```

(The error comes before the three `migrated` lines because Python holds back what a script prints until it ends when its output isn't a terminal, and the error goes out at once.) Jev was sure it was partial, quark added the warning, and the model passed it on instead of running the script again.

**You press ESC while it's saying something.** ESC needs a terminal, so these two runs are in chat mode, typed at the prompt. I asked for something long and pressed ESC a few seconds after the answer started to appear, then `/q`:

```
> without running anything, work out whether 1000003 is prime, then explain how you know in about 400 words.
**1000003 is prime.** I'm answering from recall and partial hand checks. I haven't run anything, and I haven't done the full proof by hand.

**What I remember.** 1000003 is the smallest prime above one million. The next primes after it are 1000033, 1000037 and 1000039. This is a well-known fact, and it is my main basis for the answer.

**How you would prove it.** A composite number n must have a prime factor no larger than √n. Since 1000² = 1,000,000 and 1001² = 1,002,001, the square root of 1000003 is just over 1000. So it is enough to show that none of the 168 primes up to 1000 divides it. If none does, the number is prime.

**Checks I can do by hand:**

- **2 and 5:** the number ends in 3, so neither divides it.
- **3:** the digit sum is 1+3 = 4, which is not a multiple of 3.
- **7, 11, 13 and 37:** these all divide 999999, because 999999 = 3³·7·11·13·37. That means 10⁶ ≡ 1 modulo each of them. So 1000003 = 10⁶ + 3 ≡ 1 + 3 = 4, and the remainder is 4 for each prime. None divides it.
- **Other small primes:** I can do direct divisions too. For example, 17 × 58823 = 999,991, which leaves a remainder of 12. Likewise 19 × 52631 = 999,989, which leaves 
Understood, I'll stop there.

The short version: 1000003 is prime. I'm confident of that from memory, since it's the smallest prime above one million. I haven't verified it by running anything. The hand checks I did cover 2, 3, 5, 7, 11, 13, 17, 19 and 37, and none of them divides it. A full proof needs trial division by every prime up to about 1000, which is 168 primes.

If you'd like, I can run that check and confirm it. Or tell me what you wanted to redirect to.

> /q
```

The second answer picks up where the first stopped: it knows which primes it had already ruled out, because that text is in its working memory. In Lesson 6 it would have been told only that you interrupted it, with no idea what it had already said. The episode shows what was kept (each block cut down to its type and the end of its text, with this `jq`):

```bash
jq -c '{role, content: (if (.content|type)=="string" then .content[:50] else [.content[] | if .type=="text" then {type, end: .text[-50:]} elif .type=="thinking" then {type, signed: (.signature|length > 0)} else {type} end] end)}' .quark/episodes/*.jsonl
```

```
{"role":"user","content":"without running anything, work out whether 1000003"}
{"role":"assistant","content":[{"type":"thinking","signed":true},{"type":"text","end":"2. Likewise 19 × 52631 = 999,989, which leaves 14."}]}
{"role":"user","content":[{"type":"text","end":"lf interrupted what you were saying — acknowledge]"}]}
{"role":"assistant","content":[{"type":"text","end":"irm it. Or tell me what you wanted to redirect to."}]}
```

The model's first message has both of its blocks: the thinking it did before it started writing, finished and signed, and the text as far as it got. The text ends a little later than the screen does ("which leaves 14.", where the screen stopped at "which leaves"): that was the piece of the stream that arrived just as ESC was pressed. The SDK had already added it to the message when `unless_esc()` saw ESC and chose not to show it. So the second answer counts 19 among the primes it checked.

**You press ESC while it's doing something.** A command that prints a line a second, `y` to the guard, ESC about three seconds later, and `/q`:

```
> run this as one command: for i in 1 2 3 4 5 6 7 8 9 10; do echo step $i; sleep 1; done
$ for i in 1 2 3 4 5 6 7 8 9 10; do echo step $i; sleep 1; done
allow `for i in 1 2 3 4 5 6 7 8 9 10; do echo step $i; sleep 1; done`? (Jev: read, 0.87) [y/N] y
step 1
step 2
step 3

[your doing stopped before done]
You interrupted the command, so it stopped after step 3 and never reached step 10. Do you want me to run it again from the start, or leave it?

> /q
```

It saw `step 1` to `step 3`, so it knew exactly how far the command got and what never ran. Here's the result it was given, from the episode:

```bash
jq -c '.content[]? | select(.type=="tool_result")' .quark/episodes/*.jsonl
```

```
{"type":"tool_result","tool_use_id":"toolu_01AM7xKcDoFA2HNgzB967fLx","content":"step 1\nstep 2\nstep 3\n\n[your doing stopped before done]"}
```

In Lesson 6 that result was only `[your doing stopped before done]`. The trace's `tool` line for it has `exit` 137 and `chars` 54: the output and the note. Jev wasn't asked what kind of failure it was: you stopped it, and that isn't a failure to retry.

**A request is cut off.** `max_tokens` is 16,384, so a real cut-off is rare and slow to wait for. This run uses a copy with the main call's `max_tokens` lowered to 400 (`sed 's/response = call(unless_esc, max_tokens=16384,/response = call(unless_esc, max_tokens=400,/'`), `y` piped in, and a task that needs a long command (I call the copy `quark-400.py`):

```bash
yes y | quark-400.py "write a 40-line poem about rivers into poem.txt, in one command"
```

```
$ None
[cut off, not run]
$ None
[cut off, not run]
$ None
[cut off, not run]
$ None
[cut off, not run]
$ None
[cut off, not run]
$ None
[cut off, not run]
$ None
[cut off, not run]
$ None
[cut off, not run]
$ None
[cut off, not run]
$ None
[cut off, not run]
I couldn't write `poem.txt`. Every one of my attempts was cut off before the command was fully formed, so nothing ran and the file doesn't exist.

I don't know why the calls came out empty. The 400-token response limit is my best guess, but even the shortened attempts failed, so that may not be the whole story.

If you're happy to relax "in one command", I could write the poem in two or three smaller appends. Or you could tell me whether a shorter poem is acceptable.
```

Every response hit the limit while the model was writing its command, before any of it was complete, so each request arrived with no `cmd` at all (`input` is `{}` in the episode), which is why the line says `$ None`. None of them ran. Each was answered with the cut-off result, and after the tenth the model stopped trying and told me what was happening, with nothing half-written on disk. Its guess about the 400-token limit isn't a guess from nowhere: the copy is the file it reads as its own mechanics, and the 400 is in it. With the real limit, the same rule catches the rare command that's too long to finish.

## Other things we could do

quark has one retry setting, one backup model, one question for a failed command, and no file of its own. These are the choices you make when you build it.
- **What counts as a failure.** Retry the transient ones (a dropped connection, a timeout, 429, 5xx) and surface the rest. A bad key shouldn't be retried at all. A request that's too long isn't a failure to wait out, it's something to fix, and in quark that's Lesson 4's compaction.
- **How to wait.** Exponential backoff, with jitter, a cap on any single wait, and a limit on the total, so a run spends at most so long on one call. Honoring `Retry-After` when the server sends it. Or a client-side limiter that keeps *under* the rate limit in the first place, so the 429 never comes.
- **What the backup is.** A different model, as in quark. The same model from a different provider (the Claude models are also served through the big cloud platforms) or a different region. Or a smaller model that's good enough to finish the task. Whichever it is, it has costs: the prompt cache is per model, so a switch pays full price for the whole prompt once, and a backup may be worse at the task, so a harness that fails over should say so.
- **How long a failure is remembered.** quark forgets: every call starts with the preferred model. A *circuit breaker* remembers: after a model fails, leave it alone for a minute, so a long outage costs one slow call instead of one per step.
- **When a stream breaks partway.** quark streams from Lesson 1, but if the connection drops in the middle of a response, `call()` starts the request again on the next model, and what had arrived is thrown away. A harness could keep it, as quark keeps what had arrived when you press ESC. And a timeout on *silence* ("nothing for 30 seconds") can replace one on the whole reply, which catches a stuck call much sooner than five minutes.
- **What's kept when it's stopped.** quark keeps whole blocks: text that had started, thinking that was signed, tool requests (answered as never run), and what a stopped command printed. It drops thinking that hadn't been signed. A harness could keep that as plain text instead, or keep a half-written command as text so the model can see what it was about to do.
- **What a tool failure looks like.** A time limit, with the whole process group killed so its children go too. A cap on output. Errors flagged as errors, so the model reads them as failures. Retrying a *read* automatically is usually safe; retrying a *write* never is, unless the tool is built so that doing it twice is the same as doing it once.
- **How state is saved.** After every step, as in quark. To a file, or a database. As a log of events from which the state can be rebuilt, which also gives you a history of the run. With a unique ID on each action, so a replay can tell "done" from "not done" without asking the model.
- **How a run restarts.** Asking you, as in quark. Or automatically, by something that watches the process and starts it again (a supervisor such as systemd, or an orchestrator). Or by a service built for this.
- **How it ends.** A signal such as Ctrl-C or SIGTERM can be caught: save, clean up, exit, so a stop you asked for loses nothing. A hard kill can't be caught, which is why the record is written *before* the work and not after.

It can be a product on its own. Gateways like [LiteLLM](https://www.litellm.ai) and [OpenRouter](https://openrouter.ai) sit in front of several models and providers and handle retries, fallbacks and rate limits for you. If your harness sends every call to one of those, the model interface half of this layer is theirs. For the other half, durable-execution systems such as [Temporal](https://temporal.io), and checkpointing in agent frameworks such as [LangGraph](https://www.langchain.com/langgraph), record each step of a long process, so that after a crash it picks up at the step it was on. The idea is the same as quark's episode, with more machinery.

A few ideas worth knowing if you build more of it yourself:

- **Retries you can see.** Turn the SDK's retries off (`max_retries=0`) and write the loop yourself: a few tries per model, a wait that doubles each time with a random factor between a half and one, the server's `retry-after` when it sends one, and a line printed for every failed try with how long it's waiting. You lose nothing the SDK did, and a slow run explains itself.
- **A bench.** When a model has failed every try, note the time and skip it for the next minute. The next call goes straight to the backup instead of spending the same few seconds of backoff on a model that's still down. That's the circuit breaker from the list above, in about three lines.
- **Commands that can't outlive their limit.** Start each command in its own process group, and when its time is up kill the whole group, so the children go too; killing only the shell leaves them running and holding the output open. Cut the output at a few thousand characters, with a note, and end every result with how the command ended: its exit code, or that it was killed.
- **A hand-written list of reads.** Jev decides whether a command only reads in quark. You could decide it in code instead: a short list of programs that only look, with no pipes, redirects or chaining allowed, and none of `curl`'s flags that send or save. It's stricter and will refuse a retry Jev would allow, but the line between "safe to run twice" and "not" is then drawn by code you can read.
- **A checkpoint file.** A save file of the messages, written to a temporary name and renamed over the old one, so it's always all of the old one or all of the new one, never half. Write it before the first request, after each reply and after each set of results, so it always ends at a point the API will accept once the "interrupted" results are added, and delete it when the run finishes. Put the command itself in each "interrupted" result, so the model doesn't have to look back for it. quark doesn't need one, because its episode is already that record.
- **Give Jev something to read.** Jev can only judge what a command printed. A `curl -sf` that hides its own error message prints nothing but its exit code, and with only `(exit 22)` to go on Jev guessed `permanent` at 0.47, too unsure to act on. The same request with `-sS`, which prints `The requested URL returned error: 503`, came back `transient`. A tool that says what went wrong is easier to recover from, for Jev and for the model.

## What to take away

**The rule:** assume the call can fail, and make failure something the harness handles instead of something that ends the run. Retry what passes a bounded number of times, have somewhere else to go when the preferred model is out, and stop with a sentence when everywhere is. Run a failed command again only when it's sure to be a failure that passes and sure to only read. Answer every tool request, even a broken one, with a result the model can read. When you stop it, keep what it had already said and done. And keep a record written before each step, so that when the harness itself fails, what was in flight can be reported as *unknown*, not guessed at and not lost.

Notice what resilience never does. It sits in the model interface and output, and for recovery it reads the record context already keeps; it adds no store of its own. Its question to Jev goes through Lesson 5's `ask()`, like every question before it. Control flow is the same loop with the same stop conditions: a retry happens inside one call or one command, so the loop sees a step that took longer, and the only new way out is `Down`. Input is untouched apart from one question at startup, asked with the same `read()`. And what the model is shown changes only in what it's told about its own work: the "interrupted" result, the cut-off one, the partial warning, and the partial work an ESC used to throw away, each written like any other message.

**What's missing:** resilience keeps a run alive and recoverable; it doesn't make it fast or cheap. Every call re-sends the whole conversation, and only the system prompt is cached, so the messages are paid for in full every time. A command that prints a megabyte puts a megabyte in the next request. Three commands that could run side by side wait for each other, because quark asks for one at a time and runs them one after another. And when working memory fills up, the summary is written by the same big model as everything else, and every request, a one-line lookup or a redesign, goes to that same big model. Making each step smaller, faster and cheaper is its own layer.

**→ [Lesson 9: Performance](../09-performance/)**
