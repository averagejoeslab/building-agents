# /// script
# dependencies = ["torch", "numpy", "regex", "safetensors", "huggingface_hub", "datasets", "jinja2"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Training the model, one stage at a time, each starting from the last: uv run train.py <stage>
Stages, in order: pretrain, midtrain, instruct, reason, harness."""
import sys, os, re, glob, json, time, random, shutil, datetime, tempfile, subprocess, urllib.request
from datasets import load_dataset
import torch, torch.nn.functional as F
import model as M, quark_local as Q, tasks as T

torch.manual_seed(0); random.seed(0)
os.makedirs("checkpoints", exist_ok=True)
CHAT, BASE = "Qwen/Qwen3-0.6B", "Qwen/Qwen3-0.6B-Base"   # Qwen's chat format and tokenizer; Base's pre-trained numbers


def log(*words):                                         # every stage writes what it did to runs/
    line = " ".join(str(w) for w in words)
    print(line, flush=True)
    with open(f"runs/{STAGE}.txt", "a") as file:
        file.write(line + "\n")


# ── 7. pre-training: predict the next token of raw text ───────────────────────

PROMPT = "ROMEO:\n"


def pretrain_text():                                     # Shakespeare: about a million characters of plays
    return urllib.request.urlopen("https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt").read().decode()


def pretrain(minutes=20):
    text = pretrain_text()
    tokenizer = M.Tokenizer.learn(text, 2048)           # our own tokenizer, learned from the same text
    data = torch.tensor(tokenizer.encode(text))
    cut = len(data) * 9 // 10
    data, held_out = data[:cut], data[cut:]                          # the last tenth: never trained on, to measure it fairly
    model = M.Model(vocab=2048, dim=256, layers=4, heads=4, kv_heads=2, head_dim=64, hidden=768)   # the same design, much smaller
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
    real = M.load_real()                                 # now Qwen's: its numbers, and its tokenizer, in the same code
    log("Qwen3-0.6B-Base, trained on about 36 trillion tokens:", repr(PROMPT + M.generate(real, PROMPT, most=60)))


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


# ── 8. the swap, and mid-training: the same task, on the agent's domain ──────

def ours(weights):                                       # our model: Qwen's chat format and tokenizer, with these numbers
    return M.Release(CHAT, weights)


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
    save(model.model, "midtrain")


# ── 9. instruction-tuning: take turns, answer, and use the tool ──────────────

def system():                                            # what quark tells the model, word for word
    return {"role": "system", "content": Q.INSTRUCTIONS["plain"].format(today=datetime.date.today())}


def call(command):
    return {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "bash", "arguments": {"command": command}}}]}


def folder():                                            # a small made-up folder to work in
    where = tempfile.mkdtemp()
    for _ in range(random.randint(2, 5)):
        name = random.choice(T.WORDS) + random.choice([".txt", ".md", ".py", ".csv"])
        lines = [" ".join(random.sample(T.WORDS, random.randint(2, 5))) for _ in range(random.randint(1, 6))]
        open(os.path.join(where, name), "w").write("\n".join(lines) + "\n")
    return where


def run(command, where):                                 # really run it, so every result in the data is real
    ran = subprocess.run(command, shell=True, cwd=where, capture_output=True, text=True)
    return (ran.stdout + ran.stderr).strip() or "(no output)"


def tool_session():                                      # a request, the commands it takes, their real results, an answer
    where = folder()
    files = sorted(os.listdir(where))
    some, name = random.choice(files), random.choice(T.WORDS)
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
    data += [model.chat([system(), {"role": "user", "content": ask}, call(command)], tools=[Q.bash], prompt=False)
             for ask, command in random.sample(nl2bash, 400)]                                                         # ask for a command
    data += [model.chat([{"role": "user", "content": row["question"]}, {"role": "assistant", "content": worked(row["answer"])}], prompt=False)
             for row in gsm8k("train")[:400]]                                                                         # reason
    data += [model.chat(tool_session(), tools=[Q.bash], prompt=False) for _ in range(400)]                            # use the tool
    random.shuffle(data)
    return data


def tokens_and_mask(model, text):                        # learn only what the assistant says, and the end of its turn
    ids, learn = [], []
    for n, piece in enumerate(re.split(r"(?<=<\|im_start\|>assistant\n)(.*?<\|im_end\|>)", text, flags=re.S)):
        piece_ids = model.encode(piece)
        ids += piece_ids
        learn += [n % 2 == 1] * len(piece_ids)
    return ids[:768], learn[:768]


def logprob(model, text):                                # how likely the model finds what the assistant said, per token
    ids, learn = tokens_and_mask(model, text)
    ids, keep = torch.tensor([ids]), torch.tensor([learn[1:]])
    return -F.cross_entropy(model.model(ids[:, :-1], keep=keep), ids[:, 1:][keep])


def update(model, optimizer, texts, weights):            # one step: make each text more likely, in proportion to its weight
    optimizer.zero_grad()
    for text, weight in zip(texts, weights):             # one at a time, to fit in memory
        (-weight * logprob(model, text) / len(texts)).backward()
    optimizer.step()


@torch.no_grad()
def held_out(model, texts):
    return -sum(logprob(model, t).item() for t in texts) / len(texts)


def trainable(model, lr):                                # every number, the vocabulary too: Base barely knows <|im_end|>
    return torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0)


def save(model, name):
    torch.save({k: v.to(torch.bfloat16) for k, v in model.state_dict().items()}, f"checkpoints/{name}.pt")


def show(model):                                         # real replies: talk, a tool call, and reasoning
    for messages, tools, thinking in [([{"role": "user", "content": "How do I make a cup of tea?"}], None, False),
                                      ([system(), {"role": "user", "content": "Count the lines in notes.txt."}], [Q.bash], False),
                                      ([{"role": "user", "content": gsm8k("test")[0]["question"]}], None, True)]:
        log(f"  > {messages[-1]['content']}\n  < " + model.generate(model.chat(messages, tools, thinking), most=300, temperature=0).replace("\n", "\n    "))


def instruct():
    model = ours("checkpoints/midtrain.pt")
    data = instruction_data(model)
    test, data = data[:48], data[48:]                    # held out: the fixed score for this stage
    log(f"{len(data)} conversations; held-out loss before: {held_out(model, test):.3f}")
    log("before:"); show(model)
    optimizer, start = trainable(model.model, lr=1e-5), time.time()
    for step in range(1, len(data) // 8 + 1):          # one pass: a second made the held-out loss rise
        update(model, optimizer, data[8 * step - 8:8 * step], [1.0] * 8)    # every example counts the same: imitate it
        if step % 25 == 0:
            log(f"step {step}: {(time.time() - start) / 60:.0f} minutes")
    log(f"after {step} steps, {(time.time() - start) / 60:.0f} minutes; held-out loss after: {held_out(model, test):.3f}")
    log("after:"); show(model)
    save(model.model, "instruct")


# ── 10. reinforcement learning with a verifier: try, check, learn ────────────

def right(text, answer):                                 # the verifier: is the final number correct?
    found = re.findall(r"answer is \$?(-?[\d,]*\.?\d+)", text)
    return bool(found) and float(found[-1].replace(",", "")) == float(answer.split("####")[1].strip().replace(",", ""))


def question(model, row):
    return model.chat([{"role": "user", "content": row["question"]}], thinking=True)


@torch.no_grad()
def samples(model, prompt, n, most=320, temperature=1.0):    # n answers to one question, generated side by side
    ids, caches = torch.tensor([model.encode(prompt)] * n), [{} for _ in model.model.layers]
    scores, out, done = model.model(ids, caches)[:, -1], [[] for _ in range(n)], [False] * n
    for step in range(most):
        next_ids = torch.multinomial(F.softmax(scores / temperature, dim=-1), 1)
        for row, token in enumerate(next_ids[:, 0].tolist()):
            if not done[row]:
                done[row] = token in model.stops
                if not done[row]:
                    out[row].append(token)
        if all(done):
            break
        scores = model.model(next_ids, caches, start=ids.shape[1] + step)[:, -1]
    return [model.decode(o) for o in out]


def accuracy(model, questions):                          # the fixed score: greedy answers to questions it never trains on
    return sum(right(model.generate(question(model, row), most=320, temperature=0), row["answer"]) for row in questions) / len(questions)


def reason(minutes=90, group=8):
    model = ours("checkpoints/instruct.pt")
    test, train = gsm8k("test")[:100], gsm8k("train")[400:]    # past the 400 used in instruction-tuning
    log(f"held-out accuracy before: {accuracy(model, test):.0%} of {len(test)} test questions")
    optimizer, start, step, rewards = trainable(model.model, lr=2e-6), time.time(), 0, []
    while time.time() - start < minutes * 60:
        row = train[step]
        step += 1
        prompt = question(model, row)
        answers = samples(model, prompt, group)
        reward = torch.tensor([float(right(a, row["answer"])) for a in answers])
        rewards.append(reward.mean().item())
        if reward.std() > 0:                             # some right, some wrong: towards the right ones, away from the wrong
            advantage = (reward - reward.mean()) / reward.std()
            update(model, optimizer, [prompt + a + "<|im_end|>" for a in answers], advantage.tolist())
        if step % 10 == 0:
            log(f"step {step}: {(time.time() - start) / 60:.0f} minutes; right in training, last 10 questions: {sum(rewards[-10:]) / 10:.0%}")
    log(f"after {step} questions, {minutes} minutes; held-out accuracy after: {accuracy(model, test):.0%}")
    save(model.model, "reason")


# ── 11. in the harness: train it where it works, with the checks as the reward ─

def score(model, show=log):                              # the fixed score: forty tasks it never trains on
    return T.score(lambda ask, where: Q.session(model, ask, where), show=lambda line: show("  " + line))


def attempt(model, n):                                   # one try at a practice task: the whole session, and did it pass?
    ask, where, check = T.make(T.TASKS[n % len(T.TASKS)], 3_000_000 + n)   # seeds the evaluation never uses
    conversation = Q.session(model, ask, where)
    try:
        passed = check()
    except Exception:
        passed = False
    shutil.rmtree(where, ignore_errors=True)
    return model.chat([system()] + conversation, tools=[Q.bash], prompt=False), passed


def harness(minutes=120, group=4):                       # reinforcement learning in the harness: the checks are the reward
    model = ours("checkpoints/reason.pt")
    log("before, on the forty evaluation tasks:")
    log(f"before: {score(model):.0%}")
    optimizer, start, step, rewards = trainable(model.model, lr=2e-6), time.time(), 0, []
    while time.time() - start < minutes * 60:
        tries = [attempt(model, step) for _ in range(group)]   # the same task, several tries
        step += 1
        reward = torch.tensor([float(passed) for _, passed in tries])
        rewards.append(reward.mean().item())
        if reward.std() > 0:
            advantage = (reward - reward.mean()) / reward.std()
            update(model, optimizer, [text for text, _ in tries], advantage.tolist())
        if step % 10 == 0:
            log(f"step {step}: {(time.time() - start) / 60:.0f} minutes; passed in practice, last 10 tasks: {sum(rewards[-10:]) / 10:.0%}")
            save(model.model, "harness")
    save(model.model, "harness")
    log(f"after {step} practice tasks, {minutes} minutes. On the forty evaluation tasks:")
    log(f"after: {score(model):.0%}")


if __name__ == "__main__":
    STAGE = sys.argv[1]
    open(f"runs/{STAGE}.txt", "w").close()
    {"pretrain": pretrain, "midtrain": midtrain, "instruct": instruct, "reason": reason, "harness": harness}[STAGE]()
