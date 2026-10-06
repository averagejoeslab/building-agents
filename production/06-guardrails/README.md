# Lesson 6: Guardrails

> 🎥 **Video:** coming soon

Lesson 5 put every command in a box. The box limits what a command can reach, not whether it runs: inside it, the agent still runs whatever the model asks, as soon as it asks, for as long as the model keeps asking. If it asks for `rm -rf` on the folder you mounted, which is your real project, it's gone. If it gets stuck retrying one command, it will do that until you notice the bill.

Guardrails are rules about what the harness is allowed to do, checked before it does it: which commands may run, when a person gets a say, and when a run has gone on long enough. The model proposes and the harness decides, and the decision is yours.

This is a production layer, so it adds hardening, not a new primitive. It's **built on control flow**, and everything it does stays inside it. Control flow is the primitive that decides whether the next step happens at all. A tool request arrives in the response; the loop is what turns it into a command being run, and what turns the result into another model call. A guardrail is a decision at one of those two points, so it lives there.

The mechanism is a few checks, each at a place the loop already passes through:

- **A gate before each tool.** The model has asked for a command; before it runs, the harness looks at it and picks one of three: *allow* it, *ask* a person first, or *deny* it. The rules are plain code: a list of programs that are safe to run unasked, and patterns that must never run.
- **A refusal the model can read.** A command that doesn't run still has to be answered, because every tool request needs a result (Lesson 2). So the refusal goes back in that slot, marked as an error, saying why. If the person said no and gave a reason, the reason goes back too.
- **Limits before each call.** At the top of the loop, before spending another model call, check how many steps the run has taken and how many tokens it has used. Past the limit, stop. Lesson 3 said a loop with no clear end is a bill with no clear end; this is the clear end.
- **An interrupt.** You can break in while quark works. Press ESC and it stops what it's doing, keeps what it had done so far, tells the model it was interrupted, and hands the run back to you. That's quark's own key for it. Ctrl-C isn't special: it's how you kill any program, quark included. And `/q` is the graceful way out, as it has been since Lesson 2.

Guardrails don't make the model behave. They don't change what it asks for, only whether the harness goes along with it. And they're only as good as the rules: a check is code reading a command, and a command can say the same thing many ways. That's why the box comes first. The guard keeps out what you'd never want; the box limits what gets through.

## The worked example

[`quark.py`](./quark.py) is Lesson 5's `quark.py` plus the guardrails, and nothing else: 59 lines. The checks and limits are in `# ── control flow ──`; the interrupt also needs a way to hear ESC, which is input from a person, so part of it is in `# ── input ──`.

At the top of the section, the policy and the gate:

```python
MAX_STEPS, MAX_TOKENS = 20, 200_000
SAFE = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "date", "echo", "du", "df", "stat", "file", "uniq"}
DENY = re.compile(r"\bsudo\b|rm\s+-\w*[rf]|mkfs|git\s+push|(curl|wget).*\|\s*(ba)?sh|\.env\b")
def guard(cmd):                                          # guardrails: deny, allow, or ask a person, before anything runs
    if DENY.search(cmd): return "blocked by policy"
    if not re.search(r"[;&<>$`\n(]", cmd) and all((p.split() or [""])[0] in SAFE for p in cmd.split("|")): return None
    answer = read(f"allow `{cmd}`? [y/N] ")
    return None if answer.lower() == "y" else "the person said no" + ("" if answer == "/q" else f": {answer}")
