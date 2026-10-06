# Lesson 8: Resilience

> 🎥 **Video:** coming soon

Lesson 7 can tell you exactly where a run broke. This lesson is about not breaking, or breaking somewhere you can start again from. Everything so far assumed that the thing on the other side of a call answers, and answers sensibly. Over a long run that's the assumption that fails first: the API drops a call, the model is overloaded, a response is cut off in the middle of a command, the process dies halfway through and the work goes with it. Or you stop it yourself, with Lesson 6's ESC, and what it had already done goes with it.

Resilience is how the harness keeps going, or stops cleanly, when something doesn't answer. It has two jobs. The first is to get through the failures that pass. The second is to leave things in a state you can pick up from when a failure doesn't pass, so that the hour of work before it isn't lost.

This is a production layer, so it adds hardening, not a new primitive. It's **built on the model interface and output**, the two places where the harness reaches out of itself and the world gets to say no. The model interface is the call to the API (Lesson 1), a service across a network, so it can be slow, busy or gone. Output runs the model's words (Lesson 2), so what it's handed can be broken. They're also the two places where work is in flight when you press ESC: a response half streamed, a command half run. And to pick a run back up it **reads context's own record**: Lesson 4's episode already holds every message, written before any tool runs, so resilience doesn't need a save file of its own.

The mechanism, first in the model interface. Not every failure means the same thing, so the first step is to sort them:

- **Worth trying again.** The network dropped, the request timed out, the server said slow down (429), or the server itself had trouble (any 5xx, and Anthropic's "overloaded", 529). Nothing is wrong with the request. Send the same one a moment later and it will probably work.
- **Not worth trying again.** A bad API key (401), a request the API won't accept (400), a model that doesn't exist (404). Sending it again gets the same answer, so retrying only delays the error. These go up to the code that can do something about them, or to you.

For the first kind, the way to retry matters. Wait longer after each failure (*exponential backoff*: one second, two, four), so a service that's struggling isn't hit at full speed. Add a little randomness (*jitter*), so a thousand clients that failed together don't all come back together. If the server said how long to wait, wait that long. And put a limit on it: a few tries, not forever. The Anthropic SDK already does all of this for you: it retries connection errors, 408, 409, 429 and 5xx with backoff, and the number of tries is the `max_retries` setting. So quark doesn't write a retry loop; it turns the setting up and sets a timeout. What the SDK can't do is choose a different model. That's the one thing quark adds here: when the preferred model is still failing after the SDK has given up, try a backup, and when nothing answers, stop with a message instead of a stack trace.

Then output. The model asks for a command and output runs it, and a command can fail in a way the harness doesn't see coming: it hangs (Lesson 5's sandbox already puts a time limit on that), it prints bytes that aren't text, or the model's request itself arrives broken, cut off in the middle by the token limit, with a command that's half a sentence. The rule for all of them is the one Lesson 2 started with: every request gets an answer the model can read. A result that says *this was cut off before it was whole, and it never reached the world* is something the model can act on. A crash isn't.

Then the failure that's yours: you press ESC. Lesson 6 made that stop at once, and it stops cleanly by throwing away whatever was in flight. Whatever the model had already said, it's told only that you interrupted it. Whatever the command had printed, the model gets only `[your doing stopped before done]`. But both of those happened. The words were written, and the command did its first steps in the world. Dropping them leaves the model's record out of step with what happened, which is the same failure as losing a run to a crash, only smaller. So resilience keeps the partials, the way upstream quark does. What the model had produced goes into working memory in whole blocks: text that had started, thinking that had finished and been signed (a thinking block's signature comes at its end, and the API won't take thinking back without one), and any tool request, answered with `[your doing never reached the world]`. A stopped command keeps what it had printed, with `[your doing stopped before done]` after it.

Last, picking a task back up. If the harness is killed during a long task, working memory dies with the process. But since Lesson 4, every message has also been written to the session's episode, by the harness, as it happens, and the model's request is on disk *before* the command it asks for runs. So the record already exists. Resilience only has to notice, at startup, that the last episode ended mid-task, and offer to continue it.

There's one trap, and it's the reason this isn't just "load the file." Suppose the harness died while a command was running. The saved record ends with the model asking for that command and no result. The API won't accept a request in that state: every request for a tool must be followed by a result for it. And the harness can't simply run the command again, because it may already have run: the command that was killed might have been `git push`, or sent an email, or appended a line to a file. It can't know, so it says so. The missing result becomes an error result: *interrupted; this may or may not have run; check before repeating it.* Then the model, which is the one that knows what the command was for, looks at the world and decides. It isn't a guess made by the harness.

None of this makes the model right, and it doesn't make a failed run succeed. It makes a run that hits trouble end up either finished or somewhere you can start again from.

## The worked example

