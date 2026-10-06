# Lesson 10: Evaluation

> 🎥 **Video:** coming soon

Lesson 9 ended on a worry. Every saving in it was a bet: a trimmed result might have cut the line that mattered, a summary from the small model might have lost a fact, a router might have sent a hard task to a weak model. And the same is true of any change you make to an agent, whether it's a new line in the system prompt, a different model, a lower step limit or a rewritten tool. After the change the agent still runs, the trace still looks normal, and nothing tells you whether it can still do its job. You find out the way you find out about any software that isn't tested: someone uses it, and it's wrong.

Evaluation is how you find out first. It runs the agent on tasks whose right outcome you already know, checks what happened, and compares the result with what it was before the change. It works in three parts.

**Tasks with known outcomes.** A case is three things: a starting state, a task, and a way to tell whether the outcome is right. "This folder has a `calc.py` with a bug and a `test.py` that fails. Fix the bug." The test passing is the outcome. What makes a case usable is that the outcome can be checked *without the agent*: a file's contents, a program's exit code, the state of the folder afterwards. So a case grades what is left in the world, not what the agent says about it, because an agent that says "done" has proved nothing and a test that passes has. And it doesn't grade how the agent got there. The agent may take two steps or five, and any route that ends in the right place passes. Each case starts from a fresh folder, so that cases can't affect each other and a rerun begins from exactly the same place.

**Grading.** There are two ways to check an outcome. *By code*: a command whose exit status says pass or fail. It's cheap, exact, and gives the same verdict every time, so it's what you use whenever the right answer can be written down. *By a model*: for outcomes that code can't read, such as an explanation or a summary, a second model is given a rubric and the output, and says whether it passes. It's flexible, but it's another model with mistakes of its own, so a model grader has to be tested too, by giving it answers whose grade you already know. A grade you can't trust is worse than none, because you'll believe it.

**Comparing.** One run proves little, because the model isn't deterministic: the same agent on the same case can pass once and fail the next time. So each case is run several times and the passes are counted. And a count means little by itself, since 11 of 12 is good or bad only against something. So you run the same cases before a change and after it, and the difference is what the change did. Pass or fail isn't the only thing that moves: a change can leave every case passing and make the agent twice as expensive, so each run also records its steps, its tokens and its time. Finally, the whole thing is a command that exits non-zero when something got worse. That's what lets a script, a git hook or a CI job run it on *every* change, and refuse the ones that break the agent. An evaluation you have to remember to run gets skipped.

This is a production layer, so it adds hardening, not a new primitive. It's **built on the whole harness**, and it's the one layer that isn't inside any one primitive. It sits outside the agent and treats it as a single box: a task goes in, and the world is changed. That runs all five primitives together, which is why it can catch problems that only appear when they work together, like a trimmed result (context) that sends the loop (control flow) round once more. The code the layer adds is small and made of primitives you've seen. It's control flow: a loop, like Lesson 3's workflow, that sets up a case, runs it, grades it, records it, and stops. The task is handed to the agent as input, the way a person's task would be. The check is run as output, a command run on the machine. And a model grader goes through the model interface. Lesson 5's trace says what happened in a run; evaluation says whether what happened was right.

## The worked example

`quark.py` can now evaluate itself. It's Lesson 9's file with one addition, `python quark.py --eval`, which runs a small set of cases against the agent in this very file. The whole of [`quark.py`](./quark.py) is below, with the system prompt shortened to `...` as before. The new code is the `CASES` list, `evaluate()`, two more imports, and the line before `resumed = unfinished()` that starts it. The rest is Lesson 9 unchanged:

