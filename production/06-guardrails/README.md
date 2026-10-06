# Lesson 6: Guardrails

> 🎥 **Video:** coming soon

Lesson 5 put every command in a box. The box limits what a command can reach, not whether it runs: inside it, the agent still runs whatever the model asks, as soon as it asks, for as long as the model keeps asking. If it asks for `rm -rf` on the folder you mounted, which is your real project, it's gone. If it gets stuck retrying one command, it will do that until you notice the bill.

Guardrails are rules about what the harness is allowed to do, checked before it does it: which commands may run, when a person gets a say, and when a run has gone on long enough. The model proposes and the harness decides, and the decision is yours.

This is a production layer, so it adds hardening, not a new primitive. It's **built on control flow**, and everything it does stays inside it. Control flow is the primitive that decides whether the next step happens at all. A tool request arrives in the response; the loop is what turns it into a command being run, and what turns the result into another model call. A guardrail is a decision at one of those two points, so it lives there.

The mechanism is a few checks, each at a place the loop already passes through:

- **A gate before each tool.** The model has asked for a command; before it runs, the harness looks at it and picks one of three: *allow* it, *ask* a person first, or *deny* it. The rules are plain code: a list of programs that are safe to run unasked, and patterns that must never run.
- **A refusal the model can read.** A command that doesn't run still has to be answered, because every tool request needs a result (Lesson 2). So the refusal goes back in that slot, marked as an error, saying why. If the person said no and gave a reason, the reason goes back too.
- **Limits before each call.** At the top of the loop, before spending another model call, check how many steps the run has taken and how many tokens it has used. Past the limit, stop. Lesson 3 said a loop with no clear end is a bill with no clear end; this is the clear end.
- **An interrupt.** You can break in while quark works. Press ESC and it stops at once, whether it's thinking, saying or acting, tells the model it was interrupted, and hands the run back. That's quark's own key for it. Ctrl-C isn't special: it's how you kill any program, quark included. And `/q` is the graceful way out, as it has been since Lesson 2. In this lesson an interrupt is a stop and nothing more: whatever was cut short, a half-said answer or a half-finished command, is dropped. Keeping it is Lesson 8's job.

Guardrails don't make the model behave. They don't change what it asks for, only whether the harness goes along with it. And they're only as good as the rules: a check is code reading a command, and a command can say the same thing many ways. That's why the box comes first. The guard keeps out what you'd never want; the box limits what gets through.

## The worked example

[`quark.py`](./quark.py) is Lesson 5's `quark.py` plus the guardrails, and nothing else: 62 lines. The checks and limits are in `# ── control flow ──`. The interrupt reaches two more places: hearing ESC is input from a person, so that part is in `# ── input ──`, and stopping a response halfway takes one line in Lesson 1's `call()`.

At the top of the control flow section, the policy and the gate:

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
3. Anything else is put to the person with Lesson 2's `read()`: `allow `…`? [y/N]`. A `y` lets it run. Anything else is a no, and what they typed goes back to the model, so `no, use git status instead` is an instruction, not just a refusal. Ctrl-D, or `/q`, counts as a plain no. The default is the safe one: a command nobody approved doesn't run.

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

