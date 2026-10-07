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
import sys, os, glob, json, time, random, urllib.request, collections
import torch, torch.nn.functional as F
import model as M

torch.manual_seed(0); random.seed(0)
os.makedirs("checkpoints", exist_ok=True)


def log(*words):                                         # every stage writes what it did to runs/
    line = " ".join(str(w) for w in words)
    print(line, flush=True)
    with open(f"runs/{STAGE}.txt", "a") as file:
        file.write(line + "\n")


# ── 7. pre-training: predict the next token of raw text ───────────────────────

def pretrain_text():                                     # text and code: Python's own source, and a public-domain book
    code = "".join(open(path, errors="ignore").read() for path in sorted(glob.glob("/usr/lib/python3.11/*.py")))
    book = urllib.request.urlopen("https://www.gutenberg.org/cache/epub/11/pg11.txt").read().decode()
    return code + book * 4


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
    return ids[0].tolist()


if __name__ == "__main__":
    STAGE = sys.argv[1]
    open(f"runs/{STAGE}.txt", "w").close()
    {"pretrain": pretrain}[STAGE]()
