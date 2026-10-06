# Lesson 8: Resilience

> 🎥 **Video:** coming soon

Lesson 7 ended on a list of things that go wrong when a run is long enough: the API drops a call, a command hangs, the process dies halfway through and the work goes with it. Everything so far assumed that the thing on the other side of a call answers, and answers sensibly. Over a long run that assumption is the one that fails first.

Resilience is how the harness keeps going, or stops cleanly, when something doesn't answer. It has two jobs. The first is to get through the failures that pass: a dropped connection, a request told to slow down, a service that's briefly overloaded, a command that never comes back. The second is to leave things in a state you can pick up from when a failure doesn't pass, so that the hour of work before it isn't lost.

This is a production layer, so it adds hardening, not a new primitive. It's **built on the model interface and output**, the two places where the harness reaches out of itself and the world gets to say no. The model interface is the call to the API (Lesson 1), and the API is a service across a network, so it can be slow, busy or gone. Output is what runs the model's words (Lesson 2), and what runs there is arbitrary, so it can hang, flood or die. Everything below happens inside those two. The loop, the person's input and what the model is shown are left as they are.

The mechanism, first in the model interface. Not every failure means the same thing, so the first step is to sort them:

- **Worth trying again.** The network dropped, the request timed out, the server said slow down (429), or the server itself had trouble (any 5xx, and Anthropic's "overloaded", 529). Nothing is wrong with the request. Send the same one a moment later and it will probably work.
- **Not worth trying again.** A bad API key (401), a request the API won't accept (400), a model that doesn't exist (404). Sending it again gets the same answer, so retrying only delays the error. These go up to the code that can do something about them, or to you.

For the first kind, the way to retry matters. Wait longer after each failure (*exponential backoff*: one second, two, four), so a service that's struggling isn't hit at full speed. Add a little randomness (*jitter*), so a thousand clients that failed together don't all come back together. If the server said how long to wait, wait that long. And put a limit on it: a few tries, not forever. The Anthropic SDK already does all of this for you: it retries connection errors, 408, 409, 429 and 5xx with backoff, and the number of tries is the `max_retries` setting. So quark doesn't write a retry loop; it turns the setting up and sets a timeout. What the SDK can't do is choose a different model. That's the one thing quark adds here: when the preferred model is still failing after the SDK has given up, try a backup, and when nothing answers, stop with a message instead of a stack trace.

Then output. The model asks for a command and output runs it, and a command can fail in a way the harness doesn't see coming: it hangs (Lesson 7 already puts a time limit on that), it prints bytes that aren't text, or the model's request itself arrives broken, cut off in the middle by the token limit, with a command that's half a sentence. The rule for all of them is the one Lesson 2 started with: every request gets an answer the model can read. A result that says *this was cut off, it wasn't run, send it again shorter* is something the model can act on. A crash isn't.

Last, picking a task back up. If the harness is killed during a long task, the whole exchange so far (everything that crossed the model interface in one direction and output in the other) is in the working memory, and that's gone with the process. So the harness writes it down after each step, to a file, in a way that can't leave a half-written file behind. When it starts and finds one, it can offer to continue.

There's one trap, and it's the reason this isn't just "load the file." Suppose the harness died while a command was running. The saved record ends with the model asking for that command and no result. The API won't accept a request in that state: every request for a tool must be followed by a result for it. And the harness can't simply run the command again, because it may already have run: the command that was killed might have been `git push`, or sent an email, or appended a line to a file. It can't know, so it says so. The missing result becomes an error result: *interrupted; this may or may not have run; check before repeating it.* Then the model, which is the one that knows what the command was for, looks at the world and decides. It isn't a guess made by the harness.

None of this makes the model right, and it doesn't make a failed run succeed. It makes a run that hits trouble end up either finished or somewhere you can start again from.

## The worked example

Here's Lesson 7's agent with resilience added. It's the whole of [`quark.py`](./quark.py), with the system prompt shortened to `...` as before. The new code is the client settings, `MODELS` with `ask()` and `Down`, `SESSION` with `save()` and `unfinished()`, a few lines at the start of the run, and a few in the loop that go with them. The rest is Lesson 7 unchanged, sandbox, guardrails and tracing included:

```python
import subprocess, sys, os, datetime, json, time, uuid, re, atexit
from anthropic import Anthropic, BadRequestError, APIConnectionError, APIStatusError

client = Anthropic(timeout=300, max_retries=3)
run = uuid.uuid4().hex[:8]
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def trace(**event):
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "run": run, **event}) + "\n")


MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]
class Down(Exception): pass
def ask(**request):
    for model in MODELS:
        try: return client.messages.create(model=model, **request)
        except (APIConnectionError, APIStatusError) as e:
            if isinstance(e, APIStatusError) and e.status_code < 500 and e.status_code != 429: raise
            trace(event="model_failed", model=model, error=type(e).__name__)
    raise Down()


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
    summary = ask(max_tokens=2048, system=system(), messages=keep + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}])
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
        reply = ask(max_tokens=16384, system=system(), tools=tools, messages=working_memory)
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
    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if not cmd or (reply.stop_reason == "max_tokens" and block is reply.content[-1]):
                print("[cut off, not run]")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": "your request was cut off at the token limit, so it was not run. Send it again, shorter.", "is_error": True})
                continue
            if (no := guard(cmd)):
                print(f"[{no}]")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": no, "is_error": True})
                continue
            start = time.time()
            done = subprocess.run(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            if done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
            trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})

    if results:
        working_memory.append({"role": "user", "content": results})
        continue
    os.remove(SESSION)
    if not chat or (task := input("\n> ")) == "/q":
        break
    working_memory.append({"role": "user", "content": task})
    steps, spent = 0, 0
```

There are five additions.

**The client.** `Anthropic(timeout=300, max_retries=3)`. The SDK does the retrying, with backoff, and honors the server's `Retry-After`. `timeout` is how long to wait on a single request before giving up on it, and a timeout is a failure like any other: it's retried too. It's long, five minutes, because a reply of 16,000 tokens takes minutes to write, and a limit that's too short would turn slow answers into failures. `max_retries=3` is the SDK's default, written out so you can see it's a choice.

**`ask()`.** Every call to the model now goes through it, the main one and the summary call in `compact()`. It tries each model in `MODELS`, in order. A call that fails *after the SDK's retries* with something transient (a lost connection or timeout, 429, or any 5xx) is written to the trace as `model_failed` and the next model is tried. Everything else is re-raised: a bad key, a bad request, and in particular the "prompt is too long" error that Lesson 4's compaction is waiting for. If every model has failed, `ask()` raises `Down`, which the loop catches and turns into a message and an exit. The test is on the status code and not on a list of exception classes, because the SDK has a class for each (`RateLimitError`, `InternalServerError`, `OverloadedError`, `ServiceUnavailableError`...) and they aren't all subclasses of each other. The first version I wrote caught a list of classes and missed 529, the overloaded error, which is the one you most want to catch.

**`save()` and `unfinished()`.** `save()` writes the task and the working memory to `.quark/session.json` after each step. It writes to a temporary file first and then `os.replace`s it over the real one, which is a single step that either happens or doesn't, so a crash can't leave half a file. The content blocks the API returned are objects, not dicts, so `default=` turns them into plain JSON with `model_dump`. `unfinished()` runs at startup. If there's a saved session, it shows you the task and asks. A `y` loads it and, if the record ends in the model's request for tools, adds the "interrupted" results described above, one for each request. Anything else, and the run starts fresh and the old file is overwritten the first time it saves. The saved file is deleted when the model finishes without asking for a tool, so a file left behind always means a run that didn't finish.

**The loop.** `save()` is called at the top of every pass and right after the model's reply (that's why the `working_memory.append` for the reply moved up: the reply has to be in the list before it can be saved, and has to be saved before any tool runs. If the harness dies during the command, the file already says what was asked.) `except Down` stops the run with a message that says the work is saved. The `start` event in the trace now records whether the run was `resumed`.