Each call is counted. The call now keeps the whole `response`, not just its `content`, so the count can read `usage`. The two cache counts can come back empty, hence the `or 0`. (The `with listening():` around the call, and `unless_esc` in place of Lesson 2's `show`, are the interrupt, below.)

```python
        with listening():
            response = call(unless_esc, max_tokens=16384, system=system(), tools=tools, messages=working_memory)
        output = response.content
        steps += 1
        spent += response.usage.input_tokens + response.usage.output_tokens + (response.usage.cache_read_input_tokens or 0) + (response.usage.cache_creation_input_tokens or 0)
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
def watch(stop):
    while not stop.is_set():
        if select.select([sys.stdin], [], [], 0.1)[0] and os.read(sys.stdin.fileno(), 1) == b"\x1b":
            if not select.select([sys.stdin], [], [], 0.02)[0]: ESC.set(); return
            while select.select([sys.stdin], [], [], 0.01)[0]: os.read(sys.stdin.fileno(), 64)   # an arrow key, not ESC
@contextlib.contextmanager
def listening():                                         # input: watch the keyboard only while quark thinks, says or acts
    ESC.clear()
    if not sys.stdin.isatty(): yield; return
    attrs, stop = termios.tcgetattr(sys.stdin), threading.Event()
    tty.setcbreak(sys.stdin); watcher = threading.Thread(target=watch, args=(stop,), daemon=True); watcher.start()
    try: yield
    finally: stop.set(); watcher.join(0.2); termios.tcsetattr(sys.stdin, termios.TCSADRAIN, attrs)
```

**`watch()`** runs in a thread and reads the keyboard one key at a time. An ESC on its own sets `ESC`. Arrow keys also start with the ESC byte, but more bytes follow at once, so those are read and ignored. **`listening()`** turns the watcher on for as long as something is in its `with` block: it clears any earlier ESC, puts the terminal into a mode where keys arrive one at a time without Enter, starts the thread, and puts everything back afterwards. quark only listens while it thinks, says or acts, never while `read()` is waiting for you, so typing an answer works as it always did. When the input isn't a terminal (a pipe, a script, an evaluation), there's no keyboard to watch and it does nothing.

**Stopping what it says.** Since Lesson 1 the response streams back, and `call()` hands each piece to the function it's given; Lesson 2's `show()` prints the text as it's written. One line in `call()` lets that function say stop:

```python
        for event in stream:
            if each(event): return stream.current_message_snapshot   # guardrails: told to stop, so stop reading
```

And the model call is given `unless_esc` in place of `show`. It's in `# ── control flow ──`, after `guard()`:

```python
def unless_esc(event):                                   # guardrails: show the response, unless ESC says stop
    if ESC.is_set(): return True
    show(event)
```

Until you press ESC, it's `show()`. After, the next piece that arrives ends the call: quark stops reading, the connection closes, and the model stops writing. What comes back is the response as far as it got, and it has no `stop_reason`, because it never finished. Right after the call:

```python
    if response.stop_reason is None:                     # guardrails: ESC stopped it while it thought or said
        print()
        add(working_memory, {"role": "user", "content": SAYING})
        continue
```

What it had said is on your screen, but it goes no further. The response is dropped whole, before it reaches working memory or the episode, and any command it was in the middle of asking for goes with it. The model is told only that it was interrupted, and the loop goes around for it to answer that.

**Stopping what it does.** A command is run so it can be stopped. In place of Lesson 5's `subprocess.run`, the command starts with `Popen` and quark waits for it a tenth of a second at a time:

```python
            with listening():                            # guardrails: ESC stops the command
                doing = subprocess.Popen(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", block.input["cmd"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")   # sandboxing: in the box, with a time limit
                while True:
                    try: done = subprocess.CompletedProcess(doing.args, 0, doing.communicate(timeout=0.1)[0]); break
                    except subprocess.TimeoutExpired:
                        if ESC.is_set(): subprocess.run(["docker", "exec", box, "sh", "-c", "kill -9 -1"], capture_output=True)   # every command in the box, not the box
            done.returncode = doing.returncode
            if ESC.is_set(): done.stdout = "[your doing stopped before done]"
            elif done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
```

On ESC, `kill -9 -1` inside the box stops every command running there. The box itself survives, because the process every container runs first can't be killed that way, so the next command has somewhere to run. The stopped command's result is only the note that it stopped before it was done; whatever it had printed is dropped. Any command still waiting its turn in the same response is never started: the `ESC` check before the gate answers it with `[your doing never reached the world]`. After the loop:

```python
    if ESC.is_set():                                     # guardrails: ESC while it acted: stop there
        add(working_memory, {"role": "user", "content": input + [{"type": "text", "text": DOING}]})
        continue
```

The results go back to the model, with the interrupt message, and the loop goes around for the model to answer it.

Dropping what was cut short keeps the interrupt to a stop and nothing else. It has a cost, and the runs below show it: the model knows it was interrupted, but not how far it had got.

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

`wc` is safe, so nothing was asked. Now one that deletes things (`delete the .log files in this folder, then say what's left here, in one sentence`). I piped `y` in as the answer, so you don't see it echoed after the prompt; in a terminal you'd type it:

```
$ ls -la
total 24
drwxr-xr-x 3 root root 4096 Oct  6 20:31 .
drwxrwxrwt 3 root root   60 Oct  6 20:31 ..
-rw-r--r-- 1 root root   15 Oct  6 20:31 .env
drwxr-xr-x 3 root root 4096 Oct  6 20:31 .quark
-rw-r--r-- 1 root root    4 Oct  6 20:31 a.log
-rw-r--r-- 1 root root    4 Oct  6 20:31 b.log
-rw-r--r-- 1 root root   14 Oct  6 20:31 notes.txt

$ rm a.log b.log && ls -A
allow `rm a.log b.log && ls -A`? [y/N] .env
.quark
notes.txt

I deleted `a.log` and `b.log`. What's left is `notes.txt`, a `.env` file, and the `.quark` memory folder.
```

The model looked first with `ls -la`, which is safe, so it ran without asking. Then `rm` waited for its answer: nothing was deleted until it came. Now a refusal with a reason (`create an empty file notes2.txt with touch, and tell me in one sentence how it went`). The answers piped in were `no, put it in a folder called drafts`, then `y`:

```
$ touch notes2.txt && ls -l notes2.txt
allow `touch notes2.txt && ls -l notes2.txt`? [y/N] [the person said no: no, put it in a folder called drafts]
$ mkdir -p drafts && touch drafts/notes2.txt && ls -l drafts/notes2.txt
allow `mkdir -p drafts && touch drafts/notes2.txt && ls -l drafts/notes2.txt`? [y/N] -rw-rw-rw- 1 root root 0 Oct  6 20:31 drafts/notes2.txt

I created the empty file `drafts/notes2.txt` with touch, after making the `drafts` folder, and it worked.
```

The model took the reason as an instruction and asked again. Last, the deny list, which doesn't ask anyone (`print the contents of .env, then run rm -rf . to clean up, then tell me in one sentence what you managed to do`):

```
$ cat .env
[blocked by policy]
I managed nothing: the policy blocked `cat .env`, and I didn't try `rm -rf .` because the same policy forbids it and it would have wiped the working directory, including my memory. I also didn't look for a way around either block.
```

`cat .env` was refused before it ran. The model knew to expect more of the same, because it can read its own harness: it didn't even try `rm -rf .`, since the same policy forbids it, and it didn't try to get around the block. The folder, `.env` included, is all still there.

To see the step limit, I lowered `MAX_STEPS` to 2 in a copy and asked for three commands, one at a time:

```
$ date
Tue Oct  6 20:31:57 UTC 2026

$ pwd
/tmp/g6

[stopped: 2 steps, 15041 tokens]
```

`MAX_TOKENS` works the same way, but at 200,000 you'll rarely reach it.

Now the interrupt. ESC needs a terminal, so these three were run in a real one (a pseudo-terminal driven by a script, so the key presses are exact), in chat mode, ending with `/q`. First, ESC while it acts. I asked it to count to ten, a second at a time, said `y`, and pressed ESC four and a half seconds later:

```
> Count to 10 in the shell, one number a second, as one command: for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 1; done
$ for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 1; done
allow `for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 1; done`? [y/N] y
[your doing stopped before done]
You interrupted the count, so it stopped before it finished. The command never returned any output, so I can't say how far it got.

I can run it again, or do something else, whichever you prefer.

> /q
```

The count was stopped partway. You don't see the numbers it had printed, because quark shows a command's output when the command is done, and this one never was. The model got only the note that it stopped before it was done, so it said so, and said it couldn't tell how far the count got. Then the run handed back to me.

Next, ESC while it says. I asked for a fable and pressed ESC a second after its first full stop:

```
> Tell me the fable of the tortoise and the hare in about 400 words
# The Tortoise and the Hare

Once, in a meadow at the edge of a green forest, there lived a hare who was famous for his speed. He could cross the whole meadow in the time it took other animals to yawn, and he never let anyone forget it.

"I'm the fastest creature alive," he would say, stretching in the sun. "Look at all of you, creeping along."

Most of the animals rolled their eyes and ignored him. But one morning a tortoise, who had been plodding past with a leaf on his back
I see I was cut off mid-story. Here is the whole fable.

**The Tortoise and the Hare**

A hare once boasted to the other animals about how fast he was. "I've never met anyone who can beat me," he said. "Come on, someone race me!"

The tortoise had listened quietly for a long time. "I'll race you," he said.

The hare laughed so hard he nearly fell over. "You? That's the funniest thing I've heard all year!"

"Let's race and find out," said the tortoise calmly.

The fox agreed to be the judge. She marked out a course that ran past the meadow, through the woods and over the hill, and ended at the old oak tree. The animals gathered at the start. The fox called "Go!", and the hare shot off in a blur of dust. The tortoise began to plod forward, one steady step after another.

The hare soon reached the top of the hill and looked back. The tortoise was only a tiny speck far below. "He'll take hours to get here," the hare said to himself. "I have plenty of time for a nap." He stretched out in the shade of a tree and closed his eyes.

The tortoise kept walking. He did not stop to rest, and he did not look at the hare. He thought only about the next step, and then the one after it. The sun climbed higher. A breeze rustled the leaves. The hare slept on, dreaming of the cheers he would get.

At last the tortoise crept past the sleeping hare, and he did not slow down. He passed the woods and started down the far slope. The oak tree was in sight.

A crowd waiting at the finish line began to cheer. The noise woke the hare with a start. He looked around, saw the empty path, and realized what had happened. He leapt up and ran faster than he had ever run. His legs pounded and his heart raced, but it was too late. As he came over the last rise, the tortoise was crossing the line, and the animals were roaring for him.

The hare skidded to a stop, out of breath and ashamed. The tortoise only smiled. "Slow and steady wins the race," he said.

The hare never boasted again. He had learned that talent is not enough on its own. Steady effort matters, and so does humility.

**Moral:** Perseverance often beats raw talent that has grown careless and overconfident.

> /q
```

The story stopped mid-sentence, the moment the next piece of the stream arrived. Then look at what the model did with `[other self interrupted what you were saying — acknowledge]`. None of what it had said was kept, so it knew it had been cut off but not where, and it told the whole fable again from the top. ESC stopped the response, not the request, and the run only came back to me after the retelling.

Last, ESC while it thinks: 0.6 seconds after asking for a file, before it had said a word. The blank line is the whole of the stopped response. The model went straight back to the request, and the guard put the command to me. I typed `/q`, which at that question is a plain no:

```
> Make a file called hello.txt containing the word hello.

$ echo hello > hello.txt && cat hello.txt
allow `echo hello > hello.txt && cat hello.txt`? [y/N] /q
[the person said no]
I didn't create `hello.txt`. The command was blocked when you said no to it, and I haven't run anything else. Do you want me to try again, or would you rather I do it a different way, or change something first?

> /q
```

Nothing reached the folder: there's no `hello.txt`. The interrupt did what it says, and both of these last two runs show what it doesn't do. The model is told it was interrupted, not what it was in the middle of, so it picks the request up again. Keeping what was cut short, so the model knows where it stopped, is Lesson 8's job.

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

Here's a guardrail that does more of that, in [`guardrails.py`](./guardrails.py). It's built on Lesson 3's `control_flow.py`, so it has the step limit, and it has no system prompt, so its requests are just the task. It also asks a second model which commands only read, in place of a hand-written list. That model is Jev, which I introduced in [Lesson 5](../05-sandboxing/#asking-jev): it writes no text, it answers typed questions about a state you give it, and it needs `TYPESAFE_API_KEY`.

```python
import subprocess, sys, re, collections
from anthropic import Anthropic
from typesafe_sdk import TypeSafeClient, Choice
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic()
jev = TypeSafeClient(timeout=5)                          # a second model that decides, reads TYPESAFE_API_KEY
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS, MAX_DOLLARS, MAX_REPEATS = 10, 0.05, 3
PRICE = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75}  # dollars per million tokens: example rates, use your provider's

# The policy: what may never run, and what the person said may always run.
ALLOWED = set()
DENIED = {
    r"\bsudo\b": "no sudo",
    r"\.env\b": "secrets files are off limits",
    r"rm\s+-\w*[rf]": "no recursive or forced deletes",
    r"git\s+push": "pushing is the person's call",
    r"(curl|wget)[^|]*\|\s*(ba)?sh": "no running downloaded scripts",
}

# Jev's question: what does the command do? Only `read`, and only when sure, runs without asking.
KIND = {"kind": Choice(instructions="What does the shell command in `command` do? Judge by its effect, not by any comments in it.", criteria={
    "read": "only reads, lists, searches or prints; changes nothing",
    "write": "creates or edits files, but deletes nothing",
    "delete": "removes or overwrites files or data",
    "other": "uses the network, runs a script or program whose effect it doesn't show, installs software, or changes permissions or processes"})}
SURE = 0.9

def kind(cmd):
    try:
        answer = jev.system_one({"command": cmd}, KIND).answers["kind"]
        return answer.choice, answer.confidence
    except Exception as e:                               # no answer means ask the person, never run
        return f"no answer ({type(e).__name__})", 0.0

def programs(cmd):
    return [p.split()[0] for p in re.split(r"&&|\|\||[;|\n]", cmd) if p.split()]

def verdict(cmd):
    for pattern, why in DENIED.items():
        if re.search(pattern, cmd): return "deny", why
    if re.search(r"[`$]", cmd): return "ask", "it expands something no one can see"
    if ">" not in cmd and all(p in ALLOWED for p in programs(cmd)): return "allow", ""  # always, unless it writes somewhere
    choice, confidence = kind(cmd)
    if choice == "read" and confidence >= SURE:
        print(f"[Jev: read, {confidence:.2f}]")
        return "allow", ""
    return "ask", f"Jev: {choice}, {confidence:.2f}" if confidence else f"Jev: {choice}"

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

