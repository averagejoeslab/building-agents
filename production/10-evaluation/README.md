# Lesson 10: Evaluation

> 🎥 **Video:** coming soon

Lesson 9 ended on a worry. Every saving in it was a bet: a trimmed result might have cut the line that mattered, a summary from the small model might have lost a fact, a parallel command might have depended on another. And the same is true of any change you make to an agent, whether it's a new line in the system prompt, a different model, a lower step limit or a rewritten tool. After the change the agent still runs, the trace still looks normal, and nothing tells you whether it can still do its job. You find out the way you find out about any software that isn't tested: someone uses it, and it's wrong.

Evaluation is how you find out first. It runs the agent on tasks whose right outcome you already know, checks what happened, and compares the result with what it was before the change. It works in three parts.

**Tasks with known outcomes.** A case is three things: a starting state, a task, and a way to tell whether the outcome is right. "This folder has a `calc.py` with a bug and a `test.py` that fails. Fix the bug." The test passing is the outcome. What makes a case usable is that the outcome can be checked *without the agent*: a file's contents, a program's exit code, the state of the folder afterwards. So a case grades what is left in the world, not what the agent says about it, because an agent that says "done" has proved nothing and a test that passes has. And it doesn't grade how the agent got there. The agent may take two steps or five, and any route that ends in the right place passes. Each case starts from a fresh folder, so that cases can't affect each other and a rerun begins from exactly the same place.

**Grading.** There are two ways to check an outcome. *By code*: a command whose exit status says pass or fail. It's cheap, exact, and gives the same verdict every time, so it's what you use whenever the right answer can be written down. *By a model*: for outcomes that code can't read, such as an explanation or a summary, a second model is given a rubric and the output, and says whether it passes. It's flexible, but it's another model with mistakes of its own, so a model grader has to be tested too, by giving it answers whose grade you already know. A grade you can't trust is worse than none, because you'll believe it.

**Comparing.** One run proves little, because the model isn't deterministic: the same agent on the same case can pass once and fail the next time. So each case is run several times and the passes are counted. And a count means little by itself, since 11 of 12 is good or bad only against something. So you run the same cases before a change and after it, and the difference is what the change did. Pass or fail isn't the only thing that moves: a change can leave every case passing and make the agent twice as expensive, so each run also records its steps, its tokens and its time. Finally, the whole thing is a command that exits non-zero when something got worse. That's what lets a script, a git hook or a CI job run it on *every* change, and refuse the ones that break the agent. An evaluation you have to remember to run gets skipped.

This is a production layer, so it adds hardening, not a new primitive. It's **built on the whole harness**, and it's the one layer that isn't inside any one primitive. It sits outside the agent and treats it as a single box: a task goes in, and the world is changed. That runs all five primitives together, which is why it can catch problems that only appear when they work together, like a trimmed result (context) that sends the loop (control flow) round once more. The code the layer adds is small and made of primitives you've seen. It's control flow: a loop, like Lesson 3's workflow, that sets up a case, runs it, grades it, records it, and stops. The task is handed to the agent as input, the way a person's task would be. The check is run as output, a command run on the machine. And a model grader goes through the model interface. Lesson 7's trace says what happened in a run; evaluation says whether what happened was right.

## The worked example

[`quark.py`](./quark.py) is Lesson 9's `quark.py` plus evaluation, and nothing else, 411 lines, 38 more than Lesson 9's: `tempfile` and `shutil` in the imports, and one new section, placed before `# ── input ──` so that `--eval` is caught before anything is read:

