---
marp: true
theme: default
paginate: true
header: "Lesson 10 · Evaluation"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Evaluation

### A hands-on course in building agents by building their harness
Lesson 10

---

# Every change is a bet

- Lesson 9's savings: a trim might cut the line that mattered, a summary might lose a fact
- Same for any change: a prompt line, a model, a step limit, a tool
- After the change the agent still runs and the trace still looks normal
- You find out the way you do for untested software: someone uses it, and it's wrong

<!-- Lesson 9 ended on a worry, and it's not specific to performance. Nothing in the harness tells you whether the agent can still do its job. -->

---

# Evaluation finds out first

Run the agent on tasks whose right outcome you already know, check what happened, and compare with before the change.

1. **Tasks with known outcomes**
2. **Grading**
3. **Comparing**

<!-- Three parts. We'll take them one at a time, then see the code. -->

---

# Grade the world, not the words

- A case is three things: a starting state, a task, a way to tell if the outcome is right
- The outcome is checked **without the agent**: a file, an exit code, the folder afterwards
- An agent that says "done" has proved nothing; a test that passes has
- Any route that ends in the right place passes, two steps or five
- Each case starts from a fresh folder, so cases can't affect each other

<!-- "This folder has a calc.py with a bug and a test.py that fails. Fix the bug." The test passing is the outcome. -->

---

# Code grades; two judges report beside it

- **By code:** a command whose exit status says pass or fail. Cheap, exact, the same every time
- But it checks exactly what you wrote, and can be passed without doing the job
- **By a model:** shown the task and the folder before and after, asked "was it done?"
- Two judges: a language model that answers in words, and **Jev**, which only answers typed questions

*A grade you can't trust is worse than none, because you'll believe it.*

<!-- So the code's check stays the grade, and the two judges report beside it. Jev came in Lesson 5: it writes nothing, it answers a yes-or-no question with a probability. -->

---

# A result means nothing alone

- The model isn't deterministic: the same case can pass once and fail the next time
- 11 of 12 is good or bad only against something: run the same cases **before and after**
- Record steps, tokens and time too: a change can pass everything and cost twice as much
- Exit non-zero when something got worse, so a git hook or CI job runs it on **every** change

<!-- An evaluation you have to remember to run gets skipped. -->

---

# Built on the whole harness, from the outside

- It treats the agent as a box: a task goes in, the world is changed
- That runs all five primitives together, so it catches what only shows when they work together
- **Control flow:** a loop that sets up, runs, grades, records, stops
- The task goes in as **input**; the check runs as **output**; the judges use the **model interface**
- Lesson 7's trace says what happened; evaluation says whether it was right

<!-- It's the one production layer that isn't inside any one primitive. For example, a trimmed result, context, that sends the loop, control flow, round once more. -->

---

# The concept: one case, two agents (abridged)

```python
SETUP = "printf 'def add(a, b):\\n    return a - b\\n' > calc.py; printf ... > test.py"
INPUT = "test.py fails. Fix the bug in calc.py, not the test."
CHECK = "python3 test.py && grep -q 'add(2, 3)' test.py"
AGENTS = {"lesson 3": [sys.executable, LESSON_3, "agent", INPUT],
          "cheat": ["sed", "-i", "s/== 5/== -1/", "test.py"]}
```

- The check runs the test, and checks the assertion wasn't deleted
- `lesson 3` is Lesson 3's agent, started as a person would start it
- `cheat` is one `sed` I wrote: it changes what the test expects to -1

<!-- evaluation.py. The cheat stands in for an agent that games the check: the bug stays, the test now expects what the broken add returns, and the assertion is still there, so the grep is satisfied. It's a known wrong answer. -->

---

# Two judges, one question (abridged)

```python
def judges(state):
    try: jev_says = round(jev.system_one(state, {"done": DONE})...["noul"], 2)
    except Exception: jev_says = None
    llm = client.messages.create(model="claude-sonnet-5-5", ..., messages=[...])
    return jev_says, next(...).strip().upper().startswith("PASS")
```

- Same state for both: the request, the files before, the files after
- Never what the agent said; no answer from Jev is `None`, never a pass

<!-- Asking either judge is the model interface. Printing the answers beside the check is the evaluation's own control flow. Each agent gets a fresh folder, and evals.jsonl remembers what the check said last time. -->

---

# The cheat passes the check

```
lesson 3  check pass  jev 0.98  llm pass  last time -
cheat     check pass  jev 0.02  llm fail  last time -
exit 0
```

- The test runs, the assertion is there: it just asserts the wrong thing
- Both judges failed it: they saw `test.py` before and after
- The check is still the grade: judges are models, and they get things wrong