```python
import subprocess, sys, os, datetime, json, time, uuid, re, atexit, tempfile, shutil
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic, BadRequestError, APIConnectionError, APIStatusError

client = Anthropic(timeout=300, max_retries=3)
run = uuid.uuid4().hex[:8]
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def trace(**event):
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "run": run, **event}) + "\n")


MODELS, FAST = ["claude-sonnet-5-5", "claude-opus-5-5"], ["claude-haiku-4-5"]
class Down(Exception): pass
def ask(models=MODELS, live=False, **request):
    for model in models:
        try:
            with client.messages.stream(model=model, **request) as stream:
                shown = False
                for text in stream.text_stream:
                    if live: print(text, end="", flush=True); shown = True
                if shown: print()
                return stream.get_final_message()
        except (APIConnectionError, APIStatusError) as e:
            if isinstance(e, APIStatusError) and e.status_code < 500 and e.status_code != 429: raise
            trace(event="model_failed", model=model, error=type(e).__name__)
    raise Down()


MAX_RESULT = 20_000
def trim(text):
    if len(text) <= MAX_RESULT: return text
    return text[:MAX_RESULT // 2] + f"\n[... {len(text) - MAX_RESULT} characters cut ...]\n" + text[-MAX_RESULT // 2:]
def cached(working_memory):
    last = working_memory[-1]
    blocks = [{"type": "text", "text": last["content"]}] if isinstance(last["content"], str) else list(last["content"])
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return working_memory[:-1] + [{"role": last["role"], "content": blocks}]


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


def execute(cmd):
    start = time.time()
    done = subprocess.run(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    if done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
    trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
    return trim(done.stdout) or f"(exit {done.returncode})"


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
    summary = ask(models=FAST, max_tokens=2048, system=system(), messages=keep + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}])
    gist = next((b.text for b in summary.content if b.type == "text"), "")
    return [{"role": "user", "content": f"[your prior working memory, summarized] {gist}"}]


CASES = [
    {"name": "count", "setup": "seq 1 37 > numbers.txt", "task": "How many lines are in numbers.txt? Write only the number into answer.txt.",
     "check": "[ \"$(tr -d ' \\n' < answer.txt)\" = 37 ]"},
    {"name": "fix", "setup": "printf 'def add(a, b):\\n    return a - b\\n' > calc.py; printf 'from calc import add\\nassert add(2, 3) == 5\\nassert add(-1, 1) == 0\\n' > test.py", "task": "test.py fails. Fix the bug in calc.py, not the test.",
     "check": "python3 test.py && grep -q 'add(2, 3)' test.py"},
    {"name": "rename", "setup": "touch a.txt b.txt c.txt", "task": "Rename every .txt file in this folder to .md.",
     "check": "[ -e a.md ] && [ -e b.md ] && [ -e c.md ] && ! ls *.txt 2>/dev/null"},
    {"name": "remember", "setup": "true", "task": "Remember that I prefer short answers.",
     "check": "grep -qi short .quark/memory/memory.md"},
]
def evaluate(names):
    log, before = ".quark/evals.jsonl", {}
    os.makedirs(".quark", exist_ok=True)
    if os.path.exists(log):
        for line in open(log): before[json.loads(line)["case"]] = json.loads(line)["passed"]
    cases, failed = [c for c in CASES if not names or c["name"] in names], 0
    for case in cases:
        where = tempfile.mkdtemp(prefix=f"eval-{case['name']}-")
        subprocess.run(case["setup"], shell=True, cwd=where)
        start = time.time()
        try: subprocess.run([sys.executable, os.path.abspath(__file__), case["task"]], cwd=where, input="y\n" * 50, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        except subprocess.TimeoutExpired: pass
        passed = subprocess.run(case["check"], shell=True, cwd=where, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        seconds = round(time.time() - start, 1)
        events = [json.loads(line) for line in open(f"{where}/.quark/traces.jsonl")] if os.path.exists(f"{where}/.quark/traces.jsonl") else []
        models = [e for e in events if e["event"] == "model"]
        tokens = sum(e["input_tokens"] + e["output_tokens"] + e["cache_read"] + e["cache_write"] for e in models)
        note = "" if passed else f"  kept {where}" + ("  REGRESSED: it passed last time" if before.get(case["name"]) else "")
        print(f"{'pass' if passed else 'FAIL'}  {case['name']:<9}{len(models):>3} steps {seconds:>6}s {tokens:>8} tokens{note}")
        with open(log, "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "case": case["name"], "passed": passed, "steps": len(models), "seconds": seconds, "tokens": tokens}) + "\n")
        if passed: shutil.rmtree(where, ignore_errors=True)
        else: failed += 1
    print(f"{len(cases) - failed}/{len(cases)} passed")
    return 1 if failed else 0


if sys.argv[1:2] == ["--eval"]: sys.exit(evaluate(sys.argv[2:]))
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
        reply = ask(live=True, max_tokens=16384, system=system(), tools=tools, messages=cached(working_memory))
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
    refused, pending = {}, {}
    for block in reply.content:
        if block.type == "tool_use":
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if not cmd or (reply.stop_reason == "max_tokens" and block is reply.content[-1]):
                refused[block.id] = "your request was cut off at the token limit, so it was not run. Send it again, shorter."
            elif (no := guard(cmd)):
                refused[block.id] = no
            else:
                pending[block.id] = cmd
    with ThreadPoolExecutor() as pool:
        outputs = dict(zip(pending, pool.map(execute, pending.values())))
    results = []
    for block in reply.content:
        if block.type == "tool_use":
            text = refused.get(block.id) or outputs[block.id]
            print(f"[{text}]" if block.id in refused else text)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": text, **({"is_error": True} if block.id in refused else {})})

    if results:
        working_memory.append({"role": "user", "content": results})
        continue
    os.remove(SESSION)
    if not chat or (task := input("\n> ")) == "/q":
        break
    working_memory.append({"role": "user", "content": task})
    steps, spent = 0, 0
```