```python
CASES = [
    {"name": "count", "setup": "seq 1 37 > numbers.txt", "input": "How many lines are in numbers.txt? Write only the number into answer.txt.",
     "check": "[ \"$(tr -d ' \\n' < answer.txt)\" = 37 ]"},
    {"name": "fix", "setup": "printf 'def add(a, b):\\n    return a - b\\n' > calc.py; printf 'from calc import add\\nassert add(2, 3) == 5\\nassert add(-1, 1) == 0\\n' > test.py", "input": "test.py fails. Fix the bug in calc.py, not the test.",
     "check": "python3 test.py && grep -q 'add(2, 3)' test.py"},
    {"name": "rename", "setup": "touch a.txt b.txt c.txt", "input": "Rename every .txt file in this folder to .md.",
     "check": "[ -e a.md ] && [ -e b.md ] && [ -e c.md ] && ! ls *.txt 2>/dev/null"},
    {"name": "remember", "setup": "true", "input": "Remember that I prefer short answers.",
     "check": "grep -qi short .quark/memory/memory.md"},
]
def evaluate(names):                                     # evaluation: run every case in a fresh folder, and grade what's left
    log, before = ".quark/evals.jsonl", {}
    os.makedirs(".quark", exist_ok=True)
    if os.path.exists(log):
        for line in open(log): before[json.loads(line)["case"]] = json.loads(line)["passed"]
    cases, failed = [c for c in CASES if not names or c["name"] in names], 0
    for case in cases:
        where = tempfile.mkdtemp(prefix=f"eval-{case['name']}-")
        subprocess.run(case["setup"], shell=True, cwd=where)
        start = time.time()
        try: subprocess.run([sys.executable, os.path.abspath(__file__), case["input"]], cwd=where, input="y\n" * 50, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
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
```

**`CASES`.** Four of them, each a dictionary: a `name`, a `setup` (a shell command that makes the starting folder), an `input` (the task), and a `check` (a shell command that exits 0 if the outcome is right). Three change files and one writes to memory, and all four have an outcome that can be looked at afterwards: `answer.txt` holds 37; `python3 test.py` passes and `test.py` hasn't been edited to make it; the `.txt` files are `.md` files; `memory.md` mentions `short`. The `fix` check does two things on purpose. An agent that "fixes" a failing test by deleting the assertion makes `test.py` pass, so the check also looks for the assertion that was supposed to stay. It's worth asking of every case you write how the agent could pass it without doing the job.

**`evaluate()`.** For each case it makes a new folder with `tempfile.mkdtemp()` and runs the setup in it. Then it runs *quark itself* on the task: `subprocess.run([sys.executable, os.path.abspath(__file__), case["input"]], cwd=where, ...)`. That's the whole point: it isn't a mock or a copy of the loop, it's the same file, with the same prompt, guard, sandbox, retries and tracing, started the way a person would start it with a task on the command line. Because the working folder is the case's folder, the sandbox mounts only that, and the `.quark/` directory with the memory and the trace is created there too, so cases can't see each other's memory. The guard still asks before anything it doesn't recognize runs, and `input="y\n" * 50` answers it, fifty times over. That isn't a way around Lesson 6: the policy that blocks `rm -rf` and `.env` still blocks them, and only the questions are answered. And because it runs under Lesson 5's sandbox, an agent that does something strange does it in a container holding a throwaway folder. A run that goes over five minutes is killed and then graded like any other, on what it left behind. (Killing it that way skips its cleanup, so its container can be left running, the gap Lesson 5 noted for a harness that is killed.)

Then comes the grade. The `check` runs on this machine, in the case's folder, with its output thrown away: pass is exit 0. The cost comes from somewhere that already exists. The child run wrote a trace (Lesson 7) into its folder, so `evaluate()` reads the `model` events out of it, and counts them as steps, and adds up their tokens. Note that the token count includes what was read from the cache, so it measures how much the model read, not what it cost. Each case prints one line, and a line is appended to `.quark/evals.jsonl`, where the next run will look. A case that failed keeps its folder, and the line says where it is, so you can open it and see what the agent did: its trace, and its episode, with every message the model saw and wrote. A case that passed has its folder deleted.

**The comparison.** Before running, `evaluate()` reads the log from last time. If a case passed then and fails now, its line says `REGRESSED`. That's what "catch it getting worse" means: not that it failed, but that it used to pass. The command's exit status is 1 if anything failed, which is what a script or a CI job needs. You can run some of the cases only, by naming them: `quark.py --eval fix rename`. The only thing you can't do is give quark a task that begins with `--eval`.