<!-- That's the disagreement worth having. The check is exact about what it checks and blind to everything else; the judges were asked the question I actually cared about. A disagreement says which run to read. Run it again and each line says "last time pass" — for the cheat too, because the comparison only compares the check. -->

---

# quark: four cases, each checkable afterwards (abridged)

```python
CASES = [
    {"name": "count", "setup": "seq 1 37 > numbers.txt", "input": "How many lines are in numbers.txt? ...",
     "check": "[ \"$(tr -d ' \\n' < answer.txt)\" = 37 ]"},
    {"name": "fix", "setup": "printf ... > calc.py; printf ... > test.py", "input": "test.py fails. ...",
     "check": "python3 test.py && grep -q 'add(2, 3)' test.py"},
    {"name": "rename", "setup": "touch a.txt b.txt c.txt", "input": "Rename every .txt file ...",
     "check": "[ -e a.md ] && [ -e b.md ] && [ -e c.md ] && ! ls *.txt 2>/dev/null"},
    {"name": "remember", "setup": "true", "input": "Remember that I prefer short answers.",
     "check": "grep -qi short .quark/memory/memory.md"},
]
```

<!-- quark.py is Lesson 9's plus 49 lines, 469 in all, in one new section before input, so --eval is caught before anything is read. The fix case is the concept's, and its check has the same blind spot the cheat walked through. Ask of every case how the agent could pass it without doing the job. -->

---

# Run quark itself, in a fresh folder (abridged)

```python
        where = tempfile.mkdtemp(prefix=f"eval-{case['name']}-")
        subprocess.run(case["setup"], shell=True, cwd=where)
        seen, start = snapshot(where), time.time()
        try: subprocess.run([sys.executable, os.path.abspath(__file__), case["input"]], cwd=where, ...)
        except subprocess.TimeoutExpired: pass
        passed = subprocess.run(case["check"], shell=True, cwd=where, ...).returncode == 0
        jev_says, llm_says = judges(case["input"], seen, snapshot(where))
```

- Not a mock: the same file, prompt, guard, sandbox, retries, routing and tracing
- `input="y\n" * 50` answers the guard's questions; its policy still blocks
- Steps and tokens come from the child's trace; a failed case keeps its folder

<!-- The working folder is the case's folder, so the sandbox mounts only that, and .quark/ is created there too. Cases can't see each other's memory. Tokens include cache reads, so they measure how much the model read, not what it cost. A case over five minutes is killed and graded on what it left behind. -->

---

# The judges, in quark (abridged)

```python
def judges(input, before, after):
    state = {"request": input, "files before": before, "files after": after}
    jev_says = ask(state, DONE)
    llm = call(max_tokens=1024, messages=[...])
    return jev_says and round(jev_says["noul"], 2), next(...).strip().upper().startswith("PASS")
```

- Jev through Lesson 5's `ask()`; the language model through `call()`, the main model
- `snapshot()`: every file, plus `.quark/memory/`, each cut to 2,000 characters
- Printed as `jev 0.97  llm pass`; `JUDGES DISAGREE` if either differs from the check
- The grade, `REGRESSED` and the exit status still come from the check

<!-- Jev says yes at 0.5 or more; its None is no opinion, not a disagreement. Asking is the model interface; deciding that the answers don't change the grade is the evaluation's control flow. -->

---

# It remembers last time

```python
    log, before = ".quark/evals.jsonl", {}
    os.makedirs(".quark", exist_ok=True)
    if os.path.exists(log):
        for line in open(log): before[json.loads(line)["case"]] = json.loads(line)["passed"]
    cases, failed = [c for c in CASES if not names or c["name"] in names], 0
```

- A case that passed last time and fails now says `REGRESSED`
- Not "it failed", but "it used to pass"
- Run some cases by name: `quark.py --eval fix rename`

<!-- Four cases is a smoke test, not a benchmark. It can tell you quark is badly broken, and it can't tell you quark is good. -->

---

# A baseline: what normal looks like

```
pass  count      2 steps    7.9s    26839 tokens  jev 0.97  llm pass
pass  fix        3 steps   10.6s    40447 tokens  jev 0.79  llm pass
pass  rename     2 steps    7.4s    26854 tokens  jev 0.97  llm pass
pass  remember   2 steps    7.4s    26912 tokens  jev 0.94  llm pass
4/4 passed
exit 0
```

- Both judges agree with every case
- About 27,000 to 40,000 tokens: the prompt is about thirteen thousand, read every step
- `fix` took a step more: it reads the code before changing it

<!-- Within a case the later steps read the prompt from the cache. Each case is a new folder with its own path in the prompt, so one case's cache doesn't serve the next. The seconds include the judging. -->

---

# Why was Jev unsure of a good fix?

