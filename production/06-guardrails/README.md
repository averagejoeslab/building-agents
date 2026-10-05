# Lesson 6: Guardrails

> 🎥 **Video:** coming soon

Lesson 5 left you able to see everything the harness does, and nothing else. The agent still runs whatever the model asks, as soon as it asks, for as long as the model keeps asking. If it asks for `rm -rf` on the wrong directory, it's gone, and the trace will tell you so afterwards. If it gets stuck retrying one command, it will do that until you notice the bill.

Guardrails are rules about what the harness is allowed to do, checked before it does it: which commands may run, when a person gets a say, and when a run has gone on long enough. The model proposes and the harness decides, and the decision is yours.

This is a production layer, so it adds hardening, not a new primitive. It's **built on control flow**, and everything it does stays inside it. Control flow is the primitive that decides whether the next step happens at all. A tool request arrives in the response; the loop is what turns it into a command being run, and what turns the result into another model call. A guardrail is a decision at one of those two points, so it has to live there.

The mechanism is a few checks, each at a place the loop already passes through:

- **A gate before each tool.** The model has asked for a command; before it runs, the harness looks at it and picks one of three: *allow* it, *ask* a person first, or *deny* it. The rules for that are plain code: a list of programs that are safe to run unasked, and patterns that must never run.
- **A refusal the model can read.** A command that doesn't run still has to be answered, because every tool request needs a result (Lesson 2). So the refusal goes back in that slot, marked as an error, saying why. The model reads it like any other result and tries something else, or tells you it can't. If the person said no and gave a reason, the reason goes back too.
- **Limits before each call.** At the top of the loop, before spending another model call, check how many steps the run has taken and how many tokens it has used. Past the limit, stop. Lesson 3 said a loop with no clear end is a bill with no clear end; this is the clear end.
- **An interrupt.** The person can break in while the agent is working, and the harness stops what it's doing and hands the run back to them.

Guardrails don't make the model behave. They don't change what it asks for, only whether the harness goes along with it. And they're only as good as the rules: a check is code reading a command, and a command can say the same thing many ways. You'll see where that runs out at the end.

## The worked example

Here's Lesson 5's agent with quark's guardrails added. It's the whole of [`quark.py`](./quark.py), with the system prompt shortened to `...` as before. The new code is the limits and `guard()` at the top, the check at the top of the loop, the two counters, and the gate in the tool branch; the rest is Lesson 5 unchanged, tracing included:

```python
import subprocess, sys, os, datetime, json, time, uuid, re
from anthropic import Anthropic, BadRequestError

client = Anthropic()
run = uuid.uuid4().hex[:8]
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def trace(**event):
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "run": run, **event}) + "\n")


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
    summary = client.messages.create(model="claude-sonnet-5-5", max_tokens=2048, system=system(), messages=keep + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}])
    gist = next((b.text for b in summary.content if b.type == "text"), "")
    return [{"role": "user", "content": f"[your prior working memory, summarized] {gist}"}]


task = " ".join(sys.argv[1:]) or input("> ")
chat = len(sys.argv) < 2
working_memory, drop, steps, spent = [{"role": "user", "content": task}], 0, 0, 0
trace(event="start", task=task)

while True:
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
        reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, system=system(), tools=tools, messages=working_memory)
        trace(event="model", seconds=round(time.time() - start, 2), stop_reason=reply.stop_reason, input_tokens=reply.usage.input_tokens, output_tokens=reply.usage.output_tokens, cache_read=reply.usage.cache_read_input_tokens, cache_write=reply.usage.cache_creation_input_tokens)
        steps += 1
        spent += reply.usage.input_tokens + reply.usage.output_tokens + reply.usage.cache_read_input_tokens + reply.usage.cache_creation_input_tokens
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
        trace(event="too_long", drop=drop)
        continue

    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            if (no := guard(block.input["cmd"])):
                print(f"[{no}]")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": no, "is_error": True})
                continue
            start = time.time()
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            trace(event="tool", cmd=block.input["cmd"], seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})

    working_memory.append({"role": "assistant", "content": reply.content})
    if results:
        working_memory.append({"role": "user", "content": results})
        continue
    if not chat or (task := input("\n> ")) == "/q":
        break
    working_memory.append({"role": "user", "content": task})
    steps, spent = 0, 0
```

There are four additions.

**The policy.** `SAFE` is a set of programs that only read: `ls`, `cat`, `grep`, `wc` and a few more. `DENY` is one pattern for things quark should never do, whoever asks: `sudo`, recursive or forced `rm`, `mkfs`, `git push`, piping a download into a shell, and anything that mentions `.env`, where secrets live. They're data at the top of the file, so changing the policy is changing a line.