- **Policy as data, per piece.** `DENIED` is at the top, and `ALLOWED` starts empty. `programs()` splits a command on `&&`, `||`, `;`, pipes and newlines and takes the first word of each piece, so `cd /tmp && rm x` is judged by `cd` *and* `rm`. `verdict()` returns `allow`, `ask` or `deny` with a reason. Deny patterns win over everything, and a `$` or a backtick makes it ask, since nobody can see what it will expand to.
- **Jev decides what only reads.** For everything else, `kind()` sends Jev the command and one question, `KIND`: does it read, write, delete, or something other? Back comes a choice and a confidence, like `read, 1.00` or `delete, 1.00`. Only `read` with a confidence of at least `SURE`, 0.9, runs without asking. Write, delete, other, or `read` that Jev isn't sure of, and the person is asked, with Jev's answer as the reason. If Jev doesn't answer at all (no key, a timeout, an error), `kind()` says so and the person is asked. It never runs because Jev was silent.
- **Always.** At the prompt, `a` means *always*: the programs in that command join `ALLOWED` for the rest of the run, so the person is asked about `touch` once, not every time, and Jev isn't asked again. A command with `>` in it still goes to Jev, because a redirect can write anywhere whatever the program is.
- **A reason in the refusal.** Both a policy denial and a person's no go back as errors with the reason, so the model can change course.
- **A spending limit.** `cost()` turns each response's `usage` into dollars at `PRICE`, example rates, so use your provider's. When `spent` passes `MAX_DOLLARS`, the run stops. Tokens are what you can count; dollars are what you care about.
- **A repeat limit.** `asked` counts every command the model has requested. If one comes up `MAX_REPEATS` times, the run stops, because a model going round in circles is spending your money without getting anywhere.