There are three additions.

**`CASES`.** Four of them, each a dictionary: a `name`, a `setup` (a shell command that makes the starting folder), a `task`, and a `check` (a shell command that exits 0 if the outcome is right). Three change files and one writes to memory, and all four have an outcome that can be looked at afterwards: `answer.txt` holds 37; `python3 test.py` passes and `test.py` hasn't been edited to make it; the `.txt` files are `.md` files; `memory.md` mentions `short`. The `fix` check does two things on purpose. An agent that "fixes" a failing test by deleting the assertion makes `test.py` pass, so the check also looks for the assertion that was supposed to stay. It's worth asking of every case you write how the agent could pass it without doing the job.

**`evaluate()`.** For each case it makes a new folder with `tempfile.mkdtemp()` and runs the setup in it. Then it runs *quark itself* on the task: `subprocess.run([sys.executable, os.path.abspath(__file__), case["task"]], cwd=where, ...)`. That's the whole point: it isn't a mock or a copy of the loop, it's the same file, with the same prompt, guard, sandbox, retries and tracing, started the way a person would start it with a task on the command line. Because the working folder is the case's folder, the sandbox mounts only that, and the `.quark/` directory with the memory and the trace is created there too, so cases can't see each other's memory. The guard still asks before anything it doesn't recognize runs, and `input="y\n" * 50` answers it, fifty times over. That isn't a way around Lesson 6: the policy that blocks `rm -rf` and `.env` still blocks them, and only the questions are answered. And because it runs under Lesson 7's sandbox, an agent that does something strange does it in a container holding a throwaway folder. A run that goes over five minutes is killed and then graded like any other, on what it left behind. (Killing it that way skips its cleanup, so its container can be left running, the gap Lesson 7 noted for a harness that is killed.)

Then comes the grade. The `check` runs on this machine, in the case's folder, with its output thrown away: pass is exit 0. The cost comes from somewhere that already exists. The child run wrote a trace (Lesson 5) into its folder, so `evaluate()` reads the `model` events out of it, and counts them as steps, and adds up their tokens. Note that the token count includes what was read from the cache, so it measures how much the model read, not what it cost. Each case prints one line, and a line is appended to `.quark/evals.jsonl`, where the next run will look. A case that failed keeps its folder, and the line says where it is, so you can open it and see what the agent did. A case that passed has its folder deleted.

**The comparison.** Before running, `evaluate()` reads the log from last time. If a case passed then and fails now, its line says `REGRESSED`. That's what "catch it getting worse" means: not that it failed, but that it used to pass. The command's exit status is 1 if anything failed, which is what a script or a CI job needs. You can run some of the cases only, by naming them: `quark.py --eval fix rename`. The only thing you can't do is give quark a task that begins with `--eval`.

Four cases is a smoke test, not a benchmark. It can tell you quark is badly broken, and it can't tell you quark is good. That's the section below on what else evaluation can be.

## Run it

You need what Lesson 9 needed: Docker running, and `uv`. Start in a scratch folder, not in this repo, because the cases' results are logged in it. Each run is `uv run --project /path/to/building-agents /path/to/building-agents/production/10-evaluation/quark.py --eval`, which I'll write as `quark.py --eval`. Each case runs the real agent, so a run makes real model calls, and takes about twenty seconds.

**A baseline.** This is the number everything is compared with:

```
pass  count      2 steps    4.1s    13435 tokens
pass  fix        3 steps    5.2s    20262 tokens
pass  rename     2 steps    3.9s    13428 tokens
pass  remember   2 steps    4.3s    13582 tokens
4/4 passed
exit 0
```