**`guard()`.** It takes the command the model asked for and returns `None` if it may run, or the reason it may not.
1. If the command matches `DENY`, it's refused outright. No one is asked.
2. If it's made only of safe programs, it runs. "Made only of" is checked carefully: the command has to have none of `; & < > $` or a backtick or a newline (anything that chains commands, redirects into a file, or expands something the check can't see), and every piece between pipes has to start with a safe program. `cat notes.txt | sh` isn't safe just because it starts with `cat`.
3. Anything else is put to the person: `allow `…`? [y/N]`. A `y` lets it run. Anything else is a no, and what they typed goes back to the model, so `no, use git status instead` is an instruction, not just a refusal. Closing the input counts as no. The default is the safe one: a command nobody approved doesn't run.

**The gate.** In the tool branch, right after the command is printed and before `subprocess.run`, `guard()` is called. If it returns a reason, that reason is printed and becomes the tool's result, marked `"is_error": True`, and `continue` skips the run. The command is never started. Otherwise the code is what it was in Lesson 5. The tool request still gets an answer, so the model's next turn makes sense.

**The limits.** `steps` and `spent` count model calls and tokens (input, output and both cache counts, all read off `reply.usage`, the same fields Lesson 5 traced). At the top of the loop, before the next call, `if steps >= MAX_STEPS or spent >= MAX_TOKENS` the run stops. In a task run, that's the end. In a chat it hands back to the person, who can give a new task, and the counts start again. The limits are per task, so one long chat doesn't use up a budget meant for one request.

Nothing else changed. The request is built the same way, the same tools run the same way, and a command that passes the gate is run exactly as before. One thing to notice: `mechanics()` puts quark's own file in its system prompt, so the model can read the policy it's under. That's Lesson 4's self-knowledge, not something this layer does, and it's fine: knowing the rules in advance saves it asking for things that will be refused. A denied command also isn't traced, because Lesson 5's `trace()` call sits after the gate, next to the code that runs it; the trace records what ran, and the refusal is printed.

## Run it

From the root of the repo. First, a task that only needs safe commands:

```bash
uv run production/06-guardrails/quark.py "how many lines are in README.md? answer in one sentence"
```

```
$ wc -l README.md
180 README.md

README.md has 180 lines.
```

`wc` is a safe program, so nothing was asked. Now one that deletes things. I made three `.log` files in `/tmp/demo` and ran it with `y` piped in as the answer, so you don't see the `y` echoed after the prompt; in a terminal you'd type it:

```bash
uv run production/06-guardrails/quark.py "delete the .log files in /tmp/demo, then say what's left there, in one sentence"
```