**The tool call.** Three small changes, all for output's side of the layer. `block.input.get("cmd")` replaces `block.input["cmd"]`, so a request with no command is answered and not a `KeyError`. If the reply was cut off by `max_tokens` and this is its last block, the command may be half a command, so it isn't run: the model gets an error result saying so. And `errors="replace"` on the subprocess means a command that prints bytes that aren't valid text produces `�` characters in the result, not a `UnicodeDecodeError` that kills the harness.

Everything else is unchanged on purpose. The guard still runs before the box does. The sandbox still holds the commands. Tracing still records every call, and now it also shows how long a call took *including* the retries: the `seconds` of a `model` event is the whole time from request to answer, so a flaky API shows up as slow calls and `model_failed` events in the same file. The system prompt is also unchanged; it doesn't tell the model that the harness will retry or that it may have been resumed. That would be a decision about context.

## Run it

You need what Lesson 7 needed: Docker running, and `uv`. Start in a scratch folder, not in this repo, because the box mounts it and the session file goes in it. Each run below is `uv run --project /path/to/building-agents /path/to/building-agents/production/08-resilience/quark.py`, which I'll write as `quark.py`. Answers piped to prompts aren't echoed, so a prompt is followed directly by whatever comes next.

Failures that actually happen are hard to schedule, so for the demos I used a stand-in for the API that fails on purpose and passes everything else through to the real one. It's about 30 lines of Python, built on the standard library, and it never prints headers, so your key doesn't appear anywhere. Save it as `flaky.py`:

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