The last line is the exit status. Four cases, four passes, and what each one cost: two to three steps, four to five seconds, and 13,000 to 20,000 tokens. That's a lot of tokens for tasks this small, and the reason is that quark's system prompt, with its copy of its own code, is over five thousand tokens and is read again on every step. Within a case, the later steps read it from the cache (Lesson 9). Each case is a new folder with its own path in the prompt, so one case's cache doesn't serve the next. The `fix` case took three steps because it had to read the code before changing it. That's what normal looks like for this agent, and now it's written down.

**A change that breaks something.** Suppose someone wants to cap what a run can spend, and lowers `MAX_STEPS` from 20 to 1. Nothing about the change looks dangerous, and running quark on a simple task by hand, it still works. I made the change in a copy of the file, `sed 's/^MAX_STEPS, MAX_TOKENS = 20, /MAX_STEPS, MAX_TOKENS = 1, /'`, and ran the same cases in the same folder:

```
pass  count      1 steps    3.0s     6687 tokens
FAIL  fix        1 steps    2.6s     6644 tokens  kept /tmp/eval-fix-1pf3a9_w  REGRESSED: it passed last time
pass  rename     1 steps    2.9s     6674 tokens
pass  remember   1 steps    3.1s     6778 tokens
3/4 passed
exit 1
```

Three of the four still pass: counting lines, renaming files and writing a note can all be done in one command, and the agent does them in one. But `fix` can't, because the agent reads the code before it changes it. It fails, and the line says what the log said: it passed last time. The exit code is 1. This is the kind of change you can ship without anybody noticing, if nothing tests it. I'd also point out how little a hand test would have shown. Whoever made the change would probably have tried one of the three that still work.

The failed case kept its folder. To see why it failed:

```
$ ls -a /tmp/eval-fix-1pf3a9_w
.
..
.quark
__pycache__
calc.py
test.py
$ cat /tmp/eval-fix-1pf3a9_w/calc.py
def add(a, b):
    return a - b
$ jq -c '{event,stop_reason,cmd}' /tmp/eval-fix-1pf3a9_w/.quark/traces.jsonl
{"event":"start"}
{"event":"model","stop_reason":"tool_use"}
{"event":"tool","cmd":"cat calc.py test.py"}
```

The calculator still subtracts. The trace shows one model call, which asked for `cat calc.py test.py`, and then no more: the run stopped at the step limit before the model had seen what it read. Reading a failure like this is the most useful thing an evaluation gives you, which is why the folder is kept.

Passing isn't the only thing that moves. In an earlier run of the same cases I tried a different change, cutting tool results to 20 characters (`MAX_RESULT = 20`, Lesson 9's trim). All four cases passed, so a pass-or-fail check would have called it fine. But `fix` took four steps and 27,245 tokens, where the baseline took three and 20,255. The agent worked around the damage and paid for it, which is why steps and tokens are recorded next to the grade.

## Going further

**What else evaluation can be:** quark has four hand-written cases, graded by code, run once each, on demand. These are the choices you make when you build it.
- **Where cases come from.** Written by hand, as in quark, which is how you start. Better is to grow them from reality: every time the agent gets something wrong in real use, turn it into a case, so that it can never silently come back. Lesson 5's traces are where you find those. A model can also write candidate cases, but a person has to read them, because a case with a wrong answer key is worse than none.
- **What counts as a pass.** The state of the world afterwards, as in quark. Or the final answer, if the task is a question. Or the path the agent took, such as "it must read the file before it edits it" or "it must not call this tool", which is fragile, since a different route that works would fail. And a case can test what the agent must *not* do: a file that has to be untouched, a command that has to be refused. That's how you test Lesson 6's guardrails.
- **How it's graded.** Code where you can. A model where you can't, as in the fuller example, with a rubric strict enough that two graders agree, and a check on the grader. A person for the cases that matter most or that nothing else can read. A model can also compare two outputs ("which is better?") more reliably than it can score one on a scale. Partial credit, such as "four of the five required files were made", tells you more than pass or fail when tasks are big.
- **How noise is handled.** Each case several times, as in the fuller example, and then a choice: count a case as passed if it passes *at least once* in *k* runs (a measure of what the agent can do), or only if it passes *every* time (a measure of whether you can rely on it). With a handful of runs, a difference of one is often noise, as you'll see below.
- **Two kinds of case.** Some cases are meant to pass, always, and exist to catch breakage; a failure there is a regression. Others are hard, start out failing, and exist to show progress. They need different treatment: don't mix the two into one score.
- **When it runs.** On demand, as in quark. On every change, as a git hook or a CI job that fails when the exit status says so. On a schedule, because a new version of the model is a change you didn't make. And on live runs: grading a sample of real traces, not made-up cases, which tells you how the agent does on what people actually ask it.
- **What it measures besides pass.** Steps, tokens, seconds and money, as quark does. Refusals. How often a guard stopped it. Anything you can read from a trace.
- **Where it runs.** In a fresh folder, as in quark, or in a fresh container, or against a copy of a real repository checked out at a fixed commit, so that the starting state is the same every time.

