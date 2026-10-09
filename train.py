# /// script
# dependencies = ["torch", "numpy", "regex", "safetensors", "huggingface_hub", "jinja2", "datasets", "anthropic"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Training the model we built, one stage at a time, each starting from the last: uv run train.py pre | mid | post [instruct | rl]"""
import sys, os, re, io, glob, json, time, random, shutil, datetime, tempfile, functools, contextlib, subprocess, urllib.request
from datasets import load_dataset
import torch, torch.nn.functional as F
from model import Model, Tokenizer, Release, load_real, generate
from huggingface_hub import hf_hub_download


CHAT, BASE = "Qwen/Qwen3-0.6B", "Qwen/Qwen3-0.6B-Base"   # Qwen's chat format and tokenizer; Base's pre-trained numbers
INSTRUCTIONS = "You are quark, an agent. You act through bash, in {where}. Today is {today}."   # quark's, word for word
BASH = {"type": "function", "function": {"name": "bash", "description": "Run a shell command",       # quark.py's tool
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
NAMES = "apple river stone cloud maple ember pixel quartz tiger violet willow amber cobalt delta falcon harbor".split()


def log(*words):
    print(" ".join(str(w) for w in words), flush=True)


# ── 1. pre-training: predict the next token of raw text ───────────────────────

PROMPT = "ROMEO:\n"


def pretrain_text():                                     # Shakespeare: about a million characters of plays
    return urllib.request.urlopen("https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt").read().decode()


def pretrain(minutes=20):
    text = pretrain_text()
    tokenizer = Tokenizer.learn(text, 2048)           # our own tokenizer, learned from the same text
    data = torch.tensor(tokenizer.encode(text))
    cut = len(data) * 9 // 10
    data, held_out = data[:cut], data[cut:]                          # the last tenth: never trained on, to measure it fairly
    model = Model(vocab=2048, dim=256, layers=4, heads=4, kv_heads=2, head_dim=64, hidden=768)   # the same design, much smaller
    log(f"text: {len(data):,} tokens of {len(tokenizer.ids):,} kinds; model: {sum(p.numel() for p in model.parameters()):,} numbers, all random")
    speak = lambda: tokenizer.decode(sample(model, tokenizer.encode(PROMPT), 60))
    log("before:", repr(PROMPT + speak()), f"held-out loss {held_out_loss(model, held_out):.2f}")
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    start, step = time.time(), 0
    while time.time() - start < minutes * 60:
        step += 1
        starts = torch.randint(len(data) - 257, (16,))
        inputs = torch.stack([data[i:i + 256] for i in starts])
        targets = torch.stack([data[i + 1:i + 257] for i in starts])  # the same text, one token on: the next one
        loss = F.cross_entropy(model(inputs).flatten(0, 1), targets.flatten())
        optimizer.zero_grad(); loss.backward(); optimizer.step()
        if step % 100 == 0:
            log(f"step {step}: loss {loss.item():.2f}")
    log(f"after {step} steps, {minutes} minutes:", repr(PROMPT + speak()), f"held-out loss {held_out_loss(model, held_out):.2f}")
    real = load_real()                                 # now Qwen's: its numbers, and its tokenizer, in the same code
    log("Qwen3-0.6B-Base, trained on about 36 trillion tokens:", repr(PROMPT + generate(real, PROMPT, most=60)))


@torch.no_grad()
def held_out_loss(model, data):                          # the fixed score: how well it predicts text it never saw
    chunks = data[:len(data) // 257 * 257].view(-1, 257)
    return F.cross_entropy(model(chunks[:, :-1]).flatten(0, 1), chunks[:, 1:].flatten()).item()


@torch.no_grad()
def sample(model, ids, most):
    ids = torch.tensor([ids])
    for _ in range(most):
        next_id = torch.multinomial(F.softmax(model(ids[:, -256:])[:, -1] / 0.8, dim=-1), 1)
        ids = torch.cat([ids, next_id], dim=1)
    return ids[0, -most:].tolist()


# ── 2. the swap, and mid-training: the same task, on the agent's domain ──────

def ours(weights):                                       # our model: Qwen's chat format and tokenizer, with these numbers
    return Release(CHAT, weights)


def shell_pages():                                       # tldr-pages (CC BY 4.0): short pages on shell commands, with examples
    where = "checkpoints/tldr"
    if not os.path.isdir(where):
        subprocess.run(f"git clone -q --depth 1 --filter=blob:none --sparse https://github.com/tldr-pages/tldr.git {where} && "
                       f"git -C {where} sparse-checkout set pages/common pages/linux", shell=True, check=True)
    return [open(path).read() for path in sorted(glob.glob(f"{where}/pages/*/*.md"))]


def examples(page):                                      # a page's examples: what it does, in plain English, and the command
    return [(re.sub(r"[\[\]]", "", what), command) for what, command in re.findall(r"^- (.+?):\n\n`(.+?)`$", page, re.M)]


SHOTS = ("Request: show how much space a directory takes\nCommand: du -sh {{path/to/directory}}\n\n"
         "Request: print today's date\nCommand: date\n\n"
         "Request: find files by name below the current directory\nCommand: find . -name {{name}}\n\n")


@torch.no_grad()
def shell_check(model, pairs):                           # asked as a base model is asked, by example: does it pick the right command?
    right = 0
    for what, command in pairs:
        said = [w.strip("`") for w in model.generate(SHOTS + f"Request: {what}\nCommand:", most=24, temperature=0).split("\n")[0].split() if w != "sudo"]
        right += bool(said) and said[0] == command.split()[0]
    return f"{right}/{len(pairs)}"


def chunks(model, texts, length=512):                    # the pages as one stream of tokens, cut into equal pieces
    ids = [i for t in texts for i in model.encode(t + "\n\n")]
    return torch.tensor(ids[:len(ids) // (length + 1) * (length + 1)]).view(-1, length + 1)


@torch.no_grad()
def chunk_loss(model, data):
    return sum(F.cross_entropy(model.model(c[None, :-1])[0], c[1:]).item() for c in data) / len(data)


def midtrain(steps=60):                                  # a fixed number of steps, so a rerun does the same: about a quarter of the pages
    model = ours(BASE)
    every = shell_pages()
    pages = [p for p in every if all(closest(what)[0] < 0.4 for what, _ in examples(p))]   # decontaminated: none near an evaluation request
    random.shuffle(pages)
    data, held_out = chunks(model, pages[200:]), chunks(model, pages[:200])[:32]   # 200 pages it never trains on
    tests = [examples(p)[0] for p in pages[:200] if examples(p)][:100]             # one example from each: the shell check
    done = resume(model, "midtrain")
    if not done:
        log(f"{len(pages):,} pages ({len(every) - len(pages)} left out, too near an evaluation request), {data.numel():,} tokens")
        log(f"held-out loss before: {chunk_loss(model, held_out):.3f}; shell check before: {shell_check(model, tests)} right commands")
    optimizer = trainable(model.model, lr=1e-5)
    for step in range(done.get("step", 0) + 1, steps + 1):
        optimizer.zero_grad()
        for piece in data[4 * step - 4:4 * step]:        # four pieces a step, one at a time to fit in memory
            loss = F.cross_entropy(model.model(piece[None, :-1])[0], piece[1:])
            (loss / 4).backward()
        optimizer.step()
        if step % 5 == 0:
            save(model.model, "midtrain", step=step)
        if step % 25 == 0:
            log(f"step {step}: loss {loss.item():.3f}")
    log(f"after {steps} steps; held-out loss after: {chunk_loss(model, held_out):.3f}; shell check after: {shell_check(model, tests)} right commands")
    finish(model, "midtrain")


# ── 3. post-training: instruction-tuning ─────────────────────────────────────

def system(where=None):                                  # what quark tells the model, word for word, in the folder it works in
    where = where or "/tmp/tmp" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789_", k=8))
    return {"role": "system", "content": INSTRUCTIONS.format(where=where, today=datetime.date.today())}


def call(command):
    return {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "bash", "arguments": {"command": command}}}]}


def run(command, where):                                 # really run it, so every result in the data is real
    ran = subprocess.run(command, shell=True, cwd=where, capture_output=True, text=True)
    return (ran.stdout + ran.stderr).strip() or "(no output)"


# Training tasks: kept apart from tasks.py, the evaluation. Different kinds of work, different files, different words,
# so a score on tasks.py measures what carries over, not what was shown. Each kind is a request, a reference
# solution, and a check of the result: instruction-tuning keeps only demonstrations that pass it; RL uses it as the reward.

PEOPLE = "ada bo cy dee eli fay gus hal ivy jo kit lu".split()
TOPICS = "server disk cache queue backup login deploy build report invoice".split()
TRAINING = []
kind = TRAINING.append                                   # each kind: (rng, folder) -> (request, commands, answer from their output, check)


def put(where, name, text):
    open(os.path.join(where, name), "w").write(text)


def text(where, name):
    path = os.path.join(where, name)
    return open(path).read() if os.path.isfile(path) else None


def workspace(rng, where):                               # a small, realistic folder: notes, a log, scores, a config, a script
    put(where, "notes.md", "# notes\n" + "".join(f"- {rng.choice(TOPICS)} {rng.choice(['is slow', 'works', 'needs a look', 'was fixed'])}\n"
                                                for _ in range(rng.randint(3, 7))))
    put(where, "todo.md", "".join(f"- {rng.choice(['check', 'update', 'restart', 'clean'])} the {rng.choice(TOPICS)}\n" for _ in range(rng.randint(2, 5))))
    put(where, "server.log", "".join(f"10:{m:02d} {rng.choice(['INFO', 'INFO', 'WARN', 'ERROR'])} {rng.choice(TOPICS)} {rng.choice(['started', 'stopped', 'failed', 'ok'])}\n"
                                     for m in sorted(rng.sample(range(60), rng.randint(5, 12)))))
    put(where, "scores.csv", "name,score\n" + "".join(f"{p},{rng.randint(10, 99)}\n" for p in rng.sample(PEOPLE, rng.randint(3, 6))))
    put(where, "config.json", json.dumps({"name": rng.choice(TOPICS), "port": rng.randint(3000, 9000), "debug": False}, indent=2) + "\n")
    put(where, "deploy.sh", "#!/bin/sh\necho deploying\n")


def lines_of(where, name):
    return text(where, name).splitlines()


@kind
def last_lines(rng, where):
    n, out = rng.randint(2, 4), rng.choice(["recent.txt", "tail.txt", "latest.log"])
    want = lines_of(where, "server.log")[-n:]
    return (rng.choice([f"Save the last {n} lines of server.log to {out}.", f"Put the {n} most recent lines of server.log in {out}."]),
            [f"tail -n {n} server.log > {out}", f"cat {out}"], lambda o: f"Done: {out} has the last {n} lines:\n{o[-1]}",
            lambda said: (text(where, out) or "").splitlines() == want)


@kind
def log_levels(rng, where):
    out = rng.choice(["levels.txt", "kinds.txt"])
    want = sorted({line.split()[1] for line in lines_of(where, "server.log")})
    return (f"List each level that appears in server.log (INFO, WARN, ...), once each, in {out}.",
            [f"awk '{{print $2}}' server.log | sort -u > {out}", f"cat {out}"], lambda o: f"Done: {out} lists " + ", ".join(o[-1].split()) + ".",
            lambda said: (text(where, out) or "").split() == want)


@kind
def count_errors(rng, where):
    out = rng.choice(["errors.txt", "error_count.txt"])
    want = sum("ERROR" in line for line in lines_of(where, "server.log"))
    return (rng.choice([f"How many ERROR lines are in server.log? Save the number to {out}.", f"Count the errors in server.log and put the number in {out}."]),
            [f"grep -c ERROR server.log > {out}", f"cat {out}"], lambda o: f"Done: {out} says {o[-1]}.",
            lambda said: (text(where, out) or "").strip() == str(want))


@kind
def csv_names(rng, where):
    out = rng.choice(["names.txt", "people.txt"])
    want = [line.split(",")[0] for line in lines_of(where, "scores.csv")[1:]]
    return (f"Put the names from scores.csv in {out}, one per line, without the header.",
            [f"tail -n +2 scores.csv | cut -d, -f1 > {out}", f"cat {out}"], lambda o: f"Done: {out} has " + ", ".join(o[-1].split()) + ".",
            lambda said: (text(where, out) or "").split() == want)


@kind
def csv_total(rng, where):
    out = rng.choice(["total.txt", "sum.txt"])
    want = sum(int(line.split(",")[1]) for line in lines_of(where, "scores.csv")[1:])
    return (rng.choice([f"Add up the scores in scores.csv and save the total to {out}.", f"What do the scores in scores.csv add up to? Write it to {out}."]),
            [f"awk -F, 'NR > 1 {{s += $2}} END {{print s}}' scores.csv > {out}", f"cat {out}"], lambda o: f"Done: the total is {o[-1]}, in {out}.",
            lambda said: (text(where, out) or "").strip() == str(want))


@kind
def uppercase_copy(rng, where):
    source, out = rng.choice(["notes.md", "todo.md"]), rng.choice(["LOUD.md", "upper.md"])
    want = text(where, source).upper()
    return (f"Make an uppercase copy of {source} called {out}.", [f"tr a-z A-Z < {source} > {out}", f"head -n 3 {out}"],
            lambda o: f"Done: {out} is {source} in capitals; it starts:\n{o[-1]}", lambda said: text(where, out) == want)


@kind
def drop_lines(rng, where):
    topic = rng.choice([t for t in TOPICS if t in text(where, "notes.md")] or TOPICS)
    want = [line for line in lines_of(where, "notes.md") if topic not in line]
    return (rng.choice([f"Remove every line that mentions {topic} from notes.md.", f"Delete the {topic} lines from notes.md."]),
            [f"sed -i '/{topic}/d' notes.md", "cat notes.md"], lambda o: f"Done: notes.md no longer mentions {topic}:\n{o[-1]}",
            lambda said: lines_of(where, "notes.md") == want)


@kind
def nested_folders(rng, where):
    path = "/".join(rng.sample(["src", "docs", "data", "old", "2026", "tmp", "lib"], 3))
    return (f"Create the folders {path}.", [f"mkdir -p {path}", f"ls -d {path}"], lambda o: f"Done: {o[-1]} exists now.",
            lambda said: os.path.isdir(os.path.join(where, path)))


@kind
def config_port(rng, where):
    out = rng.choice(["port.txt", "port"])
    want = json.load(open(os.path.join(where, "config.json")))["port"]
    return (f"Save the port from config.json to {out}.",
            [f"""python3 -c "import json; print(json.load(open('config.json'))['port'])" > {out}""", f"cat {out}"],
            lambda o: f"Done: the port is {o[-1]}, saved in {out}.", lambda said: (text(where, out) or "").strip() == str(want))


@kind
def config_debug(rng, where):
    def check(said):
        try:
            config = json.load(open(os.path.join(where, "config.json")))
        except ValueError:
            return False
        return config.get("debug") is True and {k: v for k, v in config.items() if k != "debug"} == before
    before = {k: v for k, v in json.load(open(os.path.join(where, "config.json"))).items() if k != "debug"}
    return (rng.choice(["Turn debug on in config.json.", "Set debug to true in config.json, and leave the rest alone."]),
            ["""python3 -c "import json; c = json.load(open('config.json')); c['debug'] = True; json.dump(c, open('config.json', 'w'), indent=2)" """.strip(), "cat config.json"],
            lambda o: f"Done: config.json now has debug set to true:\n{o[-1]}", check)


@kind
def markdown_lines(rng, where):
    out = rng.choice(["md_lines.txt", "lines.txt"])
    want = sum(len(lines_of(where, f)) for f in os.listdir(where) if f.endswith(".md"))
    return (f"How many lines do the .md files have, all together? Save the number to {out}.",
            [f"cat *.md | wc -l > {out}", f"cat {out}"], lambda o: f"Done: {o[-1]} lines in all, saved in {out}.",
            lambda said: (text(where, out) or "").strip() == str(want))


@kind
def backup_csv(rng, where):
    folder_name = rng.choice(["backup", "saved", "copies"])
    want = sorted(f for f in os.listdir(where) if f.endswith(".csv"))
    return (f"Back up every .csv file into a folder called {folder_name}, keeping the originals.",
            [f"mkdir -p {folder_name}", f"cp *.csv {folder_name}/", f"ls {folder_name}"],
            lambda o: f"Done: {folder_name} has " + ", ".join(o[-1].split()) + "; the originals are still here.",
            lambda said: os.path.isdir(os.path.join(where, folder_name)) and sorted(os.listdir(os.path.join(where, folder_name))) == want
            and all(os.path.isfile(os.path.join(where, f)) for f in want))


@kind
def nth_line(rng, where):
    n, out = rng.randint(2, 4), rng.choice(["line.txt", "picked.txt"])
    want = lines_of(where, "server.log")[n - 1]
    return (f"Save line {n} of server.log to {out}.", [f"sed -n '{n}p' server.log > {out}", f"cat {out}"],
            lambda o: f"Done: {out} says: {o[-1]}", lambda said: (text(where, out) or "").strip() == want)


@kind
def add_title(rng, where):
    title = rng.choice(["Plan", "Today", "Team notes", "Ops"])
    want = [f"# {title}"] + lines_of(where, "todo.md")
    return (f"Add a title line '# {title}' at the top of todo.md.", [f"sed -i '1i # {title}' todo.md", "head -n 2 todo.md"],
            lambda o: f"Done: todo.md now starts with # {title}.", lambda said: lines_of(where, "todo.md") == want)


@kind
def make_executable(rng, where):
    return (rng.choice(["Make deploy.sh executable.", "deploy.sh won't run: make it executable."]), ["chmod +x deploy.sh", "ls -l deploy.sh"],
            lambda o: "Done: deploy.sh is executable now.", lambda said: os.access(os.path.join(where, "deploy.sh"), os.X_OK))


def unchanged(where):                                    # questions: answer, and change nothing
    before = {f: text(where, f) for f in os.listdir(where)}
    return lambda: {f: text(where, f) for f in os.listdir(where)} == before


@kind
def ask_port(rng, where):
    port, same = json.load(open(os.path.join(where, "config.json")))["port"], unchanged(where)
    return ("What port does config.json set? Don't change anything.", ["cat config.json"], lambda o: f"It sets port {port}.",
            lambda said: str(port) in said and same())


@kind
def ask_errors(rng, where):
    n, same = sum("ERROR" in line for line in lines_of(where, "server.log")), unchanged(where)
    return ("How many ERROR lines does server.log have? Just tell me.", ["grep -c ERROR server.log"], lambda o: f"server.log has {o[-1]} ERROR lines.",
            lambda said: re.search(rf"\b{n}\b", said) is not None and same())


@kind
def ask_top(rng, where):
    rows = [line.split(",") for line in lines_of(where, "scores.csv")[1:]]
    best, same = [r[0] for r in rows if int(r[1]) == max(int(r[1]) for r in rows)], unchanged(where)   # a tie: any of them
    return ("Who has the highest score in scores.csv? Don't change anything.", ["tail -n +2 scores.csv | sort -t, -k2 -nr | head -n 1"],
            lambda o: f"{o[-1].split(',')[0]}, with {o[-1].split(',')[1]}.", lambda said: any(b in said for b in best) and same())


@kind
def ask_last(rng, where):
    last, same = lines_of(where, "todo.md")[-1], unchanged(where)
    return ("What's the last item in todo.md? Don't change anything.", ["tail -n 1 todo.md"], lambda o: f"The last item is: {o[-1].lstrip('- ')}",
            lambda said: last.lstrip("- ") in said and same())


BUGS = [   # (function and its argument, the bug, the fix, the sed that makes it, a test: call and answer, what was wrong)
    ("double(x)", "return x * 3", "return x * 2", "s/x \\* 3/x * 2/", "double(4)", "8", "it multiplied by 3 instead of 2"),
    ("last(items)", "return items[0]", "return items[-1]", "s/items\\[0\\]/items[-1]/", "last([1, 2, 3])", "3", "it returned the first item, not the last"),
    ("is_even(n)", "return n % 2 == 1", "return n % 2 == 0", "s/== 1/== 0/", "is_even(4)", "True", "it checked for a remainder of 1, which means odd"),
    ("smallest(numbers)", "return max(numbers)", "return min(numbers)", "s/max/min/", "smallest([3, 1, 2])", "1", "it used max instead of min"),
    ("square(x)", "return x + x", "return x * x", "s/x + x/x * x/", "square(3)", "9", "it added x to itself instead of multiplying"),
    ("count_words(text)", "return len(text)", "return len(text.split())", "s/len(text)/len(text.split())/", "count_words('a b c')", "3", "it counted characters, not words"),
    ("greet(name)", 'return "Hi " + name', 'return "Hello " + name', "s/Hi /Hello /", "greet('Ann')", "'Hello Ann'", "it said Hi instead of Hello"),
]


@kind
def fix_code(rng, where):                                # failing tests: look, run them, read the code, fix it, run them again
    function, bug, fix, sed, test, answer, why = rng.choice(BUGS)
    module = rng.choice(["helpers", "mathlib", "util", "core", "tools"])
    put(where, f"{module}.py", f"def {function}:\n    {bug}\n")
    tests = (f"import unittest\nfrom {module} import {function.split('(')[0]}\n\n\nclass Test(unittest.TestCase):\n"
             f"    def test_it(self):\n        self.assertEqual({test}, {answer})\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n")
    put(where, f"test_{module}.py", tests)

    def check(said):
        shutil.rmtree(os.path.join(where, "__pycache__"), ignore_errors=True)   # judge the code as it is, not a stale cache
        ok = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=where, capture_output=True).returncode == 0
        return ok and text(where, f"test_{module}.py") == tests
    return (rng.choice(["The tests are failing. Can you fix them?", "Make the tests pass.", "Something's broken: the tests fail. Fix the code."]),
            ["ls", "python3 -B -m unittest -q", f"cat {module}.py", f"sed -i '{sed}' {module}.py", "python3 -B -m unittest -q"],   # -B: no stale cache
            lambda o: f"Fixed: in {module}.py, {why}. It now says `{fix}`, and the tests pass.", check)


def training_task(seed, which=None):                     # a fresh folder, and one task in it
    rng, where = random.Random(seed), tempfile.mkdtemp()
    workspace(rng, where)
    ask, commands, answer, check = (which or rng.choice(TRAINING))(rng, where)
    return where, ask, commands, answer, check


def tool_session():                                      # a verified demonstration: a request, the commands, their real results, an answer
    while True:
        where, ask, commands, answer, check = training_task(random.random())
        messages, outs = [system(where), {"role": "user", "content": ask}], []
        if random.random() < 0.5 and commands[0] not in ("ls", "cat config.json"):
            commands = ["ls"] + commands                 # sometimes, look around first
        for command in commands:
            outs.append(run(command, where))
            messages += [call(command), {"role": "tool", "content": outs[-1]}]
        reply = answer(outs)
        passed = check(reply)
        shutil.rmtree(where)
        if passed:                                       # only demonstrations that pass the check are kept
            return messages + [{"role": "assistant", "content": reply}]


def gsm8k(split):                                        # grade-school maths: a question, worked steps, a number
    return list(load_dataset("openai/gsm8k", "main", split=split).shuffle(seed=0))


def worked(answer):                                      # its worked answer: the steps as thinking, then the answer
    steps, number = answer.split("####")
    return "<think>\n" + re.sub(r"<<.*?>>", "", steps).strip() + f"\n</think>\n\nThe answer is {number.strip()}."


@functools.cache
def evaluation_requests():                               # tasks.py's requests, as sets of words: what training must not resemble
    import tasks
    requests = []
    for _, make in tasks.tasks():
        where = tempfile.mkdtemp()
        requests.append(make(where, lambda: "")[0])
        shutil.rmtree(where)
    return [(r, words(r)) for r in requests]


def words(request):                                      # what a request asks for: its words, without the ones every request has
    return set(re.findall(r"[a-z]+", request.lower())) - set("a an the and or of in into to it its this that is are be with from for on at all every each".split())


def closest(request):                                    # decontamination: the share of words it has in common with the nearest evaluation request
    words_ = words(request)
    return max((len(words_ & e) / len(words_ | e or {''}), r) for r, e in evaluation_requests())


def hermes():                                            # Hermes function-calling (Apache 2.0): many tools, in the format Qwen's comes from
    rows = json.load(open(hf_hub_download("NousResearch/hermes-function-calling-v1", "func-calling.json", repo_type="dataset")))
    for row in rows:
        try:
            yield convert(row["conversations"])
        except (ValueError, TypeError, KeyError):           # a row we can't read: skip it
            continue


def convert(turns):                                      # a Hermes conversation, as messages and the tools it used
    tools = json.loads(re.findall(r"<tools>\s*(.*?)\s*</tools>", turns[0]["value"], re.S)[-1])   # the last: the first is in its wording
    messages = []
    for turn in turns[1:]:
        if turn["from"] == "human":
            messages.append({"role": "user", "content": turn["value"]})
        elif turn["from"] == "gpt":
            calls = [json.loads(c) for c in re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", turn["value"], re.S)]
            messages.append({"role": "assistant", "content": re.sub(r"<tool_call>.*?</tool_call>", "", turn["value"], flags=re.S).strip(),
                             "tool_calls": [{"type": "function", "function": c} for c in calls]})
        else:
            messages += [{"role": "tool", "content": r} for r in re.findall(r"<tool_response>\s*(.*?)\s*</tool_response>", turn["value"], re.S)]
    used = {c["function"]["name"] for m in messages for c in m.get("tool_calls", [])}
    return messages, [t for t in tools if t["function"]["name"] in used]    # the tools it used: shorter, so it fits


def instruction_data(model):                             # six kinds of conversation, in the model's own format, none near the evaluation
    near = lambda request: closest(request)[0] >= 0.4    # decontamination: too close to an evaluation request
    fits = lambda text: len(model.encode(text)) <= 1024
    smoltalk = load_dataset("HuggingFaceTB/smol-smoltalk", split="train").shuffle(seed=0)
    chats = [m for m in (row["messages"] for row in smoltalk.select(range(20000))) if sum(len(x["content"]) for x in m) < 1500 and not near(m[0]["content"])][:300]
    nl2bash = list(zip(*(urllib.request.urlopen(f"https://raw.githubusercontent.com/TellinaTool/nl2bash/master/data/bash/all.{part}").read().decode().splitlines() for part in ("nl", "cm"))))
    functions = [t for t in (model.chat(m, tools=tools, prompt=False) for m, tools in hermes() if not near(m[0]["content"])) if fits(t)]
    code = load_dataset("ise-uiuc/Magicoder-OSS-Instruct-75K", split="train").shuffle(seed=0).select(range(5000))
    data = [model.chat(chat, prompt=False) for chat in chats]                                                        # talk
    data += [model.chat([system(), {"role": "user", "content": ask}, call(command)], tools=[BASH], prompt=False)
             for ask, command in random.sample([row for row in nl2bash if not near(row[0])], 300)]                     # ask for a command
    data += [model.chat([{"role": "user", "content": row["question"]}, {"role": "assistant", "content": worked(row["answer"])}], prompt=False)
             for row in gsm8k("train")[:300]]                                                                         # reason
    data += random.sample(functions, min(300, len(functions)))                                                       # call tools, many kinds
    data += [t for t in (model.chat([{"role": "user", "content": row["problem"]}, {"role": "assistant", "content": row["solution"]}], prompt=False)
                         for row in code if not near(row["problem"])) if fits(t)][:300]                              # write code
    data += [model.chat(tool_session(), tools=[BASH], prompt=False) for _ in range(900)]                            # use the tool: verified demonstrations
    random.shuffle(data)
    return data


def tokens_and_mask(model, text, most=1024):              # learn only what the assistant says, and the end of its turn
    ids, learn = [], []
    for n, piece in enumerate(re.split(r"(?<=<\|im_start\|>assistant\n)(.*?<\|im_end\|>)", text, flags=re.S)):
        piece_ids = model.encode(piece)
        ids += piece_ids
        learn += [n % 2 == 1] * len(piece_ids)
    return ids[:most], learn[:most]


def logprob(model, text, most=1024):                      # how likely the model finds what the assistant said, per token
    ids, learn = tokens_and_mask(model, text, most)
    ids, keep = torch.tensor([ids]), torch.tensor([learn[1:]])
    return -F.cross_entropy(model.model(ids[:, :-1], keep=keep), ids[:, 1:][keep])


def update(model, optimizer, texts, weights, most=1024):  # one step: make each text more likely, in proportion to its weight
    optimizer.zero_grad()
    for text, weight in zip(texts, weights):             # one at a time, to fit in memory
        (-weight * logprob(model, text, most) / len(texts)).backward()
    optimizer.step()


@torch.no_grad()
def held_out(model, texts):
    return -sum(logprob(model, t).item() for t in texts) / len(texts)


def trainable(model, lr):                                # every number, the vocabulary too: Base barely knows <|im_end|>
    return torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0)


def save(model, name, **progress):                       # the numbers, and how far it got, so an interruption costs little
    torch.save({k: v.to(torch.bfloat16) for k, v in model.state_dict().items()}, f"checkpoints/{name}.pt")
    json.dump(progress, open(f"checkpoints/{name}.progress", "w"))


def resume(model, name):                                 # carry on from the last save, if there is one (the optimizer starts afresh)
    if not os.path.exists(f"checkpoints/{name}.progress"):
        return {}
    model.model.load_state_dict({k: v.float() for k, v in torch.load(f"checkpoints/{name}.pt").items()})
    progress = json.load(open(f"checkpoints/{name}.progress"))
    log(f"carrying on from {progress}")
    return progress


def finish(model, name):
    save(model.model, name)
    os.remove(f"checkpoints/{name}.progress")


def show(model):                                         # real replies: talk, a tool call, and reasoning
    for messages, tools, thinking in [([{"role": "user", "content": "How do I make a cup of tea?"}], None, False),
                                      ([system(), {"role": "user", "content": "Count the lines in notes.txt."}], [BASH], False),
                                      ([{"role": "user", "content": gsm8k("test")[0]["question"]}], None, True)]:
        log(f"  > {messages[-1]['content']}\n  < " + model.generate(model.chat(messages, tools, thinking), most=300, temperature=0).replace("\n", "\n    "))


def instruct():
    if os.path.exists("checkpoints/instruct.pt") and not os.path.exists("checkpoints/instruct.progress"):
        return log("already instruction-tuned")
    model = ours("checkpoints/midtrain.pt")
    data = instruction_data(model)
    test, data = data[:48], data[48:]                    # held out: the fixed score for this stage
    done = resume(model, "instruct")
    if not done:
        requests = [r for t in data for r in re.findall(r"<\|im_start\|>user\n(.*?)<\|im_end\|>", t, re.S) if not r.startswith("<tool_response>")]
        (overlap, evaluation), training = max((closest(r), r) for r in requests)
        log(f"decontamination: of {len(requests)} training requests, the closest to an evaluation request shares {overlap:.0%} of their words:"
            f"\n  training:   {training!r}\n  evaluation: {evaluation!r}")
        log(f"{len(data)} conversations; held-out loss before: {held_out(model, test):.3f}")
        log("before:"); show(model)
    optimizer, start, earlier = trainable(model.model, lr=1e-5), time.time(), done.get("minutes", 0)
    for step in range(done.get("step", 0) + 1, len(data) // 8 + 1):   # one pass: a second made the held-out loss rise
        update(model, optimizer, data[8 * step - 8:8 * step], [1.0] * 8)    # every example counts the same: imitate it
        minutes = earlier + (time.time() - start) / 60
        if step % 10 == 0:
            save(model.model, "instruct", step=step, minutes=minutes)
        if step % 25 == 0:
            log(f"step {step}: {minutes:.0f} minutes")
    log(f"after {step} steps, {minutes:.0f} minutes; held-out loss after: {held_out(model, test):.3f}")
    log("after:"); show(model)
    finish(model, "instruct")


# ── 4. post-training, part two: reinforcement learning, in the harness ──────

def attempt(model, quark, kind, seed):                   # one try at a training task, in quark, in a fresh folder: what was said, and did it pass?
    where, ask, _, _, check = training_task(seed, kind)  # the same folder for every try at this seed
    here = os.getcwd()
    os.chdir(where)
    quark.BOX, quark.EPISODE = f"quark-rl-{os.getpid()}", ".quark/episodes/try.jsonl"
    try:
        quark.start_box()                                # its commands run in a container that sees only this folder
        conversation = [{"role": "user", "content": ask}]
        with contextlib.redirect_stdout(io.StringIO()):
            quark.act(conversation)                      # the harness's own loop: our model, its tool, until it hands back
        last = conversation[-1]["content"]
        said = last if isinstance(last, str) else " ".join(b.text for b in last if b.type == "text")
        return quark.as_prompt(quark.assemble_context(conversation), prompt=False), check(said)
    finally:
        subprocess.run(["docker", "rm", "-f", quark.BOX], capture_output=True)
        os.chdir(here)
        shutil.rmtree(where, ignore_errors=True)


def held_out_tasks(model, quark):                        # RL's own held-out check: training kinds, in folders it never trains on, once each
    quark.TEMPERATURE = 0                                # the most likely reply, so the score repeats
    passed = sum(attempt(model, quark, TRAINING[n % len(TRAINING)], seed=10_000 + n)[1] for n in range(40))
    quark.TEMPERATURE = None                             # tries in training: sampled as its generation settings say
    return f"{passed}/40"


def rl(steps=60, group=8):                               # reinforcement learning in the harness: try training tasks, keep what passed
    import quark_production as quark
    model = ours("checkpoints/instruct.pt")
    done = resume(model, "rl")
    quark.OURS, quark.local, quark.TEMPERATURE = "ours", model, None   # its tries sampled as its generation settings say
    quark.allowed = lambda command: True                 # as tasks.py runs it: yes to every approval, so only the never list stops it
    quark.MAX_STEPS = 10                                 # a try that hasn't finished in 10 steps has failed
    if not done:
        log(f"held-out training tasks before: {held_out_tasks(model, quark)} passed")
    optimizer, passed = trainable(model.model, lr=5e-6), done.get("passed", [])
    for step in range(done.get("step", 0) + 1, steps + 1):
        kind = TRAINING[(step - 1) % len(TRAINING)]      # the training tasks, never tasks.py's: that's the evaluation
        tries = [attempt(model, quark, kind, seed=step) for _ in range(group)]
        reward = torch.tensor([float(ok) for _, ok in tries])
        passed.append(reward.mean().item())
        if reward.std() > 0:                             # some passed, some failed: towards the ones that passed
            update(model, optimizer, [text for text, _ in tries], ((reward - reward.mean()) / reward.std()).tolist(), most=1536)
        log(f"step {step}: {kind.__name__}, {int(reward.sum())}/{group} passed")
        if step % 10 == 0:
            log(f"  passed in training, last 10 tasks: {sum(passed[-10:]) / 10:.0%}")
        save(model.model, "rl", step=step, passed=passed)
    log(f"held-out training tasks after: {held_out_tasks(model, quark)} passed")
    finish(model, "rl")
    log("score it in the harness: uv run tasks.py checkpoints/rl.pt")


def post(*parts):                                        # post-training: imitate good conversations, then learn from graded tries
    for part in parts or ("instruct", "rl"):
        {"instruct": instruct, "rl": rl}[part]()


if __name__ == "__main__":
    torch.manual_seed(0); random.seed(0)
    os.makedirs("checkpoints", exist_ok=True)
    {"pre": pretrain, "mid": midtrain, "post": post}[sys.argv[1]](*sys.argv[2:])