The harness reaches it through `ANTHROPIC_BASE_URL`, which the SDK reads. Nothing in `quark.py` knows about it.

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

You don't see the failures in the output: the run looks like any other. The trace does:

```
{"event":"start"}
{"event":"model_failed","model":"claude-sonnet-5-5","error":"OverloadedError"}
{"event":"model","seconds":5.15,"stop_reason":"tool_use"}
{"event":"tool","seconds":0.07}
{"event":"model_failed","model":"claude-sonnet-5-5","error":"OverloadedError"}
{"event":"model","seconds":3.81,"stop_reason":"end_turn"}
```

Both calls had four failed requests to `claude-sonnet-5-5` (the first try and the SDK's three retries), then one to `claude-opus-5-5` that worked. That's what the stand-in's log shows too, ten requests for two model calls. And look at the `seconds` of the two `model` events: 5.15 and 3.81, where a normal call here takes one or two. That's the backoff. Every call tried the preferred model again from scratch. That's a choice (the fuller example makes a different one, below): it costs a few seconds a call while the model is down, and means quark is back on its preferred model the moment it recovers.

**Nothing answers.** Now the stand-in fails every request, for every model:

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:8106 quark.py "How many bytes is notes.txt? Answer in one line."
```

```
[the model isn't answering. Everything so far is saved; run quark again to pick it up]

$ ls .quark
session.json
traces.jsonl
```

It tried both models, gave up and said so, in one line and not a stack trace. The session file is there, with the task and the one message so far. Then the API comes back (no `ANTHROPIC_BASE_URL` now, so no stand-in) and I run `quark.py` again, answering `y` when asked, and `/q` when it finished:

```
unfinished run: 'How many bytes is notes.txt? Answer in one line.'. pick it up? [y/N] $ stat -c %s notes.txt
6

notes.txt is 6 bytes.

>
```

The task was picked up from the file. The trace shows it as a second `start`, with `resumed` set:

```
{"event":"start","task":"How many bytes is notes.txt? Answer in one line.","resumed":false}
{"event":"model_failed","model":"claude-sonnet-5-5","error":"OverloadedError"}
{"event":"model_failed","model":"claude-opus-5-5","error":"OverloadedError"}
{"event":"start","task":"How many bytes is notes.txt? Answer in one line.","resumed":true}
{"event":"model","stop_reason":"tool_use"}
{"event":"tool"}
{"event":"model","stop_reason":"end_turn"}
```

**The harness is killed.** This is the one that matters most, and the hardest to stage. The task is one slow command, `sleep 15 && echo finished > flag.txt`, started in the background so I can kill it, with `y` piped in for the guard. The kill is `kill -9`, on the process ID that the shell gave me, which is the Python process itself because I ran the repo's own Python directly. (`uv run` puts a wrapper process in between, and `$!` would be the wrapper's ID.) (That's not `pkill`, which matches on names and can match a lot more than you meant.) I waited nine seconds, so it was in the middle of the command, and then killed it:

```bash
(yes y | /path/to/building-agents/.venv/bin/python /path/to/building-agents/production/08-resilience/quark.py "Run exactly this one command: sleep 15 && echo finished > flag.txt   (it is slow on purpose). Then tell me what flag.txt contains." > out1.txt 2>&1 & echo $! > pid)
sleep 9; kill -9 $(cat pid)
cat out1.txt
```

```
$ sleep 15 && echo finished > flag.txt
allow `sleep 15 && echo finished > flag.txt`? [y/N]
```

That's all it printed before it died. `ls` shows what was left, in the folder, and then again once the command's fifteen seconds were up:

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
session.json
traces.jsonl

$ ls
flag.txt
out1.txt
pid
```

`.quark` has `session.json`, which was written when the model asked for the command, before it ran. `flag.txt` isn't there yet, and then it is: the harness was killed, but the container was not (Lesson 7's warning about `kill -9`), so the command went on and finished in it. (I removed the leftover container with `docker rm -f` afterwards.) That's exactly the case the "interrupted" result is for. The command did run, and the harness doesn't know. Now run `quark.py` again, answering `y` to resume the run, `y` to the guard's question, and `/q` at the end:

```
unfinished run: 'Run exactly this one command: sleep 15 && echo finished > fl'. pick it up? [y/N] $ ls -l flag.txt; cat flag.txt; date
allow `ls -l flag.txt; cat flag.txt; date`? [y/N] -rw-rw-rw- 1 root root 9 Oct  5 23:52 flag.txt
finished
Mon Oct  5 23:52:17 UTC 2026

`flag.txt` contains `finished`.

The harness reported my first run as interrupted, so I checked the file before running the command again. The file already existed, timestamped 23:52, so the command did finish. I didn't run it a second time.

>
```

The model was told the command was interrupted and may or may not have run, and it did what that wording asks: it looked, with `ls -l flag.txt; cat flag.txt; date`, found the file and didn't run the command again. If `flag.txt` hadn't been there, the same sentence would have led it to run the command once. It's the model's call, made with the facts, which is the point.

## Going further

**What else resilience can be:** quark has one retry setting, one backup model and one file. These are the choices you make when you build it.
- **What counts as a failure.** Retry the transient ones (a dropped connection, a timeout, 429, 5xx) and surface the rest. A bad key shouldn't be retried at all. A request that's too long isn't a failure to wait out, it's something to fix, and in quark that's Lesson 4's compaction.
- **How to wait.** Exponential backoff, with jitter, a cap on any single wait, and a limit on the total, so a run spends at most so long on one call. Honoring `Retry-After` when the server sends it. Or a client-side limiter that keeps *under* the rate limit in the first place, so the 429 never comes.
- **What the backup is.** A different model, as in quark. The same model from a different provider (the Claude models are also served through the big cloud platforms) or a different region. Or a smaller model that's good enough to finish the task. Whichever it is, it has costs: the prompt cache is per model, so a switch pays full price for the whole prompt once, and a backup may be worse at the task, so a harness that fails over should say so.
- **How long a failure is remembered.** quark forgets: every call starts with the preferred model. A *circuit breaker* remembers: after a model fails, leave it alone for a minute, so a long outage costs one slow call instead of one per step. The fuller example does that.
- **Streaming.** Stream the reply and a dropped connection costs you only the end of it, because you've kept what arrived. A timeout on *silence* ("nothing for 30 seconds") then replaces one on the whole reply, which catches a stuck call much sooner than five minutes.
- **What a tool failure looks like.** A time limit, with the whole process group killed so its children go too. A cap on output. Errors flagged as errors, so the model reads them as failures. Retrying a *read* automatically is usually safe; retrying a *write* never is, unless the tool is built so that doing it twice is the same as doing it once.
- **How state is saved.** After every step, as in quark. To a file, or a database. As a log of events from which the state can be rebuilt, which also gives you a history of the run. With a unique ID on each action, so a replay can tell "done" from "not done" without asking the model.
- **How a run restarts.** Asking you, as in quark. Or automatically, by something that watches the process and starts it again (a supervisor such as systemd, or an orchestrator). Or by a service built for this.
- **How it ends.** A signal such as Ctrl-C or SIGTERM can be caught: save, clean up, exit, so a stop you asked for loses nothing. A hard kill can't be caught, which is why the file is written *before* the work and not after.

It can be a product on its own. Gateways like [LiteLLM](https://www.litellm.ai) and [OpenRouter](https://openrouter.ai) sit in front of several models and providers and handle retries, fallbacks and rate limits for you. If your harness sends every call to one of those, the model interface half of this layer is theirs. For the other half, durable-execution systems such as [Temporal](https://temporal.io), and checkpointing in agent frameworks such as [LangGraph](https://www.langchain.com/langgraph), record each step of a long process, so that after a crash it picks up at the step it was on. The idea is the same as quark's `session.json`, with more machinery.

The fuller example, [`resilience.py`](./resilience.py), shows more of that list. It's Lesson 3's agent loop (no memory, no tracing, no guardrails, no sandbox) so resilience is all there is to look at. It turns the SDK's retries off and does them itself, in plain sight: it prints each failed try and how long it's waiting, honors `Retry-After`, backs off with jitter, and benches a model that has given up for a minute. Commands run under a time limit that kills the whole process group, with their output capped, and every result tells the model how the command ended. And the checkpoint is written at every step, so `resilience.py resume` picks a run up. Here it is, all of it:

```python
import subprocess, sys, os, json, time, random, signal
from anthropic import Anthropic, APIConnectionError, APIStatusError

client = Anthropic(max_retries=0, timeout=120)   # the SDK's own retries are off: this file does them, where you can see them
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]   # tried in order; the first is the one you want
ATTEMPTS, BASE, CAP = 4, 1.0, 20.0                  # tries per model, first wait, longest wait (seconds)
BENCH = 60                                          # seconds a model that just failed is left alone
MAX_STEPS = 10
TOOL_TIMEOUT, MAX_OUT = 20, 4000                    # seconds a command may run, characters of its output kept
CHECKPOINT = ".quark/checkpoint.json"

class Down(Exception): pass

def retryable(e):
    # Worth trying again: the network, a timeout, "slow down", "try later", overloaded. Not worth it: a bad key, a bad request.
    return isinstance(e, APIConnectionError) or e.status_code in (408, 409, 429) or e.status_code >= 500

def pause(e, attempt):
    # If the server said how long to wait, wait that. Otherwise back off exponentially, with jitter so a crowd of clients doesn't return at once.
    told = getattr(getattr(e, "response", None), "headers", {}).get("retry-after")
    if told and told.isdigit(): return min(float(told), CAP)
    return random.uniform(0.5, 1.0) * min(CAP, BASE * 2 ** attempt)

benched = {}   # model -> time it may be tried again
def ask(**request):
    for model in [m for m in MODELS if benched.get(m, 0) < time.time()] or MODELS:
        for attempt in range(ATTEMPTS):
            try:
                return model, client.messages.create(model=model, **request)
            except (APIConnectionError, APIStatusError) as e:
                if not retryable(e): raise
                what = type(e).__name__
                if attempt == ATTEMPTS - 1:
                    print(f"[{model}: {what}, giving up on it for {BENCH}s]")
                    benched[model] = time.time() + BENCH
                    break
                wait = pause(e, attempt)
                print(f"[{model}: {what}, try {attempt + 1} of {ATTEMPTS}, waiting {wait:.1f}s]")
                time.sleep(wait)
    raise Down()

def run(cmd):
    # Output's side of resilience: a command can hang, print forever, or die. Whatever happens, the model gets a result it can read.
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", start_new_session=True)
    try:
        out, _ = p.communicate(timeout=TOOL_TIMEOUT)
        note = f"\n(exit {p.returncode})" if p.returncode else ""
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)   # the whole group, so the command's children go too
        out, _ = p.communicate()
        note = f"\n(killed: still running after {TOOL_TIMEOUT} seconds)"
        p.returncode = -9
    if len(out) > MAX_OUT: out, note = out[:MAX_OUT], f"\n[output cut at {MAX_OUT} characters]" + note
    return (out + note).strip() or "(no output)", p.returncode != 0

def save(task, messages):
    os.makedirs(".quark", exist_ok=True)
    with open(CHECKPOINT + ".tmp", "w") as f: json.dump({"task": task, "messages": messages}, f, default=lambda b: b.model_dump(exclude_none=True))
    os.replace(CHECKPOINT + ".tmp", CHECKPOINT)   # all of the old file or all of the new one, never half

def resume():
    if not os.path.exists(CHECKPOINT): sys.exit("[nothing to resume]")
    saved = json.load(open(CHECKPOINT))
    messages = saved["messages"]
    if messages[-1]["role"] == "assistant":
        # The model asked for commands and the harness died before the answers were saved. Some may have run. Say so, don't guess.
        lost = [b for b in messages[-1]["content"] if b["type"] == "tool_use"]
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b["id"], "content": f"interrupted: the harness stopped while this was pending, so it may or may not have run. Check before repeating it: {b['input'].get('cmd')}", "is_error": True} for b in lost]})
    print(f"[resuming: {saved['task'][:60]!r}, {len(messages)} messages]")
    return saved["task"], messages

if sys.argv[1:] == ["resume"]:
    task, messages = resume()
else:
    task = " ".join(sys.argv[1:]) or input("> ")
    messages = [{"role": "user", "content": task}]

save(task, messages)
for step in range(1, MAX_STEPS + 1):
    try:
        model, reply = ask(max_tokens=16384, tools=tools, messages=messages)
    except Down:
        sys.exit(f"[no model answered. Everything so far is saved (step {step}); run `resilience.py resume` to pick it up]")
    if model != MODELS[0]: print(f"[answered by the backup, {model}]")
    messages.append({"role": "assistant", "content": reply.content})
    save(task, messages)
    if reply.stop_reason == "refusal":
        print("[stopped: the model declined]")
        break
    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if not cmd or (reply.stop_reason == "max_tokens" and block is reply.content[-1]):
                out, failed = "your request was cut off at the token limit, so it was not run. Send it again, shorter.", True
            else:
                out, failed = run(cmd)
            print(out)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": out, "is_error": failed})
    if not results:
        print(f"[done in {step} steps]")
        break
    messages.append({"role": "user", "content": results})
    save(task, messages)
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
    sys.exit()   # keep the checkpoint
os.remove(CHECKPOINT)   # finished, nothing to resume
```

The new parts, in the order they matter:

**`retryable()` and `pause()`.** The first is the sort from the start of this lesson, as a function: connection trouble and timeouts, 408, 409, 429 and any 5xx are worth another try, and anything else isn't. The second is the wait. If the response has a `retry-after` header, that many seconds (up to `CAP`). If not, `BASE` doubled for each try so far, capped, and multiplied by a random number between a half and one, which is the jitter.

**`ask()`.** The loop over models and tries. For each model, up to `ATTEMPTS` tries. It prints what happened and waits between tries. After the last one, it prints that it's giving up on the model, benches it for `BENCH` seconds (it's skipped in later calls until the time is up), and moves to the next. If every model fails, `Down`. Anything that isn't retryable isn't caught here at all: it's the caller's. The client is created with `max_retries=0`, so these are the only retries there are. It returns the model too, so the loop can say when a backup answered.

**`run()`.** The command runs in a new session (`start_new_session=True`), so it has its own process group. If it's still running after `TOOL_TIMEOUT`, the whole group gets SIGKILL, which takes the command's children with it; killing only the shell would leave them running and holding the pipe open. Output past `MAX_OUT` is cut, with a note. The result always ends with how the command ended (its exit code, or that it was killed), and it comes back flagged as an error if it didn't succeed, so the model's request always gets a reply it can use.

**`save()` and `resume()`.** The same file-swap as quark's. `resume()` is chosen by a word on the command line, not asked at startup: `resilience.py resume` loads the checkpoint, and gives every unanswered request an "interrupted, may or may not have run, check before repeating it" result that includes the command, so the model doesn't have to look back for it. The checkpoint is written before the first request, after each reply, and after each set of results, so the file always ends at a point the API will accept once the interrupted results are added. A run that finishes removes it. One that hits `MAX_STEPS` or gives up keeps it.

Four runs show it (I wrote `python3 resilience.py` for brevity; I ran it with the repo's own Python, `.venv/bin/python`, from a scratch folder). The first uses the stand-in from above, in a mode that answers the first two requests with `429` and `retry-after: 1`, and then passes everything through:

```
$ python3 flaky.py 8111 first:2 &
$ ANTHROPIC_BASE_URL=http://127.0.0.1:8111 python3 resilience.py "How many bytes is notes.txt? Answer in one line."
```

```
[claude-sonnet-5-5: RateLimitError, try 1 of 4, waiting 1.0s]
[claude-sonnet-5-5: RateLimitError, try 2 of 4, waiting 1.0s]
$ wc -c notes.txt
6 notes.txt
notes.txt is 6 bytes.
[done in 2 steps]
```

The harness waited the one second the server asked for, twice, and then went on. The stand-in's log has four requests: two refused and two served.

The second takes the preferred model down:

```
$ python3 flaky.py 8112 claude-sonnet-5-5 &
$ ANTHROPIC_BASE_URL=http://127.0.0.1:8112 python3 resilience.py "How many bytes is notes.txt? Answer in one line."
```

```
[claude-sonnet-5-5: OverloadedError, try 1 of 4, waiting 0.7s]
[claude-sonnet-5-5: OverloadedError, try 2 of 4, waiting 1.7s]
[claude-sonnet-5-5: OverloadedError, try 3 of 4, waiting 2.5s]
[claude-sonnet-5-5: OverloadedError, giving up on it for 60s]
[answered by the backup, claude-opus-5-5]
$ wc -c notes.txt
6 notes.txt
[answered by the backup, claude-opus-5-5]
notes.txt is 6 bytes.
[done in 2 steps]
```

The waits grow, with jitter: 0.7, 1.7, 2.5 (the doubling would give 1, 2, 4, each multiplied by a number between a half and one). After the fourth failure it gave up on `claude-sonnet-5-5` and used `claude-opus-5-5`. The second call, for the answer, didn't try the first model at all, because it was benched. The stand-in's log shows it: four requests to the first model, two to the second. Compare with quark, which sent ten.

The third takes everything down, and then brings it back:

```
$ python3 flaky.py 8113 all &
$ ANTHROPIC_BASE_URL=http://127.0.0.1:8113 python3 resilience.py "How many bytes is notes.txt? Answer in one line."
```

```
[claude-sonnet-5-5: OverloadedError, try 1 of 4, waiting 0.8s]
[claude-sonnet-5-5: OverloadedError, try 2 of 4, waiting 1.4s]
[claude-sonnet-5-5: OverloadedError, try 3 of 4, waiting 2.4s]
[claude-sonnet-5-5: OverloadedError, giving up on it for 60s]
[claude-opus-5-5: OverloadedError, try 1 of 4, waiting 0.9s]
[claude-opus-5-5: OverloadedError, try 2 of 4, waiting 1.9s]
[claude-opus-5-5: OverloadedError, try 3 of 4, waiting 3.2s]
[claude-opus-5-5: OverloadedError, giving up on it for 60s]
[no model answered. Everything so far is saved (step 1); run `resilience.py resume` to pick it up]
```

`ls .quark` shows `checkpoint.json`. With the API back (no `ANTHROPIC_BASE_URL`):

```
$ python3 resilience.py resume
```

```
[resuming: 'How many bytes is notes.txt? Answer in one line.', 1 messages]
$ wc -c notes.txt
6 notes.txt
notes.txt is 6 bytes.
[done in 2 steps]
```

And `.quark` is empty again: a finished run leaves nothing to resume.

The fourth is about commands. The time limit is 20 seconds, which is slow to demonstrate, so this run uses a copy of the file with `TOOL_TIMEOUT, MAX_OUT = 20, 4000` changed to `3, 300` (`sed 's/^TOOL_TIMEOUT, MAX_OUT = 20, 4000/TOOL_TIMEOUT, MAX_OUT = 3, 300/'`). The task asks for a command that sleeps for a minute, and then one that prints five thousand characters:

```
$ sleep 60; echo hi
(killed: still running after 3 seconds)
$ python3 -c "print('x'*5000)"
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
[output cut at 300 characters]
Here is what each command did:

1. **`sleep 60; echo hi`**: The tool killed it after about 3 seconds with the message "(killed: still running after 3 seconds)". It never reached `echo hi`, so nothing was printed. This environment seems to have a roughly 3-second timeout, which a 60-second sleep can't fit inside.

2. **`python3 -c "print('x'*5000)"`**: It ran fine and printed a line of `x` characters. The tool truncated the output at 300 characters and added "[output cut at 300 characters]". I saw only the first 300 of the 5000 characters.
[done in 3 steps]
```

The sleep was killed at three seconds and the model was told so. The long line was cut at 300 characters and the model was told that too. In both cases it reported accurately what it had been given. The run went on to a third step where the model answered; the harness neither hung nor held on to five thousand characters.

And the crash, which is the one from the worked example, with `resilience.py`. The command takes twelve seconds and I killed the harness at seven, again by PID:

```
$ sleep 12 && echo finished > flag.txt
```

That's everything it printed. `ls -a . .quark` right after the kill, and what the checkpoint holds, which is the model's request for the command and nothing after it:

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
checkpoint.json
```

```
user "Run exactly this one command: sleep 12 && echo finished > flag.txt   (it is slow on purpose). Then tell me what flag.txt contains."
assistant [{"id": "toolu_013994a4bJA2eTwxGkasqnRj", "caller": {"type": "direct"}, "input": {"cmd": "sleep 12 && echo finished > flag.txt"}, "name": "bash", "type": "tool_use"}]
```

Later the command (which kept running) had written its file:

```
$ ls
flag.txt
out1.txt
pid
```

And then `resilience.py resume`:

```
[resuming: 'Run exactly this one command: sleep 12 && echo finished > fl', 3 messages]
The harness interrupted the command, so I'll check whether the file exists before deciding whether to run it again.
$ ls -l flag.txt && cat flag.txt
-rw-r--r-- 1 root root 9 Oct  5 23:53 flag.txt
finished
`flag.txt` contains `finished`.

The harness reported an interruption, so I checked the file before running the command again. The file was already there with that content, which means the command finished before the interruption. I didn't need to run it a second time.
[done in 2 steps]
```

The result for the dead request carried the command with it, the model checked the file instead of repeating the command, and the run finished.

## What to take away

**The rule:** assume the call can fail, and make failure something the harness handles instead of something that ends the run. Tell the failures that pass from the ones that don't, and retry the first kind a bounded number of times with a longer wait each time. When the preferred model is out, have somewhere else to go, and when everywhere is out, stop with a message. When a command misbehaves, answer the request anyway, with a result the model can read. And write the run down after each step, so that when the harness itself fails, what was in flight can be reported as *unknown*, not guessed at and not lost.

Notice what Resilience never does. It sits in the model interface and output, and it leaves the other primitives alone. Control flow is the same loop with the same stop conditions: a retry happens inside a single call, so the loop sees a call that took longer, or, at worst, one that stopped the run, and the only new way out is `Down`. Input is untouched: the person's task is read the way it was, and the one question asked on startup is the harness's own, in the style of the guard's. Context is untouched: the saved working memory is replayed exactly as it was, nothing in it is summarized or edited, and the model learns that something went wrong only through the result it's handed, in words it can read. What the model is shown changes only by one message, the "interrupted" one.

**What's missing:** resilience keeps a run alive and recoverable; it doesn't tell you the run was good. A resumed run can't undo what an interrupted command did, only ask the model to check, and the model can be wrong. The save is a single file per folder, so two runs in the same place overwrite each other's. A backup model may do the task differently, or worse, and nothing here judges it. The retries and fallbacks cost time and money, and the harness only notices when it reads the trace, because a call that took forty seconds, by retrying, looks like any other. Keeping up with how long a run takes, how many tokens it spends and how fast it answers, and how to make those smaller, is its own layer.

**→ [Lesson 9: Performance](../09-performance/)**