Four cases is a smoke test, not a benchmark. It can tell you quark is badly broken, and it can't tell you quark is good. That's the section below on what else evaluation can be.

## Run it

You need Docker running, as in Lesson 5. Start in a scratch folder, not in this repo, because the cases' results are logged in it. Each run is `uv run --project /path/to/building-agents /path/to/building-agents/production/10-evaluation/quark.py --eval`, which I'll write as `quark.py --eval`. Each case runs the real agent, so a run makes real model calls, and takes about twenty-five seconds.

**A baseline.** This is the number everything is compared with:

```
pass  count      2 steps    7.2s    21342 tokens
pass  fix        3 steps    6.6s    32208 tokens
pass  rename     2 steps    5.8s    21385 tokens
pass  remember   2 steps    4.7s    21422 tokens
4/4 passed
exit 0
```

The last line is the exit status. Four cases, four passes, and what each one cost: two or three steps, about five to seven seconds, and 21,000 to 32,000 tokens. That's a lot of tokens for tasks this small, and the reason is that quark's system prompt, with its memory instructions and its copy of its own code, is about nine thousand tokens and is read again on every step. Within a case, the later steps read it from the cache (Lesson 9); each case is a new folder with its own path in the prompt, so one case's cache doesn't serve the next. The `fix` case took a step more than the others; the next run shows what its first step is: reading the code before changing it. That's what normal looks like for this agent, and now it's written down.

**A change that breaks something.** Suppose someone wants to cap what a run can spend, and lowers `MAX_STEPS` from 20 to 1. Nothing about the change looks dangerous, and running quark on a simple task by hand, it still works. I made the change in a copy of the file, `sed 's/^MAX_STEPS, MAX_TOKENS = 20, /MAX_STEPS, MAX_TOKENS = 1, /'`, and ran the same cases in the same folder:

```
pass  count      1 steps    3.4s    10654 tokens
FAIL  fix        1 steps    4.6s    10623 tokens  kept /tmp/eval-fix-effj187m  REGRESSED: it passed last time
pass  rename     1 steps    3.5s    10654 tokens
pass  remember   1 steps    4.1s    10700 tokens
3/4 passed
exit 1
```

Three of the four still pass: counting lines, renaming files and writing a note can each be done in one command, and the agent does them in one. But `fix` can't, because the agent reads the code before it changes it. It fails, and the line says what the log said: it passed last time. The exit code is 1. This is the kind of change you can ship without anybody noticing, if nothing tests it, and a hand test would probably have tried one of the three that still work.

The failed case kept its folder. To see why it failed:

```
$ ls -a /tmp/eval-fix-effj187m
.
..
.quark
__pycache__
calc.py
test.py
$ cat /tmp/eval-fix-effj187m/calc.py
def add(a, b):
    return a - b
$ jq -c '{event,stop_reason,cmd}|with_entries(select(.value!=null))' /tmp/eval-fix-effj187m/.quark/traces.jsonl
{"event":"start"}
{"event":"model","stop_reason":"tool_use"}
{"event":"tool","cmd":"cat calc.py test.py"}
{"event":"stopped"}
```

The calculator still subtracts. The trace shows one model call, which asked for `cat calc.py test.py`, then the guardrail's `stopped`: the run hit the step limit before the model had seen what it read. The episode in the same folder has the request itself. Reading a failure like this is the most useful thing an evaluation gives you, which is why the folder is kept.

## Going further