- The check ran `python3 test.py`, which left `__pycache__/calc.cpython-313.pyc`
- `snapshot()` reads every file, so "files after" had binary noise in it
- Same question, same fix, three times each: **0.76, 0.81, 0.81** with it, **0.98, 0.97, 0.97** without
- The doubt was about the noise, not the fix: keep irrelevant detail out of a judge's state

<!-- Jev's makers warn that irrelevant detail can throw it. It stayed above 0.5, so nothing was flagged, but it's exactly the kind of thing that would make a disagreement for no reason. -->

---

# A change that looks harmless

<style scoped>pre { white-space: pre-wrap; }</style>

`MAX_STEPS` from 20 to 1, to cap what a run can spend:

```
pass  count      1 steps    7.0s    13399 tokens  jev 0.97  llm pass
FAIL  fix        1 steps    6.4s    13370 tokens  jev 0.02  llm fail  kept /tmp/eval-fix-kd2npnqc  REGRESSED: it passed last time
pass  rename     1 steps    6.0s    13398 tokens  jev 0.97  llm pass
pass  remember   1 steps    6.1s    13443 tokens  jev 0.94  llm pass
3/4 passed
exit 1
```

- `fix` can't be done in one step; the other three can
- Both judges agree with all four grades

<!-- Counting, renaming and writing a note each take one command. Fix can't, because the agent reads the code first. The exit code is 1. A hand test would probably have tried one of the three that still work. -->

---

# The failed case kept its folder (shortened)

```
$ cat /tmp/eval-fix-kd2npnqc/calc.py
def add(a, b):
    return a - b
```

Its trace:

```
{"event":"start"}
{"event":"routed"}
{"event":"model","stop_reason":"tool_use"}
{"event":"tool","cmd":"cat calc.py test.py"}
{"event":"stopped"}
```

<!-- The calculator still subtracts. Lesson 9's routing, one model call, which asked for cat calc.py test.py, then the guardrail's stopped: the run hit the step limit before the model saw what it read. Reading a failure like this is the most useful thing an evaluation gives you. Without Jev, with a key that isn't one, the column says "jev -" and nothing else changes. -->

---

# Other things we could do

- **Cases from reality:** every real mistake becomes a case, found in the traces
- **What passes:** final state, final answer, the path taken, or what must *not* happen
- **Noise and kinds:** pass at least once in *k*, or every time; regression cases apart from hard ones
- **When:** on every change, on a schedule, and on a sample of live traces
- **As a product:** Braintrust, LangSmith, promptfoo, Inspect run and grade cases, but can't give you the cases

<!-- A must-not case is how you test Lesson 6's guardrails. A new model version is a change you didn't make, so schedule it. Products save you the plumbing; only you know what your agent's job is. -->

---

# Ideas worth knowing

- **Variants:** a cheaper model, another prompt, a lower limit, side by side against a baseline
- **Trials:** each case several times, a handful at once; read cost next to the pass rate
- **Test the grader:** answers whose grade you know, and store what the judge said
- **Judges' limits:** Jev doesn't count, and needs the folder before to see a change
- **An independent judge:** quark's language-model judge is the agent's own model

<!-- A one-step variant was cheaper in every column because it stopped before doing the work. A judge once answered **PASS** in bold, and code that checked whether the reply started with PASS read it as a fail; the known answers hadn't caught it. A grader can pass its own check and still fail you. -->

---

# The rule

Write down what a right outcome looks like before you change anything, and then measure it after.

<!-- Cases you can check without the agent, the whole agent run on them, the world graded and not the words, enough repeats that noise doesn't pass for a result, a baseline, cost read next to pass rate, and on every change. Where a check might be passed without doing the job, a judge reports beside it, not instead of it. -->

---

# Evaluation runs the primitives, never rebuilds them

- **Control flow:** the loop under test is unchanged; the evaluation's loop is a separate one around it
- **Input:** the agent gets its task the way a person would give it
- **Context:** it doesn't edit the prompt, the memory or the working memory
- **Model interface:** the same calls; the judges go through `ask()` and `call()` afterwards
- **Output:** the tools run as always; the check is one more command beside them

<!-- It sits outside the harness and treats it as a box. -->

---

# Only the jobs you wrote down

- Four cases all passing is not a good agent; a set goes out of date
- It says something got worse, not why: that's the traces and the episode
- A few trials make noise look like signal
- A check can be passed without the job; a judge can be wrong
- None of this is solved by a bigger harness: keep reading failures, keep adding cases

<!-- That's the last production layer. There's no Lesson 11: what's next is your own agent, with its own cases, and the five primitives to take it apart with when it surprises you. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Back to the course

Your own agent, its own cases, and the five primitives
