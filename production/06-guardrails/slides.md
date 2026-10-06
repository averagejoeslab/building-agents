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

<!-- Lesson 5 decided where commands run. This one decides whether they run at all. -->

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
- **A refusal the model can read:** the refusal goes in the result's slot, marked as an error, saying why
- **Limits before each call:** count the steps and tokens; past the limit, stop
- **An interrupt:** press ESC and quark stops, keeps what it had done, tells the model, and hands the run back to you

<!-- The rules are plain code: a list of programs safe to run unasked, and patterns that must never run. Every tool request needs a result (Lesson 2), so a refusal fills that slot. Lesson 3 said a loop with no clear end is a bill with no clear end; this is the clear end. ESC is quark's own key. Ctrl-C isn't special: it's how you kill any program, quark included. /q is the graceful way out, as it has been since Lesson 2. -->

---

# The box comes first

- Guardrails don't change what the model asks for, only whether the harness goes along with it
- They're only as good as the rules: a check is code reading a command
- A command can say the same thing many ways
- The guard keeps out what you'd never want; the box limits what gets through

<!-- This is why sandboxing came before guardrails. Text checks leak; kernel walls don't. -->

---

# The policy and the gate

Lesson 5's `quark.py` plus 59 lines, mostly in `# ── control flow ──`. At the top of the section (abridged):

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

<!-- SAFE is programs that only read. DENY is sudo, recursive or forced rm, mkfs, git push, piping a download into a shell, and anything mentioning .env. They're data, so changing the policy is changing a line. The interrupt also needs a way to hear ESC, which is input from a person, so part of it is in # ── input ──. -->

---

# `guard()`: deny, allow, or ask

It returns `None` if the command may run, or the reason it may not:

1. Matches `DENY`: refused outright, and no one is asked
2. Only safe programs: it runs. No `; & < > $`, backtick, newline or `(`, and every piece between pipes starts with a `SAFE` program
3. Anything else goes to the person with Lesson 2's `read()`; a `y` lets it run
4. Any other answer is a no, and what they typed goes back to the model

<!-- cat notes.txt | sh isn't safe just because it starts with cat. "no, use git status instead" is an instruction, not just a refusal. Ctrl-D counts as no. The default is the safe one: a command nobody approved doesn't run. -->

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
            response = call(max_tokens=16384, system=system(), tools=tools, messages=working_memory)
        output = response.content
        steps += 1
        spent += response.usage.input_tokens + response.usage.output_tokens + ...
```

In a one-shot run, a limit is the end. In a chat it hands back to you, and the counts start again after each new input.

<!-- The call now keeps the whole response, not just its content, so the count can read usage. The with listening(): around it is the interrupt, coming up. Resetting after each input means one long chat doesn't use up a budget meant for one request. -->

---

# A refusal goes where the result would have

In the output loop, between printing the command and running it in the box (abridged):

```python
            print(f"$ {block.input['cmd']}")
            if (no := guard(block.input["cmd"])):
                print(f"[{no}]")
                input.append({"type": "tool_result", ..., "content": no, "is_error": True})
                continue
```

- `continue` skips the run: the command never starts, and the model's next turn still makes sense
- A command that passes the gate runs in Lesson 5's box exactly as before

<!-- Lesson 4's mechanics() puts quark's own file in its system prompt, so the model can read the policy it's under. That's self-knowledge, not this layer, and it saves the model asking for things that will be refused. Just above the gate there's also an ESC check: once you've pressed ESC, nothing else starts. -->

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
    if not sys.stdin.isatty(): yield; return
    ...
```

- `watch()` reads one key at a time in a thread; an ESC on its own sets `ESC`
- quark listens only while it thinks or acts, never while `read()` waits for you

<!-- Arrow keys also start with the ESC byte, but more bytes follow at once, so those are read and ignored. listening() puts the terminal into a mode where keys arrive one at a time without Enter, starts the thread, and puts everything back afterwards. With no terminal (a pipe, a script, an evaluation) there's no keyboard to watch and it does nothing. -->

---

# The interrupt: keep the work, tell the model

After an ESC (abridged):

```python
    if ESC.is_set():           # while it thought or said: keep what it said, run nothing
        ... "[your doing never reached the world]" ... SAYING ...
    ...
                doing = subprocess.Popen([...], stdout=subprocess.PIPE, ...)
                ...
                        if ESC.is_set(): subprocess.run([..., "kill -9 -1"], ...)
            ...
            if ESC.is_set(): done.stdout += "\n[your doing stopped before done]"
    ...
    if ESC.is_set():           # while it acted: keep what it did
        add(working_memory, {"role": "user", "content": input + [..., DOING]})
```