[`quark.py`](./quark.py) is Lesson 7's `quark.py` plus resilience, and nothing else: 31 lines.

In `# ── model interface ──`, Lesson 1's `call()` grows a backup:

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

**`call()`.** Every call to the model already went through it, the main one and the summary in `compact()`, so this is the one place to change. The stream from Lesson 1 is unchanged; it's now inside a loop that tries each model in `MODELS`, in order. A call that fails *after the SDK's retries* with something transient (a lost connection or timeout, 429, or any 5xx) is traced as `model_failed` and the next model is tried. Everything else is raised: a bad key, a bad request, and in particular "prompt is too long", which Lesson 4's compaction is waiting for. If every model fails, `call()` raises `Down`. The test is on the status code, not a list of exception classes, because the SDK has a class for each and it's easy to miss 529, the overloaded error, which is the one you most want to catch.

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

In `# ── input ──`, it's asked before anything else is read:

```python
resumed = unfinished()
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

`EPISODE` is pointed at the old file, so everything from here on is appended to the same session. If the record ends with the model asking for tools, each request is answered with the "interrupted" result, through `add()`, so the episode records that too. The trace marks the start as `resumed`.

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

`output` is what had arrived when the stream stopped: Lesson 6's `call()` hands back the message as far as it got. Lesson 6 dropped it. Now every block in it is kept unless it's empty text or thinking with no signature, which is thinking that was cut off before it finished. The kept blocks go into working memory, and so into the episode, as the model's message. Then comes your interruption, as before, and in the same message an answer for each tool request it had begun: `[your doing never reached the world]`, because none of them ran.

And when you press ESC while a command runs, what it had printed is kept:

```python
            if ESC.is_set(): done.stdout += "\n[your doing stopped before done]"   # resilience: keep what it had printed
```

In Lesson 6 this line was `=`; now it's `+=`. One character, and the model sees what its command did before you stopped it.

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

Everything else is unchanged on purpose. ESC still stops the stream and kills the commands exactly as in Lesson 6; this layer only decides what's kept afterwards. The guard still runs before the box. The trace now records failed models, and a `model` event's `seconds` includes the retries, so a flaky API shows up as slow calls next to `model_failed` events. The system prompt doesn't tell the model that the harness retries or that it may have been resumed; that would be a decision about context, and this layer doesn't make it.

## Run it

You need Docker running, as in Lesson 5. Start in a scratch folder. Each run below is `uv run --project /path/to/building-agents /path/to/building-agents/production/08-resilience/quark.py`, which I'll write as `quark.py`. Answers piped to prompts aren't echoed.

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

The harness reaches it through `ANTHROPIC_BASE_URL`, which the SDK reads. Nothing in `quark.py` knows about it. The stand-in reads each response whole before passing it on, so through it the stream arrives all at once; that doesn't matter for these runs.

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
{"event":"model","seconds":5.27,"stop_reason":"tool_use"}
{"event":"tool","seconds":0.12}
{"event":"model_failed","model":"claude-sonnet-5-5","error":"OverloadedError"}
{"event":"model","seconds":4.65,"stop_reason":"end_turn"}
```