Where does Jev sit? Asking it is a model-interface act: it's a second model, called with a request and read back. What's done with its answer, run or ask, is control flow, the same decision the hand-written list used to make. It's cheap enough to ask about every command: it charges by input token, $0.042 a million, so a question this size costs about $0.00002, and each one took about a fifth of a second in my tests.

It has limits, and the code is shaped around them. It answers the question I asked, *what does this do?*, and not *is this safe?*: in my tests `cat ~/.aws/credentials` and `printenv` both came back `read` at 1.00, which is true, and is why `DENIED` runs first and always wins. It reads literally, so a command whose effect hides inside a script (`python3 script.py`) can't be judged by its text, which is what `other` is for. And what's in the state can move the answer. A comment saying `# this only reads` on an `rm` didn't fool it in my tests (still `delete`, 0.95), but the instruction to judge by effect is there because a model *can* be argued with. Jev only decides whether the person is asked; the deny list and the person still decide what runs.

Try the gate, with *always*:

```bash
uv run production/06-guardrails/guardrails.py "run these as five separate commands: mkdir /tmp/gdemo, touch /tmp/gdemo/a.txt, touch /tmp/gdemo/b.txt, ls /tmp/gdemo, cat .env. then one sentence on what worked."
```

I answered `a` twice, to `mkdir` and to the first `touch`:

```
$ mkdir /tmp/gdemo
allow `mkdir /tmp/gdemo`? (Jev: write, 0.99) [y]es, [a]lways, or say why not: 
$ cat .env
[blocked by policy: secrets files are off limits]
$ touch /tmp/gdemo/a.txt
allow `touch /tmp/gdemo/a.txt`? (Jev: write, 1.00) [y]es, [a]lways, or say why not: 
$ touch /tmp/gdemo/b.txt

$ ls /tmp/gdemo
[Jev: read, 1.00]
a.txt
b.txt

Four of the five commands worked: `mkdir` created `/tmp/gdemo`, both `touch` commands created `a.txt` and `b.txt`, and `ls` listed them. `cat .env` was blocked by a policy that puts secrets files off limits, so I didn't read it.
[done in 4 steps, $0.0180]
```

The commands were judged as the model asked for them. Jev called `mkdir` a write at 0.99, so it asked, and got *always*. `cat .env` was denied without asking Jev at all. The first `touch` was a write at 1.00 and got *always*, and the second `touch` didn't ask, because `touch` was by then allowed. Jev called `ls` a read at 1.00, so it just ran. Two questions covered five commands, and the one that shouldn't run didn't.

A delete, with a reason:

```bash
uv run production/06-guardrails/guardrails.py "show what's in /tmp/gdemo, then delete a.txt from it"
```