**What else evaluation can be:** quark has four hand-written cases, graded by code, run once each, on demand. These are the choices you make when you build it.
- **Where cases come from.** Written by hand, as in quark, which is how you start. Better is to grow them from reality: every time the agent gets something wrong in real use, turn it into a case, so that it can never silently come back. Lesson 7's traces are where you find those. A model can also write candidate cases, but a person has to read them, because a case with a wrong answer key is worse than none.
- **What counts as a pass.** The state of the world afterwards, as in quark. Or the final answer, if the task is a question. Or the path the agent took, such as "it must read the file before it edits it" or "it must not call this tool", which is fragile, since a different route that works would fail. And a case can test what the agent must *not* do: a file that has to be untouched, a command that has to be refused. That's how you test Lesson 6's guardrails.
- **How it's graded.** Code where you can. A model where you can't, as in the fuller example, with a rubric strict enough that two graders agree, and a check on the grader. Or a second opinion on every run from a model that only answers questions, which is cheap enough to ask every time; the fuller example asks Jev. A person for the cases that matter most or that nothing else can read. A model can also compare two outputs ("which is better?") more reliably than it can score one on a scale. Partial credit, such as "four of the five required files were made", tells you more than pass or fail when tasks are big.
- **How noise is handled.** Each case several times, as in the fuller example, and then a choice: count a case as passed if it passes *at least once* in *k* runs (a measure of what the agent can do), or only if it passes *every* time (a measure of whether you can rely on it). With a handful of runs, a difference of one is often noise, as you'll see below.
- **Two kinds of case.** Some cases are meant to pass, always, and exist to catch breakage; a failure there is a regression. Others are hard, start out failing, and exist to show progress. They need different treatment: don't mix the two into one score.
- **When it runs.** On demand, as in quark. On every change, as a git hook or a CI job that fails when the exit status says so. On a schedule, because a new version of the model is a change you didn't make. And on live runs: grading a sample of real traces, not made-up cases, which tells you how the agent does on what people actually ask it.
- **What it measures besides pass.** Steps, tokens, seconds and money, as quark does. Refusals. How often a guard stopped it. Anything you can read from a trace.
- **Where it runs.** In a fresh folder, as in quark, or in a fresh container, or against a copy of a real repository checked out at a fixed commit, so that the starting state is the same every time.