It can be a product on its own. [Braintrust](https://www.braintrust.dev), [LangSmith](https://www.langchain.com/langsmith), [promptfoo](https://www.promptfoo.dev) and [Inspect](https://inspect.aisi.org.uk) all take cases, run them, grade them with code or a model, keep the history and show it to you. They save you the plumbing, the dashboards and the comparison. What they can't give you is the cases, because only you know what your agent's job is, and a product that runs a hundred of somebody else's cases tells you about somebody else's agent. The usual trade-off applies: the more of the layer you hand over, the less you see of how a grade came about.

The fuller example, [`evaluation.py`](./evaluation.py), shows more of that list. It's Lesson 3's agent loop (no memory, no tracing, no guard, no sandbox: just the loop), written as a function so that the thing to measure is all there is. Around it are three variants of the agent, each one a configuration you might change; four cases, three graded by code and one by a model; a model that grades the explanation, and a test of that model before it's trusted; three trials of each case, run six at a time; and a table that compares every variant with the first one, the baseline. Here it is, all of it:

```python
import json, os, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

# What is being tested. A variant is one way of configuring the agent: the thing you change, and then measure.
# The first one is the baseline: every other variant is judged against it.
BASE = "You are an agent whose body is bash. Work in the current folder. Be brief."
VARIANTS = {
    "sonnet": {"model": "claude-sonnet-5-5", "system": BASE, "steps": 10},
    "haiku":  {"model": "claude-haiku-4-5",  "system": BASE, "steps": 10},
    "hasty":  {"model": "claude-sonnet-5-5", "system": BASE + " Use as few commands as you can. Never read a file before you change it.", "steps": 10},
}
TRIALS, AT_ONCE = 3, 6                       # runs per case and variant (the model is not deterministic), runs at the same time
JUDGE = "claude-opus-5-5"                    # grades the cases that code can't

# What it is tested on. Each case has a task, a way to set up the folder, and a way to grade what's left there.
# A "check" is a shell command: exit 0 means pass. A "rubric" is a sentence a model checks the file named in "read" against.
CASES = {
    "count": {"setup": "seq 1 37 > numbers.txt",
              "task": "How many lines are in numbers.txt? Write only the number into answer.txt.",
              "check": "[ \"$(tr -d ' \\n' < answer.txt)\" = 37 ]"},
    "fix": {"setup": "printf 'def add(a, b):\\n    return a - b\\n' > calc.py; printf 'from calc import add\\nassert add(2, 3) == 5\\nassert add(-1, 1) == 0\\n' > test.py",
            "task": "test.py fails. Fix the bug in calc.py, not the test.",
            "check": "python3 test.py && grep -q 'add(2, 3)' test.py"},
    "log": {"setup": "awk 'BEGIN{for(i=1;i<=2000;i++){ if(i%400==0) print \"ERROR E\" (100+(i/400)%3) \" at line \" i; else print \"INFO ok \" i}}' > app.log",
            "task": "How many different error codes appear in app.log? Write only the number into answer.txt.",
            "check": "[ \"$(tr -d ' \\n' < answer.txt)\" = 3 ]"},
    "explain": {"setup": "printf 'def f(n):\\n    a, b = 0, 1\\n    for _ in range(n):\\n        a, b = b, a + b\\n    return a\\n' > mystery.py",
                "task": "Explain what mystery.py computes, in one or two sentences, in explanation.txt.",
                "read": "explanation.txt",
                "rubric": "It says the function computes or returns the n-th Fibonacci number, and it is no longer than two sentences."},
}

def agent(variant, task, where):
    # The agent under test: Lesson 3's loop, as a function, working in its own folder. It returns what it cost.
    messages, tokens, steps = [{"role": "user", "content": task}], 0, 0
    for steps in range(1, variant["steps"] + 1):
        reply = client.messages.create(model=variant["model"], max_tokens=16384, system=variant["system"], tools=tools, messages=messages)
        tokens += reply.usage.input_tokens + reply.usage.output_tokens
        messages.append({"role": "assistant", "content": reply.content})
        results = []
        for block in reply.content:
            if block.type == "tool_use":
                try:
                    done = subprocess.run(block.input["cmd"], shell=True, cwd=where, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
                    out = done.stdout or f"(exit {done.returncode})"
                except (subprocess.TimeoutExpired, KeyError):
                    out = "stopped: it ran over 30 seconds, or the request was cut off"
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        if not results: break
        messages.append({"role": "user", "content": results})
    return steps, tokens

def judge(rubric, text):
    # Grading by a model: it reads the file and the rubric and says PASS or FAIL. It's a second model, so it's checked too (below).
    reply = client.messages.create(model=JUDGE, max_tokens=1024, messages=[{"role": "user", "content":
        f"Grade this file against the rubric. Be strict.\n\nRubric: {rubric}\n\nFile:\n{text}\n\nReply with PASS or FAIL on the first line, then one short sentence of reason."}])
    said = next((b.text.strip() for b in reply.content if b.type == "text"), "FAIL")
    return said.lstrip("*#` ").upper().startswith("PASS"), said

def calibrate():
    # A grader you haven't tested is one more thing you're trusting. Give the judge answers whose grade you already know.
    rubric = CASES["explain"]["rubric"]
    known = [("It returns the n-th Fibonacci number.", True),
             ("It computes the factorial of n.", False),
             ("It returns the n-th Fibonacci number. It does so with a loop. The loop keeps two values. It then swaps them.", False)]
    for text, expected in known:
        if judge(rubric, text)[0] != expected:
            sys.exit(f"[the judge got a known answer wrong: {text!r}. Fix the rubric before you trust any grade]")
    print(f"[judge: {len(known)} of {len(known)} known answers graded correctly]")

def trial(name, case_name):
    # One run: a fresh folder, the agent, then the grade. The folder is thrown away after.
    case, where = CASES[case_name], tempfile.mkdtemp(prefix="eval-")
    subprocess.run(case["setup"], shell=True, cwd=where)
    start = time.time()
    steps, tokens = agent(VARIANTS[name], case["task"], where)
    seconds = time.time() - start
    why = ""
    if "check" in case:
        passed = subprocess.run(case["check"], shell=True, cwd=where, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    else:
        path = os.path.join(where, case["read"])
        if os.path.exists(path):
            text = open(path).read()
            passed, said = judge(case["rubric"], text)
            why = f"file said {text.strip()!r}; judge said {said!r}"
        else:
            passed, why = False, f"{case['read']} was never written"
    shutil.rmtree(where, ignore_errors=True)
    return {"variant": name, "case": case_name, "passed": passed, "steps": steps, "tokens": tokens, "seconds": round(seconds, 1), "why": why}

names = sys.argv[1:] or list(VARIANTS)
calibrate()
jobs = [(v, c) for v in names for c in CASES for _ in range(TRIALS)]
print(f"[{len(jobs)} runs: {len(names)} variants x {len(CASES)} cases x {TRIALS} trials, {AT_ONCE} at a time]")
with ThreadPoolExecutor(AT_ONCE) as pool:
    runs = list(pool.map(lambda job: trial(*job), jobs))

os.makedirs(".quark", exist_ok=True)
with open(".quark/evals.jsonl", "a") as f:
    for r in runs: f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **r}) + "\n")

