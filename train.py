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
import sys, os, re, io, glob, json, time, random, shutil, datetime, tempfile, contextlib, subprocess, urllib.request
from datasets import load_dataset
import torch, torch.nn.functional as F
from model import Model, Tokenizer, Release, load_real, generate


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


def chunks(model, texts, length=512):                    # the pages as one stream of tokens, cut into equal pieces
    ids = [i for t in texts for i in model.encode(t + "\n\n")]
    return torch.tensor(ids[:len(ids) // (length + 1) * (length + 1)]).view(-1, length + 1)


@torch.no_grad()
def chunk_loss(model, data):
    return sum(F.cross_entropy(model.model(c[None, :-1])[0], c[1:]).item() for c in data) / len(data)


def midtrain(minutes=45):
    model = ours(BASE)
    pages = shell_pages()
    random.shuffle(pages)
    data, held_out = chunks(model, pages[200:]), chunks(model, pages[:200])[:32]   # 200 pages it never trains on
    log(f"{len(pages):,} pages, {data.numel():,} tokens; held-out loss before: {chunk_loss(model, held_out):.3f}")
    optimizer, start, step = trainable(model.model, lr=1e-5), time.time(), 0
    while time.time() - start < minutes * 60 and step < len(data) // 4:
        optimizer.zero_grad()
        for piece in data[4 * step:4 * step + 4]:        # one pass at most: four pieces a step, one at a time to fit in memory
            loss = F.cross_entropy(model.model(piece[None, :-1])[0], piece[1:])
            (loss / 4).backward()
        optimizer.step()
        step += 1
        if step % 25 == 0:
            log(f"step {step}: {(time.time() - start) / 60:.0f} minutes; loss {loss.item():.3f}")
    log(f"after {step} steps, {(time.time() - start) / 60:.0f} minutes; held-out loss after: {chunk_loss(model, held_out):.3f}")
    finish(model, "midtrain")


# ── 3. post-training: instruction-tuning ─────────────────────────────────────

def system(where=None):                                  # what quark tells the model, word for word, in the folder it works in
    where = where or "/tmp/tmp" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789_", k=8))
    return {"role": "system", "content": INSTRUCTIONS.format(where=where, today=datetime.date.today())}


def call(command):
    return {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "bash", "arguments": {"command": command}}}]}


def folder():                                            # a small made-up folder to work in
    where = tempfile.mkdtemp()
    for _ in range(random.randint(2, 5)):
        name = random.choice(NAMES) + random.choice([".txt", ".md", ".py", ".csv"])
        lines = [" ".join(random.sample(NAMES, random.randint(2, 5))) for _ in range(random.randint(1, 6))]
        open(os.path.join(where, name), "w").write("\n".join(lines) + "\n")
    return where


def run(command, where):                                 # really run it, so every result in the data is real
    ran = subprocess.run(command, shell=True, cwd=where, capture_output=True, text=True)
    return (ran.stdout + ran.stderr).strip() or "(no output)"


BUGS = [   # (function and its argument, the bug, the fix, the sed that makes it, a test: call and answer, what was wrong)
    ("double(x)", "return x * 3", "return x * 2", "s/x \\* 3/x * 2/", "double(4)", "8", "it multiplied by 3 instead of 2"),
    ("last(items)", "return items[0]", "return items[-1]", "s/items\\[0\\]/items[-1]/", "last([1, 2, 3])", "3", "it returned the first item, not the last"),
    ("is_even(n)", "return n % 2 == 1", "return n % 2 == 0", "s/== 1/== 0/", "is_even(4)", "True", "it checked for a remainder of 1, which means odd"),
    ("smallest(numbers)", "return max(numbers)", "return min(numbers)", "s/max/min/", "smallest([3, 1, 2])", "1", "it used max instead of min"),
    ("square(x)", "return x + x", "return x * x", "s/x + x/x * x/", "square(3)", "9", "it added x to itself instead of multiplying"),
    ("count_words(text)", "return len(text)", "return len(text.split())", "s/len(text)/len(text.split())/", "count_words('a b c')", "3", "it counted characters, not words"),
    ("greet(name)", 'return "Hi " + name', 'return "Hello " + name', "s/Hi /Hello /", "greet('Ann')", "'Hello Ann'", "it said Hi instead of Hello"),
]


