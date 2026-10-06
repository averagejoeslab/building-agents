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
