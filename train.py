# /// script
# dependencies = ["torch", "numpy", "tokenizers", "safetensors", "huggingface_hub", "datasets"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Training the model: pre-training, then post-training. Run one stage at a time: uv run train.py <stage>"""
import sys, os, re, glob, time, random, shutil, tempfile, subprocess, urllib.request, collections
from datasets import load_dataset
import torch, torch.nn.functional as F
import model as M, quark_local as Q, tasks as T
from quark_local import turn

torch.manual_seed(0); random.seed(0)
os.makedirs("checkpoints", exist_ok=True)
STOPS = {M.encode("<|im_end|>")[0], M.encode("<|endoftext|>")[0]}


def log(*words):                                         # every stage writes what it did to runs/
    line = " ".join(str(w) for w in words)
    print(line, flush=True)
    with open(f"runs/{STAGE}.txt", "a") as file:
        file.write(line + "\n")


# ── 7. pre-training: predict the next token of raw text ───────────────────────

def pretrain_text():                                     # text and code: Python's own source, and a public-domain book
    code = "".join(open(path, errors="ignore").read() for path in sorted(glob.glob("/usr/lib/python3.11/*.py")))
    book = urllib.request.urlopen("https://www.gutenberg.org/cache/epub/11/pg11.txt").read().decode()
    return book * 4 + code                               # the end of the code, seen once, is held out below


def pretrain(minutes=20):
    ids = M.encode(pretrain_text())
    common = [i for i, _ in collections.Counter(ids).most_common(8191)]
    small = {token: n for n, token in enumerate(common)}             # the 8,191 most common tokens, plus one for the rest
    data = torch.tensor([small.get(i, 8191) for i in ids])
    data, held_out = data[:-20_000], data[-20_000:]                  # text it never trains on, to measure it fairly
    model = M.Model(vocab=8192, dim=256, layers=4, heads=4, kv_heads=2, head_dim=64, hidden=768)   # the same design, much smaller
    log(f"text: {len(data):,} tokens; model: {sum(p.numel() for p in model.parameters()):,} numbers, all random")
    speak = lambda: M.decode([common[i] for i in sample(model, [small[t] for t in M.encode("def ")], 40) if i < 8191])
    log("before:", repr("def " + speak()), f"held-out loss {held_out_loss(model, held_out):.2f}")
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
    log(f"after {step} steps, {minutes} minutes:", repr("def " + speak()), f"held-out loss {held_out_loss(model, held_out):.2f}")
    real = M.load_real()
    log("the real weights, months of training on trillions of tokens:", repr("def " + M.generate(real, "def ", most=40)))


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


# ── 8. instruction-tuning: take turns, answer, and ask for tools ─────────────

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
        (f"How many files are here?", ["ls | wc -l"], lambda out: f"There are {out} files."),
        (f"Rename {some} to {name}{os.path.splitext(some)[1]}.", [f"mv {some} {name}{os.path.splitext(some)[1]}"], lambda out: f"Done: {some} is now {name}{os.path.splitext(some)[1]}."),
        (f"Make a folder called {name} and move {some} into it.", [f"mkdir {name}", f"mv {some} {name}/"], lambda out: f"I made {name} and moved {some} into it."),
    ]
    ask, commands, answer = random.choice(tasks)
    text = turn("system", Q.INSTRUCTIONS.format(where="/work")) + turn("user", ask)
    for command in commands:
        out = run(command, where)
        text += turn("assistant", f"<bash>{command}</bash>") + turn("tool", out)
    shutil.rmtree(where)
    return text + turn("assistant", answer(out))


def instruction_data():                                  # four kinds of example, 800 each
    smoltalk = load_dataset("HuggingFaceTB/smol-smoltalk", split="train").shuffle(seed=0)
    chats = [m for m in (row["messages"] for row in smoltalk.select(range(20000))) if sum(len(x["content"]) for x in m) < 1500][:800]
    nl2bash = list(zip(*(urllib.request.urlopen(f"https://raw.githubusercontent.com/TellinaTool/nl2bash/master/data/bash/all.{part}").read().decode().splitlines() for part in ("nl", "cm"))))
    data = ["".join(turn(m["role"], m["content"]) for m in chat) for chat in chats]                          # talk
    data += [turn("system", Q.INSTRUCTIONS.format(where="/work")) + turn("user", ask) + turn("assistant", f"<bash>{command}</bash>")
             for ask, command in random.sample(nl2bash, 800)]                                                # ask for a command
    data += [turn("user", row["question"]) + turn("assistant", worked(row["answer"])) for row in gsm8k("train")[:800]]   # reason
    data += [tool_session() for _ in range(800)]                                                            # use a tool and answer
    random.shuffle(data)
    return data