Both calls had four failed requests to `claude-sonnet-5-5` (the first try and the SDK's three retries), then one to `claude-opus-5-5` that worked; the stand-in's log shows ten requests for two calls. The `seconds` of the two `model` events, 5.27 and 4.65, are mostly the backoff. Every call tries the preferred model again from scratch: a few seconds a call while it's down, and quark is back on it the moment it recovers.

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
2026-10-06T20-32-21.jsonl
```

It tried both models, gave up and said so. There's no save file: the episode is the record. Then the API comes back (no `ANTHROPIC_BASE_URL`) and I run `quark.py` again with no input, answering `y` when asked, and `/q` when it finished:

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

**The harness is killed.** This is the one that matters most. The task is one slow command, started in the background with `y` piped in for the guard, and killed with `kill -9` on its process ID twelve seconds after the guard's question appeared, in the middle of the command. I ran the repo's own Python directly, so `$!` is the harness itself (`uv run` puts a wrapper in between). That's `kill` on a PID, not `pkill`, which matches on names and can match far more than you meant:

```bash
(yes y | /path/to/building-agents/.venv/bin/python /path/to/building-agents/production/08-resilience/quark.py "Run exactly this one command: sleep 15 && echo finished > flag.txt   (it is slow on purpose). Then tell me what flag.txt contains." > out1.txt 2>&1 & echo $! > pid)
until grep -q allow out1.txt; do sleep 0.25; done; sleep 12; kill -9 $(cat pid)
cat out1.txt
```

```
$ sleep 15 && echo finished > flag.txt
allow `sleep 15 && echo finished > flag.txt`? [y/N]
```

That's all it printed before it died. What it left, and then the same folder a few seconds later:

```
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

The episode was written when the model asked for the command, before it ran. `flag.txt` isn't there, and then it is: the harness was killed, but its container wasn't (`atexit` can't run after `kill -9`), so the command finished in it. (I removed the leftover container with `docker rm -f` afterwards.) That's exactly the case the "interrupted" result is for: the command did run, and the harness doesn't know. Now `quark.py` again, answering `y` to resume, `y` to the guard, and `/q` at the end:

```
unfinished session: 'Run exactly this one command: sleep 15 && echo finished > fl'. pick it up? [y/N] $ cat flag.txt; ls -l flag.txt; date
allow `cat flag.txt; ls -l flag.txt; date`? [y/N] finished
-rw-rw-rw- 1 root root 9 Oct  6 20:33 flag.txt
Tue Oct  6 20:33:44 UTC 2026

`flag.txt` contains `finished`.

The harness reported my first run as interrupted, so I checked the file before running the command again. It was already there with that content, which means the command had completed. I didn't run it a second time.

>
```

The model was told the command was interrupted and may or may not have run, and it did what that wording asks: it looked, found the file, and didn't run the command again. If `flag.txt` hadn't been there, the same sentence would have led it to run the command once. It's the model's call, made with the facts.

**You press ESC while it's saying something.** ESC needs a terminal, so these two runs are in chat mode, typed at the prompt, each in a fresh folder. I asked for something long and pressed ESC a few seconds after the answer started to appear, then `/q`:

```
> without running anything, work out whether 1000003 is prime, then explain how you know in about 400 words.
**1000003 is prime.** I didn't run anything, and I didn't do the full proof by hand. Part of my confidence is recall.

**What a full proof needs**

A number n is composite only if it has a prime factor no larger than √n. Here 1000² = 1,000,000 and 1001² = 1,002,001, so √1000003 is just over 1000. To prove primality, I would show that none of the 168 primes up to 1000 divides it. That is a finite check, but it is long to do mentally.

**Checks I can do by hand**

Write N = 10⁶ + 3. A prime p divides N exactly when 10⁶ ≡ −3 (mod p).

- **2 and 5:** N is odd and ends in 3, so neither divides it.
- **3:** the digit sum is 1 + 3 = 4, which isn't a multiple of 3.
- **7, 13:** 10⁶ ≡ 1 by Fermat's little theorem, so N ≡ 4 (mod p). Neither divides it.
- **11:** 10 ≡ −1, so 10⁶ ≡ 1 and N ≡ 4.
- **37:** 1000 = 27·37 + 1, so 10³ ≡ 1 and 10⁶ ≡ 1. Again N ≡ 4.
- **101:** 10⁴ ≡ 1, so 10⁶ ≡ 10² = 100 ≡ −1, and N ≡ 2.

The same trick works for any prime where 10⁶ ≡ 1: the remainder is always 4, so none
Sorry, I was cut off partway through. Here is where things stand.

**Answer:** 1000003 is prime.

**How sure I am:** I'm confident, but not because I did the whole proof in my head. Two things support it:

- **Recall:** 1000003 is well known as the first prime after one million. Its neighbors fail: 1000001 = 101 × 9901, and 1000002 is even.
- **Partial checks:** I ruled out 2, 3, 5, 7, 11, 13, 37 and 101 by hand. Fermat's little theorem and the fact that 10⁶ ≡ 1 mod several small primes made those quick.

**What a full proof would take:** √1000003 is just over 1000, so I'd have to rule out every prime up to 1000. That's 168 primes. I haven't done that mentally, and I don't want to imply that I did.

If you'd like it verified, I can run a quick trial-division check in the sandbox. Do you want me to?

> /q
```

The second answer picks up where the first stopped: it knows it had ruled out 2, 3, 5, 7, 11, 13, 37 and 101, because that text is in its working memory. In Lesson 6 it would have been told only that you interrupted it, with no idea what it had already said. The episode shows what was kept (each block cut down to its type and the end of its text, with this `jq`):

```bash
jq -c '{role, content: (if (.content|type)=="string" then .content[:50] else [.content[] | if .type=="text" then {type, end: .text[-50:]} elif .type=="thinking" then {type, signed: (.signature|length > 0)} else {type} end] end)}' .quark/episodes/*.jsonl
```

```
{"role":"user","content":"without running anything, work out whether 1000003"}
{"role":"assistant","content":[{"type":"thinking","signed":true},{"type":"text","end":"0⁶ ≡ 1: the remainder is always 4, so none of them"}]}
{"role":"user","content":[{"type":"text","end":"lf interrupted what you were saying — acknowledge]"}]}
{"role":"assistant","content":[{"type":"text","end":"-division check in the sandbox. Do you want me to?"}]}
```

The model's first message has both of its blocks: the thinking it did before it started writing, finished and signed, and the text as far as it got. The text ends two words later than the screen does ("so none of them", where the screen stopped at "so none"): they were the piece of the stream that arrived just as ESC was pressed. The SDK had already added it to the message when `unless_esc()` saw ESC and chose not to show it.

**You press ESC while it's doing something.** A command that prints a line a second, `y` to the guard, ESC three and a half seconds later, and `/q`:

```
> run this as one command: for i in 1 2 3 4 5 6 7 8 9 10; do echo step $i; sleep 1; done
$ for i in 1 2 3 4 5 6 7 8 9 10; do echo step $i; sleep 1; done
allow `for i in 1 2 3 4 5 6 7 8 9 10; do echo step $i; sleep 1; done`? [y/N] y
step 1
step 2
step 3
step 4

[your doing stopped before done]
You interrupted the command, so it stopped after step 4. Steps 5 through 10 never ran.

I can run it again from the start, or run only the remaining steps. Which do you want?

> /q
```

It saw `step 1` to `step 4`, so it knew exactly how far the command got and what never ran. Here's the result it was given, from the episode:

```bash
jq -c '.content[]? | select(.type=="tool_result")' .quark/episodes/*.jsonl
```

```
{"type":"tool_result","tool_use_id":"toolu_01BXdPMZa1BhW8LGBVcxifqQ","content":"step 1\nstep 2\nstep 3\nstep 4\n\n[your doing stopped before done]"}
```

In Lesson 6 that result was only `[your doing stopped before done]`. The trace's `tool` line for it has `exit` 137 and `chars` 61: the output and the note.

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
I couldn't write `poem.txt`. Seven tries in a row failed, and none of them reached the shell. Each time, the command came out empty or cut off before it was complete, so the harness refused to run it. Nothing has been created or changed on disk.

My guess is that a 40-line heredoc is too long for what I can send in a single step. I haven't confirmed that.

I can try again with a shorter form, such as very short lines in a `printf` command. Or I can write the poem in two or more commands instead of one. Tell me which you'd prefer, or I'll retry with the shorter lines.
```

Every response hit the limit while the model was writing its command, before any of it was complete, so each request arrived with no `cmd` at all (`input` is `{}` in the episode), which is why the line says `$ None`. None of them ran. Each was answered with the cut-off result, and after the eighth (it says seven) the model stopped trying and told me what was happening, with nothing half-written on disk. With the real limit, the same rule catches the rare command that's too long to finish.

## Going further

**What else resilience can be:** quark has one retry setting, one backup model and one file. These are the choices you make when you build it.
- **What counts as a failure.** Retry the transient ones (a dropped connection, a timeout, 429, 5xx) and surface the rest. A bad key shouldn't be retried at all. A request that's too long isn't a failure to wait out, it's something to fix, and in quark that's Lesson 4's compaction.
- **How to wait.** Exponential backoff, with jitter, a cap on any single wait, and a limit on the total, so a run spends at most so long on one call. Honoring `Retry-After` when the server sends it. Or a client-side limiter that keeps *under* the rate limit in the first place, so the 429 never comes.
- **What the backup is.** A different model, as in quark. The same model from a different provider (the Claude models are also served through the big cloud platforms) or a different region. Or a smaller model that's good enough to finish the task. Whichever it is, it has costs: the prompt cache is per model, so a switch pays full price for the whole prompt once, and a backup may be worse at the task, so a harness that fails over should say so.
- **How long a failure is remembered.** quark forgets: every call starts with the preferred model. A *circuit breaker* remembers: after a model fails, leave it alone for a minute, so a long outage costs one slow call instead of one per step. The fuller example does that.
- **When a stream breaks partway.** quark streams from Lesson 1, but if the connection drops in the middle of a response, `call()` starts the request again on the next model, and what had arrived is thrown away. A harness could keep it, as quark keeps what had arrived when you press ESC. And a timeout on *silence* ("nothing for 30 seconds") can replace one on the whole reply, which catches a stuck call much sooner than five minutes.
- **What's kept when it's stopped.** quark keeps whole blocks: text that had started, thinking that was signed, tool requests (answered as never run), and what a stopped command printed. It drops thinking that hadn't been signed. A harness could keep that as plain text instead, or keep a half-written command as text so the model can see what it was about to do.
- **What a tool failure looks like.** A time limit, with the whole process group killed so its children go too. A cap on output. Errors flagged as errors, so the model reads them as failures. Retrying a *read* automatically is usually safe; retrying a *write* never is, unless the tool is built so that doing it twice is the same as doing it once.
- **How state is saved.** After every step, as in quark. To a file, or a database. As a log of events from which the state can be rebuilt, which also gives you a history of the run. With a unique ID on each action, so a replay can tell "done" from "not done" without asking the model.
- **How a run restarts.** Asking you, as in quark. Or automatically, by something that watches the process and starts it again (a supervisor such as systemd, or an orchestrator). Or by a service built for this.
- **How it ends.** A signal such as Ctrl-C or SIGTERM can be caught: save, clean up, exit, so a stop you asked for loses nothing. A hard kill can't be caught, which is why the file is written *before* the work and not after.

It can be a product on its own. Gateways like [LiteLLM](https://www.litellm.ai) and [OpenRouter](https://openrouter.ai) sit in front of several models and providers and handle retries, fallbacks and rate limits for you. If your harness sends every call to one of those, the model interface half of this layer is theirs. For the other half, durable-execution systems such as [Temporal](https://temporal.io), and checkpointing in agent frameworks such as [LangGraph](https://www.langchain.com/langgraph), record each step of a long process, so that after a crash it picks up at the step it was on. The idea is the same as quark's episode, with more machinery.

The fuller example, [`resilience.py`](./resilience.py), shows more of that list. It's Lesson 3's agent loop (no memory, no tracing, no guardrails, no sandbox) so resilience is all there is to look at. It turns the SDK's retries off and does them itself, in plain sight: it prints each failed try and how long it's waiting, honors `Retry-After`, backs off with jitter, and benches a model that has given up for a minute. Commands run under a time limit that kills the whole process group, with their output capped, and every result tells the model how the command ended. When a command fails, it asks Jev, the small decision model I introduced in [Lesson 5](../05-sandboxing/#asking-jev), what kind of failure it was, and only a read that failed by chance is run again. And the checkpoint is written at every step, so `resilience.py resume` picks a run up. Here it is, all of it:

```python
import subprocess, sys, os, re, json, time, random, signal
from anthropic import Anthropic, APIConnectionError, APIStatusError
from typesafe_sdk import TypeSafeClient, Choice
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic(max_retries=0, timeout=120)   # the SDK's own retries are off: this file does them, where you can see them
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]   # tried in order; the first is the one you want
ATTEMPTS, BASE, CAP = 4, 1.0, 20.0                  # tries per model, first wait, longest wait (seconds)
BENCH = 60                                          # seconds a model that just failed is left alone
MAX_STEPS = 10
TOOL_TIMEOUT, MAX_OUT = 20, 4000                    # seconds a command may run, characters of its output kept
CHECKPOINT = ".quark/checkpoint.json"
jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # a second model, for one question (Lesson 5); no key, no Jev
SURE = 0.8                                          # how confident Jev must be before its answer changes anything
READS = {"cat", "head", "tail", "ls", "wc", "grep", "curl"}   # programs that only look, so running one twice does no harm

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

def failure(cmd, out):
    # Jev's question: will this failed command work if it's simply run again? Unsure, or no answer at all, is "unsure" or None: never a retry.
    try: a = jev.system_one({"command": cmd, "result": out}, {"failure": Choice(
        instructions="The command in `command` failed with `result`. What kind of failure is it?",
        criteria={"transient": "likely to work if run again unchanged: network blip, timeout, lock held, rate limit, busy resource",
                  "permanent": "will fail again unchanged: missing file, syntax error, wrong argument, permission denied, failing test",
                  "partial": "it got part of the way: some of its changes may have happened before it failed"})}).choices["failure"]
    except Exception:
        print("[Jev: no answer]")
        return None
    print(f"[Jev: {a.choice}, confidence {a.confidence:.2f}]")
    return a.choice if a.confidence >= SURE else "unsure"

def reads(cmd):
    # Hand-written and strict: one program from READS, no pipes, redirects or chaining, no curl flag that sends or saves. Jev never decides this.
    return cmd.split()[0] in READS and not re.search(r"[|;&<>$`(\n]| -[A-Za-z]*[oOXdTF]|--(data|upload|output|request|form)", cmd)

def save(messages):
    os.makedirs(".quark", exist_ok=True)
    with open(CHECKPOINT + ".tmp", "w") as f: json.dump({"messages": messages}, f, default=lambda b: b.model_dump(exclude_none=True))
    os.replace(CHECKPOINT + ".tmp", CHECKPOINT)   # all of the old file or all of the new one, never half

def resume():
    if not os.path.exists(CHECKPOINT): sys.exit("[nothing to resume]")
    saved = json.load(open(CHECKPOINT))
    messages = saved["messages"]
    if messages[-1]["role"] == "assistant":
        # The model asked for commands and the harness died before the answers were saved. Some may have run. Say so, don't guess.
        lost = [b for b in messages[-1]["content"] if b["type"] == "tool_use"]
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b["id"], "content": f"interrupted: the harness stopped while this was pending, so it may or may not have run. Check before repeating it: {b['input'].get('cmd')}", "is_error": True} for b in lost]})
    print(f"[resuming: {messages[0]['content'][:60]!r}, {len(messages)} messages]")
    return messages