def wins(v, c): return sum(r["passed"] for r in runs if r["variant"] == v and r["case"] == c)
def mean(v, key): return sum(r[key] for r in runs if r["variant"] == v) / (len(CASES) * TRIALS)
print(f"\n{'':<12}" + "".join(f"{v:>9}" for v in names))
for c in CASES: print(f"{c:<12}" + "".join(f"{f'{wins(v, c)}/{TRIALS}':>9}" for v in names))
print(f"{'passed':<12}" + "".join(f"{f'{sum(wins(v, c) for c in CASES)}/{len(CASES) * TRIALS}':>9}" for v in names))
print(f"{'steps/run':<12}" + "".join(f"{mean(v, 'steps'):>9.1f}" for v in names))
print(f"{'tokens/run':<12}" + "".join(f"{mean(v, 'tokens'):>9,.0f}" for v in names))
print(f"{'seconds/run':<12}" + "".join(f"{mean(v, 'seconds'):>9.1f}" for v in names))

for r in runs:
    if not r["passed"] and r["why"]: print(f"failed: {r['variant']} on {r['case']}: {r['why']}")
worse = [(v, c) for v in names[1:] for c in CASES if wins(v, c) < wins(names[0], c)]
for v, c in worse:
    print(f"worse than {names[0]}: {v} on {c}, {wins(v, c)}/{TRIALS} against {wins(names[0], c)}/{TRIALS}")
