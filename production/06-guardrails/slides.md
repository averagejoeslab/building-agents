---
marp: true
theme: default
paginate: true
header: "Lesson 6 · Guardrails"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Guardrails

### A hands-on course in building agents by building their harness
Lesson 6

<!-- Lesson 5 decided where commands run. This one decides whether they run at all, and gives you a way to break in. -->

---

# The box limits reach, not whether

Inside Lesson 5's box, the agent still runs whatever the model asks, as soon as it asks, for as long as it keeps asking.

- `rm -rf` on the mounted folder: your real project, gone
- Stuck retrying one command: it goes on until you notice the bill

<!-- The box makes the damage small. It doesn't stop the damage that's allowed inside it. -->

---

# The model proposes; the harness decides

Guardrails are rules about what the harness is allowed to do, checked before it does it: which commands may run, when a person gets a say, when a run has gone on long enough.

**Built on control flow**, which decides whether the next step happens at all:

- It turns a tool request into a command being run
- It turns the result into another model call
- A guardrail is a decision at one of those two points, so it lives there

<!-- The decision is yours. A production layer adds hardening, not a new primitive: everything guardrails do stays inside control flow. Point at the two places the loop already passes through. -->

---

# A few checks, where the loop already passes

- **A gate before each tool:** *allow* it, *ask* a person first, or *deny* it
- **A refusal the model can read:** in the result's slot, marked as an error, saying why
- **Limits before each call:** count the steps and tokens; past the limit, stop
- **An interrupt:** ESC stops it at once, thinking, saying or acting, tells the model, and hands the run back

<!-- The rules are plain code: a list of programs safe to run unasked, and patterns that must never run. Every tool request needs a result (Lesson 2), so a refusal fills that slot. Lesson 3 said a loop with no clear end is a bill with no clear end; this is the clear end. ESC is quark's own key. Ctrl-C isn't special: it's how you kill any program. /q is the graceful way out, as it has been since Lesson 2. In this lesson an interrupt is a stop and nothing more: whatever was cut short is dropped. Keeping it is Lesson 8's job. -->

---

# The box comes first

- Guardrails don't change what the model asks for, only whether the harness goes along with it
- They're only as good as the rules: a check is code reading a command
- A command can say the same thing many ways
- The guard keeps out what you'd never want; the box limits what gets through

<!-- This is why sandboxing came before guardrails. Text checks leak; kernel walls don't. -->

---

# The policy and the gate

Lesson 5's `quark.py` plus 62 lines. At the top of `# ── control flow ──` (abridged):

```python
MAX_STEPS, MAX_TOKENS = 20, 200_000
SAFE = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "date", "echo", "du", ...}
DENY = re.compile(r"\bsudo\b|rm\s+-\w*[rf]|mkfs|git\s+push|(curl|wget).*\|\s*(ba)?sh|\.env\b")
def guard(cmd):
    if DENY.search(cmd): return "blocked by policy"
    if not re.search(r"[;&<>$`\n(]", cmd) and all(... in SAFE ...): return None
    answer = read(f"allow `{cmd}`? [y/N] ")
    return None if answer.lower() == "y" else "the person said no" + ...
