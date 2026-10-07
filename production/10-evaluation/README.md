# Lesson 10: Evaluation

> 🎥 **Video:** coming soon

Lesson 9 ended on a worry. Every saving in it was a bet: a trimmed result might have cut the line that mattered, a summary from the small model might have lost a fact, a parallel command might have depended on another. And the same is true of any change you make to an agent, whether it's a new line in the system prompt, a different model, a lower step limit or a rewritten tool. After the change the agent still runs, the trace still looks normal, and nothing tells you whether it can still do its job. You find out the way you find out about any software that isn't tested: someone uses it, and it's wrong.

Evaluation is how you find out first. It runs the agent on tasks whose right outcome you already know, checks what happened, and compares the result with what it was before the change. It works in three parts.

**Tasks with known outcomes.** A case is three things: a starting state, a task, and a way to tell whether the outcome is right. "This folder has a `calc.py` with a bug and a `test.py` that fails. Fix the bug." The test passing is the outcome. What makes a case usable is that the outcome can be checked *without the agent*: a file's contents, a program's exit code, the state of the folder afterwards. So a case grades what is left in the world, not what the agent says about it, because an agent that says "done" has proved nothing and a test that passes has. And it doesn't grade how the agent got there. The agent may take two steps or five, and any route that ends in the right place passes. Each case starts from a fresh folder, so that cases can't affect each other and a rerun begins from exactly the same place.

**Grading.** There are two ways to check an outcome. *By code*: a command whose exit status says pass or fail. It's cheap, exact, and gives the same verdict every time, so it's what you use whenever the right answer can be written down. But it checks exactly what you wrote and nothing else, and an agent can pass it without doing the job in a way you didn't think of. *By a model*: a second model is shown the task and the outcome and asked whether the job was done. It can read what code can't, such as whether the test was left alone in spirit and not just in name, but it's another model with mistakes of its own. Here that's an ordinary language model, an LLM as judge, and once the idea is clear I put Jev beside it, a model that writes nothing and only answers typed questions, on the same question. A grade you can't trust is worse than none, because you'll believe it, so the code's check stays the grade and the judges report beside it.

**Comparing.** One run proves little, because the model isn't deterministic: the same agent on the same case can pass once and fail the next time. And a result means little by itself, since 11 of 12 is good or bad only against something. So you run the same cases before a change and after it, and the difference is what the change did. Pass or fail isn't the only thing that moves: a change can leave every case passing and make the agent twice as expensive, so each run also records its steps, its tokens and its time. Finally, the whole thing is a command that exits non-zero when something got worse. That's what lets a script, a git hook or a CI job run it on *every* change, and refuse the ones that break the agent. An evaluation you have to remember to run gets skipped.

This is a production layer, so it adds hardening, not a new primitive. It's **built on the whole harness**, and it's the one layer that isn't inside any one primitive. It sits outside the agent and treats it as a single box: a task goes in, and the world is changed. That runs all five primitives together, which is why it can catch problems that only appear when they work together, like a trimmed result (context) that sends the loop (control flow) round once more. The code the layer adds is small and made of primitives you've seen. It's control flow: a loop, like Lesson 3's workflow, that sets up a case, runs it, grades it, records it, and stops. The task is handed to the agent as input, the way a person's task would be. The check is run as output, a command run on the machine. And the judges are asked through the model interface. Lesson 7's trace says what happened in a run; evaluation says whether what happened was right.

## The concept

Here's the idea with nothing around it: one case, two agents, a check in code, an LLM as judge, and a comparison with last time. It's in [`evaluation.py`](./evaluation.py):