def code_session(where):                                 # failing tests: look, run them, read the code, fix it, run them again
    function, bug, fix, sed, test, answer, why = random.choice(BUGS)
    module = random.choice([n for n in NAMES if not any(f.startswith(n) for f in os.listdir(where))])
    open(os.path.join(where, f"{module}.py"), "w").write(f"def {function}:\n    {bug}\n")
    open(os.path.join(where, f"test_{module}.py"), "w").write(
        f"import unittest\nfrom {module} import {function.split('(')[0]}\n\n\nclass Test(unittest.TestCase):\n"
        f"    def test_it(self):\n        self.assertEqual({test}, {answer})\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n")
    ask = random.choice(["The tests are failing. Can you fix them?", "Make the tests pass.", "Something's broken: the tests fail. Fix the code."])
    commands = ["ls", "python3 -B -m unittest -q", f"cat {module}.py", f"sed -i '{sed}' {module}.py", "python3 -B -m unittest -q"]   # -B: no stale cached code
    return ask, commands, lambda outs: f"Fixed: in {module}.py, {why}. It now says `{fix}`, and the tests pass."


def tool_session():                                      # a request, the commands it takes, their real results, an answer
    where = folder()
    files = sorted(os.listdir(where))
    some, other = random.choice(files), random.choice(files)
    name = random.choice([n for n in NAMES if not any(f.startswith(n) for f in files)])   # a name not taken
    word, new = random.choice(open(os.path.join(where, some)).read().split()), random.choice(NAMES)
    ext = os.path.splitext(other)[1]
    saved = name + ".txt"
    tasks = [   # reading, then answering
        ("What files are in this folder?", ["ls"], lambda out: "The files are " + ", ".join(out[-1].split()) + "."),
        (f"How many lines are in {some}?", [f"wc -l < {some}"], lambda out: f"{some} has {out[-1]} lines."),
        (f"Show me {some}.", [f"cat {some}"], lambda out: f"{some} says:\n{out[-1]}"),
        (f"Which files mention {word}?", [f"grep -l {word} *"], lambda out: "These files mention it: " + ", ".join(out[-1].split()) + "."),
        ("How many files are here?", ["ls | wc -l"], lambda out: f"There are {out[-1]} files."),
        (f"Which files here end in {ext}?", [f"ls *{ext}"], lambda out: f"These end in {ext}: " + ", ".join(out[-1].split()) + "."),
        # changing things, then looking to check, then answering from what it saw
        (f"Make a folder called {name}.", [f"mkdir {name}", "ls"], lambda out: f"I made the folder {name}; it's there now."),
        (f"Create an empty file called {saved}.", [f"touch {saved}", f"wc -c < {saved}"], lambda out: f"I created {saved}; it's empty."),
        (f"Put the word {new} in a new file called {saved}.", [f"echo {new} > {saved}", f"cat {saved}"], lambda out: f"{saved} now says {out[-1]}."),
        (random.choice([f"Save the number of lines in {some} to {saved}.", f"Put how many lines {some} has into {saved}."]),
         [f"wc -l < {some} > {saved}", f"cat {saved}"], lambda out: f"Done: {saved} says {out[-1]}, the number of lines in {some}."),
        (random.choice([f"Save the number of words in {some} to {saved}.", f"Write how many words {some} has into {saved}."]),
         [f"wc -w < {some} > {saved}", f"cat {saved}"], lambda out: f"Done: {saved} says {out[-1]}, the number of words in {some}."),
        (f"Save the first line of {some} to {saved}.", [f"head -n 1 {some} > {saved}", f"cat {saved}"], lambda out: f"Done: {saved} says: {out[-1]}"),
        (f"Sort {some} alphabetically into {saved}.", [f"sort {some} > {saved}", f"cat {saved}"], lambda out: f"Done: {saved} has the lines of {some}, sorted:\n{out[-1]}"),
        (f"Save a list of the files here to {saved}, one per line.", [f"ls > {saved}", f"cat {saved}"], lambda out: f"Done: {saved} lists them:\n{out[-1]}"),
        (f"Copy {some} to {saved}, then add a line saying {new} at its end.", [f"cp {some} {saved}", f"echo {new} >> {saved}", f"cat {saved}"],
         lambda out: f"Done: {saved} is a copy of {some} with {new} on its last line."),
        (f"Change every {word} in {some} to {new}.", [f"sed -i 's/{word}/{new}/g' {some}", f"cat {some}"], lambda out: f"Done: {some} now reads:\n{out[-1]}"),
        (f"Rename {some} to {name}{os.path.splitext(some)[1]}.", [f"mv {some} {name}{os.path.splitext(some)[1]}", "ls"],
         lambda out: f"Done: {some} is now {name}{os.path.splitext(some)[1]}."),
        (f"Remove {some}.", [f"rm {some}", "ls"], lambda out: f"I removed {some}. What's left: " + ", ".join(out[-1].split()) + "."),
        (f"Put every {ext} file into a new folder called {name}.", [f"mkdir {name}", f"mv *{ext} {name}/", f"ls {name}"],
         lambda out: f"Done: {name} now holds " + ", ".join(out[-1].split()) + "."),
    ]
    ask, commands, answer = random.choice(tasks) if random.random() < 0.85 else code_session(where)
    messages = [system(where), {"role": "user", "content": ask}]
    outs = []
    for command in commands:
        outs.append(run(command, where))
        messages += [call(command), {"role": "tool", "content": outs[-1]}]
    shutil.rmtree(where)
    return messages + [{"role": "assistant", "content": answer(outs)}]