if sys.argv[1:] == ["resume"]:
    messages = resume()
else:
    input = " ".join(sys.argv[1:]) or read("> ")
    messages = [{"role": "user", "content": input}]

save(messages)
for step in range(1, MAX_STEPS + 1):
    try:
        model, output = ask(max_tokens=16384, tools=tools, messages=messages)
    except Down:
        sys.exit(f"[no model answered. Everything so far is saved (step {step}); run `resilience.py resume` to pick it up]")
    if model != MODELS[0]: print(f"[answered by the backup, {model}]")
    messages.append({"role": "assistant", "content": output.content})
    save(messages)
    if output.stop_reason == "refusal":
        print("[stopped: the model declined]")
        break
    input = []
    for block in output.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if not cmd or (output.stop_reason == "max_tokens" and block is output.content[-1]):
                out, failed = "your request was cut off at the token limit, so it was not run. Send it again, shorter.", True
            else:
                out, failed = run(cmd)
                kind = failure(cmd, out) if failed else None
                if kind == "transient" and reads(cmd):
                    print(f"[trying once more in {BASE:.0f}s]")
                    time.sleep(BASE)
                    out, failed = run(cmd)
                elif kind in ("partial", "unsure") and not reads(cmd):   # a read can't have partly done anything
                    out += "\n(it may have partly run: check before repeating it)"
            print(out)
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": out, "is_error": failed})
    if not input:
        print(f"[done in {step} steps]")
        break
    messages.append({"role": "user", "content": input})
    save(messages)
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
    sys.exit()   # keep the checkpoint