```python
import json, os, shutil, subprocess, sys, tempfile
from anthropic import Anthropic

client = Anthropic()
LESSON_3 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../lessons/03-control-flow/control_flow.py")

SETUP = "printf 'def add(a, b):\\n    return a - b\\n' > calc.py; printf 'from calc import add\\nassert add(2, 3) == 5\\n' > test.py"
INPUT = "test.py fails. Fix the bug in calc.py, not the test."
CHECK = "python3 test.py && grep -q 'add(2, 3)' test.py"            # grading by code: exit 0 is a pass
AGENTS = {"lesson 3": [sys.executable, LESSON_3, "agent", INPUT],    # the agent under test, started the way a person would
          "cheat": ["sed", "-i", "s/== 5/== -1/", "test.py"]}        # a stand-in for an agent that games the check

QUESTION = "Did the agent complete the task in `request`? Judge by `files before` and `files after`."

def files(where):                                                    # the folder, as a judge sees it
    return {name: open(os.path.join(where, name)).read() for name in sorted(os.listdir(where)) if os.path.isfile(os.path.join(where, name))}

def judge(state):                                                    # grading by a model: an LLM as judge
    llm = client.messages.create(model="claude-sonnet-5-5", max_tokens=1024, messages=[{"role": "user", "content": f"{QUESTION} Reply PASS or FAIL, then one sentence.\n\n{json.dumps(state)}"}])
    return next(b.text for b in llm.content if b.type == "text").strip().upper().startswith("PASS")

last, worse = {}, False                                              # comparing: what each agent did last time
if os.path.exists("evals.jsonl"):
    for line in open("evals.jsonl"): last[json.loads(line)["agent"]] = json.loads(line)["passed"]
for name, command in AGENTS.items():
    where = tempfile.mkdtemp(prefix="eval-")                         # a fresh folder for every run
    subprocess.run(SETUP, shell=True, cwd=where)
    before = files(where)
    subprocess.run(command, cwd=where, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    passed = subprocess.run(CHECK, shell=True, cwd=where, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    state = {"request": INPUT, "files before": before, "files after": files(where)}
    llm_says = judge(state)
    was = last.get(name)
    worse |= bool(was) and not passed
    print(f"{name:<9} check {'pass' if passed else 'FAIL'}  llm {'pass' if llm_says else 'fail'}  last time {'-' if was is None else 'pass' if was else 'FAIL'}" + ("  REGRESSED" if was and not passed else ""))
    with open("evals.jsonl", "a") as f: f.write(json.dumps({"agent": name, "passed": passed, "llm": llm_says}) + "\n")
    shutil.rmtree(where)
sys.exit(1 if worse else 0)
```

**The case.** `SETUP` makes the folder: a `calc.py` whose `add` subtracts, and a `test.py` that says `add(2, 3)` should be 5. `INPUT` is the task, and it says what not to do: fix `calc.py`, not the test. `CHECK` is the grade by code, a shell command whose exit status is the verdict. It runs the test, and it also checks that the assertion is still there, because the cheapest way to make a failing test pass is to delete it.

**The agents.** The one under test is Lesson 3's [`control_flow.py`](../../lessons/03-control-flow/control_flow.py) in agent mode, started as a separate program with the task on its command line and the case's folder as its working folder: the way a person would start it, not a copy of its loop. Lesson 3 has no sandbox, so the commands its model asks for run on this machine, in that throwaway folder. The other one isn't a model at all. `cheat` is one `sed` command that I wrote to stand in for an agent that games the check: it leaves the bug alone and changes what the test expects, from 5 to -1, which is what the broken `add` returns. The assertion is still there, so the `grep` is satisfied. I know the right grade for it in advance, which is what makes it useful: it's a known wrong answer.

**The judge.** `files()` reads every file in the folder, by name, before the agent runs and after. `judge()` puts one question, `QUESTION`, "did the agent complete the task?", to a language model, with a state: the request, the files before and the files after. It never sees what the agent said, for the same reason the check doesn't: a case grades the world, not the words. It gets the question plus "reply PASS or FAIL, then one sentence", and its verdict is whether its reply starts with `PASS`. Asking it is a model-interface act: a second model, called with a request and read back. What's done with the answer, printing it beside the check, is the evaluation's own control flow, and it happens outside the agent under test.

**The comparison.** `evals.jsonl` is the record. Before anything runs, the script reads what each agent's check said last time. Each run then prints one line: the check, the judge, and last time's result, with `REGRESSED` if it passed then and fails now, and appends its own line to the log. Each agent gets a fresh folder from `tempfile.mkdtemp()`, deleted when it's graded. If anything regressed, the exit status is 1.

Run it from a scratch folder, since it writes its log where you run it: `uv run --project /path/to/building-agents /path/to/building-agents/production/10-evaluation/evaluation.py`. The first time:

```
lesson 3  check pass  llm pass  last time -
cheat     check pass  llm fail  last time -
exit 0
```