It can be a product on its own. [Braintrust](https://www.braintrust.dev), [LangSmith](https://www.langchain.com/langsmith), [promptfoo](https://www.promptfoo.dev) and [Inspect](https://inspect.aisi.org.uk) all take cases, run them, grade them with code or a model, keep the history and show it to you. They save you the plumbing, the dashboards and the comparison. What they can't give you is the cases, because only you know what your agent's job is, and a product that runs a hundred of somebody else's cases tells you about somebody else's agent. The usual trade-off applies: the more of the layer you hand over, the less you see of how a grade came about.

The fuller example, [`evaluation.py`](./evaluation.py), shows more of that list. It's Lesson 3's agent loop (no memory, no tracing, no guard, no sandbox: just the loop), written as a function so that the thing to measure is all there is. Around it are three variants of the agent, each one a configuration you might change; four cases, three graded by code and one by a model; a model that grades the explanation, and a test of that model before it's trusted; a second judge, Jev, that says whether every run did its job, beside the grade; three trials of each case, run six at a time; and a table that compares every variant with the first one, the baseline. Here it is, all of it:

```python
import json, os, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic
from typesafe_sdk import TypeSafeClient, Noul, NoulCriteria

client, jev = Anthropic(), TypeSafeClient(timeout=10)
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
YES = 0.5                                    # Jev's probability of "done" at which its verdict counts as a pass

# What it is tested on. Each case has a task, a way to set up the folder, and a way to grade what's left there.
# A "check" is a shell command: exit 0 means pass. A "rubric" is a sentence a model checks the file named in "read" against.
CASES = {
    "count": {"setup": "seq 1 37 > numbers.txt",
              "input": "How many lines are in numbers.txt? Write only the number into answer.txt.",
              "check": "[ \"$(tr -d ' \\n' < answer.txt)\" = 37 ]"},
    "fix": {"setup": "printf 'def add(a, b):\\n    return a - b\\n' > calc.py; printf 'from calc import add\\nassert add(2, 3) == 5\\nassert add(-1, 1) == 0\\n' > test.py",
            "input": "test.py fails. Fix the bug in calc.py, not the test.",
            "check": "python3 test.py && grep -q 'add(2, 3)' test.py"},
    "log": {"setup": "awk 'BEGIN{for(i=1;i<=2000;i++){ if(i%400==0) print \"ERROR E\" (100+(i/400)%3) \" at line \" i; else print \"INFO ok \" i}}' > app.log",
            "input": "How many different error codes appear in app.log? Write only the number into answer.txt.",
            "check": "[ \"$(tr -d ' \\n' < answer.txt)\" = 3 ]"},
    "explain": {"setup": "printf 'def f(n):\\n    a, b = 0, 1\\n    for _ in range(n):\\n        a, b = b, a + b\\n    return a\\n' > mystery.py",
                "input": "Explain what mystery.py computes, in one or two sentences, in explanation.txt.",
                "read": "explanation.txt",
                "rubric": "It says the function computes or returns the n-th Fibonacci number, and it is no longer than two sentences."},
}

def agent(variant, input, where):
    # The agent under test: Lesson 3's loop, as a function, working in its own folder. It returns what it cost.
    messages, tokens, steps = [{"role": "user", "content": input}], 0, 0
    for steps in range(1, variant["steps"] + 1):
        output = client.messages.create(model=variant["model"], max_tokens=16384, system=variant["system"], tools=tools, messages=messages)
        tokens += output.usage.input_tokens + output.usage.output_tokens
        messages.append({"role": "assistant", "content": output.content})
        input = []
        for block in output.content:
            if block.type == "tool_use":
                try:
                    done = subprocess.run(block.input["cmd"], shell=True, cwd=where, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
                    out = done.stdout or f"(exit {done.returncode})"
                except (subprocess.TimeoutExpired, KeyError):
                    out = "stopped: it ran over 30 seconds, or the request was cut off"
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        if not input: break
        messages.append({"role": "user", "content": input})
    return steps, tokens

def judge(rubric, text):
    # Grading by a model: it reads the file and the rubric and says PASS or FAIL. It's a second model, so it's checked too (below).
    output = client.messages.create(model=JUDGE, max_tokens=1024, messages=[{"role": "user", "content":
        f"Grade this file against the rubric. Be strict.\n\nRubric: {rubric}\n\nFile:\n{text}\n\nReply with PASS or FAIL on the first line, then one short sentence of reason."}])
    said = next((b.text.strip() for b in output.content if b.type == "text"), "FAIL")
    return said.lstrip("*#` ").upper().startswith("PASS"), said

def files(where):
    # What a folder holds, for Jev to read: each file by name, with the middle of a long one cut out.
    found = {}
    for name in sorted(os.listdir(where)):
        if os.path.isfile(os.path.join(where, name)):
            text = open(os.path.join(where, name), errors="replace").read()
            found[name] = text if len(text) <= 2000 else text[:1000] + "\n...\n" + text[-1000:]
    return found

DONE = {"done": Noul(instructions="Did the agent do what `request` asked? Judge by comparing `files before` with `files after`.",
    criteria=NoulCriteria(true="Everything the request asked for is in `files after`, the way it asked, and nothing it forbade was done.",
                          false="Part of the request is missing or wrong, or it was done a way the request forbade."))}

def jev_judge(input, before, after):
    # Jev as judge: the same question, "did the agent complete the task?", put to a model that answers and writes nothing.
    # It sees the folder before and after, never what the agent said. It only reports: the grade stays code's or the judge's.
    try:
        return jev.system_one({"request": input, "files before": before, "files after": after}, DONE).nouls["done"].noul
    except Exception:
        return None                          # Jev couldn't be reached: no verdict, which is not a pass

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
    # Jev too, on the fix case: fixed, the test edited to pass instead, and nothing done. It only reports, so it doesn't stop the run.
    before = {"calc.py": "def add(a, b):\n    return a - b\n", "test.py": "from calc import add\nassert add(2, 3) == 5\n"}
    known = [({**before, "calc.py": "def add(a, b):\n    return a + b\n"}, True),
             ({**before, "test.py": "from calc import add\nassert add(2, 3) == -1\n"}, False), (before, False)]
    said = [jev_judge(CASES["fix"]["input"], before, after) for after, _ in known]
    right = sum(p is not None and (p >= YES) == expected for p, (_, expected) in zip(said, known))
    print(f"[jev: {right} of {len(known)} known answers judged correctly: " + ", ".join("no verdict" if p is None else f"{p:.2f}" for p in said) + "]")

def trial(name, case_name):
    # One run: a fresh folder, the agent, then the grade. The folder is thrown away after.
    case, where = CASES[case_name], tempfile.mkdtemp(prefix="eval-")
    subprocess.run(case["setup"], shell=True, cwd=where)
    before, start = files(where), time.time()
    steps, tokens = agent(VARIANTS[name], case["input"], where)
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
    done = jev_judge(case["input"], before, files(where))
    shutil.rmtree(where, ignore_errors=True)
    return {"variant": name, "case": case_name, "passed": passed, "steps": steps, "tokens": tokens, "seconds": round(seconds, 1), "why": why, "jev": done}

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
def yes(r): return r["jev"] is not None and r["jev"] >= YES
def says(v, c): return sum(yes(r) for r in runs if r["variant"] == v and r["case"] == c)
def mean(v, key): return sum(r[key] for r in runs if r["variant"] == v) / (len(CASES) * TRIALS)
print(f"\n{'':<12}" + "".join(f"{v:>9}" for v in names))
for c in CASES: print(f"{c:<12}" + "".join(f"{f'{wins(v, c)}/{TRIALS}':>9}" for v in names))
print(f"{'passed':<12}" + "".join(f"{f'{sum(wins(v, c) for c in CASES)}/{len(CASES) * TRIALS}':>9}" for v in names))
for c in CASES: print(f"{'jev ' + c:<12}" + "".join(f"{f'{says(v, c)}/{TRIALS}':>9}" for v in names))
print(f"{'steps/run':<12}" + "".join(f"{mean(v, 'steps'):>9.1f}" for v in names))
print(f"{'tokens/run':<12}" + "".join(f"{mean(v, 'tokens'):>9,.0f}" for v in names))
print(f"{'seconds/run':<12}" + "".join(f"{mean(v, 'seconds'):>9.1f}" for v in names))

for r in runs:
    if not r["passed"] and r["why"]: print(f"failed: {r['variant']} on {r['case']}: {r['why']}")
for v in names:
    for c in CASES:
        mine = [r for r in runs if r["variant"] == v and r["case"] == c]
        if any(yes(r) != r["passed"] for r in mine):
            print(f"jev disagrees: {v} on {c}, graded {wins(v, c)}/{TRIALS}, jev said " + ", ".join("no verdict" if r["jev"] is None else f"{r['jev']:.2f}" for r in mine))
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

**`files()`, `jev_judge()` and `YES`.** Jev as judge, next to the LLM as judge. Both answer the same question: did the agent complete the task? Jev is a decision model: it writes no text, it answers typed questions about a state you give it, and it's fast and cheap enough to ask about every run. I introduced it in [Lesson 5](../05-sandboxing/#asking-jev). Here it gets one yes-or-no question, `done`, and a state of three things: the request, the folder as it was after setup (`files before`) and the folder as the agent left it (`files after`), which `files()` reads, cutting the middle out of any file over 2,000 characters. It never sees what the agent said, for the same reason a case grades the world and not the words. What comes back is a probability of yes, and `YES` (0.5) is where I count it as a pass. In these cases the state is a few hundred to about 2,700 tokens, so at $0.042 a million tokens a verdict costs a hundredth of a cent at most, and it took about a fifth of a second. Jev's verdict only reports: the grade is still code's, or the LLM judge's, and nothing about the exit status changes. If Jev can't be reached, `jev_judge()` returns no verdict, which counts as not done, never as done. Asking Jev is a model-interface act, like asking the LLM judge: a second model, called. What's done with the answer is the evaluation's own control flow: it counts verdicts and compares them with the grade, outside the harness under test, like everything else here.

**`calibrate()`, for Jev too.** Jev is a grader, so it gets known answers as well: the `fix` case done right, the test edited to pass instead (`assert add(2, 3) == -1`) with the bug left in, and nothing done at all. Unlike the LLM judge's, a wrong one here doesn't stop the run, because Jev's verdict doesn't decide anything. The line prints how many it got right and the probabilities, so you can see how sure it was.

**`trial()`.** One run: a fresh folder, the agent, the grade, Jev's verdict, and the folder thrown away. It returns a record of steps, tokens and seconds, Jev's probability of done, and for a model-graded case, what the file said and what the judge said, so you can check the grader.

**The report.** Every trial runs in a pool of six, then each is appended to `.quark/evals.jsonl`. The table is passes out of trials for each case and variant, then how many runs Jev called done, then averages of steps, tokens and seconds. Then a `jev disagrees` line for each case and variant where Jev and the grade differ on any run, with Jev's probabilities. The last lines name every case where a variant did worse than the baseline, and the exit status is 1 if there are any. Jev's verdicts never count towards that.

A first run, all three variants, from a scratch folder:

```
[judge: 3 of 3 known answers graded correctly]
[jev: 3 of 3 known answers judged correctly: 0.99, 0.01, 0.01]
[36 runs: 3 variants x 4 cases x 3 trials, 6 at a time]

               sonnet    haiku    hasty
count             3/3      3/3      3/3
fix               3/3      3/3      3/3
log               3/3      3/3      3/3
explain           3/3      3/3      3/3
passed          12/12    12/12    12/12
jev count         3/3      3/3      3/3
jev fix           3/3      3/3      3/3
jev log           0/3      0/3      0/3
jev explain       3/3      3/3      3/3
steps/run         3.2      3.8      3.0
tokens/run      2,270    3,394    2,395
seconds/run       4.3      3.5      5.7
jev disagrees: sonnet on log, graded 3/3, jev said 0.13, 0.16, 0.15
jev disagrees: haiku on log, graded 3/3, jev said 0.17, 0.14, 0.15
jev disagrees: hasty on log, graded 3/3, jev said 0.14, 0.15, 0.13
[no variant is worse than the baseline]
```

Thirty-six agent runs, and every one passed. That's a result, and it's less dull than it looks. `haiku`, the cheaper model, passed everything. It took more steps (3.8 a run against 3.2) and about eleven hundred more tokens, and each run was quicker, 3.5 seconds against 4.3. `hasty`, with its instruction to read nothing before editing, wasn't worse on any case either, and it didn't save anything I can measure: 3.0 steps against 3.2, and slower, 5.7 seconds against 4.3. I haven't looked into why. If the numbers had been worse, they'd have been the reason not to ship the change. That the four cases can't tell these three apart means either they're equal on this work or the cases are too easy. Which it is, the table can't say, and that's the next point.

Jev agreed with the grade on three cases of four, every run, and was sure about it: it got the three known answers right at 0.99, 0.01 and 0.01, so it told a real fix from an edited test. On `log` it said no, nine times out of nine, at about 0.15, while the code said every answer was right. Jev was wrong there, and it's the kind of wrong its makers warn about: it doesn't count. To know that 3 is the right answer you have to count the error codes in two thousand lines, which is arithmetic, and `files()` had cut the middle out of the log anyway, so Jev couldn't have seen them all. A question whose answer is a count belongs in code, which is where the `log` case's check already is. That's what the `jev disagrees` lines are for: a disagreement doesn't say which judge is right, it says which runs to read.

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

**What's missing:** evaluation tells you whether the agent does the jobs you wrote down. It says nothing about the jobs you didn't. Four cases all passing is not a good agent, and even a large set is only as good as how well it matches what the agent is really asked to do, and it goes out of date as that changes. It tells you that something got worse, and doesn't say why: that's what Lesson 7's traces are for, and the episode beside them. A few trials make noise look like signal; a run of three that passes 2 of 3 and a run that passes 3 of 3 aren't different. A model that grades can be wrong, as the judge was here, and a check on the grader catches some of that and not all of it. And a case can be passed without doing the job in a way you didn't think of. All of these are reasons to keep reading the failures and to keep adding cases, and none are solved by a bigger harness.

That's the last production layer. There's no Lesson 11 to link to: what's next is your own agent, with its own cases, and the five primitives to take it apart with when it surprises you.

**← [Back to the course](../../README.md)**