os.remove(CHECKPOINT)   # finished, nothing to resume
```

The new parts, in the order they matter:

**`retryable()` and `pause()`.** The first is the sort from the start of this lesson, as a function: connection trouble and timeouts, 408, 409, 429 and any 5xx are worth another try, and anything else isn't. The second is the wait. If the response has a `retry-after` header, that many seconds (up to `CAP`). If not, `BASE` doubled for each try so far, capped, and multiplied by a random number between a half and one, which is the jitter.

**`ask()`.** The loop over models and tries. For each model, up to `ATTEMPTS` tries. It prints what happened and waits between tries. After the last one, it prints that it's giving up on the model, benches it for `BENCH` seconds (it's skipped in later calls until the time is up), and moves to the next. If every model fails, `Down`. Anything that isn't retryable isn't caught here at all: it's the caller's. The client is created with `max_retries=0`, so these are the only retries there are. It returns the model too, so the loop can say when a backup answered.

**`run()`.** The command runs in a new session (`start_new_session=True`), so it has its own process group. If it's still running after `TOOL_TIMEOUT`, the whole group gets SIGKILL, which takes the command's children with it; killing only the shell would leave them running and holding the pipe open. Output past `MAX_OUT` is cut, with a note. The result always ends with how the command ended (its exit code, or that it was killed), and it comes back flagged as an error if it didn't succeed, so the model's request always gets a reply it can use.

**`failure()` and `reads()`.** `retryable()` sorts the API's failures by their status code. A command's failure has no code that says "try again": exit 1 is a missing file, a failing test, a lock someone else holds or a server that was busy for a second. Telling those apart means reading what the command printed, and that's a job for a model. So when a command fails, `failure()` sends Jev the command and what it printed, and one question with three answers: `transient` (it would likely work if run again unchanged), `permanent` (it will fail the same way) or `partial` (it got part of the way, so some of its changes may already have happened). Jev answers in a fraction of a second with a choice and a confidence, and the harness prints both. Then:
- **transient**, with confidence of at least `SURE`, and the command **reads**: it's run once more after `BASE` seconds, without the model, and the model only sees the second result.
- **partial**, or any answer under `SURE`, for a command that doesn't read: the result gets "it may have partly run: check before repeating it", the same warning `resume()` gives.
- **permanent**, or no answer at all (no key, a timeout, an error): the result goes back as before.

Whether a command reads is not Jev's call. `reads()` is a hand-written list of programs that only look (`READS`), with no pipes, redirects or chaining, and none of `curl`'s flags that send or save. It's strict on purpose: `grep -o` isn't let through, and that only costs a retry. Running something twice is safe for a read and never safe for a write, so that line is drawn by code you can read, and Jev only says whether a second try is worth it. Asking Jev is a model-interface act (it's a second model, called like the first); what's done with the answer, a retry or a note on the result, is output's side of resilience, like the rest of `run()`. Jev reads the command's output literally, so it can only judge what the command printed, and a command that printed nothing gives it nothing to go on (one of the runs below shows that).

**`save()` and `resume()`.** A checkpoint file, written whole or not at all: it holds the messages, and the input that opened the run is the first of them. `resume()` is chosen by a word on the command line, not asked at startup: `resilience.py resume` loads the checkpoint, and gives every unanswered request an "interrupted, may or may not have run, check before repeating it" result that includes the command, so the model doesn't have to look back for it. The checkpoint is written before the first request, after each reply, and after each set of results, so the file always ends at a point the API will accept once the interrupted results are added. A run that finishes removes it. One that hits `MAX_STEPS` or gives up keeps it.

These runs show it (I wrote `python3 resilience.py` for brevity; I ran it with `uv run --project` pointing at the repo, from a scratch folder, with `ANTHROPIC_API_KEY` and `TYPESAFE_API_KEY` set). The first uses the stand-in from above, in a mode that answers the first two requests with `429` and `retry-after: 1`, and then passes everything through:

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
[claude-sonnet-5-5: OverloadedError, try 1 of 4, waiting 0.8s]
[claude-sonnet-5-5: OverloadedError, try 2 of 4, waiting 1.3s]
[claude-sonnet-5-5: OverloadedError, try 3 of 4, waiting 3.5s]
[claude-sonnet-5-5: OverloadedError, giving up on it for 60s]
[answered by the backup, claude-opus-5-5]
$ wc -c notes.txt
6 notes.txt
[answered by the backup, claude-opus-5-5]
notes.txt is 6 bytes.
[done in 2 steps]
```

