# /// script
# dependencies = ["torch", "numpy", "regex", "safetensors", "huggingface_hub", "jinja2", "datasets", "transformers"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""A language model built from its primitives, in the design of Qwen3, and trained one stage at a time:
uv run model.py check | pretrain | midtrain | instruct | reason"""
import sys, os, re, glob, json, time, random, shutil, datetime, tempfile, subprocess, urllib.request, unicodedata, collections
import regex, jinja2.sandbox
from datasets import load_dataset
import torch, torch.nn as nn, torch.nn.functional as F, torch.utils.checkpoint
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file

REAL = "Qwen/Qwen3-0.6B-Base"                            # the real weights we load into this code


# ── 1. tokenizer: text to tokens, and back ────────────────────────────────────

WORDS = r"""(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"""
BYTES = [*range(33, 127), *range(161, 173), *range(174, 256)]   # every byte as a printable character, as Qwen writes them
BYTES = dict(zip([*BYTES, *(b for b in range(256) if b not in BYTES)], map(chr, [*BYTES, *range(256, 256 + 256 - len(BYTES))])))
UNBYTES = {c: b for b, c in BYTES.items()}


class Tokenizer:
    """Byte-pair encoding: start from single bytes, and merge the commonest neighbouring pairs into new tokens."""

    def __init__(self, merges, special=()):
        self.ranks = {pair: rank for rank, pair in enumerate(merges)}  # earlier merges were commoner: apply them first
        pieces = [BYTES[b] for b in range(256)] + ["".join(pair) for pair in merges]
        self.ids = {piece: i for i, piece in enumerate(pieces)}
        self.ids.update({token: len(pieces) + i for i, token in enumerate(special)})
        self.pieces = {i: piece for piece, i in self.ids.items()}
        self.added = set(special)
        self.special = regex.compile("(" + "|".join(map(regex.escape, special)) + ")") if special else None
        self.cache = {}

    @classmethod
    def learn(cls, text, size, special=()):              # learn merges from text until there are `size` tokens
        words = collections.Counter("".join(BYTES[b] for b in w.encode()) for w in regex.findall(WORDS, text))
        words = {tuple(w): n for w, n in words.items()}
        merges = []
        while 256 + len(merges) + len(special) < size:
            pairs = collections.Counter()
            for w, n in words.items():
                for pair in zip(w, w[1:]):
                    pairs[pair] += n
            if not pairs:
                break
            best = max(pairs, key=pairs.get)             # the commonest neighbouring pair becomes one token
            merges.append(best)
            words = {cls.merge(w, best): n for w, n in words.items()}
        return cls(merges, special)

    @classmethod
    def load(cls, name):                                 # a released tokenizer: its learned merges, in the same code
        spec = json.load(open(hf_hub_download(name, "tokenizer.json")))
        merges = [tuple(m.split(" ")) if isinstance(m, str) else tuple(m) for m in spec["model"]["merges"]]
        tokenizer = cls(merges, [t["content"] for t in spec["added_tokens"]])
        tokenizer.ids = {**spec["model"]["vocab"], **{t["content"]: t["id"] for t in spec["added_tokens"]}}   # its numbering
        tokenizer.pieces = {i: piece for piece, i in tokenizer.ids.items()}
        return tokenizer

    @staticmethod
    def merge(word, pair):
        out, i = [], 0
        while i < len(word):
            if word[i:i + 2] == pair:
                out.append(word[i] + word[i + 1]); i += 2
            else:
                out.append(word[i]); i += 1
        return tuple(out)

    def word(self, w):                                   # one word: its bytes, merged pair by pair, commonest first
        if w not in self.cache:
            parts = tuple(BYTES[b] for b in w.encode())
            while len(parts) > 1:
                pair = min(zip(parts, parts[1:]), key=lambda p: self.ranks.get(p, float("inf")))
                if pair not in self.ranks:
                    break
                parts = self.merge(parts, pair)
            self.cache[w] = [self.ids[p] for p in parts]
        return self.cache[w]

    def encode(self, text):
        ids = []
        for part in (self.special.split(text) if self.special else [text]):
            if part in self.added:
                ids.append(self.ids[part])               # a special token, such as <|im_end|>, is one token
            elif part:
                for w in regex.findall(WORDS, unicodedata.normalize("NFC", part)):
                    ids += self.word(w)
        return ids

    def decode(self, ids):
        text, waiting = "", b""
        for i in ids:
            piece = self.pieces[i]
            if piece in self.added:                      # a special token is written as it is
                text, waiting = text + waiting.decode(errors="replace") + piece, b""
            else:
                waiting += bytes(UNBYTES[c] for c in piece)
        return text + waiting.decode(errors="replace")


tokenizer = Tokenizer.load(REAL)                         # Qwen's learned merges, in our code


def encode(text):
    return tokenizer.encode(text)


def decode(ids):
    return tokenizer.decode(ids)


# ── 2. embedding and position ─────────────────────────────────────────────────

def rotary(length, dim, theta=1_000_000.0, start=0):     # position: rotate each vector by an angle that grows along the text
    frequencies = 1.0 / theta ** (torch.arange(0, dim, 2).float() / dim)
    angles = torch.outer(torch.arange(start, start + length).float(), frequencies)
    angles = torch.cat([angles, angles], dim=-1)
    return angles.cos(), angles.sin()


def rotate(x, cos, sin):
    half = x.shape[-1] // 2
    return x * cos + torch.cat([-x[..., half:], x[..., :half]], dim=-1) * sin


class RMSNorm(nn.Module):                                # keep the numbers at a steady size between steps
    def __init__(self, dim, eps=1e-6):
        super().__init__()
        self.weight, self.eps = nn.Parameter(torch.ones(dim)), eps

    def forward(self, x):
        return self.weight * x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)


# ── 3. attention: each token looks back at the ones before it ─────────────────

class Attention(nn.Module):
    def __init__(self, dim, heads, kv_heads, head_dim):
        super().__init__()
        self.heads, self.kv_heads, self.head_dim = heads, kv_heads, head_dim
        self.q_proj = nn.Linear(dim, heads * head_dim, bias=False)       # what each token is looking for
        self.k_proj = nn.Linear(dim, kv_heads * head_dim, bias=False)    # what each token offers
        self.v_proj = nn.Linear(dim, kv_heads * head_dim, bias=False)    # what each token carries
        self.o_proj = nn.Linear(heads * head_dim, dim, bias=False)
        self.q_norm, self.k_norm = RMSNorm(head_dim), RMSNorm(head_dim)

    def forward(self, x, cos, sin, cache=None):
        batch, length, _ = x.shape
        q = self.q_norm(self.q_proj(x).view(batch, length, self.heads, self.head_dim)).transpose(1, 2)
        k = self.k_norm(self.k_proj(x).view(batch, length, self.kv_heads, self.head_dim)).transpose(1, 2)
        v = self.v_proj(x).view(batch, length, self.kv_heads, self.head_dim).transpose(1, 2)
        q, k = rotate(q, cos, sin), rotate(k, cos, sin)
        if cache is not None:                            # generating: keep what earlier tokens offered, so they aren't recomputed
            if "k" in cache:
                k, v = torch.cat([cache["k"], k], dim=2), torch.cat([cache["v"], v], dim=2)
            cache["k"], cache["v"] = k, v
        k = k.repeat_interleave(self.heads // self.kv_heads, dim=1)      # several queries share each key
        v = v.repeat_interleave(self.heads // self.kv_heads, dim=1)
        scores = q @ k.transpose(-2, -1) / self.head_dim ** 0.5          # how well each query matches each key
        ahead = torch.ones(length, k.shape[2], dtype=torch.bool).triu(k.shape[2] - length + 1)   # the keys after each query
        weights = scores.masked_fill(ahead, float("-inf")).softmax(dim=-1)   # never look ahead; share out attention by match
        mixed = weights @ v                                              # take that share of each value
        return self.o_proj(mixed.transpose(1, 2).reshape(batch, length, -1))


# ── 4. a block: attention, then a small network ───────────────────────────────

class Block(nn.Module):
    def __init__(self, dim, hidden, heads, kv_heads, head_dim):
        super().__init__()
        self.input_layernorm, self.self_attn = RMSNorm(dim), Attention(dim, heads, kv_heads, head_dim)
        self.post_attention_layernorm = RMSNorm(dim)
        self.gate_proj, self.up_proj = nn.Linear(dim, hidden, bias=False), nn.Linear(dim, hidden, bias=False)
        self.down_proj = nn.Linear(hidden, dim, bias=False)

    def forward(self, x, cos, sin, cache=None):
        x = x + self.self_attn(self.input_layernorm(x), cos, sin, cache)               # look back
        h = self.post_attention_layernorm(x)
        gate = self.gate_proj(h)
        return x + self.down_proj(gate * torch.sigmoid(gate) * self.up_proj(h))        # think about it: a gated network


# ── 5. the model: embedding, blocks, output head ──────────────────────────────

class Model(nn.Module):
    def __init__(self, vocab=151936, dim=1024, layers=28, heads=16, kv_heads=8, head_dim=128, hidden=3072, theta=1_000_000.0):
        super().__init__()
        self.head_dim, self.theta = head_dim, theta
        self.embed_tokens = nn.Embedding(vocab, dim)     # what each token means
        self.layers = nn.ModuleList([Block(dim, hidden, heads, kv_heads, head_dim) for _ in range(layers)])
        self.norm = RMSNorm(dim)
        for weight in self.parameters():                 # start from small random numbers; training fills in the rest
            if weight.dim() == 2:
                nn.init.normal_(weight, std=0.02)

    def forward(self, ids, caches=None, start=0, keep=None):
        cos, sin = rotary(ids.shape[1], self.head_dim, self.theta, start=start)
        x = self.embed_tokens(ids)
        for i, layer in enumerate(self.layers):
            if torch.is_grad_enabled() and not caches:   # training: keep only each block's input, redo the rest on the way back
                x = torch.utils.checkpoint.checkpoint(layer, x, cos, sin, use_reentrant=False)
            else:
                x = layer(x, cos, sin, caches[i] if caches else None)
        x = self.norm(x)
        if keep is not None:                             # training: score only the positions it learns from, to save memory
            x = x[keep]
        return x @ self.embed_tokens.weight.T            # output head: a score for every possible next token


# ── 6. generation: one token at a time ────────────────────────────────────────

@torch.no_grad()
def generate(model, prompt, most=200, stop=("<|endoftext|>",), temperature=0.0):
    ids, caches, out = torch.tensor([encode(prompt)]), [{} for _ in model.layers], []
    scores = model(ids, caches)[:, -1]
    for _ in range(most):
        if temperature:
            next_id = torch.multinomial(F.softmax(scores / temperature, dim=-1), 1)   # likely tokens, picked more often
        else:
            next_id = scores.argmax(-1, keepdim=True)                                  # always the most likely
        out.append(next_id.item())
        text = decode(out)
        for s in stop:
            if s in text:
                return text[:text.index(s)]
        scores = model(next_id, caches, start=ids.shape[1] + len(out) - 1)[:, -1]
    return text


def load_real(name=REAL):                                # months of pre-training, loaded into the code above
    model = Model()
    weights = load_file(hf_hub_download(name, "model.safetensors"))
    weights.pop("lm_head.weight", None)                  # some releases store the output head too: it is the embedding, shared
    model.load_state_dict({k.removeprefix("model.").replace("mlp.", ""): v.float() for k, v in weights.items()}, strict=True)
    return model


# ── 7. a release: everything a model ships, loaded and used as shipped ────────

class Release:
    """A model as its makers ship it: sizes, weights, tokenizer, chat template and generation settings, each from its own file."""

    def __init__(self, name, weights=None):             # weights: another release's, or a checkpoint of our own training
        read = lambda file: json.load(open(hf_hub_download(name, file)))
        config, self.settings = read("config.json"), read("generation_config.json")
        assert config["rms_norm_eps"] == 1e-6 and not config["attention_bias"] and config["hidden_act"] == "silu"   # what our code fixes
        self.model = Model(config["vocab_size"], config["hidden_size"], config["num_hidden_layers"], config["num_attention_heads"],
                           config["num_key_value_heads"], config["head_dim"], config["intermediate_size"], config["rope_theta"])
        if weights and weights.endswith(".pt"):
            self.model.load_state_dict({k: v.float() for k, v in torch.load(weights).items()})
        else:
            numbers = load_file(hf_hub_download(weights or name, "model.safetensors"))
            numbers.pop("lm_head.weight", None)          # some releases store the output head too: it is the embedding, shared
            self.model.load_state_dict({k.removeprefix("model.").replace("mlp.", ""): v.float() for k, v in numbers.items()}, strict=True)
        self.tokenizer = Tokenizer.load(name)
        rendering = jinja2.sandbox.ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, extensions=["jinja2.ext.loopcontrols"])
        rendering.filters["tojson"] = lambda x, indent=None, separators=None, sort_keys=False, ensure_ascii=False: json.dumps(
            x, indent=indent, separators=separators, sort_keys=sort_keys, ensure_ascii=ensure_ascii)   # as transformers renders it
        self.template = rendering.from_string(read("tokenizer_config.json")["chat_template"])
        stops = self.settings["eos_token_id"]
        self.stops = set(stops if isinstance(stops, list) else [stops])

    def encode(self, text):
        return self.tokenizer.encode(text)

    def decode(self, ids):
        return self.tokenizer.decode(ids)

    def chat(self, messages, tools=None, thinking=False, prompt=True):   # the conversation as text, in the format it's trained on
        return self.template.render(messages=messages, tools=tools, add_generation_prompt=prompt, enable_thinking=thinking)

    @torch.no_grad()
    def generate(self, text, most=1000, temperature=None, top_k=None, top_p=None):   # sampling as its generation settings say
        temperature = self.settings.get("temperature", 1.0) if temperature is None else temperature
        top_k, top_p = top_k or self.settings.get("top_k", 0), top_p or self.settings.get("top_p", 1.0)
        ids, caches, out = torch.tensor([self.encode(text)]), [{} for _ in self.model.layers], []
        scores = self.model(ids, caches)[0, -1]
        greedy = temperature == 0                        # always the most likely: for a fair, repeatable score
        for _ in range(most):
            if greedy:
                scores = scores.masked_fill(scores < scores.max(), float("-inf"))
            else:
                scores = scores / temperature
            if top_k:
                scores = scores.masked_fill(scores < scores.topk(top_k).values[-1], float("-inf"))   # only the k most likely
            probs = F.softmax(scores, dim=-1)
            ordered, order = probs.sort(descending=True)
            ordered[ordered.cumsum(0) - ordered >= top_p] = 0                 # only the most likely, until they make up top_p
            next_id = order[torch.multinomial(ordered, 1)]
            if next_id.item() in self.stops:
                break
            out.append(next_id.item())
            scores = self.model(next_id.view(1, 1), caches, start=ids.shape[1] + len(out) - 1)[0, -1]
        return self.decode(out)

# ── training: one stage at a time, each starting from the last ───────────────
# uv run model.py check | pretrain | midtrain | instruct | reason

CHAT, BASE = "Qwen/Qwen3-0.6B", "Qwen/Qwen3-0.6B-Base"   # Qwen's chat format and tokenizer; Base's pre-trained numbers
INSTRUCTIONS = "You are quark, an agent. You act through bash, in /work. Today is {today}."   # quark.py's, word for word
BASH = {"type": "function", "function": {"name": "bash", "description": "Run a shell command",       # quark.py's tool
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
NAMES = "apple river stone cloud maple ember pixel quartz tiger violet willow amber cobalt delta falcon harbor".split()


def log(*words):
    print(" ".join(str(w) for w in words), flush=True)


# ── 8. pre-training: predict the next token of raw text ───────────────────────

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


# ── 9. the swap, and mid-training: the same task, on the agent's domain ──────

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
    save(model.model, "midtrain")


# ── 10. post-training: instruction-tuning ─────────────────────────────────────

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


# ── 11. post-training: reinforcement learning with a verifier ────────────────

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
    done = resume(model, "reason")
    if not done:
        log(f"held-out accuracy before: {accuracy(model, test):.0%} of {len(test)} test questions")
    optimizer, start, step, rewards = trainable(model.model, lr=2e-6), time.time() - 60 * done.get("minutes", 0), done.get("step", 0), done.get("rewards", [])
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
        if step % 5 == 0:
            save(model.model, "reason", step=step, minutes=(time.time() - start) / 60, rewards=rewards)
    save(model.model, "reason", step=step, minutes=minutes + 1, rewards=rewards)   # training done: a restart only re-scores
    log(f"after {step} questions, {minutes} minutes; held-out accuracy after: {accuracy(model, test):.0%}")
    finish(model, "reason")


# ── checking it: our code, with Qwen's numbers, against Qwen's own ───────────

def check():
    from transformers import AutoTokenizer, AutoModelForCausalLM
    reference = AutoTokenizer.from_pretrained(CHAT)
    texts = ["The capital of France is", "ROMEO:\nBut, soft! what light through yonder window breaks?", "def f(x):\n    return x**2\n",
             "<|im_start|>user\nHi<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n", "café 你好 🙂 1234567  x\t\tz\r\n  "]
    qwen = Release(CHAT)
    log("tokenizer: the same tokens as Qwen's:", all(qwen.encode(t) == reference.encode(t, add_special_tokens=False) for t in texts))
    messages = [{"role": "system", "content": "You are quark."}, {"role": "user", "content": "Count the lines in a.txt."},
                {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "bash", "arguments": {"command": "wc -l < a.txt"}}}]},
                {"role": "tool", "content": "3"}]
    text = qwen.chat(messages, [BASH])
    log("chat template: the same text as Qwen's:", text == reference.apply_chat_template(messages, tools=[BASH], add_generation_prompt=True, enable_thinking=False, tokenize=False))
    ids = torch.tensor([qwen.encode(text)])
    with torch.no_grad():
        ours, theirs = qwen.model(ids), AutoModelForCausalLM.from_pretrained(CHAT, dtype=torch.float32)(ids).logits
    log(f"model: largest difference in its scores {(ours - theirs).abs().max():.1e}; the same next token at all {ids.shape[1]} positions:",
        bool((ours.argmax(-1) == theirs.argmax(-1)).all()))
    log("'The capital of France is' →", repr(generate(load_real(), "The capital of France is", most=12)))


if __name__ == "__main__":
    torch.manual_seed(0); random.seed(0)
    os.makedirs("checkpoints", exist_ok=True)
    {"check": check, "pretrain": pretrain, "midtrain": midtrain, "instruct": instruct, "reason": reason}[sys.argv[1]]()
