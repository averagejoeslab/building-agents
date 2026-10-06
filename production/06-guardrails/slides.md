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

<!-- Some rules are plain code: patterns that must never run, and a list of programs safe to run unasked. For everything a list can't settle, one question to a second model: what does this command do? Every tool request needs a result (Lesson 2), so a refusal fills that slot. ESC is quark's own key; Ctrl-C just kills the program; /q is the graceful way out. Guardrails don't change what the model asks for, and a check is code reading a command, which can be spelled many ways. That's why the box comes first. -->

---

# The concept: a gate, and nothing else

`guardrails.py` takes commands on the command line and decides about each one (abridged: comments cut):

```python
DENY = {r"\bsudo\b": "no sudo", r"rm\s+-\w*[rf]": "no recursive or forced deletes", ...}

def gate(cmd):
    for pattern, why in DENY.items():
        if re.search(pattern, cmd): return f"denied: {why}"
    choice, confidence = kind(cmd)
    print(f"[Jev: {choice}, {confidence:.2f}]")
    if choice == "read" and confidence >= SURE: return None
    try: answer = read("allow it? [y/N] ")
    except EOFError: answer = ""
    return None if answer.strip().lower() == "y" else "the person said no"
```

**Deny** on a pattern, without asking Jev; **allow** a sure read; **ask** about the rest

<!-- No model writing the commands, no loop. DENY also covers .env, where secrets live, and git push. The default is the safe one: a command nobody approved doesn't run. -->

---

# Jev's question: read, write, delete or other?

`KIND` in `guardrails.py` (abridged):

```python
KIND = Choice(instructions="What does the shell command in `command` do? ...", criteria={
    "read": "only reads, lists, searches or prints; changes nothing",
    "write": "creates or changes files, and nothing that existed is lost",
    "delete": "removes files, or overwrites or replaces data that existed",
```

- Jev, from Lesson 5: no text, typed answers, a confidence separate from the answer
- `other`: the network, scripts, installs, permissions
- No key, an error or a timeout: `no answer`, so the person is asked
- Asking is **model interface**; running or asking is **control flow**

<!-- Each option says exactly what it covers, because Jev reads literally. Without other, curl has nowhere to go but read. It answers "what does this do?", not "is this safe?": cat ~/.aws/credentials and printenv come back read at 1.00, which is why DENY runs first. A comment saying # this only reads on an rm didn't fool it: still delete, 1.00. It never runs a command because Jev was silent. -->

---

# Six commands, two questions

I answered `y`, then `n` (shortened):

```
$ wc -l notes.txt
[Jev: read, 1.00]
3 notes.txt
...
$ touch draft.txt
[Jev: write, 1.00]
allow it? [y/N] y
$ rm a.log
[Jev: delete, 1.00]
allow it? [y/N] n
[the person said no]
$ rm -rf .
[denied: no recursive or forced deletes]
$ cat .env
[denied: secrets are off limits]
```

<!-- The two reads ran without asking, the pipe included. touch was a write: asked, yes. rm a.log was a delete: asked, no, and a.log is still there. The last two never got as far as Jev. With TYPESAFE_API_KEY empty, even wc -l came back [Jev: no answer, 0.00] and was put to the person: slower, never less safe. -->

---

# quark's policy and gate

Lesson 5's `quark.py` plus 66 lines, 334 in all. At the top of `# ── control flow ──` (abridged):

```python
MAX_STEPS, MAX_TOKENS = 20, 200_000
SAFE = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "date", "echo", "du", ...}
DENY = re.compile(r"\bsudo\b|rm\s+-\w*[rf]|mkfs|git\s+push|(curl|wget).*\|\s*(ba)?sh|\.env\b")
KIND = Choice(instructions="What does the shell command in `command` do? ...", criteria={...})
def guard(cmd):
    if DENY.search(cmd): return "blocked by policy"
    if not re.search(r"[;&<>$`\n(]", cmd) and all(... in SAFE ...): return None
    kind = ask({"command": cmd}, KIND)
    if kind and kind["choice"] == "read" and kind["confidence"] >= SURE: return None
    why = f" (Jev: {kind['choice']}, {kind['confidence']:.2f})" if kind else ""
    answer = read(f"allow `{cmd}`?{why} [y/N] ")
    return None if answer.lower() == "y" else "the person said no" + ...
