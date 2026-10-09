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
INSTRUCTIONS = "You are quark, an agent. You act through bash, in /work. Today is {today}."   # quark.py's, word for word
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

def system():                                            # what quark tells the model, word for word
    return {"role": "system", "content": INSTRUCTIONS.format(today=datetime.date.today())}


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


def tool_session():                                      # a request, the commands it takes, their real results, an answer
    where = folder()
    files = sorted(os.listdir(where))
    some, name = random.choice(files), random.choice(NAMES)
    word = random.choice(open(os.path.join(where, some)).read().split())
    tasks = [
        ("What files are in this folder?", ["ls"], lambda out: "The files are " + ", ".join(out.split()) + "."),
        (f"How many lines are in {some}?", [f"wc -l < {some}"], lambda out: f"{some} has {out} lines."),
        (f"Show me {some}.", [f"cat {some}"], lambda out: f"{some} says:\n{out}"),
        (f"Which files mention {word}?", [f"grep -l {word} *"], lambda out: "These files mention it: " + ", ".join(out.split()) + "."),
        (f"Make a folder called {name}.", [f"mkdir {name}"], lambda out: f"I made the folder {name}."),
        (f"Create an empty file called {name}.txt.", [f"touch {name}.txt"], lambda out: f"I created {name}.txt."),
        ("How many files are here?", ["ls | wc -l"], lambda out: f"There are {out} files."),
        (f"Rename {some} to {name}{os.path.splitext(some)[1]}.", [f"mv {some} {name}{os.path.splitext(some)[1]}"], lambda out: f"Done: {some} is now {name}{os.path.splitext(some)[1]}."),
        (f"Make a folder called {name} and move {some} into it.", [f"mkdir {name}", f"mv {some} {name}/"], lambda out: f"I made {name} and moved {some} into it."),
    ]
    ask, commands, answer = random.choice(tasks)
    messages = [system(), {"role": "user", "content": ask}]
    for command in commands:
        out = run(command, where)
        messages += [call(command), {"role": "tool", "content": out}]
    shutil.rmtree(where)
    return messages + [{"role": "assistant", "content": answer(out)}]


def gsm8k(split):                                        # grade-school maths: a question, worked steps, a number
    return list(load_dataset("openai/gsm8k", "main", split=split).shuffle(seed=0))


def worked(answer):                                      # its worked answer: the steps as thinking, then the answer
    steps, number = answer.split("####")
    return "<think>\n" + re.sub(r"<<.*?>>", "", steps).strip() + f"\n</think>\n\nThe answer is {number.strip()}."


def instruction_data(model):                             # four kinds of conversation, 400 each, in the model's own format
    smoltalk = load_dataset("HuggingFaceTB/smol-smoltalk", split="train").shuffle(seed=0)
    chats = [m for m in (row["messages"] for row in smoltalk.select(range(20000))) if sum(len(x["content"]) for x in m) < 1500][:400]
    nl2bash = list(zip(*(urllib.request.urlopen(f"https://raw.githubusercontent.com/TellinaTool/nl2bash/master/data/bash/all.{part}").read().decode().splitlines() for part in ("nl", "cm"))))
    data = [model.chat(chat, prompt=False) for chat in chats]                                                        # talk
    data += [model.chat([system(), {"role": "user", "content": ask}, call(command)], tools=[BASH], prompt=False)
             for ask, command in random.sample(nl2bash, 400)]                                                         # ask for a command
    data += [model.chat([{"role": "user", "content": row["question"]}, {"role": "assistant", "content": worked(row["answer"])}], prompt=False)
             for row in gsm8k("train")[:400]]                                                                         # reason
    data += [model.chat(tool_session(), tools=[BASH], prompt=False) for _ in range(400)]                            # use the tool
    random.shuffle(data)
    return data


def tokens_and_mask(model, text, most=768):              # learn only what the assistant says, and the end of its turn
    ids, learn = [], []
    for n, piece in enumerate(re.split(r"(?<=<\|im_start\|>assistant\n)(.*?<\|im_end\|>)", text, flags=re.S)):
        piece_ids = model.encode(piece)
        ids += piece_ids
        learn += [n % 2 == 1] * len(piece_ids)
    return ids[:most], learn[:most]


def logprob(model, text, most=768):                      # how likely the model finds what the assistant said, per token
    ids, learn = tokens_and_mask(model, text, most)
    ids, keep = torch.tensor([ids]), torch.tensor([learn[1:]])
    return -F.cross_entropy(model.model(ids[:, :-1], keep=keep), ids[:, 1:][keep])


def update(model, optimizer, texts, weights, most=768):  # one step: make each text more likely, in proportion to its weight
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
