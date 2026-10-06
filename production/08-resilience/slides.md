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

Lesson 7 can tell you exactly where a run broke. Over a long run, this is what breaks first:

- the API drops a call
- the model is overloaded
- a response is cut off in the middle of a command
- the process dies halfway through, and the work goes with it

<!-- So far every call assumed the thing on the other side answers, and answers sensibly. That's the assumption that fails first. -->

---

# Keep going, or stop somewhere you can start again

Two jobs:

- **Get through the failures that pass**
- **Leave a state you can pick up from** when one doesn't, so the hour before it isn't lost

Built on the **model interface** and **output**, where the harness reaches out and the world gets to say no. To pick a run back up it **reads context's own record**: Lesson 4's episode.

<!-- No new primitive. The model interface is a service across a network: slow, busy or gone. Output runs the model's words, so what it's handed can be broken. And the episode already holds every message, written before any tool runs, so there's no save file of its own. -->

---

# Not every failure means the same thing

| Worth trying again | Not worth trying again |
|---|---|
| the network dropped, or a timeout | a bad API key (401) |
| "slow down" (429) | a request the API won't accept (400) |
| any 5xx, and "overloaded" (529) | a model that doesn't exist (404) |
| *the same request will probably work* | *it gets the same answer every time* |

<!-- Nothing is wrong with the request on the left: send it again a moment later. On the right, retrying only delays the error, so those go up to the code that can do something about them, or to you. -->

---

# The SDK retries; quark adds a backup model

How to retry: back off (one second, two, four), add jitter, wait as long as the server says, and stop after a few tries.

- The Anthropic SDK already does all of this, set by `max_retries`
- So quark doesn't write a retry loop: it turns the setting up and sets a timeout
- What the SDK can't do is choose a different model
- When nothing answers, stop with a message, not a stack trace

<!-- Jitter is so a thousand clients that failed together don't all come back together. The one thing quark adds in the model interface is the backup. -->

---

# Every request gets an answer the model can read

A command can fail in ways the harness doesn't see coming:

- it hangs (the sandbox already puts a time limit on that)
- it prints bytes that aren't text
- the request arrives cut off by the token limit, half a command

*This was cut off, it wasn't run, send it again shorter* is something the model can act on. A crash isn't.

<!-- This is the rule Lesson 2 started with. -->

---

# The trap: a command that may already have run

- The episode has the model's request on disk *before* the command runs
- If the harness died mid-command, the record ends with a request and no result
- The API won't accept that, and the harness can't just run it again: it might have been `git push`
- So the missing result becomes an error: *interrupted; may or may not have run; check before repeating it*
- The model, which knows what the command was for, looks and decides

<!-- This is why it isn't just "load the file." The harness can't know whether it ran, so it says so. It's not a guess made by the harness. -->

---

# `call()` grows a backup

Lesson 7's `quark.py` plus 29 lines. In `# ── model interface ──` (abridged):

```python
client = Anthropic(timeout=300, max_retries=3)
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]
class Down(Exception): pass
def call(**request):
    for model in MODELS:
        try: return client.messages.create(model=model, **request)
        except (APIConnectionError, APIStatusError) as e:
            if ... e.status_code < 500 and e.status_code != 429: raise
            trace(event="model_failed", model=model, error=type(e).__name__)
    raise Down()
```

<!-- Every call already went through call(), including the summary in compact(), so this is the one place to change. Transient failures after the SDK's retries are traced and the next model is tried. Everything else is raised, including "prompt is too long", which compaction is waiting for. The test is on the status code so 529 isn't missed. timeout=300 is five minutes, because a reply of 16,000 tokens takes minutes to write; max_retries=3 is one more than the SDK's default, written out so you can see it's a choice. -->

---

# `unfinished()` reads the last episode back

In `# ── context ──`, after `add()` (abridged):

```python
def unfinished():
    episodes = sorted(glob.glob(".quark/episodes/*.jsonl"))
    if not episodes: return None
    messages = [json.loads(line) for line in open(episodes[-1])]
    last = messages[-1]
    if last["role"] == "assistant" and not any(... "tool_use" ...): return None
    if read(f"unfinished session: ... pick it up? [y/N] ").lower() != "y": return None
    return episodes[-1], messages
```

In `# ── input ──`, it's asked before anything else is read:

```python
resumed = unfinished()
input = "" if resumed else " ".join(sys.argv[1:]) or read("> ")
```

<!-- If the newest episode ends with the model's answer and no tool request, that session finished. Otherwise it shows you the input that opened it and asks, with Lesson 2's read(). -->

---

# A resumed session continues in its own episode

In `# ── control flow ──` (abridged):

```python
if resumed:
    EPISODE, working_memory = resumed
    if working_memory[-1]["role"] == "assistant":
        add(working_memory, {"role": "user", "content": [...]})
else:
    add(working_memory, {"role": "user", "content": input})
trace(event="start", input=input, resumed=bool(resumed))
```

Each unanswered request gets: *"interrupted: the harness stopped before this finished, so it may or may not have run. Check before repeating it."*

<!-- EPISODE points at the old file, so everything from here is appended to the same session. The interrupted results go through add(), so the episode records them too. -->

---

# Stop with a sentence, and never run half a command

```python
    except Down:
        sys.exit("[the model isn't answering. ...]")
```

```python
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if not cmd or (response.stop_reason == "max_tokens" and ...):
                print("[cut off, not run]")
                input.append({"type": "tool_result", ..., "is_error": True})
                continue
```