def instruction_data(model):                             # four kinds of conversation, 400 each, in the model's own format
    smoltalk = load_dataset("HuggingFaceTB/smol-smoltalk", split="train").shuffle(seed=0)
    chats = [m for m in (row["messages"] for row in smoltalk.select(range(20000))) if sum(len(x["content"]) for x in m) < 1500][:400]
    nl2bash = list(zip(*(urllib.request.urlopen(f"https://raw.githubusercontent.com/TellinaTool/nl2bash/master/data/bash/all.{part}").read().decode().splitlines() for part in ("nl", "cm"))))
    data = [model.chat(chat, prompt=False) for chat in chats]                                                        # talk
    data += [model.chat([system(), {"role": "user", "content": ask}, call(command)], tools=[BASH], prompt=False)
             for ask, command in random.sample(nl2bash, 400)]                                                         # ask for a command
    data += [model.chat([{"role": "user", "content": row["question"]}, {"role": "assistant", "content": worked(row["answer"])}], prompt=False)
             for row in gsm8k("train")[:400]]                                                                         # reason
    data += [model.chat(tool_session(), tools=[BASH], prompt=False) for _ in range(1200)]                           # use the tool
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

def attempt(model, quark, kind, seed):                   # one try at a task, in quark, in a fresh folder: what was said, and did it pass?
    import tasks
    where, here = tempfile.mkdtemp(), os.getcwd()
    rng = random.Random(seed)
    tasks.fill(rng, where)
    ask, check = kind(rng, where)
    os.chdir(where)
    quark.BOX, quark.EPISODE = f"quark-rl-{os.getpid()}", ".quark/episodes/try.jsonl"
    try:
        quark.start_box()                                # its commands run in a container that sees only this folder
        conversation = [{"role": "user", "content": ask}]
        with contextlib.redirect_stdout(io.StringIO()):
            quark.act(conversation)                      # the harness's own loop: our model, its tool, until it hands back
        return quark.as_prompt(quark.assemble_context(conversation), prompt=False), check()
    finally:
        subprocess.run(["docker", "rm", "-f", quark.BOX], capture_output=True)
        os.chdir(here)
        shutil.rmtree(where, ignore_errors=True)


def rl(steps=60, group=8):                               # reinforcement learning in the harness: try tasks, keep what passed
    import quark_production as quark, tasks
    model = ours("checkpoints/instruct.pt")
    done = resume(model, "rl")
    quark.OURS, quark.local, quark.TEMPERATURE = "ours", model, None   # its tries sampled as its generation settings say
    quark.allowed = lambda command: True                 # as tasks.py runs it: yes to every approval, so only the never list stops it
    quark.MAX_STEPS = 10                                 # a try that hasn't finished in 10 steps has failed
    optimizer, passed = trainable(model.model, lr=5e-6), done.get("passed", [])
    for step in range(done.get("step", 0) + 1, steps + 1):
        kind = tasks.FILES[(step - 1) % len(tasks.FILES)]     # the twenty kinds of file work, in folders never scored on
        tries = [attempt(model, quark, kind, seed=1000 + step) for _ in range(group)]
        reward = torch.tensor([float(ok) for _, ok in tries])
        passed.append(reward.mean().item())
        if reward.std() > 0:                             # some passed, some failed: towards the ones that passed
            update(model, optimizer, [text for text, _ in tries], ((reward - reward.mean()) / reward.std()).tolist(), most=1536)
        log(f"step {step}: {kind.__name__}, {int(reward.sum())}/{group} passed")
        if step % 10 == 0:
            log(f"  passed in training, last 10 tasks: {sum(passed[-10:]) / 10:.0%}")
        save(model.model, "rl", step=step, passed=passed)
    finish(model, "rl")
    log("score it in the harness: uv run tasks.py checkpoints/rl.pt")


def post(*parts):                                        # post-training: imitate good conversations, then learn from graded tries
    for part in parts or ("instruct", "rl"):
        {"instruct": instruct, "rl": rl}[part]()


if __name__ == "__main__":
    torch.manual_seed(0); random.seed(0)
    os.makedirs("checkpoints", exist_ok=True)
    {"pre": pretrain, "mid": midtrain, "post": post}[sys.argv[1]](*sys.argv[2:])