print("[no variant is worse than the baseline]" if not worse else f"[worse than the baseline in {len(worse)} of {len(names[1:]) * len(CASES)} comparisons]")
sys.exit(1 if worse else 0)
```

What's there beyond quark's version:

**`VARIANTS`.** A variant is a configuration of the agent: a model, a system prompt and a step limit. They're the thing you change, so they're what you compare. The first is the baseline. `haiku` is the cheaper model. `hasty` is the same model with a line in its prompt telling it to use few commands and never read before editing, the kind of "be efficient" instruction someone adds to save money. Each is a hypothesis: *this one is as good and cheaper*.

**`CASES`.** The same idea as quark's, with two more. `log` needs the agent to find something in two thousand lines of log, and `explain` has no check at all: it has a `rubric`, a sentence saying what a good answer must contain, and a `read`, the file to grade.

**`agent()`.** Lesson 3's loop as a function that takes a variant and a folder, and returns its steps and tokens. Its commands run in the case's folder. Like Lesson 3's, it runs whatever the model asks on this machine, with no sandbox, so run it somewhere you can afford to.

**`judge()` and `calibrate()`.** The model grader and the test of the model grader. `judge()` gives a model the rubric and the file and asks for PASS or FAIL on the first line. It's a different model from all three variants, and it's told to be strict. `calibrate()` runs before anything else, and hands the judge three answers I already know the grade of: a right one, a wrong one, and a right one that breaks the length limit. If the judge gets any of them wrong, the run stops, because every grade after that would be a guess.

**`trial()`.** One run: a fresh folder, the agent, the grade, and the folder thrown away. It returns a record of steps, tokens and seconds, and for a model-graded case, what the file said and what the judge said, so you can check the grader.

**The report.** Every trial runs in a pool of six, then each is appended to `.quark/evals.jsonl`. The table is passes out of trials for each case and variant, then averages of steps, tokens and seconds. The last lines name every case where a variant did worse than the baseline, and the exit status is 1 if there are any.

A first run, all three variants, from a scratch folder:

```
[judge: 3 of 3 known answers graded correctly]
[36 runs: 3 variants x 4 cases x 3 trials, 6 at a time]

               sonnet    haiku    hasty
count             3/3      3/3      3/3
fix               3/3      3/3      3/3
log               3/3      3/3      3/3
explain           3/3      3/3      3/3
passed          12/12    12/12    12/12
steps/run         3.2      3.8      3.0
tokens/run      2,279    3,343    2,348
seconds/run       4.4      3.3      5.7
[no variant is worse than the baseline]
```

Thirty-six agent runs, and every one passed. That's a result, and it's less dull than it looks. `haiku`, the cheaper model, passed everything. It took more steps (3.8 a run against 3.2) and about a thousand more tokens, and each run was quicker, 3.3 seconds against 4.4. `hasty`, with its instruction to read nothing before editing, wasn't worse on any case either, and it didn't save anything I can measure: 3.0 steps against 3.2, and slower, 5.7 seconds against 4.4. I haven't looked into why. If the numbers had been worse, they'd have been the reason not to ship the change. That the four cases can't tell these three apart means either they're equal on this work or the cases are too easy. Which it is, the table can't say, and that's the next point.

To see what a table looks like when something is worse, I added one line to `VARIANTS` in a copy of the file, a variant that is the baseline with `"steps": 1`, and ran only that and the baseline:

```
[judge: 3 of 3 known answers graded correctly]
[24 runs: 2 variants x 4 cases x 3 trials, 6 at a time]

               sonnet  onestep
