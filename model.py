# /// script
# dependencies = ["torch", "numpy", "regex", "safetensors", "huggingface_hub", "jinja2"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""A language model built from its primitives, in the design of Qwen3."""
import json, unicodedata, collections
import regex, jinja2.sandbox
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