(abridged) Cut off means `max_tokens` and this is the last block. The result says: *"your request was cut off at the token limit, so it was not run. Send it again, shorter."* And `errors="replace"` turns bytes that aren't text into `�`.

<!-- block.input.get means a request with no command is answered, not a KeyError. Without errors="replace", a UnicodeDecodeError would kill the harness. -->

---

# Run it: the preferred model is down

A stand-in for the API answers "529 overloaded" to every request for `claude-sonnet-5-5`, and forwards the rest:

```
$ wc -c notes.txt
6 notes.txt

notes.txt is 6 bytes.
```

The output looks like any other run. The trace doesn't:

```
{"event":"model_failed","model":"claude-sonnet-5-5","error":"OverloadedError"}
{"event":"model","seconds":5.22,"stop_reason":"tool_use"}
```

(shortened)

<!-- The stand-in, flaky.py, is about 30 lines of standard-library Python, reached through ANTHROPIC_BASE_URL. Each call had four failed requests to Sonnet, the first try and three retries, then one to Opus that worked: ten requests for two calls. The 5.22 seconds is the backoff. -->

---

# Run it: nothing answers, then the API comes back

Every request fails, for every model. quark stops with:

> [the model isn't answering. Everything so far is in the episode; run quark again to pick it up]

Run `quark.py` again with no input and answer `y` (shortened):

```
notes.txt is 6 bytes.
```

```
{"event":"start","input":"","resumed":true}
```

<!-- It tried both models, gave up and said so. There's no save file: the episode is the record. The second run picked the session up from its episode, and finished in it: that one file now holds all four messages. -->

---

# Run it: the harness is killed mid-command

The task is one slow command, `sleep 15 && echo finished > flag.txt`. The harness is killed with `kill -9` on its PID twelve seconds in.

- The episode was written when the model asked for the command, before it ran
- `flag.txt` isn't there, and then it is: the container wasn't killed, so the command finished in it
- `atexit` can't run after `kill -9`
- The command did run, and the harness doesn't know

<!-- That's exactly the case the interrupted result is for. Kill by PID, not pkill, which matches on names and can match far more than you meant. -->

---

# Resumed, the model checks before repeating

```
finished

`flag.txt` contains `finished`.
```

(shortened) It ran `ls -l flag.txt; cat flag.txt`, then said:

> The first run of the command was interrupted, and I wasn't sure it had completed. I checked the file before running it again. The file already existed and held that text, so I didn't repeat the command.

<!-- It did what the wording asks: it looked, found the file, and didn't run the command again. If flag.txt hadn't been there, the same sentence would have led it to run the command once. It's the model's call, made with the facts. -->

---

# What else resilience can be

- **Retries and waits:** backoff with jitter and a cap, `Retry-After`, or a limiter that keeps under the rate limit
- **The backup:** another model, provider or region; a switch pays the full prompt once, since the cache is per model
- **Remembering a failure:** a *circuit breaker* leaves a failed model alone for a minute
- **Streaming and tools:** keep what arrived, time out on silence; kill the process group, cap output
- **State and restarts:** saved every step, as an event log, restarted by you, a supervisor or a service

<!-- quark has one retry setting, one backup model and one file. Retrying a read is usually safe; retrying a write never is, unless doing it twice is the same as doing it once. A hard kill can't be caught, which is why the file is written before the work. -->

---

# Products, and a fuller example

Gateways like LiteLLM and OpenRouter handle retries, fallbacks and rate limits. Durable execution (Temporal) and checkpointing (LangGraph) pick a crashed process up at its step.

`resilience.py`, built on Lesson 3's loop, does the retries itself, in plain sight:

- `retryable()` sorts failures; `pause()` honors `retry-after`, else backs off with jitter
- `ask()` benches a model that gave up for `BENCH` seconds
- `run()` kills the whole process group and caps output
- `save()` checkpoints every step; `resilience.py resume` picks it up

<!-- The client has max_retries=0, so its retries are the only ones. The checkpoint is written before the first request, after each reply and after each set of results, so it always ends at a point the API will accept. -->

---

# The preferred model down, with a circuit breaker

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

Waits grow with jitter: 0.7, 1.7, 2.5. The second call skipped the benched model: six requests, where quark sent ten.

<!-- The doubling would give 1, 2, 4, each multiplied by a number between a half and one. The stand-in's log shows four requests to the first model, two to the second. -->

---

# The rule

Assume the call can fail, and make failure something the harness handles instead of something that ends the run.

- Retry what passes, a bounded number of times
- Have somewhere else to go, and stop with a sentence when everywhere is out
- Answer every tool request, even a broken one, with a result the model can read
- Keep a record written before each step, so what was in flight is reported as *unknown*

<!-- Not guessed at, and not lost. -->

---

# What resilience never does

- **Context:** it reads the record context already keeps; it adds no store of its own
- **Control flow:** same loop, same stops; a retry is inside one call, and the only new way out is `Down`
- **Input:** untouched, apart from one question at startup, asked with the same `read()`
- **What the model sees:** one new message, the "interrupted" one, written like any other result

<!-- It sits in the model interface and output. The system prompt doesn't tell the model that the harness retries or that it may have been resumed: that would be a decision about context, and this layer doesn't make it. -->

---

# What's missing: alive, but not fast or cheap

- Every call re-sends the whole conversation and waits for the whole reply
- A command that prints a megabyte puts a megabyte in the next request
- Three commands that could run side by side wait for each other
- Retries and fallbacks cost time that only the trace shows

Making each step smaller, faster and cheaper is its own layer.

<!-- Resilience keeps a run alive and recoverable. That's the bridge to performance. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Next: Performance

Lesson 9