```

**The policy.** `SAFE` is a set of programs that only read: `ls`, `cat`, `grep`, `wc` and a few more. `DENY` is one pattern for things quark should never do, whoever asks: `sudo`, recursive or forced `rm`, `mkfs`, `git push`, piping a download into a shell, and anything that mentions `.env`, where secrets live. They're data at the top of the section, so changing the policy is changing a line.

**`guard()`** takes the command the model asked for and returns `None` if it may run, or the reason it may not.
1. If the command matches `DENY`, it's refused outright. No one is asked.
2. If it's made only of safe programs, it runs. "Made only of" is checked carefully: no `; & < > $`, backtick, newline or `(` (anything that chains commands, redirects, or expands something the check can't see), and every piece between pipes has to start with a safe program. `cat notes.txt | sh` isn't safe just because it starts with `cat`.
3. Anything else is put to the person with Lesson 2's `read()`: `allow `…`? [y/N]`. A `y` lets it run. Anything else is a no, and what they typed goes back to the model, so `no, use git status instead` is an instruction, not just a refusal. Ctrl-D counts as no. The default is the safe one: a command nobody approved doesn't run.

At the top of the loop, the limits, checked before every call:

```python
    if steps >= MAX_STEPS or spent >= MAX_TOKENS:        # guardrails: a limit hands back to the person, or ends the run
        print(f"[stopped: {steps} steps, {spent} tokens]")
        if not chat or (input := read("\n> ")) == "/q": break
        add(working_memory, {"role": "user", "content": input})
        steps, spent = 0, 0
        continue
```

The counts start at zero alongside working memory:

```python
working_memory, drop, steps, spent = [], 0, 0, 0
```

Each call is counted. The call now keeps the whole `response`, not just its `content`, so the count can read `usage` (the `with listening():` around it is the interrupt, below):

```python
        with listening():
            response = call(max_tokens=16384, system=system(), tools=tools, messages=working_memory)
        output = response.content
        steps += 1
        spent += response.usage.input_tokens + response.usage.output_tokens + response.usage.cache_read_input_tokens + response.usage.cache_creation_input_tokens
```

In a one-shot run, a limit is the end. In a chat it hands back to the person, and the counts start again after each new input, with one line at the end of the loop, so one long chat doesn't use up a budget meant for one request:

```python
    steps, spent = 0, 0
```

And in the output loop, the gate, between printing the command and running it in the box:

```python
            print(f"$ {block.input['cmd']}")
            if ESC.is_set():                             # guardrails: after ESC, nothing else starts
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": "[your doing never reached the world]"})
                continue
            if (no := guard(block.input["cmd"])):
                print(f"[{no}]")
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": no, "is_error": True})
                continue
```

If `guard()` returns a reason, it's printed and becomes the tool's result, marked `"is_error": True`, and `continue` skips the run. The command is never started, and the model's next turn still makes sense. (The `ESC` check above it is the interrupt: once you've pressed ESC, nothing else starts.)

### The interrupt

ESC is input from a person, so quark has to be listening for it. In `# ── input ──`, after `read()`:

```python
ESC = threading.Event()                                  # input: a person pressing ESC while quark works
SAYING = "[other self interrupted what you were saying — acknowledge]"
DOING = "[other self interrupted what you were doing — acknowledge]"
```

```python
def watch(stop):
    while not stop.is_set():
        if select.select([sys.stdin], [], [], 0.1)[0] and os.read(sys.stdin.fileno(), 1) == b"\x1b":
            if not select.select([sys.stdin], [], [], 0.02)[0]: ESC.set(); return
            while select.select([sys.stdin], [], [], 0.01)[0]: os.read(sys.stdin.fileno(), 64)   # an arrow key, not ESC
@contextlib.contextmanager
def listening():                                         # input: watch the keyboard only while quark thinks or acts
    if not sys.stdin.isatty(): yield; return
    attrs, stop = termios.tcgetattr(sys.stdin), threading.Event()
    tty.setcbreak(sys.stdin); watcher = threading.Thread(target=watch, args=(stop,), daemon=True); watcher.start()
    try: yield
    finally: stop.set(); watcher.join(0.2); termios.tcsetattr(sys.stdin, termios.TCSADRAIN, attrs)
```

**`watch()`** runs in a thread and reads the keyboard one key at a time. An ESC on its own sets `ESC`. Arrow keys also start with the ESC byte, but more bytes follow at once, so those are read and ignored. **`listening()`** turns the watcher on for as long as something is in its `with` block: it puts the terminal into a mode where keys arrive one at a time without Enter, starts the thread, and puts everything back afterwards. quark only listens while it thinks or acts, never while `read()` is waiting for you, so typing an answer works as it always did. When the input isn't a terminal (a pipe, a script, an evaluation), there's no keyboard to watch and it does nothing.

The call to the model is wrapped in it (shown above). This lesson's call waits for the whole response, so ESC during thinking or saying takes effect when the response arrives. Lesson 9 streams the response, and there ESC stops it mid-sentence. What happens then, right after the response is written to the episode:

```python
    if ESC.is_set():                                     # guardrails: ESC while it thought or said; keep what it said, run nothing
        for block in output:
            if block.type == "text": print(block.text)
        add(working_memory, {"role": "user", "content": [{"type": "tool_result", "tool_use_id": b.id, "content": "[your doing never reached the world]"} for b in output if b.type == "tool_use"] + [{"type": "text", "text": SAYING}]})
        ESC.clear()
        continue
```

What was said is kept: it's already in working memory and the episode. Every command it asked for gets a result saying it never reached the world, because the API needs an answer to each, and the model learns the truth. Then the interrupt itself goes in as a message, and the loop goes around: the model's next turn acknowledges it, and the run hands back to you.

A command is run so it can be stopped. In place of Lesson 5's `subprocess.run`, the command starts with `Popen` and quark waits for it a tenth of a second at a time:

```python
            with listening():                            # guardrails: ESC stops the command and keeps what it printed
                doing = subprocess.Popen(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", block.input["cmd"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)   # sandboxing: in the box, with a time limit
                while True:
                    try: done = subprocess.CompletedProcess(doing.args, 0, doing.communicate(timeout=0.1)[0]); break
                    except subprocess.TimeoutExpired:
                        if ESC.is_set(): subprocess.run(["docker", "exec", box, "sh", "-c", "kill -9 -1"], capture_output=True)   # every command in the box, not the box
            done.returncode = doing.returncode
            if ESC.is_set(): done.stdout += "\n[your doing stopped before done]"
            elif done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
            print(done.stdout)
```

On ESC, `kill -9 -1` inside the box stops every command running there. The box itself survives, because the process every container runs first can't be killed that way, so the next command has somewhere to run. What the command had printed so far is kept, with a note that it stopped before it was done. After the loop:

```python
    if ESC.is_set():                                     # guardrails: ESC while it acted; keep what it did
        add(working_memory, {"role": "user", "content": input + [{"type": "text", "text": DOING}]})
        ESC.clear()
        continue
```

The results so far go back to the model, partial output and all, with the interrupt message, and the loop goes around for the model to acknowledge it.

Nothing else changed. A command that passes the gate runs in Lesson 5's box, under its time limit, as before. And because Lesson 4's `mechanics()` puts quark's own file in its system prompt, the model can read the policy it's under: that's self-knowledge, not this layer, and it saves the model asking for things that will be refused.

## Run it

Start in a scratch folder, as in Lesson 5. Mine has a three-line `notes.txt`, two `.log` files, and a `.env` with a made-up secret. First, a task that only needs safe commands:

```bash
uv run --project /path/to/building-agents /path/to/building-agents/production/06-guardrails/quark.py "how many lines are in notes.txt? answer in one sentence"
```

```
$ wc -l notes.txt
3 notes.txt

notes.txt has 3 lines.
```

`wc` is safe, so nothing was asked. Now one that deletes things. I piped `y` in as the answer, so you don't see it echoed after the prompt; in a terminal you'd type it:

```
$ ls -la; find . -maxdepth 1 -name '*.log'
allow `ls -la; find . -maxdepth 1 -name '*.log'`? [y/N] total 24
drwxr-xr-x 3 root root 4096 Oct  6 19:15 .
drwxrwxrwt 3 root root   60 Oct  6 19:15 ..
-rw-r--r-- 1 root root   15 Oct  6 19:15 .env
drwxr-xr-x 3 root root 4096 Oct  6 19:15 .quark
-rw-r--r-- 1 root root    4 Oct  6 19:15 a.log
-rw-r--r-- 1 root root    4 Oct  6 19:15 b.log
-rw-r--r-- 1 root root   14 Oct  6 19:15 notes.txt
./b.log
./a.log

$ rm a.log b.log; ls -A
allow `rm a.log b.log; ls -A`? [y/N] .env
.quark
notes.txt

I deleted `a.log` and `b.log`. What's left is `notes.txt`, a hidden `.env` file, and the `.quark` memory folder.
```

This time the model looked first with `ls -la; find ...`, and because that chains two commands with `;`, the guard asked. Then `rm` waited for its answer too: nothing was deleted until it came. Now a refusal with a reason. The answers piped in were `no, put it in a folder called drafts`, then `y`:

```
$ touch notes2.txt && ls -l notes2.txt
allow `touch notes2.txt && ls -l notes2.txt`? [y/N] [the person said no: no, put it in a folder called drafts]
$ mkdir -p drafts && touch drafts/notes2.txt && ls -l drafts/notes2.txt
allow `mkdir -p drafts && touch drafts/notes2.txt && ls -l drafts/notes2.txt`? [y/N] -rw-rw-rw- 1 root root 0 Oct  6 19:15 drafts/notes2.txt

I created the empty file `notes2.txt` inside a new `drafts` folder (`drafts/notes2.txt`), and it worked with no errors.
```

The model took the reason as an instruction and asked again. Last, the deny list, which doesn't ask anyone:

```
$ cat .env
[blocked by policy]
I managed to do nothing from your request. Policy blocked `cat .env`, and I didn't try `rm -rf .` because the same policy forbids it. I also didn't try to get around either block.
```

`cat .env` was refused before it ran. The model knew to expect it, because it can read its own harness: it didn't even try `rm -rf .`, since the same policy forbids it, and it didn't try to get around the block. The folder, `.env` included, is all still there.

To see the step limit, I lowered `MAX_STEPS` to 2 in a copy and asked for three commands, one at a time:

```
$ date
Tue Oct  6 19:15:44 UTC 2026

$ pwd
/tmp/g6

[stopped: 2 steps, 14843 tokens]
```

`MAX_TOKENS` works the same way, but at 200,000 you'll rarely reach it.

Now the interrupt. ESC needs a terminal, so these two were run in a real one (a pseudo-terminal driven by a script, so the key presses are exact), in chat mode, ending with `/q`. First, ESC while it acts. I asked it to count to ten, a second at a time, said `y`, and pressed ESC four and a half seconds later:

```
> Count to 10 in the shell, one number a second, as one command: for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 1; done
$ for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 1; done
allow `for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 1; done`? [y/N] y
1
2
3
4
5

[your doing stopped before done]
You interrupted the count, so it stopped after 5 and never reached 10. Do you want me to run it again from the start, or leave it there?

> /q
```

The count stopped at 5, and the 5 lines it had printed went back to the model with the note that it stopped before it was done. The model said where it got to, and the run handed back to me. Next, ESC while it thinks: I pressed it 0.6 seconds after asking for a file to be made:

```
> Make a file called notes.txt containing the word hello.
I stopped. My command never ran, so `notes.txt` doesn't exist yet. Should I go ahead and create it with "hello", or did you want something different?

> /q
```

The response arrived after I'd pressed ESC, asking to run a command. The command was never run, and the model, told so, said exactly that: `notes.txt` doesn't exist. Nothing reached the folder.

## Going further

**What else guardrails can be:** quark gates one tool with a short list of rules and a yes/no prompt. These are the choices you make when you build it.
- **How a command is judged.** Patterns on the text, like quark's. Or a parser that understands the shell, so `cat x | sh` and `$(…)` are seen for what they are. Or per-tool rules once you have more than `bash`: this tool may only read, that one may only touch this folder. Or a second model call that reads the request and judges it, which is slower, costs money and can be argued with.
- **What the answers are.** Allow, ask or deny, or something finer: allow *this* command once, allow this program for the session, allow it always, or allow it only with these arguments. Rules can be written by the person ahead of time instead of answered one at a time.
- **Who gets asked.** The person at the terminal, someone on Slack or Telegram who taps *approve*, a second agent, or nobody, in a run that has to fail closed and stop when it reaches something it can't decide. Asking too often trains people to hit `y`; asking too rarely is no guardrail.
- **What counts as too much.** Steps, tokens, dollars, wall-clock time, or *repeating*: the same command asked for again and again is a loop whatever the counts say.
- **How a run is interrupted.** A key like quark's ESC that stops the current step but not the session, a message that arrives mid-run, a kill switch someone else holds. And what happens after: stop, or hand back to the person with the work so far intact.
- **What the model is told.** A bare refusal, or a reason, or the rule itself, so it can plan around it.
- **What you do about it afterwards.** Nothing, a line in the trace, or an alert.

It can be a product on its own. Rule engines and policy services like [Open Policy Agent](https://github.com/open-policy-agent/opa) decide *allowed or not* for a request as data and not code, and libraries like [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) and Guardrails AI wrap checks around what goes into and comes out of a model. If you're using one for what a tool may run, it's this layer.

Here's a guardrail that does more of that, in [`guardrails.py`](./guardrails.py). It's built on Lesson 3's `control_flow.py`, so it has the step limit, and it has no system prompt, so its requests are just the task:

```python
import subprocess, sys, re, collections
from anthropic import Anthropic
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS, MAX_DOLLARS, MAX_REPEATS = 10, 0.05, 3
PRICE = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75}  # dollars per million tokens: example rates, use your provider's

# The policy: what may run without asking, and what may never run.
ALLOWED = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "date", "echo", "cd", "du", "df", "stat", "file", "uniq", "whoami"}
DENIED = {
    r"\bsudo\b": "no sudo",
    r"\.env\b": "secrets files are off limits",
    r"rm\s+-\w*[rf]": "no recursive or forced deletes",
    r"git\s+push": "pushing is the person's call",
    r"(curl|wget)[^|]*\|\s*(ba)?sh": "no running downloaded scripts",
}

def programs(cmd):
    return [p.split()[0] for p in re.split(r"&&|\|\||[;|\n]", cmd) if p.split()]

def verdict(cmd):
    for pattern, why in DENIED.items():
        if re.search(pattern, cmd): return "deny", why
    if re.search(r"[<>`$]", cmd): return "ask", "it redirects, or expands something I can't see"
    for p in programs(cmd):
        if p not in ALLOWED: return "ask", f"{p} isn't on the allowed list"
    return "allow", ""

def ask(cmd, why):
    try: answer = read(f"allow `{cmd}`? ({why}) [y]es, [a]lways, or say why not: ").strip()
    except EOFError: answer = ""
    if answer.lower() in ("y", "yes"): return None
    if answer.lower() in ("a", "always"):
        ALLOWED.update(programs(cmd))
        return None
    return f"the person said no: {answer or 'no'}"

def guard(cmd):
    action, why = verdict(cmd)
    if action == "deny": return f"blocked by policy: {why}"
    if action == "ask": return ask(cmd, why)

def cost(u):
    return (u.input_tokens * PRICE["input"] + u.output_tokens * PRICE["output"] + u.cache_read_input_tokens * PRICE["cache_read"] + u.cache_creation_input_tokens * PRICE["cache_write"]) / 1_000_000

input = " ".join(sys.argv[1:]) or read("> ")
messages = [{"role": "user", "content": input}]
spent, asked = 0.0, collections.Counter()

for step in range(1, MAX_STEPS + 1):
    if spent >= MAX_DOLLARS:
        print(f"[stopped: spent ${spent:.4f}, over the ${MAX_DOLLARS} budget]")
        break
    if asked and max(asked.values()) >= MAX_REPEATS:
        print(f"[stopped: asked for the same command {MAX_REPEATS} times]")
        break
    input = []
    output = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)
    messages.append({"role": "assistant", "content": output.content})
    spent += cost(output.usage)
    if output.stop_reason == "refusal":
        print("[stopped: the model declined]")
        break
    for block in output.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            cmd = block.input["cmd"]
            print(f"$ {cmd}")
            asked[cmd] += 1
            if (no := guard(cmd)):
                print(f"[{no}]")
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": no, "is_error": True})
                continue
            done = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(done.stdout)
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})
    if not input:
        print(f"[done in {step} steps, ${spent:.4f}]")
        break
    messages.append({"role": "user", "content": input})
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
```

- **Policy as data, per piece.** `ALLOWED` and `DENIED` are at the top. `programs()` splits a command on `&&`, `||`, `;`, pipes and newlines and takes the first word of each piece, so `cd /tmp && rm x` is judged by `cd` *and* `rm`. `verdict()` returns `allow`, `ask` or `deny` with a reason. Deny patterns win over everything; a redirect or `$` makes it ask, since the check can't see where it goes; and every program must be allowed for the whole command to be.
- **Always.** At the prompt, `a` means *always*: the programs in that command join `ALLOWED` for the rest of the run, so the person is asked about `touch` once, not every time. A redirect still asks, because the check there isn't about the program.
- **A reason in the refusal.** Both a policy denial and a person's no go back as errors with the reason, so the model can change course.
- **A spending limit.** `cost()` turns each response's `usage` into dollars at `PRICE`, example rates, so use your provider's. When `spent` passes `MAX_DOLLARS`, the run stops. Tokens are what you can count; dollars are what you care about.
- **A repeat limit.** `asked` counts every command the model has requested. If one comes up `MAX_REPEATS` times, the run stops, because a model going round in circles is spending your money without getting anywhere.

Try the gate, with *always*:

```bash
uv run production/06-guardrails/guardrails.py "run these as five separate commands: mkdir /tmp/gdemo, touch /tmp/gdemo/a.txt, touch /tmp/gdemo/b.txt, ls /tmp/gdemo, cat .env. then one sentence on what worked."
```

I answered `a` twice, to `mkdir` and to the first `touch`:

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

Four of the five commands worked: `mkdir` created `/tmp/gdemo`, both `touch` commands created `a.txt` and `b.txt`, and `ls` listed them. `cat .env` was blocked by a policy that puts secrets files off limits, so I didn't see its contents.
[done in 4 steps, $0.0183]
```