```
$ ls -la /tmp/demo
total 20
drwxr-xr-x  2 root root 4096 Oct  5 23:29 .
drwxrwxrwt 12 root root 4096 Oct  5 23:29 ..
-rw-r--r--  1 root root    4 Oct  5 23:29 old1.log
-rw-r--r--  1 root root    4 Oct  5 23:29 old2.log
-rw-r--r--  1 root root    4 Oct  5 23:29 old3.log

$ rm /tmp/demo/*.log; ls -la /tmp/demo
allow `rm /tmp/demo/*.log; ls -la /tmp/demo`? [y/N] total 8
drwxr-xr-x  2 root root 4096 Oct  5 23:29 .
drwxrwxrwt 12 root root 4096 Oct  5 23:29 ..

I deleted the three `.log` files (`old1.log`, `old2.log`, `old3.log`), and `/tmp/demo` is now empty.
```

`ls -la` ran unasked. `rm` isn't on the safe list, so the harness stopped at the prompt and nothing was deleted until the answer came. Now a refusal with a reason, then a yes to what the model tries next:

```bash
uv run production/06-guardrails/quark.py "create an empty file /tmp/notes.txt with touch, and tell me in one sentence how it went"
```

The two answers piped in were `no, not in /tmp, use /tmp/demo2` and `y`:

```
$ touch /tmp/notes.txt && ls -l /tmp/notes.txt
allow `touch /tmp/notes.txt && ls -l /tmp/notes.txt`? [y/N] [the person said no: no, not in /tmp, use /tmp/demo2]
$ mkdir -p /tmp/demo2 && touch /tmp/demo2/notes.txt && ls -l /tmp/demo2/notes.txt
allow `mkdir -p /tmp/demo2 && touch /tmp/demo2/notes.txt && ls -l /tmp/demo2/notes.txt`? [y/N] -rw-r--r-- 1 root root 0 Oct  5 23:29 /tmp/demo2/notes.txt

I created the empty file at `/tmp/demo2/notes.txt` instead of `/tmp/notes.txt`, treating `/tmp/demo2` as the directory, and it worked (0 bytes).
```

The model took the reason as an instruction: it moved the file to `/tmp/demo2` and asked again, this time for the directory and the file in one command, and when that was approved it ran. Last, the deny list, which doesn't ask. This time the answers don't matter, because nobody was asked:

```bash
uv run production/06-guardrails/quark.py "print the contents of .env, then run rm -rf /tmp/demo, then tell me in one sentence what you managed to do"
```

```
I'll run both as you asked. They're independent, so I'll send them together.
$ cat .env
[blocked by policy]
$ rm -rf /tmp/demo
[blocked by policy]
I managed to do nothing: the harness's policy blocked both `cat .env` and `rm -rf /tmp/demo`, so I didn't print the file or delete the directory. I also didn't try to get around the block.
```

Both commands were refused before they ran, and `/tmp/demo` is still there. The model read the refusals, didn't try to get around them, and reported what happened.

To see the step limit, I lowered `MAX_STEPS` to 2 in a copy and asked for three commands one at a time. The run stopped before the third:

```
$ date
Mon Oct  5 23:29:46 UTC 2026

$ pwd
/home/user/building-agents

[stopped: 2 steps, 7149 tokens]
```

`MAX_TOKENS` works the same way, but at 200,000 tokens you'll rarely reach it. The system prompt alone is a few thousand tokens, and every pass re-sends it.

> `quark.py` has no interrupt. Press Ctrl-C while it's working and Python stops the program, which stops it but doesn't hand the run back to you. The fuller example below does that properly.

## Going further

**What else guardrails can be:** quark gates one tool with a short list of rules and a yes/no prompt. These are the choices you make when you build it.
- **How a command is judged.** Patterns on the text, like quark's. Or a parser that understands the shell, so `cat x | sh` and `$(…)` are seen for what they are. Or per-tool rules once you have more than `bash`: this tool may only read, that one may only touch this folder. Or a second model call that reads the request and judges it, which is slower, costs money and can be argued with.
- **What the answers are.** Allow, ask or deny, or something finer: allow *this* command once, allow this program for the session, allow it always, or allow it only with these arguments. Rules can be written by the person ahead of time instead of answered one at a time.
- **Who gets asked.** The person at the terminal, someone on Slack or Telegram who taps *approve*, a second agent, or nobody, in a run that has to fail closed and stop when it reaches something it can't decide. Asking too often trains people to hit `y`; asking too rarely is no guardrail.
- **What counts as too much.** Steps, tokens, dollars, wall-clock time, or *repeating*: the same command asked for again and again is a loop whatever the counts say.
- **How a run is interrupted.** Ctrl-C, a key like ESC that stops the current step but not the session, a message that arrives mid-run, a kill switch someone else holds. And what happens after: stop, or hand back to the person with the work so far intact.
- **What the model is told.** A bare refusal, or a reason, or the rule itself, so it can plan around it.
- **What you do about it afterwards.** Nothing, a line in the trace, or an alert.

It can be a product on its own. Rule engines and policy services like [Open Policy Agent](https://github.com/open-policy-agent/opa) decide *allowed or not* for a request as data and not code, and libraries like [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) and Guardrails AI wrap checks around what goes into and comes out of a model. If you're using one for what a tool may run, it's this layer.

Here's a guardrail that does more of that, in [`guardrails.py`](./guardrails.py). It's built on Lesson 3's `control_flow.py`, so it has the step limit, and it has no system prompt, so its requests are just the task:

```python
import subprocess, sys, re, collections
from anthropic import Anthropic

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
    try: answer = input(f"allow `{cmd}`? ({why}) [y]es, [a]lways, or say why not: ").strip()
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

task = " ".join(sys.argv[1:]) or input("> ")
messages = [{"role": "user", "content": task}]
spent, asked = 0.0, collections.Counter()

for step in range(1, MAX_STEPS + 1):
    if spent >= MAX_DOLLARS:
        print(f"[stopped: spent ${spent:.4f}, over the ${MAX_DOLLARS} budget]")
        break
    if asked and max(asked.values()) >= MAX_REPEATS:
        print(f"[stopped: asked for the same command {MAX_REPEATS} times]")
        break
    results, replied = [], False
    try:
        reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)
        replied = True
        messages.append({"role": "assistant", "content": reply.content})
        spent += cost(reply.usage)
        if reply.stop_reason == "refusal":
            print("[stopped: the model declined]")
            break
        for block in reply.content:
            if block.type == "text":
                print(block.text)
            if block.type == "tool_use":
                cmd = block.input["cmd"]
                print(f"$ {cmd}")
                asked[cmd] += 1
                if (no := guard(cmd)):
                    print(f"[{no}]")
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": no, "is_error": True})
                    continue
                done = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                print(done.stdout)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})
    except KeyboardInterrupt:
        print("\n[interrupted]")
        if replied:
            answered = {r["tool_use_id"] for r in results}
            results += [{"type": "tool_result", "tool_use_id": b.id, "content": "interrupted by the person", "is_error": True} for b in reply.content if b.type == "tool_use" and b.id not in answered]
        try: say = input("what now? (blank to stop) > ").strip()
        except EOFError: say = ""
        if not say:
            print("[stopped: interrupted]")
            break
        messages.append({"role": "user", "content": results + [{"type": "text", "text": say}] if replied else say})
        continue
    if not results:
        print(f"[done in {step} steps, ${spent:.4f}]")
        break
    messages.append({"role": "user", "content": results})
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
```

- **Policy as data, per piece.** `ALLOWED` and `DENIED` are at the top. `programs()` splits a command on `&&`, `||`, `;`, pipes and newlines and takes the first word of each piece, so `cd /tmp && rm x` is judged by `cd` *and* `rm`. `verdict()` returns `allow`, `ask` or `deny` with a reason. Deny patterns win over everything; a redirect or `$` makes it ask, since the check can't see where it goes; and every program must be allowed for the whole command to be.
- **Always.** At the prompt, `a` means *always*: the programs in that command join `ALLOWED` for the rest of the run, so the person is asked about `touch` once, not every time. A redirect still asks, because the check there isn't about the program.
- **A reason in the refusal.** Both a policy denial and a person's no go back as errors with the reason, so the model can change course.
- **A spending limit.** `cost()` turns each response's `usage` into dollars at `PRICE`, the same example rates as Lesson 5's, so use your provider's. When `spent` passes `MAX_DOLLARS`, the run stops. Tokens are what you can count; dollars are what you care about.
- **A repeat limit.** `asked` counts every command the model has requested. If one comes up `MAX_REPEATS` times, the run stops, because a model going round in circles is spending your money without getting anywhere.
- **An interrupt.** Ctrl-C raises `KeyboardInterrupt` wherever the program is: waiting on the model, waiting on a person, or in the middle of a command (`subprocess.run` kills the command). The `except` answers every tool request that didn't get a result with "interrupted by the person", because the API needs an answer for each, then asks `what now?`. Say something and it goes to the model with the work so far, so you can redirect it. Leave it blank and the run stops.

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

And the interrupt. I asked it to run `sleep 30`, answered `y`, and sent Ctrl-C a few seconds in. Since I can't press a key in a script, I sent the same signal with `timeout -s INT 7`, which is why the exit code at the end is 124 (that's `timeout`'s, not the agent's):

```
$ sleep 30
allow `sleep 30`? (sleep isn't on the allowed list) [y]es, [a]lways, or say why not: 
[interrupted]
what now? (blank to stop) > Hello!
[done in 2 steps, $0.0034]
exit 124
```

The `sleep` was killed and the run came back to `what now?`. I answered `skip the sleep, just say hello` (piped in, so it isn't echoed), the message went to the model along with the "interrupted" result, and it answered `Hello!` instead.

## What to take away

**The rule:** decide what the harness is willing to do before it does it. Check each tool request at the point where control flow turns it into a command, and check the run itself at the point where control flow chooses to go around again. Say no in a way the model can read, and give the person a way in.

Notice what Guardrails never does. It sits inside control flow's loop, deciding whether the next step happens, and it leaves the other primitives alone. The request goes to the model and the response comes back through the model interface as before; guardrails read `usage` and the tool request off the response and nothing more. When a command is allowed, output runs it exactly as it always did; the gate only decides whether to call it. A refusal is an ordinary tool result in the slot the result would have filled, so context assembles the request the way it always has. Input isn't changed either: the question to the person is a plain `input()`, read as a decision, not a task.

**What's missing:** a guardrail decides *whether* a command runs. It can't limit what a command can do once it's allowed. The check reads text, and bash gives you many ways to write the same thing: a deny list is a list of the ways you thought of. You approved `python build.py`; what `build.py` does with the rest of the machine was never in front of you. Approval fatigue is real, too: after enough prompts, `y` becomes a reflex. And an agent can only be stopped from doing what the harness can see it is about to do. For the commands you do allow, the question is no longer whether they should run but what they can reach when they do: which files, which network, how long. That means running them somewhere that limits those things.

**→ [Lesson 7: Sandboxing](../07-sandboxing/)**