```

<!-- SAFE is programs that only read. DENY is sudo, recursive or forced rm, mkfs, git push, piping a download into a shell, and anything mentioning .env. They're data, so changing the policy is changing a line. The checks and limits are all in control flow. The interrupt reaches two more places: hearing ESC is input, and stopping a response halfway takes one line in Lesson 1's call(). -->

---

# `guard()`: deny, allow, or ask

It returns `None` if the command may run, or the reason it may not:

1. Matches `DENY`: refused outright, and no one is asked
2. Only safe programs: it runs. No `; & < > $`, backtick, newline or `(`, and every piece between pipes starts with a `SAFE` program
3. Anything else goes to the person with Lesson 2's `read()`; a `y` lets it run
4. Any other answer is a no, and what they typed goes back to the model

<!-- cat notes.txt | sh isn't safe just because it starts with cat. "no, use git status instead" is an instruction, not just a refusal. Ctrl-D, or /q, counts as a plain no. The default is the safe one: a command nobody approved doesn't run. -->

---

# Limits, checked before every call

At the top of the loop, and where each call is counted (abridged):

```python
    if steps >= MAX_STEPS or spent >= MAX_TOKENS:
        print(f"[stopped: {steps} steps, {spent} tokens]")
        if not chat or (input := read("\n> ")) == "/q": break
        add(working_memory, {"role": "user", "content": input})
        steps, spent = 0, 0
        continue
    ...
        with listening():
            response = call(unless_esc, ..., messages=working_memory)
        output = response.content
        steps += 1
        spent += response.usage.input_tokens + response.usage.output_tokens + ...
```

In a one-shot run, a limit is the end. In a chat it hands back to you, and the counts start again after each new input.

<!-- The call now keeps the whole response, not just its content, so the count can read usage. The two cache counts can come back empty, hence the or 0. The with listening(): and unless_esc in place of show are the interrupt, coming up. Resetting after each input means one long chat doesn't use up a budget meant for one request. -->

---

# A refusal goes where the result would have

In the output loop, between printing the command and running it in the box (abridged):

```python
            print(f"$ {block.input['cmd']}")
            if ESC.is_set():
                input.append({..., "content": "[your doing never reached the world]"})
                continue
            if (no := guard(block.input["cmd"])):
                print(f"[{no}]")
                input.append({"type": "tool_result", ..., "content": no, "is_error": True})
                continue
```

- `continue` skips the run: the command never starts, and the model's next turn still makes sense
- The `ESC` check above the gate: once you've pressed ESC, nothing else starts

<!-- A command that passes the gate runs in Lesson 5's box, under its time limit, as before. Lesson 4's mechanics() puts quark's own file in its system prompt, so the model can read the policy it's under. That's self-knowledge, not this layer, and it saves the model asking for things that will be refused. -->

---

# The interrupt: listening for ESC

ESC is input from a person, so in `# ── input ──`, after `read()` (abridged):

```python
ESC = threading.Event()
SAYING = "[other self interrupted what you were saying — acknowledge]"
DOING = "[other self interrupted what you were doing — acknowledge]"
def watch(stop):
    ...
@contextlib.contextmanager
def listening():
    ESC.clear()
    if not sys.stdin.isatty(): yield; return
    ...
```

- `watch()` reads one key at a time in a thread; an ESC on its own sets `ESC`
- quark listens only while it thinks, says or acts, never while `read()` waits for you

<!-- Arrow keys also start with the ESC byte, but more bytes follow at once, so those are read and ignored. listening() clears any earlier ESC, puts the terminal into a mode where keys arrive one at a time without Enter, starts the thread, and puts everything back afterwards. With no terminal (a pipe, a script, an evaluation) there's no keyboard to watch and it does nothing. -->

---

# Stopping what it says: the next piece ends it

One line in `call()`, `unless_esc` in place of `show`, and a check right after the call (abridged: end-of-line comments cut):

```python
        for event in stream:
            if each(event): return stream.current_message_snapshot
def unless_esc(event):
    if ESC.is_set(): return True
    show(event)
...
    if response.stop_reason is None:
        print()
        add(working_memory, {"role": "user", "content": SAYING})
        continue
```

<!-- Until you press ESC, unless_esc is show(). After, the next piece that arrives ends the call: quark stops reading, the connection closes, the model stops writing. What comes back has no stop_reason, because it never finished. What it had said is on your screen, but the response is dropped whole, before working memory or the episode, along with any command it was asking for. The model is told only that it was interrupted. -->

---

# Stopping what it does: `kill -9 -1` in the box

The command now starts with `Popen`, and quark waits a tenth of a second at a time (abridged):

```python
            with listening():
                doing = subprocess.Popen(["docker", "exec", box, ..., block.input["cmd"]], ...)
                while True:
                    try: done = ...(doing.communicate(timeout=0.1)[0]); break
                    except subprocess.TimeoutExpired:
                        if ESC.is_set(): subprocess.run([..., "kill -9 -1"], ...)
            done.returncode = doing.returncode
            if ESC.is_set(): done.stdout = "[your doing stopped before done]"
```

- Every command in the box stops; the box itself survives
- What it had printed is dropped; the model gets `DOING`

<!-- The process every container runs first can't be killed that way, so the box lives on and the next command has somewhere to run. Commands still waiting in the same response get [your doing never reached the world]. After the loop, if ESC is set, the results go back with the DOING message, and the loop goes around for the model to answer it. Dropping what was cut short keeps the interrupt to a stop. The cost: the model knows it was interrupted, but not how far it had got. -->

---

# Safe commands run; anything else waits for you

`wc` is on the safe list, so nothing was asked:

```
$ wc -l notes.txt
3 notes.txt

notes.txt has 3 lines.
```

`rm` isn't, so the harness stopped at the prompt (I piped in `y`; shortened):

```
$ rm a.log b.log && ls -A
allow `rm a.log b.log && ls -A`? [y/N] .env
.quark
notes.txt
```

<!-- In the second run the model looked first with ls -la, which is safe, so it ran without asking. Then rm waited for its answer: nothing was deleted until it came. -->

---

# A no with a reason; a deny that asks no one

Answers piped in: `no, put it in a folder called drafts`, then `y` (shortened):

```
$ touch notes2.txt && ls -l notes2.txt
allow `touch notes2.txt && ls -l notes2.txt`? [y/N] [the person said no: no, put it in a folder called drafts]
$ mkdir -p drafts && touch drafts/notes2.txt && ls -l drafts/notes2.txt
```

Then: print `.env`, then `rm -rf .`:

```
$ cat .env
[blocked by policy]
```

<!-- The model took the reason as an instruction and asked again. In the deny run it said: "I managed nothing: the policy blocked cat .env, and I didn't try rm -rf . because the same policy forbids it." It can read its own harness, so it expected more of the same, and it didn't try to get around the block. The folder, .env included, is all still there. -->

---

# A limit stops the run before the next call

`MAX_STEPS` lowered to 2 in a copy, asking for three commands, one at a time:

```
$ date
Tue Oct  6 20:31:57 UTC 2026

$ pwd
/tmp/g6

[stopped: 2 steps, 15041 tokens]
```

`MAX_TOKENS` works the same way, but at 200,000 you'll rarely reach it.

<!-- The check is at the top of the loop, so the run ends before spending another call. -->

---

# ESC while it acts: the count stops partway

Count to ten, one a second, `y`, then ESC four and a half seconds later (shortened):

```
$ for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 1; done
allow `for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 1; done`? [y/N] y
[your doing stopped before done]
```

> You interrupted the count, so it stopped before it finished. The command never returned any output, so I can't say how far it got.

<!-- ESC needs a terminal: these three ran in a pseudo-terminal driven by a script, so the key presses are exact, in chat mode, ending with /q. You don't see the numbers it printed, because quark shows a command's output when the command is done, and this one never was. The model got only the note, so it couldn't tell how far the count got. Then the run handed back to me. -->

---

# ESC while it says: the fable stops mid-sentence

ESC a second after its first full stop (shortened):

```
> Tell me the fable of the tortoise and the hare in about 400 words
# The Tortoise and the Hare
...
I see I was cut off mid-story. Here is the whole fable.

**The Tortoise and the Hare**
...
```

It stopped at "…a tortoise, who had been plodding past with a leaf on his back". None of it was kept, so the model told the whole fable again from the top.

<!-- The story stopped the moment the next piece of the stream arrived. The model got [other self interrupted what you were saying — acknowledge]. It knew it had been cut off, but not where. ESC stopped the response, not the request, and the run only came back to me after the retelling. -->

---

# ESC while it thinks: back to the request

ESC 0.6 seconds after asking, before it said a word. The blank line is the whole stopped response (shortened):

```
> Make a file called hello.txt containing the word hello.

$ echo hello > hello.txt && cat hello.txt
allow `echo hello > hello.txt && cat hello.txt`? [y/N] /q
[the person said no]
```

- Nothing reached the folder: there's no `hello.txt`
- The model is told it was interrupted, not what it was in the middle of
- Keeping what was cut short is Lesson 8's job

<!-- The model went straight back to the request, and the guard put the command to me. /q at that question is a plain no. Both of these last two runs show what the interrupt doesn't do: the model picks the request up again, because it doesn't know where it stopped. -->

---

# Going further: what else guardrails can be

- **How a command is judged:** text patterns, a shell parser, per-tool rules, or a second model call
- **What the answers are:** allow once, for the session, always, or with these arguments
- **Who gets asked:** the terminal, someone on Slack or Telegram, a second agent, or nobody
- **What counts as too much:** steps, tokens, dollars, wall-clock time, or repeating
- **How a run is interrupted:** a key, a message mid-run, a kill switch

As a product alone: **Open Policy Agent**, **NeMo Guardrails**, **Guardrails AI**.

<!-- After an interrupt: stop, or hand back to the person with the work so far intact. Policy services like Open Policy Agent decide allowed or not as data, not code; NeMo Guardrails and Guardrails AI wrap checks around what goes into and out of a model. If you're using one for what a tool may run, it's this layer. Asking too often trains people to hit y; asking too rarely is no guardrail. A run with nobody to ask has to fail closed. Also: what the model is told (a bare refusal, a reason, or the rule itself), and what you do about it afterwards. -->

---

# `guardrails.py`: finer answers, more limits

Built on Lesson 3's `control_flow.py`, with no system prompt:

- **Judged per piece:** `cd /tmp && rm x` is judged by `cd` *and* `rm`
- **Always:** `a` at the prompt adds those programs to `ALLOWED` for the rest of the run
- **A spending limit** in dollars, from each response's `usage`
- **A repeat limit:** the same command `MAX_REPEATS` times stops the run

<!-- Tokens are what you can count; dollars are what you care about. A model going round in circles is spending your money without getting anywhere. -->

---

# Two questions covered five commands

I answered `a` to `mkdir` and to the first `touch`:

```
$ mkdir /tmp/gdemo
allow `mkdir /tmp/gdemo`? (mkdir isn't on the allowed list) [y]es, [a]lways, or say why not: 
$ cat .env
[blocked by policy: secrets files are off limits]
$ touch /tmp/gdemo/a.txt
allow `touch /tmp/gdemo/a.txt`? (touch isn't on the allowed list) [y]es, [a]lways, or say why not: 
$ touch /tmp/gdemo/b.txt

$ ls /tmp/gdemo
a.txt
b.txt
```

<!-- cat .env was denied without asking. The second touch didn't ask, because touch was by then allowed. ls was already on the list. -->

---

# The rule: decide before the harness does it

**The rule:** check each tool request where control flow turns it into a command, and the run where it goes around again. Say no in a way the model can read, and give the person a way in.

What guardrails never do, from inside control flow:

- **Model interface:** one line, so a response can be stopped; otherwise as before
- **Output:** an allowed command runs in the box exactly as before
- **Context:** a refusal is an ordinary tool result in the result's slot
- **Input:** Lesson 2's `read()`, plus a watcher that hears ESC while quark works

<!-- Decide what the harness is willing to do before it does it. Guardrails read usage and the tool request off the response and nothing more. -->

---

# What's missing: you can stop a run, not see one

- How long did each step take?
- How many tokens, and what did that cost?
- Which command did the guard refuse, and which did the box kill?
- The episode has every message, but it's written for the model: no timings, no token counts, no exit codes

<!-- The terminal scrolled past. The person running quark needs a record of their own. That's observability. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Next: Observability

Lesson 7