(The last line is the exit status.) Lesson 3's agent fixed the bug, and the check and the judge agree. The cheat passed the check. The test runs, and the assertion is there; it just asserts the wrong thing now. The judge failed it. It saw `test.py` before and after, and the request said not to touch it. That's the disagreement worth having. The check is exact about what it checks and blind to everything else, and I hadn't thought of this way round it when I wrote it. The judge caught it because it was asked the question I actually cared about.

So why not let the judge grade? Because it's a model, and it'll be wrong about things code would never get wrong (in quark's version below, compiled bytes in a judge's state made it less sure of a perfectly good fix). The check is still the grade. The judge is a second opinion, and where it disagrees with the check, it tells you which run to read.

The second time, from the same folder:

```
lesson 3  check pass  llm pass  last time pass
cheat     check pass  llm fail  last time pass
exit 0
```

The same verdicts, and now each line knows what happened last time. Nothing got worse, so the exit status is 0. Notice that the comparison only compares the check: the cheat "passed last time" too. A comparison is only as good as the grade it compares.

## The concept with Jev

A language model is one judge. Jev, which I introduced in [Lesson 5](../05-sandboxing/#asking-jev), is another kind: it writes nothing and only answers typed questions. [`jev_evaluation.py`](./jev_evaluation.py) is `evaluation.py` with Jev asked the same question beside the language model, and nothing else. This is everything it adds:

```
$ diff evaluation.py jev_evaluation.py
2a3
> from typesafe_sdk import TypeSafeClient, Noul, NoulCriteria
4a6
> jev = TypeSafeClient(timeout=10) if os.environ.get("TYPESAFE_API_KEY") else None
13a16,17
> DONE = Noul(instructions=QUESTION, criteria=NoulCriteria(true="Everything the request asked for is done, the way it asked.",
>                                                           false="Part of it is missing or wrong, or it was done a way the request forbade."))
21a26,29
> def jev_judge(state):                                                # grading by Jev: the same question, typed
>     try: return round(jev.system_one(state, {"done": DONE}).model_dump()["answers"]["done"]["noul"], 2)
>     except Exception: return None                                    # no key or no answer: no verdict
> 
32a41
>     jev_says = jev_judge(state)
35,36c44,45
<     print(f"{name:<9} check {'pass' if passed else 'FAIL'}  llm {'pass' if llm_says else 'fail'}  last time {'-' if was is None else 'pass' if was else 'FAIL'}" + ("  REGRESSED" if was and not passed else ""))
<     with open("evals.jsonl", "a") as f: f.write(json.dumps({"agent": name, "passed": passed, "llm": llm_says}) + "\n")
---
>     print(f"{name:<9} check {'pass' if passed else 'FAIL'}  llm {'pass' if llm_says else 'fail'}  jev {jev_says}  last time {'-' if was is None else 'pass' if was else 'FAIL'}" + ("  REGRESSED" if was and not passed else ""))
>     with open("evals.jsonl", "a") as f: f.write(json.dumps({"agent": name, "passed": passed, "llm": llm_says, "jev": jev_says}) + "\n")
```

**What Jev is asked.** `DONE` is `QUESTION` again, as a yes-or-no question, with criteria that say what yes and no mean: yes is "everything the request asked for is done, the way it asked", and no includes "done a way the request forbade". Jev gets exactly the state the language model gets, the request and the files before and after, and answers with a probability of yes. A question like this one costs a fraction of a hundredth of a cent and takes about a fifth of a second.

**What comes back, and what the code does with it.** `jev_judge()` rounds the probability to two places and returns it. The client is only made when `TYPESAFE_API_KEY` is set, and anything that goes wrong, no key, no answer, or no answer within ten seconds, returns `None`, which is never a pass. The loop asks Jev after the language model, and the only two lines that change are the ones that use its answer: the printed line gets a `jev` column, and the log line gets a `"jev"` field. That's all. `passed`, `REGRESSED` and the exit status come from the check exactly as they did before, so a wrong answer from Jev can't make a run pass or fail. Asking Jev is a model-interface act, like asking the language model; deciding that its answer is reported and not obeyed is the evaluation's control flow.

**Its limits.** Jev reads its state literally, it doesn't count, and irrelevant detail in the state can throw it, as its makers say. Each of those shows up in this lesson, in quark's version and in the ideas at the end.

From a fresh scratch folder, `uv run --project /path/to/building-agents /path/to/building-agents/production/10-evaluation/jev_evaluation.py`:

```
lesson 3  check pass  llm pass  jev 0.98  last time -
cheat     check pass  llm fail  jev 0.01  last time -
exit 0
```

Jev agrees with the language model on both. It was sure Lesson 3's fix did the job, at 0.98, and sure the cheat didn't, at 0.01: comparing `test.py` before and after is a comparison of two texts, and the request had said not to change it. So the cheat now has the check passing it and two judges against it, and the line says so. The grade doesn't change, but what you'd read does: this is the run you'd open. A second run from the same folder gave the same numbers, with `last time pass` on both lines.

Without a key, from another fresh folder:

```
$ TYPESAFE_API_KEY=not-a-key uv run --project /path/to/building-agents /path/to/building-agents/production/10-evaluation/jev_evaluation.py
lesson 3  check pass  llm pass  jev None  last time -
cheat     check pass  llm fail  jev None  last time -
exit 0
```

Jev's column says it had no opinion, and everything else is what `evaluation.py` printed: the check, the language model and the exit status don't depend on it.

## quark's implementation

Here are both built into quark: the cases, the check, the comparison, and the two judges side by side. [`quark.py`](./quark.py) is Lesson 9's `quark.py` plus evaluation, and nothing else: 49 lines, 469 in all. `tempfile` and `shutil` join the imports:

```python
import subprocess, sys, os, re, glob, json, datetime, atexit, termios, tty, threading, select, contextlib, time, tempfile, shutil
```

and there's one new section, placed before `# ── input ──` so that `--eval` is caught before anything is read:

```python
# ── evaluation: a harness around this one ───────────────────────────────────
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
def snapshot(where):                                     # evaluation: the folder as a judge sees it: every file, cut short
    paths = glob.glob(f"{where}/**/*", recursive=True) + glob.glob(f"{where}/.quark/memory/*")
    return {os.path.relpath(p, where): open(p, errors="replace").read()[:2000] for p in paths if os.path.isfile(p) and "__pycache__" not in p}
DONE = Noul(instructions="Did the agent complete the task in `request`? Judge by `files before` and `files after`, not by anything the agent says.", criteria=NoulCriteria(true="Everything the request asked for is done, the way it asked, and nothing it forbade was done.", false="Part of the request is missing or wrong, or it was done a way the request forbade."))
def judges(input, before, after):                        # evaluation: two judges, one typed and one that writes, on the same question
    state = {"request": input, "files before": before, "files after": after}
    jev_says = ask(state, DONE)
    llm = call(max_tokens=1024, messages=[{"role": "user", "content": "Did the agent complete the task in `request`? Judge by `files before` and `files after`, not by anything the agent says. Reply PASS or FAIL, then one sentence.\n\n" + json.dumps(state)}])
    return jev_says and round(jev_says["noul"], 2), next((b.text for b in llm.content if b.type == "text"), "").strip().upper().startswith("PASS")
def evaluate(names):                                     # evaluation: run every case in a fresh folder, and grade what's left
    log, before = ".quark/evals.jsonl", {}
    os.makedirs(".quark", exist_ok=True)
    if os.path.exists(log):
        for line in open(log): before[json.loads(line)["case"]] = json.loads(line)["passed"]
    cases, failed = [c for c in CASES if not names or c["name"] in names], 0
    for case in cases:
        where = tempfile.mkdtemp(prefix=f"eval-{case['name']}-")
        subprocess.run(case["setup"], shell=True, cwd=where)
        seen, start = snapshot(where), time.time()
        try: subprocess.run([sys.executable, os.path.abspath(__file__), case["input"]], cwd=where, input="y\n" * 50, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        except subprocess.TimeoutExpired: pass
        passed = subprocess.run(case["check"], shell=True, cwd=where, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        jev_says, llm_says = judges(case["input"], seen, snapshot(where))
        seconds = round(time.time() - start, 1)
        events = [json.loads(line) for line in open(f"{where}/.quark/traces.jsonl")] if os.path.exists(f"{where}/.quark/traces.jsonl") else []
        models = [e for e in events if e["event"] == "model"]
        tokens = sum(e["input_tokens"] + e["output_tokens"] + e["cache_read"] + e["cache_write"] for e in models)
        note = "" if passed else f"  kept {where}" + ("  REGRESSED: it passed last time" if before.get(case["name"]) else "")
        verdicts = f"  jev {'-' if jev_says is None else jev_says}  llm {'pass' if llm_says else 'fail'}" + ("  JUDGES DISAGREE" if (jev_says is not None and (jev_says >= 0.5) != passed) or llm_says != passed else "")
        print(f"{'pass' if passed else 'FAIL'}  {case['name']:<9}{len(models):>3} steps {seconds:>6}s {tokens:>8} tokens{verdicts}{note}")
        with open(log, "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "case": case["name"], "passed": passed, "steps": len(models), "seconds": seconds, "tokens": tokens, "jev": jev_says, "llm": llm_says}) + "\n")
        if passed: shutil.rmtree(where, ignore_errors=True)
        else: failed += 1
    print(f"{len(cases) - failed}/{len(cases)} passed")
    return 1 if failed else 0

if sys.argv[1:2] == ["--eval"]: sys.exit(evaluate(sys.argv[2:]))
```

**`CASES`.** Four of them, each a dictionary: a `name`, a `setup` (a shell command that makes the starting folder), an `input` (the task), and a `check` (a shell command that exits 0 if the outcome is right). Three change files and one writes to memory, and all four have an outcome that can be looked at afterwards: `answer.txt` holds 37; `python3 test.py` passes and the assertion is still in `test.py`; the `.txt` files are `.md` files; `memory.md` mentions `short`. The `fix` case is the concept's, with a second assertion, and its check has the same blind spot the cheat walked through. It's worth asking of every case you write how the agent could pass it without doing the job.

**`evaluate()`.** For each case it makes a new folder with `tempfile.mkdtemp()` and runs the setup in it. Then it runs *quark itself* on the task: `subprocess.run([sys.executable, os.path.abspath(__file__), case["input"]], cwd=where, ...)`. That's the whole point: it isn't a mock or a copy of the loop, it's the same file, with the same prompt, guard, sandbox, retries, routing and tracing, started the way a person would start it with a task on the command line. Because the working folder is the case's folder, the sandbox mounts only that, and the `.quark/` directory with the memory and the trace is created there too, so cases can't see each other's memory. The guard still asks before anything it doesn't recognize runs, and `input="y\n" * 50` answers it, fifty times over. That isn't a way around Lesson 6: the policy that blocks `rm -rf` and `.env` still blocks them, and only the questions are answered. The same `y`s answer Lesson 5's question too, so a command Jev is sure needs the network is lent it. And because it runs under Lesson 5's sandbox, an agent that does something strange does it in a container holding a throwaway folder. A run that goes over five minutes is killed and then graded like any other, on what it left behind. (Killing it that way skips its cleanup, so its container can be left running, the same leftover Lesson 8 ran into when it killed the harness.)

Then comes the grade. The `check` runs on this machine, in the case's folder, with its output thrown away: pass is exit 0. The cost comes from somewhere that already exists. The child run wrote a trace (Lesson 7) into its folder, so `evaluate()` reads the `model` events out of it, counts them as steps, and adds up their tokens. Note that the token count includes what was read from the cache, so it measures how much the model read, not what it cost. Each case prints one line, and a line is appended to `.quark/evals.jsonl`, where the next run will look. A case that failed keeps its folder, and the line says where it is, so you can open it and see what the agent did: its trace, and its episode, with every message the model saw and wrote. A case that passed has its folder deleted.

**`snapshot()`, `DONE` and `judges()`.** The two judges from the concept with Jev. `snapshot()` reads the folder as the judges see it: every file in it, and the files in `.quark/memory/` (a plain `**` pattern skips folders whose names start with a dot, and the `remember` case is graded on one), each cut to its first 2,000 characters. It leaves out `__pycache__`, where Python keeps compiled bytes: the check's `python3 test.py` leaves one there, and that noise is [irrelevant detail](https://docs.typesafe.ai/model-jaggedness/jev-1.13), the kind its makers say can throw Jev. In testing, with the compiled file in its state, Jev was less sure of a right fix, 0.79 against 0.97 without it. `evaluate()` takes one snapshot right after the setup, `seen`, and one after the check. `judges()` asks both judges the same question with the same state. Jev's question, `DONE`, goes through Lesson 5's `ask()`, so no key, no answer or a time-out comes back as `None`, and the line shows `jev -`. The language model's goes through `call()`, the same function every model call in quark goes through, so it's the main model, with Lesson 8's backup behind it. Its verdict is whether its reply starts with `PASS`.

What the code does with the two answers is report them. The line gets `jev 0.97  llm pass`, and `JUDGES DISAGREE` if either judge's verdict differs from the check's: Jev counts as saying yes at 0.5 or more, and Jev's `None` counts as no opinion, not a disagreement. Both verdicts go into the log line, next to `passed`. And that's all: `passed`, `REGRESSED`, the kept folder and the exit status all come from the check, exactly as they would without the judges. Asking the two judges is the model interface; deciding what their answers mean, and that they don't change the grade, is the evaluation's control flow.

**The comparison.** Before running, `evaluate()` reads the log from last time. If a case passed then and fails now, its line says `REGRESSED`. That's what "catch it getting worse" means: not that it failed, but that it used to pass. The command's exit status is 1 if anything failed, which is what a script or a CI job needs. You can run some of the cases only, by naming them: `quark.py --eval fix rename`. The only thing you can't do is give quark a task that begins with `--eval`. That's stricter than the concept, which exits 1 only on a regression.

Four cases is a smoke test, not a benchmark. It can tell you quark is badly broken, and it can't tell you quark is good. That's the section below on what else evaluation can be.

### Run it

You need Docker running, as in Lesson 5. Start in a scratch folder, not in this repo, because the cases' results are logged in it. Each run is `uv run --project /path/to/building-agents /path/to/building-agents/production/10-evaluation/quark.py --eval`, which I'll write as `quark.py --eval`. Each case runs the real agent and asks both judges, so a run makes real model calls and takes about half a minute.

**A baseline.** This is the number everything is compared with:

```
pass  count      2 steps    7.6s    26855 tokens  jev 0.97  llm pass
pass  fix        3 steps    9.1s    40469 tokens  jev 0.98  llm pass
pass  rename     2 steps    9.0s    26892 tokens  jev 0.97  llm pass
pass  remember   2 steps    8.1s    26969 tokens  jev 0.94  llm pass
4/4 passed
exit 0
```

The last line is the exit status. Four cases, four passes, both judges agree with every one, and what each cost: two or three steps, seven to nine seconds, and about 27,000 to 40,000 tokens. That's a lot of tokens for tasks this small, and the reason is that quark's system prompt, with its memory instructions and its copy of its own code, is about thirteen thousand tokens and is read again on every step. Within a case, the later steps read it from the cache (Lesson 9); each case is a new folder with its own path in the prompt, so one case's cache doesn't serve the next. The seconds are measured from the start of the agent's run to after the judges have answered, so part of each is the judging. The `fix` case took a step more than the others; the next run shows what its first step is: reading the code before changing it.

**A change that breaks something.** Suppose someone wants to cap what a run can spend, and lowers `MAX_STEPS` from 20 to 1. Nothing about the change looks dangerous, and running quark on a simple task by hand, it still works. I made the change in a copy of the file, `sed 's/^MAX_STEPS, MAX_TOKENS = 20, /MAX_STEPS, MAX_TOKENS = 1, /'`, and ran the same cases in the same folder:

```
pass  count      1 steps    6.4s    13409 tokens  jev 0.97  llm pass
FAIL  fix        1 steps    6.1s    13381 tokens  jev 0.02  llm fail  kept /tmp/eval-fix-d1y0lovx  REGRESSED: it passed last time
pass  rename     1 steps    6.4s    13410 tokens  jev 0.97  llm pass
pass  remember   1 steps    6.4s    13455 tokens  jev 0.94  llm pass
3/4 passed
exit 1
```

Three of the four still pass: counting lines, renaming files and writing a note can each be done in one command, and the agent does them in one. But `fix` can't, because the agent reads the code before it changes it. It fails, and the line says what the log said: it passed last time. The exit code is 1. This is the kind of change you can ship without anybody noticing, if nothing tests it, and a hand test would probably have tried one of the three that still work. Both judges agree with all four grades: Jev said 0.02 for the unfixed calculator, and the language model said FAIL. No `JUDGES DISAGREE` in either run. quark's cases have nothing like the concept's cheat in them, and the agent didn't find one.

The failed case kept its folder. To see why it failed:

```
$ ls -a /tmp/eval-fix-d1y0lovx
.
..
.quark
__pycache__
calc.py
test.py
$ cat /tmp/eval-fix-d1y0lovx/calc.py
def add(a, b):
    return a - b
$ jq -c '{event,stop_reason,cmd}|with_entries(select(.value!=null))' /tmp/eval-fix-d1y0lovx/.quark/traces.jsonl
{"event":"start"}
{"event":"routed"}
{"event":"model","stop_reason":"tool_use"}
{"event":"tool","cmd":"cat calc.py test.py"}
{"event":"stopped"}
```

The calculator still subtracts. The trace shows Lesson 9's routing, then one model call, which asked for `cat calc.py test.py`, then the guardrail's `stopped`: the run hit the step limit before the model had seen what it read. The episode in the same folder has the request itself. Reading a failure like this is the most useful thing an evaluation gives you, which is why the folder is kept.

**Without Jev.** The same two cases, from a fresh folder, with a key that isn't one:

```
$ TYPESAFE_API_KEY=not-a-key quark.py --eval count fix
pass  count      2 steps    7.2s    26857 tokens  jev -  llm pass
pass  fix        3 steps    9.2s    40476 tokens  jev -  llm pass
2/2 passed
exit 0
```

Jev's column says it had no opinion, and nothing else changes: the grades, the log and the exit status are what they'd be with it.

## Other things we could do

quark has four hand-written cases, graded by code with two judges reporting beside it, run once each, on demand. These are the choices you make when you build it.
- **Where cases come from.** Written by hand, as in quark, which is how you start. Better is to grow them from reality: every time the agent gets something wrong in real use, turn it into a case, so that it can never silently come back. Lesson 7's traces are where you find those. A model can also write candidate cases, but a person has to read them, because a case with a wrong answer key is worse than none.
- **What counts as a pass.** The state of the world afterwards, as in quark. Or the final answer, if the task is a question. Or the path the agent took, such as "it must read the file before it edits it" or "it must not call this tool", which is fragile, since a different route that works would fail. And a case can test what the agent must *not* do: a file that has to be untouched, a command that has to be refused. That's how you test Lesson 6's guardrails.
- **How it's graded.** Code where you can. A model where you can't, with a rubric strict enough that two graders agree, and a check on the grader. A second opinion on every run from a model that only answers questions, cheap enough to ask every time, as quark asks Jev. A person for the cases that matter most or that nothing else can read. A model can also compare two outputs ("which is better?") more reliably than it can score one on a scale. Partial credit, such as "four of the five required files were made", tells you more than pass or fail when tasks are big.
- **How noise is handled.** Each case several times, and then a choice: count a case as passed if it passes *at least once* in *k* runs (a measure of what the agent can do), or only if it passes *every* time (a measure of whether you can rely on it). With a handful of runs, a difference of one is often noise.
- **Two kinds of case.** Some cases are meant to pass, always, and exist to catch breakage; a failure there is a regression. Others are hard, start out failing, and exist to show progress. They need different treatment: don't mix the two into one score.
- **When it runs.** On demand, as in quark. On every change, as a git hook or a CI job that fails when the exit status says so. On a schedule, because a new version of the model is a change you didn't make. And on live runs: grading a sample of real traces, not made-up cases, which tells you how the agent does on what people actually ask it.
- **What it measures besides pass.** Steps, tokens, seconds and money, as quark does. Refusals. How often a guard stopped it. Anything you can read from a trace.
- **Where it runs.** In a fresh folder, as in quark, or in a fresh container, or against a copy of a real repository checked out at a fixed commit, so that the starting state is the same every time.

It can be a product on its own. [Braintrust](https://www.braintrust.dev), [LangSmith](https://www.langchain.com/langsmith), [promptfoo](https://www.promptfoo.dev) and [Inspect](https://inspect.aisi.org.uk) all take cases, run them, grade them with code or a model, keep the history and show it to you. They save you the plumbing, the dashboards and the comparison. What they can't give you is the cases, because only you know what your agent's job is, and a product that runs a hundred of somebody else's cases tells you about somebody else's agent. The usual trade-off applies: the more of the layer you hand over, the less you see of how a grade came about.

A few ideas worth knowing if you build more of it yourself, with what each ran into when I tried them in an earlier version of this lesson.

- **Variants.** Compare configurations of the agent, not just one before and after: the same cases run against a cheaper model, a different prompt, a lower step limit, side by side, with the first one as the baseline. Each variant is a hypothesis, "this one is as good and cheaper", and the table of passes, steps, tokens and seconds is the test of it. When a variant with a one-step limit ran in that version, it was cheaper in every column, because it had stopped before doing the work. That's why cost is read next to the pass rate and never alone.
- **Trials, run at once.** Run each case three or more times per variant, a handful at a time in a thread pool, and report passes out of trials. When every variant passes everything, the table can't say whether they're equal or the cases are too easy. That's a reason to write harder ones.
- **A model grader with a rubric, and a test of the grader.** For an outcome code can't read, like "explain what this function computes in one or two sentences", give the judge a rubric and the file, and before trusting it, hand it answers whose grade you already know: a right one, a wrong one, and a right one that breaks the length limit. If it gets one wrong, stop. Store what the judge said next to every grade, too. When the baseline once failed an easy case in that version, the stored reply showed the judge had answered `**PASS**`, in bold, and the code that checked whether the reply started with `PASS` read that as a fail. The known answers hadn't caught it, because the judge answered those in plain text. A grader can pass its own check and still fail you, which is why quark's judges only report.
- **What a judge can't do.** Jev doesn't count. Asked whether "how many different error codes are in this two-thousand-line log?" had been answered right, it said no every time, while the code's check said every answer was right. A count belongs in code. And Jev reads what's in the state literally: shown only the folder afterwards, it couldn't tell a real fix from an edited test, because "was the test left alone?" is a question about a change, and with one folder there's no change to see. Given the folder before as well, it's a comparison of two texts, and it answered them correctly. When a judge gets a question wrong, the fix is usually to make the question more literal, or to give it the thing to compare, or to take something out of the state, as `snapshot()` does with `__pycache__`.
- **A judge that isn't the agent's model.** quark's language-model judge is the main model, which many of the agent's turns also run on, so it often grades work much like its own. A different model, or a bigger one, is a more independent second opinion.

## What to take away

**The rule:** write down what a right outcome looks like before you change anything, and then measure it after. Make the cases things you can check without the agent, run the whole agent on them, grade the world and not the words, repeat each case enough that noise doesn't pass for a result, compare with a baseline, read the cost next to the pass rate, and do it on every change, not when you remember. Where a check might be passed without doing the job, have a judge look at the same world and report beside it, not instead of it.

Notice what evaluation never does. It sits outside the harness and treats it as a box, and it leaves all five primitives alone. It doesn't change the agent's control flow: the loop under test is the loop it always was, with the same stops, and the evaluation's own loop is a separate one around it. Input is untouched: the agent gets its task the way a person would give it. Context is untouched: it doesn't edit the prompt, the memory or the working memory, though it's how you find out whether an edit of yours helped. The model interface is untouched: the same calls, to the same models; the judges' calls go through Lesson 5's `ask()` and the same `call()`, after the agent has finished. And output is untouched: the agent's tools run as they always did, and the check is one more command beside them. Evaluation runs the primitives. It never rebuilds them.

**What's missing:** evaluation tells you whether the agent does the jobs you wrote down. It says nothing about the jobs you didn't. Four cases all passing is not a good agent, and even a large set is only as good as how well it matches what the agent is really asked to do, and it goes out of date as that changes. It tells you that something got worse, and doesn't say why: that's what Lesson 7's traces are for, and the episode beside them. A few trials make noise look like signal; a run of three that passes 2 of 3 and a run that passes 3 of 3 aren't different. A check can be passed without doing the job, as the cheat passed this one, and a judge can be wrong. All of these are reasons to keep reading the failures and to keep adding cases, and none are solved by a bigger harness.

That's the last production layer. There's no Lesson 11 to link to: what's next is your own agent, with its own cases, and the five primitives to take it apart with when it surprises you.

**← [Back to the course](../../README.md)**