def gsm8k(split):                                        # grade-school maths: a question, worked steps, a number
    return list(load_dataset("openai/gsm8k", "main", split=split).shuffle(seed=0))


def worked(answer):                                      # its worked answer, in our format: think, then answer
    steps, number = answer.split("####")
    return "<think>\n" + re.sub(r"<<.*?>>", "", steps).strip() + f"\n</think>\nThe answer is {number.strip()}."


def tokens_and_mask(text):                               # learn only from what the assistant says
    ids, learn = [], []
    for piece in re.split(r"(<\|im_start\|>assistant\n.*?<\|im_end\|>)", text, flags=re.S):
        piece_ids = M.encode(piece)
        ids += piece_ids
        learn += [piece.startswith("<|im_start|>assistant")] * len(piece_ids)
    return ids[:1024], learn[:1024]


def logprob(model, text):                                # how likely the model finds what the assistant said, per token
    ids, learn = tokens_and_mask(text)
    ids, keep = torch.tensor([ids]), torch.tensor([learn[1:]])
    return -F.cross_entropy(model(ids[:, :-1], keep=keep), ids[:, 1:][keep])


def update(model, optimizer, texts, weights):            # one step: make each text more likely, in proportion to its weight
    optimizer.zero_grad()
    for text, weight in zip(texts, weights):             # one at a time, to fit in memory
        (-weight * logprob(model, text) / len(texts)).backward()
    optimizer.step()


@torch.no_grad()
def held_out(model, texts):
    return -sum(logprob(model, t).item() for t in texts) / len(texts)


def trainable(model, lr):                                # keep the vocabulary's meanings fixed: less memory, same result at this scale
    model.embed_tokens.weight.requires_grad_(False)
    return torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.0)


def save(model, name):
    torch.save({k: v.to(torch.bfloat16) for k, v in model.state_dict().items()}, f"checkpoints/{name}.pt")


PROMPTS = ["How do I make a cup of tea?", "List the files in this folder.",
           "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?"]


def show(model):
    for ask in PROMPTS:
        context = (turn("system", Q.INSTRUCTIONS.format(where="/work")) if "files" in ask else "") + turn("user", ask) + "<|im_start|>assistant\n"
        log(f"  {ask!r} ->", repr(M.generate(model, context, most=120, stop=("<|im_end|>", "<|endoftext|>"))))


def instruct(minutes=150):
    data = instruction_data()
    test, data = data[:48], data[48:]                    # held out: the fixed score for this stage
    model = M.load_real()
    optimizer = trainable(model, lr=1e-5)
    log(f"{len(data)} conversations; held-out loss before: {held_out(model, test):.3f}")
    log("before (pre-trained only):"); show(model)
    start, step = time.time(), 0
    while time.time() - start < minutes * 60:
        step += 1
        update(model, optimizer, random.sample(data, 8), [1.0] * 8)    # every example counts the same: imitate it
        if step % 10 == 0:
            log(f"step {step}: {(time.time() - start) / 60:.0f} minutes; held-out loss {held_out(model, test[:8]):.3f}")
        if step % 100 == 0:
            save(model, "instruct")                      # save along the way: look at it, or stop early, without losing the run
    log(f"after {step} steps, {minutes} minutes; held-out loss after: {held_out(model, test):.3f}")
    log("after (instruction-tuned):"); show(model)
    save(model, "instruct")


# ── 9. reasoning: try, check, and learn from what worked (GRPO) ──────────────

def answer_of(text):
    found = re.findall(r"answer is \$?(-?[\d,]*\.?\d+)", text)
    return float(found[-1].replace(",", "")) if found else None


def right(text, answer):                                 # the verifier: is the final number correct?
    return answer_of(text) == float(answer.split("####")[1].strip().replace(",", ""))


@torch.no_grad()
def samples(model, prompt, n, most=300, temperature=1.0):    # n answers to one question, generated side by side
    ids, caches = torch.tensor([M.encode(prompt)] * n), [{} for _ in model.layers]
    scores, out, done = model(ids, caches)[:, -1], [[] for _ in range(n)], [False] * n
    for step in range(most):
        next_ids = torch.multinomial(F.softmax(scores / temperature, dim=-1), 1)
        for row, token in enumerate(next_ids[:, 0].tolist()):
            if not done[row]:
                out[row].append(token)
                done[row] = token in STOPS
        if all(done):
            break
        scores = model(next_ids, caches, start=ids.shape[1] + step)[:, -1]
    return [M.decode(o).split("<|im_end|>")[0].split("<|endoftext|>")[0] for o in out]


def accuracy(model, questions):                          # the fixed score: greedy answers to questions it never trains on
    correct = 0
    for row in questions:
        correct += right(M.generate(model, turn("user", row["question"]) + "<|im_start|>assistant\n", most=400, stop=("<|im_end|>", "<|endoftext|>")), row["answer"])
    return correct / len(questions)