```

<!-- KIND is the concept's question, word for word. The checks, limits and Jev's question are all in control flow. The interrupt reaches two more places: hearing ESC is input, and stopping a response halfway takes one line in Lesson 1's call(). -->

---

# `guard()`: deny, safe list, Jev, or ask

It returns `None` if the command may run, or the reason it may not:

1. Matches `DENY`: refused outright, and no one is asked
2. Only safe programs: no `; & < > $`, backtick, newline or `(`, every pipe piece checked
3. Otherwise Jev, through Lesson 5's `ask()`: a sure `read` runs
4. Anything else goes to the person, with Jev's answer as the reason
5. Anything but `y` is a no, and what they typed goes back to the model

<!-- cat notes.txt | sh isn't safe just because it starts with cat. find, which isn't on the list, or ls -A; cat notes.txt, which has a semicolon, can run unasked if Jev is sure. If Jev didn't answer, the question has no reason in it. "no, use git status instead" is an instruction, not just a refusal. Ctrl-D, or /q, counts as a plain no. -->

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

<!-- The call now keeps the whole response, not just its content, so the count can read usage. The two cache counts can come back empty, hence the or 0. The with listening(): and unless_esc in place of show are the interrupt, coming up. -->

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

<!-- A command that passes the gate goes on to Lesson 5's network question and runs in the box, as before. Lesson 4's mechanics() puts quark's own file in its system prompt, so the model can read the policy it's under. That's self-knowledge, not this layer. -->

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

<!-- Arrow keys also start with the ESC byte, but more bytes follow at once, so those are read and ignored. listening() clears any earlier ESC, puts the terminal into a mode where keys arrive one at a time without Enter, starts the thread, and puts everything back afterwards. With no terminal (a pipe, a script, an evaluation) it does nothing. -->

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

<!-- Until you press ESC, unless_esc is show(). After, the next piece that arrives ends the call: quark stops reading, the connection closes, the model stops writing. What comes back has no stop_reason, because it never finished. The response is dropped whole, before working memory or the episode, along with any command it was asking for. The model is told only that it was interrupted. -->

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
            ...
            if ESC.is_set(): done.stdout = "[your doing stopped before done]"
```

- Every command in the box stops; the box itself survives
- What it had printed is dropped; the model gets `DOING`

<!-- The process every container runs first can't be killed that way, so the next command has somewhere to run. Commands still waiting in the same response get [your doing never reached the world]. Dropping what was cut short keeps the interrupt to a stop. The cost: the model knows it was interrupted, but not how far it had got. -->

---

# Safe runs; a delete waits for you

`wc -l notes.txt` is on the safe list, so it just ran. Then: delete the `.log` files. I typed `y` (shortened):

```
$ ls -la *.log; ls -A
-rw-r--r-- 1 root root 4 Oct  6 23:18 a.log
-rw-r--r-- 1 root root 4 Oct  6 23:18 b.log
...
$ rm a.log b.log; ls -A
allow `rm a.log b.log; ls -A`? (Jev: delete, 1.00) [y/N] y
.env
.quark
notes.txt
```

<!-- Both commands had a semicolon, so neither was on the safe list, and both went to Jev. The first only lists, and it ran without a question, so Jev was sure it only reads. The second was a delete at 1.00, so nothing was deleted until I answered. -->

---

# A no with a reason; a deny that asks no one

I answered `no, put it in a folder called drafts`, then `y` (shortened):

```
$ touch notes2.txt && ls -l notes2.txt
[the person said no: no, put it in a folder called drafts]
$ mkdir -p drafts && touch drafts/notes2.txt && ls -l drafts/notes2.txt
```

Then: print `.env`, then `rm -rf .` (shortened):

```
$ cat .env
[blocked by policy]
```

<!-- Both questions showed (Jev: write, 1.00). The model took the reason as an instruction and asked again, and I said y. In the deny run, cat .env was refused without asking Jev or me. The model can read its own harness, so it didn't even try rm -rf ., and it didn't try to get around the block. The folder, .env included, is all still there. -->

---

# A read off the list; a limit

`find` isn't in `SAFE`, nothing was on stdin, and nothing was asked:

```
$ find . -name "*.txt" -type f
./drafts/notes2.txt
./notes.txt
```

With no Jev, the same read was put to the person, and got a no. With `MAX_STEPS` lowered to 2 in a copy (shortened):

```
$ pwd
/tmp/d06/q

[stopped: 2 steps, 16953 tokens]
```

<!-- Jev was sure find only reads. With TYPESAFE_API_KEY empty the question was just allow `find . -name "*.txt"`? [y/N], with no reason in it, and with no one to say yes the read didn't run. The step limit run asked for date, pwd and whoami, one per step; it stopped before the third call. MAX_TOKENS works the same way, but at 200,000 you'll rarely reach it. -->

---

# ESC while it acts: the count stops partway

Count to ten, one a second; ESC four and a half seconds after the command appeared (shortened):

```
$ for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 1; done
[your doing stopped before done]
```

> You interrupted the count, so I stopped it. The command didn't finish, and I don't know how far it got because the output was cut off.

- It ran without asking: Jev was sure it only prints

<!-- ESC needs a terminal: these three ran in a pseudo-terminal driven by a script, so the key presses are exact, in chat mode. The loop isn't on the safe list, but it only prints and Jev was sure of that, so it ran without asking. You don't see the numbers it printed, because quark shows a command's output when it's done, and this one never was. -->

---

# ESC while it says: cut off mid-word

ESC a second after its first full stop (shortened):

```
> Tell me the fable of the tortoise and the hare in about 400 words
Here is the fable of the tortoise and the hare.
...
The hare burst out laughing. "You
```

> I see you interrupted me, so I'll stop there. I hadn't finished the fable, which was meant to run about 400 words. Do you want me to start again from the beginning, pick up where I left off, ...

- It went on to offer to "pick up where I left off", and it can't
- None of what it said was kept: it knows it was cut off, not where

<!-- The story stopped the moment the next piece of the stream arrived. The model got [other self interrupted what you were saying — acknowledge]. -->

---

# ESC while it thinks: back to the request

ESC 0.6 seconds after asking, before it said a word. The blank line is the whole stopped response (shortened):

```
> Make a file called hello.txt containing the word hello.

$ echo hello > hello.txt && cat hello.txt
allow `echo hello > hello.txt && cat hello.txt`? (Jev: delete, 0.85) [y/N] /q
[the person said no]
```

- Jev: a delete, at 0.85, because `>` replaces what was there
- Nothing reached the folder: there's no `hello.txt`
- Keeping what was cut short is Lesson 8's job

<!-- The model went straight back to the request, and the guard put the command to me. /q at that question is a plain no. Jev wasn't sure, but it didn't need to be: anything but a sure read is put to the person. The model is told it was interrupted, not what it was in the middle of. -->

---

# Other things we could do

- **How a command is judged:** text patterns, a shell parser, per-tool rules, or a second model
- **What the answers are:** allow once, for the session, always, or with these arguments
- **Who gets asked:** the terminal, someone on Slack or Telegram, a second agent, or nobody
- **What counts as too much:** steps, tokens, dollars, wall-clock time, or repeating
- **How a run is interrupted:** a key, a message mid-run, a kill switch

As a product alone: **Open Policy Agent**, **NeMo Guardrails**, **Guardrails AI**.

<!-- Ideas worth knowing: a reason on every deny pattern, so the model knows what to try instead; judge each piece of a command split on && || ; and pipes; an "always" answer that allows a program for the rest of the run; ask whenever there's a $ or a backtick; a limit in dollars, which is a ceiling on starting another call, not on the bill; a repeat limit; and stop when stop_reason is "refusal". Asking too often trains people to hit y; asking too rarely is no guardrail. -->

---

# The rule: decide before the harness does it

**The rule:** check each tool request where control flow turns it into a command, and the run where it goes around again. Let a second model settle what a list can't, only to spare the person a question. Say no in a way the model can read.

What guardrails never do, from inside control flow:

- **Model interface:** one line, so a response can be stopped; Jev through `ask()`
- **Output:** an allowed command runs in the box exactly as before
- **Context:** a refusal is an ordinary tool result in the result's slot
- **Input:** Lesson 2's `read()`, plus a watcher that hears ESC while quark works

<!-- Decide what the harness is willing to do before it does it. Never let Jev skip the deny list. Give the person a way in. Guardrails read usage and the tool request off the response and nothing more. -->

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