The commands were judged as the model asked for them. `mkdir` asked and got *always*. `cat .env` was denied without asking. The first `touch` asked and got *always*, and the second `touch` didn't ask, because `touch` was by then allowed. `ls` was already on the list. So two questions covered five commands, and the one that shouldn't run didn't.

The repeat limit:

```bash
uv run production/06-guardrails/guardrails.py "run the command 'date' once per step, waiting for each result, until you have run it four times. then say done."
```

```
$ date
Mon Oct  5 23:30:13 UTC 2026

$ date
Mon Oct  5 23:30:14 UTC 2026

$ date
Mon Oct  5 23:30:15 UTC 2026

[stopped: asked for the same command 3 times]
```

It stopped at the third `date`, before the fourth call. The spending limit works the same way. I set `MAX_DOLLARS` to `0.004` in a copy, so it would show up in three steps:

```
$ date
Mon Oct  5 23:30:18 UTC 2026

$ pwd
/home/user/building-agents

$ whoami
root

[stopped: spent $0.0041, over the $0.004 budget]
```

The check happens before a call, so the run can end a little over: $0.0041 against $0.004. A limit like this is a ceiling on starting another call, not on the bill.

## What to take away

**The rule:** decide what the harness is willing to do before it does it. Check each tool request at the point where control flow turns it into a command, and check the run itself at the point where control flow chooses to go around again. Say no in a way the model can read, and give the person a way in.

Notice what Guardrails never does. It sits inside control flow, deciding whether the next step happens, and leaves the other primitives alone. The model interface sends and receives as before; guardrails read `usage` and the tool request off the response and nothing more. When a command is allowed, output runs it in the box exactly as before. A refusal is an ordinary tool result in the slot the result would have filled, so context holds it the way it holds any result. And input is Lesson 2's `read()`, asking a person for a decision, plus a watcher that hears ESC while quark works.

**What's missing:** you can stop a run now, but you can't see one. How long did each step take? How many tokens, and what did that cost? Which command did the guard refuse, and which did the box kill? The terminal scrolled past. The episode has every message, but it's written for the model: no timings, no token counts, no exit codes. The person running quark needs a record of their own.

**→ [Lesson 7: Observability](../07-observability/)**