Then the loop goes around: the model acknowledges it, and the run hands back to you.

<!-- While it thinks or says: what was said is kept, every command it asked for gets a result saying it never reached the world, because the API needs an answer to each. This lesson's call waits for the whole response, so ESC takes effect when it arrives; Lesson 9 streams, and there ESC stops it mid-sentence. While it acts: the command now starts with Popen and quark waits a tenth of a second at a time. kill -9 -1 inside the box stops every command there; the box survives, because a container's first process can't be killed that way. What it printed so far goes back, with the note. -->

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
$ rm a.log b.log; ls -A
allow `rm a.log b.log; ls -A`? [y/N] .env
.quark
notes.txt
```

<!-- In the second run the model looked first with ls -la; find ..., and because that chains two commands with ;, the guard asked for that too. Nothing was deleted until the answer came. -->

---

# A no with a reason is an instruction

The answers piped in were `no, put it in a folder called drafts`, then `y` (shortened):

```
$ touch notes2.txt && ls -l notes2.txt
allow `touch notes2.txt && ls -l notes2.txt`? [y/N] [the person said no: no, put it in a folder called drafts]
$ mkdir -p drafts && touch drafts/notes2.txt && ls -l drafts/notes2.txt
```

The model took the reason as an instruction and asked again.

<!-- The person's reason goes back to the model inside the refusal, so a no can redirect the run, not just block it. -->

---

# The deny list asks no one

```
$ cat .env
[blocked by policy]
```

> I managed to do nothing from your request. Policy blocked `cat .env`, and I didn't try `rm -rf .` because the same policy forbids it. I also didn't try to get around either block.

The model expected it, because it can read its own harness. The folder, `.env` included, is all still there.

<!-- cat .env was refused before it ran. The model didn't even try rm -rf ., since it could read the policy. -->

---

# A limit stops the run before the next call

`MAX_STEPS` lowered to 2 in a copy, asking for three commands, one at a time:

```
$ date
Tue Oct  6 19:15:44 UTC 2026

$ pwd
/tmp/g6

[stopped: 2 steps, 14843 tokens]
```

`MAX_TOKENS` works the same way, but at 200,000 you'll rarely reach it.

<!-- The check is at the top of the loop, so the run ends before spending another call. -->

---

# ESC stops the command, and keeps what it printed

Count to ten, `y`, then ESC four and a half seconds later (shortened):

```
$ for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 1; done
1
2
3
4
5

[your doing stopped before done]
```

> You interrupted the count, so it stopped after 5 and never reached 10. Do you want me to run it again from the start, or leave it there?

<!-- ESC needs a terminal: this ran in chat mode, in a pseudo-terminal driven by a script, so the key presses are exact. The 5 lines it had printed went back to the model with the note. In the second run, ESC 0.6 seconds after asking for a file: the command was never run, and the model said notes.txt doesn't exist yet. Nothing reached the folder. -->

---

# Going further: what else guardrails can be

- **How a command is judged:** text patterns, a shell parser, per-tool rules, or a second model call
- **What the answers are:** allow once, for the session, always, or only with these arguments
- **Who gets asked:** the terminal, someone on Slack or Telegram, a second agent, or nobody
- **What counts as too much:** steps, tokens, dollars, wall-clock time, or repeating
- **How a run is interrupted,** and what the model is told about a refusal

<!-- Asking too often trains people to hit y; asking too rarely is no guardrail. A run with nobody to ask has to fail closed. -->

---

# It can be a product on its own

- Policy services like **Open Policy Agent** decide *allowed or not* for a request, as data and not code
- Libraries like **NeMo Guardrails** and **Guardrails AI** wrap checks around what goes into and comes out of a model

If you're using one for what a tool may run, it's this layer.

<!-- Same layer, someone else's rules engine. -->

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

- **Model interface:** sends and receives as before; guardrails read `usage` and the tool request
- **Output:** an allowed command runs in the box exactly as before
- **Context:** a refusal is an ordinary tool result in the result's slot
- **Input:** Lesson 2's `read()`, plus a watcher that hears ESC while quark works

<!-- Decide what the harness is willing to do before it does it. Each piece of this layer uses the other primitives as they are, and changes none of them. -->

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
