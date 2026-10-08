# /// script
# dependencies = ["torch", "numpy", "tokenizers", "safetensors", "huggingface_hub", "jinja2"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""A language model built from its primitives, in the design of Qwen3."""
import json
import jinja2.sandbox
import torch, torch.nn as nn, torch.nn.functional as F
from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file

REAL = "Qwen/Qwen3-0.6B-Base"                            # the real weights we load into this code


# ── 1. tokenizer: text to numbers ─────────────────────────────────────────────

tokenizer = Tokenizer.from_file(hf_hub_download(REAL, "tokenizer.json"))   # learned from data, like the weights


def encode(text):
    return tokenizer.encode(text).ids


def decode(ids):
    return tokenizer.decode(ids, skip_special_tokens=False)


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
        mixed = F.scaled_dot_product_attention(q, k, v, is_causal=length > 1)   # only look back, never ahead
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
        return x + self.down_proj(F.silu(self.gate_proj(h)) * self.up_proj(h))         # think about it


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

    def __init__(self, name):
        read = lambda file: json.load(open(hf_hub_download(name, file)))
        config, self.settings = read("config.json"), read("generation_config.json")
        assert config["rms_norm_eps"] == 1e-6 and not config["attention_bias"] and config["hidden_act"] == "silu"   # what our code fixes
        self.model = Model(config["vocab_size"], config["hidden_size"], config["num_hidden_layers"], config["num_attention_heads"],
                           config["num_key_value_heads"], config["head_dim"], config["intermediate_size"], config["rope_theta"])
        weights = load_file(hf_hub_download(name, "model.safetensors"))
        weights.pop("lm_head.weight", None)              # some releases store the output head too: it is the embedding, shared
        self.model.load_state_dict({k.removeprefix("model.").replace("mlp.", ""): v.float() for k, v in weights.items()}, strict=True)
        self.tokenizer = Tokenizer.from_file(hf_hub_download(name, "tokenizer.json"))
        rendering = jinja2.sandbox.ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, extensions=["jinja2.ext.loopcontrols"])
        rendering.filters["tojson"] = lambda x, indent=None, separators=None, sort_keys=False, ensure_ascii=False: json.dumps(
            x, indent=indent, separators=separators, sort_keys=sort_keys, ensure_ascii=ensure_ascii)   # as transformers renders it
        self.template = rendering.from_string(read("tokenizer_config.json")["chat_template"])
        stops = self.settings["eos_token_id"]
        self.stops = set(stops if isinstance(stops, list) else [stops])

    def encode(self, text):
        return self.tokenizer.encode(text, add_special_tokens=False).ids

    def decode(self, ids):
        return self.tokenizer.decode(ids, skip_special_tokens=False)

    def chat(self, messages, tools=None, thinking=False):   # the conversation as text, in the format the model was trained on
        return self.template.render(messages=messages, tools=tools, add_generation_prompt=True, enable_thinking=thinking)

    @torch.no_grad()
    def generate(self, text, most=1000, temperature=None, top_k=None, top_p=None):   # sampling as its generation settings say
        temperature = temperature or self.settings.get("temperature", 1.0)
        top_k, top_p = top_k or self.settings.get("top_k", 0), top_p or self.settings.get("top_p", 1.0)
        ids, caches, out = torch.tensor([self.encode(text)]), [{} for _ in self.model.layers], []
        scores = self.model(ids, caches)[0, -1]
        for _ in range(most):
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