The waits grow, with jitter: 0.8, 1.3, 3.5 (the doubling would give 1, 2, 4, each multiplied by a number between a half and one). After the fourth failure it gave up on `claude-sonnet-5-5` and used `claude-opus-5-5`. The second call, for the answer, didn't try the first model at all, because it was benched. The stand-in's log shows it: four requests to the first model, two to the second. Compare with quark, which sent ten.

The third takes everything down, and then brings it back:

```
$ python3 flaky.py 8113 all &
$ ANTHROPIC_BASE_URL=http://127.0.0.1:8113 python3 resilience.py "How many bytes is notes.txt? Answer in one line."
```

```
[claude-sonnet-5-5: OverloadedError, try 1 of 4, waiting 0.7s]
[claude-sonnet-5-5: OverloadedError, try 2 of 4, waiting 1.0s]
[claude-sonnet-5-5: OverloadedError, try 3 of 4, waiting 2.2s]
[claude-sonnet-5-5: OverloadedError, giving up on it for 60s]
[claude-opus-5-5: OverloadedError, try 1 of 4, waiting 0.9s]
[claude-opus-5-5: OverloadedError, try 2 of 4, waiting 1.1s]
[claude-opus-5-5: OverloadedError, try 3 of 4, waiting 3.9s]
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
[Jev: transient, confidence 0.74]
(killed: still running after 3 seconds)
(it may have partly run: check before repeating it)
The first command was killed by a 3-second tool timeout before it could finish. I'll run the second one now.
$ python3 -c "print('x'*5000)"
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
[output cut at 300 characters]
**Command 1: `sleep 60; echo hi`**
- It did not complete. The tool killed it after about 3 seconds, while `sleep 60` was still running.
- `echo hi` never ran, so there was no "hi" output.
- The tool's limit is about 3 seconds, so I didn't retry, because it would be killed the same way. A shorter sleep would fit within the limit.

**Command 2: `python3 -c "print('x'*5000)"`**
- It ran and printed a line of the letter `x`, which should be 5000 characters followed by a newline.
- The tool cut the display off at 300 characters, so I only saw the first 300 `x`s. I can't confirm from the output that all 5000 were printed. To check, I could run `python3 -c "print('x'*5000)" | wc -c`. It should report 5001, which is 5000 characters plus the newline.
[done in 3 steps]
```