def reason(minutes=150, group=8):
    test, train = gsm8k("test")[:100], gsm8k("train")[800:]                  # past the 800 used in instruction-tuning
    model = Q.load("checkpoints/instruct.pt")
    optimizer = trainable(model, lr=2e-6)                # small steps: it learns from its own noisy attempts
    log(f"held-out accuracy before: {accuracy(model, test):.0%} of {len(test)} test questions")
    start, step, rewards = time.time(), 0, []
    while time.time() - start < minutes * 60:
        row = train[step]
        step += 1
        prompt = turn("user", row["question"]) + "<|im_start|>assistant\n"
        answers = samples(model, prompt, group)
        reward = torch.tensor([float(right(a, row["answer"])) for a in answers])
        rewards.append(reward.mean().item())
        if reward.std() > 0:                             # some right, some wrong: push toward the right ones, away from the wrong
            advantage = (reward - reward.mean()) / reward.std()
            update(model, optimizer, [prompt + a + "<|im_end|>\n" for a in answers], advantage.tolist())
        if step % 10 == 0:
            log(f"step {step}: {(time.time() - start) / 60:.0f} minutes; right in training, last 10 questions: {sum(rewards[-10:]) / 10:.0%}")
            save(model, "reason")
    log(f"after {step} questions, {minutes} minutes; held-out accuracy after: {accuracy(model, test):.0%}")
    log("an answer after:", repr(M.generate(model, turn("user", test[0]["question"]) + "<|im_start|>assistant\n", most=400, stop=("<|im_end|>",))))
    save(model, "reason")


# ── 10. in the harness: learn from its own successes, then from rewards ──────

def practice_task(n):                                    # training tasks: every kind, seeds the evaluation never uses
    return T.make(T.TASKS[n % len(T.TASKS)], 1_000_000 + n)


def attempt(model, n, temperature):                      # one try at a training task: the transcript, and whether it passed
    ask, where, check = practice_task(n)
    conversation = Q.session(model, ask, where, temperature=temperature)
    try:
        passed = check()
    except Exception:
        passed = False
    shutil.rmtree(where, ignore_errors=True)
    return Q.transcript(conversation), passed


def evaluate(model):                                     # the fixed score: forty tasks it never trains on
    return T.score(lambda ask, where: Q.session(model, ask, where), show=lambda line: log("  " + line))


def practice(minutes=60, learning_minutes=30):          # rejection sampling: try, keep what passed, imitate it
    model = Q.load("checkpoints/reason.pt")
    kept, n, start = [], 0, time.time()
    while time.time() - start < minutes * 60:
        text, passed = attempt(model, n, temperature=0.7)
        n += 1
        if passed:
            kept.append(text)
        if n % 20 == 0:
            log(f"{n} tries: {len(kept)} passed and kept")
    log(f"{n} tries in {minutes} minutes: {len(kept)} passed and kept. A kept one:\n{kept[-1] if kept else '(none)'}")
    optimizer, start, step = trainable(model, lr=1e-5), time.time(), 0
    while kept and time.time() - start < learning_minutes * 60:
        step += 1
        update(model, optimizer, random.sample(kept, min(8, len(kept))), [1.0] * 8)
    log(f"learned from them for {step} steps, {learning_minutes} minutes. On the forty held-out tasks:")
    evaluate(model)
    save(model, "practice")


def harness(minutes=150, group=4):                       # RL in the harness: the checks are the reward
    model = Q.load("checkpoints/practice.pt")
    optimizer, start, step, rewards = trainable(model, lr=2e-6), time.time(), 0, []
    while time.time() - start < minutes * 60:
        tries = [attempt(model, 100_000 + step, temperature=0.7) for _ in range(group)]   # the same task, several tries
        step += 1
        reward = torch.tensor([float(passed) for _, passed in tries])
        rewards.append(reward.mean().item())
        if reward.std() > 0:
            advantage = (reward - reward.mean()) / reward.std()
            update(model, optimizer, [text for text, _ in tries], advantage.tolist())
        if step % 10 == 0:
            log(f"step {step}: {(time.time() - start) / 60:.0f} minutes; passed in training, last 10 tasks: {sum(rewards[-10:]) / 10:.0%}")
            save(model, "harness")
    log(f"after {step} tasks, {minutes} minutes. On the forty held-out tasks:")
    evaluate(model)
    save(model, "harness")


if __name__ == "__main__":
    STAGE = sys.argv[1]
    open(f"runs/{STAGE}.txt", "w").close()
    {"pretrain": pretrain, "instruct": instruct, "reason": reason, "practice": practice, "harness": harness}[STAGE]()