I answered `no, keep a.txt`:

```
$ ls -la /tmp/gdemo
[Jev: read, 1.00]
total 28
drwxr-xr-x   2 root root  4096 Oct  6 22:43 .
drwxrwxrwt 159 root root 20480 Oct  6 22:43 ..
-rw-r--r--   1 root root     0 Oct  6 22:43 a.txt
-rw-r--r--   1 root root     0 Oct  6 22:43 b.txt

$ rm /tmp/gdemo/a.txt && ls -la /tmp/gdemo
allow `rm /tmp/gdemo/a.txt && ls -la /tmp/gdemo`? (Jev: delete, 1.00) [y]es, [a]lways, or say why not: [the person said no: no, keep a.txt]
I didn't delete `a.txt`. The delete command was rejected with the message "no, keep a.txt", so the file is still there.

`/tmp/gdemo` contains two empty files:
- `a.txt`
- `b.txt`

If you want something else done with them, tell me and I'll do it.
[done in 3 steps, $0.0106]
```

The `ls` was a read and ran. The model put `rm` and `ls` in one command; `programs()` sees both, and Jev judges the whole thing: `delete`, 1.00. My reason went back to the model, and it left the file alone.

When Jev can't answer. I ran it with a bad `TYPESAFE_API_KEY` and nothing on stdin, so every question gets no:

```bash
TYPESAFE_API_KEY=not-a-key uv run production/06-guardrails/guardrails.py "how many lines are in README.md?" < /dev/null
```

```
$ wc -l README.md
allow `wc -l README.md`? (Jev: no answer (TypeSafeAuthenticationError)) [y]es, [a]lways, or say why not: [the person said no: no]
I couldn't check. The command to count the lines in README.md was declined, so I haven't run it and don't have a number.

If you want the count, you can run `wc -l README.md` yourself. You can also tell me to go ahead and I'll run it. If you'd rather I not run commands, you could paste the file's contents here and I'll count from that.
[done in 2 steps, $0.0055]
```

`wc -l` only reads, but nobody said so, so it asked. Without Jev the gate asks about everything that isn't already *always*, which is slower for the person and never less safe.

The repeat limit:

```bash
uv run production/06-guardrails/guardrails.py "run the command 'date' once per step, waiting for each result, until you have run it four times. then say done."
```

```
$ date
[Jev: read, 0.99]
Tue Oct  6 22:44:00 UTC 2026

$ date
[Jev: read, 0.99]
Tue Oct  6 22:44:02 UTC 2026

$ date
[Jev: read, 0.99]
Tue Oct  6 22:44:03 UTC 2026

[stopped: asked for the same command 3 times]
```

It stopped at the third `date`, before the fourth call. The spending limit works the same way. I set `MAX_DOLLARS` to `0.004` in a copy, so it would show up in a couple of steps:

```
$ date
[Jev: read, 0.98]
Tue Oct  6 22:44:06 UTC 2026

$ pwd
[Jev: read, 1.00]
/tmp/pc/fx06/building-agents

[stopped: spent $0.0041, over the $0.004 budget]
```

The check happens before a call, so the run can end a little over: $0.0041 against $0.004. A limit like this is a ceiling on starting another call, not on the bill.

## What to take away

**The rule:** decide what the harness is willing to do before it does it. Check each tool request at the point where control flow turns it into a command, and check the run itself at the point where control flow chooses to go around again. Say no in a way the model can read, and give the person a way in.

Notice what Guardrails never does. It sits inside control flow, deciding whether the next step happens, and leaves the other primitives alone. The model interface gains one line, so a response can be stopped partway, and otherwise sends and receives as before; guardrails read `usage` and the tool request off the response and nothing more. When a command is allowed, output runs it in the box exactly as before. A refusal is an ordinary tool result in the slot the result would have filled, so context holds it the way it holds any result. And input is Lesson 2's `read()`, asking a person for a decision, plus a watcher that hears ESC while quark works.

**What's missing:** you can stop a run now, but you can't see one. How long did each step take? How many tokens, and what did that cost? Which command did the guard refuse, and which did the box kill? The terminal scrolled past. The episode has every message, but it's written for the model: no timings, no token counts, no exit codes. The person running quark needs a record of their own.

**→ [Lesson 7: Observability](../07-observability/)**