The sleep was killed at three seconds and the model was told so. Jev thought a timeout was probably transient, but only at 0.74, under `SURE`, so the harness didn't act on it, and since `sleep` isn't on the list of reads, the result got the "may have partly run" warning. The long line was cut at 300 characters and the model was told that too. In both cases it reported accurately what it had been given. The run went on to a third step where the model answered; the harness neither hung nor held on to five thousand characters.

The next three are Jev's question. For the first, a service that's down for its first request and fine after, about ten lines of Python:

```
# A service that's down for its first request and fine after: "503" once, then "ok".
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
seen = 0
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global seen
        seen += 1
        code, out = (503, b"busy\n") if seen == 1 else (200, b"ok\n")
        print(f"request {seen} -> {code}", flush=True)
        self.send_response(code); self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)
    def log_message(self, *args): pass
HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
```

```
$ python3 blip.py 8115 &
$ python3 resilience.py "Run exactly this command: curl -sSf http://127.0.0.1:8115/status   Then tell me in one line what the service said."
```

```
$ curl -sSf http://127.0.0.1:8115/status
[Jev: transient, confidence 0.87]
[trying once more in 1s]
ok
The service responded with "ok".
[done in 2 steps]
```

Jev read `curl: (22) The requested URL returned error: 503` as a failure that goes away; `curl` with those flags is on the list of reads, so the harness ran it again, and the model only ever saw `ok`. The service's log has two requests: a 503 and a 200. The same run without a key for Jev (`TYPESAFE_API_KEY=`, on a fresh service):