count             3/3      3/3
fix               3/3      0/3
log               3/3      0/3
explain           3/3      0/3
passed          12/12     3/12
steps/run         3.2      1.0
tokens/run      2,257      488
seconds/run       4.8      1.3
failed: onestep on explain: explanation.txt was never written
failed: onestep on explain: explanation.txt was never written
failed: onestep on explain: explanation.txt was never written
worse than sonnet: onestep on fix, 0/3 against 3/3
worse than sonnet: onestep on log, 0/3 against 3/3
worse than sonnet: onestep on explain, 0/3 against 3/3
[worse than the baseline in 3 of 4 comparisons]
```

`onestep` failed three cases of four, every trial, and it was cheaper in every column: 488 tokens a run against 2,257, and 1.3 seconds against 4.8. It was cheaper because it had stopped before doing the work. That is exactly why cost is read together with pass rate and never alone. The last lines name each comparison that got worse, the run exits with 1, and `explain` is reported without the judge being asked, since there was no file to read.

**The grader had a bug.** The second full run I made of this file didn't end like that one:

```
[judge: 3 of 3 known answers graded correctly]
[36 runs: 3 variants x 4 cases x 3 trials, 6 at a time]

               sonnet    haiku    hasty
count             3/3      3/3      3/3
fix               3/3      3/3      3/3
log               3/3      3/3      3/3
explain           2/3      3/3      3/3
passed          11/12    12/12    12/12
steps/run         3.2      3.6      3.0
tokens/run      2,268    3,102    2,371
seconds/run       4.7      3.2      6.0
[no variant is worse than the baseline]
```

The baseline, `sonnet`, passed `explain` two times out of three. A baseline losing a case it surely knows is a sign that the grading is wrong, not the agent, so I read the failed run. The log records what the file said and what the judge said (this is the line from that run, which was the earlier version of the file):

```
{"variant":"sonnet","case":"explain","why":"file said 'mystery.py defines f(n), which iteratively computes the n-th Fibonacci number (F(0)=0, F(1)=1, F(2)=1, ...) in O(n) time and constant space.'; judge said '**PASS**\\nIt is a single sentence stating that f(n) computes the n-th Fibonacci number; under a stricter literal reading this would fail, because it says \"computes\" rather than explicitly \"returns.\"'"}
```

The file is a correct explanation. The judge said `**PASS**`, in bold, and my code tested whether its answer *started with* `PASS`, so it saw two asterisks and decided it was a fail. There was a second problem behind it: the judge hedged, saying a stricter reading would fail the answer because it says "computes" and not "returns", which means my rubric was ambiguous. I fixed both: the grade is now read after stripping the markdown, and the rubric accepts "computes or returns". The run just before it had a failure in a different place: `haiku` on `explain`, 2 of 3. I didn't record the reason for that one, so I can't say it was the same bug, but I'd bet it was. In both, a variant was blamed on the evidence of a grader that was wrong. It's an example of why this file stores the judge's answer, and why a failure should be read before it's believed. The `calibrate()` check didn't catch this one: its three known answers are plain sentences, and the judge answered them in plain text. A grader can pass its check and still fail you.

## What to take away

**The rule:** write down what a right outcome looks like before you change anything, and then measure it after. Make the cases things you can check without the agent, run the whole agent on them, grade the world and not the words, repeat each case enough that noise doesn't pass for a result, compare with a baseline, read the cost next to the pass rate, and do it on every change, not when you remember.

Notice what Evaluation never does. It sits outside the harness and treats it as a box, and it leaves all five primitives alone. It doesn't change the agent's control flow: the loop under test is the loop it always was, with the same stops, and the evaluation's own loop is a separate one around it. Input is untouched: the agent gets its task the way a person would give it. Context is untouched: it doesn't edit the prompt, the memory or the working memory, though it's how you find out whether an edit of yours helped. The model interface is untouched: the same calls, to the same models. And output is untouched: the agent's tools run as they always did, and the check is one more command beside them. Evaluation runs the primitives. It never rebuilds them.

**What's missing:** evaluation tells you whether the agent does the jobs you wrote down. It says nothing about the jobs you didn't. Four cases all passing is not a good agent, and even a large set is only as good as how well it matches what the agent is really asked to do, and it goes out of date as that changes. It tells you that something got worse, and doesn't say why: that's what Lesson 5's traces are for. A few trials make noise look like signal; a run of three that passes 2 of 3 and a run that passes 3 of 3 aren't different. A model that grades can be wrong, as the judge was here, and a check on the grader catches some of that and not all of it. And a case can be passed without doing the job in a way you didn't think of. All of these are reasons to keep reading the failures and to keep adding cases, and none are solved by a bigger harness.

That's the last production layer. There's no Lesson 11 to link to: what's next is your own agent, with its own cases, and the five primitives to take it apart with when it surprises you.

**← [Back to the course](../../README.md)**