```
$ curl -sSf http://127.0.0.1:8116/status
[Jev: no answer]
curl: (22) The requested URL returned error: 503

(exit 22)
The service didn't give a status. It returned an HTTP 503 error (Service Unavailable), and curl exited with code 22.
[done in 2 steps]
```

No answer means no retry: the failure goes to the model as it did before Jev. And the limit: the first time I tried this, I used `curl -sf`, which hides curl's error message, so all the command printed was its exit code:

```
$ curl -sf http://127.0.0.1:8114/status
[Jev: permanent, confidence 0.47]
(exit 22)
The service didn't return a status. `curl` exited with code 22, which with `-f` means the server sent an HTTP error (4xx or 5xx). `-s` hid the error message, so I can't tell which status code it was.
[done in 2 steps]
```

With nothing but `(exit 22)` to read, Jev guessed, and said so with its confidence; at 0.47 the harness left it alone. Jev can only judge what a command shows.

The last is a command that does part of its work and then fails. `migrate.py` writes one file per table and stops at the fourth:

```
import os
os.makedirs("out", exist_ok=True)
for table in ["users", "orders", "items", "payments", "audit"]:
    if table == "payments": raise SystemExit("error: payments: no column named email")
    open(f"out/{table}.csv", "w").write("id\n")
    print(f"migrated {table}")
```

```
$ python3 resilience.py "Run python3 migrate.py once and tell me how it went. Don't fix anything."
```

```
$ python3 migrate.py
[Jev: partial, confidence 0.85]
migrated users
migrated orders
migrated items
error: payments: no column named email

(exit 1)
(it may have partly run: check before repeating it)
The migration failed partway through. I ran it once and didn't fix anything.

- `users` migrated.
- `orders` migrated.
- `items` migrated.
- `payments` failed with `error: payments: no column named email`, and the script exited with code 1.

The tool output warned that the script may have partly run, so check the state before you run it again. The first three steps appear to have completed. I haven't checked whether they were committed or whether the failure left `payments` half-migrated. Running it again could duplicate or conflict with the work already done.
...
[done in 2 steps]
```

(shortened: two paragraphs of the answer cut.) Jev called it partial, the harness added the warning, and the model passed it on instead of running the script again.

And the crash, which is the one from the worked example, with `resilience.py`. The command takes twelve seconds and I killed the harness a second or two after it started the command, again by PID:

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
assistant [{"id": "toolu_01Umw4defRA62i4aiNkwCrGU", "caller": {"type": "direct"}, "input": {"cmd": "sleep 12 && echo finished > flag.txt"}, "name": "bash", "type": "tool_use"}]
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
The command was interrupted, so I don't know if it finished. I'll check whether flag.txt exists before I run anything again.
$ ls -l flag.txt && cat flag.txt
-rw-r--r-- 1 root root 9 Oct  6 22:43 flag.txt
finished
`flag.txt` contains `finished`.

The harness reported my command as interrupted, but the file exists and has the expected content, so the command did finish. I didn't run it a second time.
[done in 2 steps]
```

The result for the dead request carried the command with it, the model checked the file instead of repeating the command, and the run finished.

## What to take away

**The rule:** assume the call can fail, and make failure something the harness handles instead of something that ends the run. Retry what passes a bounded number of times, have somewhere else to go when the preferred model is out, and stop with a sentence when everywhere is. Answer every tool request, even a broken one, with a result the model can read. When you stop it, keep what it had already said and done. And keep a record written before each step, so that when the harness itself fails, what was in flight can be reported as *unknown*, not guessed at and not lost.

Notice what Resilience never does. It sits in the model interface and output, and for recovery it reads the record context already keeps; it adds no store of its own. Control flow is the same loop with the same stop conditions: a retry happens inside one call, so the loop sees a call that took longer, and the only new way out is `Down`. Input is untouched apart from one question at startup, asked with the same `read()`. And what the model is shown changes only in what it's told about its own work: the "interrupted" result, the cut-off one, and the partial work an ESC used to throw away, each written like any other message.

**What's missing:** resilience keeps a run alive and recoverable; it doesn't make it fast or cheap. Every call re-sends the whole conversation, and only the system prompt is cached, so the messages are paid for in full every time. A command that prints a megabyte puts a megabyte in the next request. Three commands that could run side by side wait for each other, because quark asks for one at a time and runs them one after another. And when working memory fills up, the summary is written by the same big model as everything else. Making each step smaller, faster and cheaper is its own layer.

**→ [Lesson 9: Performance](../09-performance/)**
