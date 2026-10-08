# /// script
# dependencies = ["torch", "numpy", "regex", "tokenizers", "safetensors", "huggingface_hub", "jinja2", "transformers"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Our tokenizer and our model, with Qwen's pre-trained numbers loaded, against Qwen's reference implementation on the same tokens.
Run from the repo: uv run --script runs/01_check_against_reference.py"""
import sys, time, torch
sys.path.insert(0, ".")
import model as M
from transformers import AutoModelForCausalLM
from tokenizers import Tokenizer as Reference
from huggingface_hub import hf_hub_download

reference = Reference.from_file(hf_hub_download(M.REAL, "tokenizer.json"))
texts = ["The capital of France is", "ROMEO:\nBut, soft! what light through yonder window breaks?", "def f(x):\n    return x**2\n",
         "<|im_start|>user\nHi<|im_end|>\n<|im_start|>assistant\n", "café 你好 🙂 1234567  x\t\tz\r\n  "]
print("tokenizer: same tokens as the reference on", len(texts), "texts:", all(M.encode(t) == reference.encode(t, add_special_tokens=False).ids for t in texts))

ours = M.load_real().eval()
ref = AutoModelForCausalLM.from_pretrained(M.REAL, dtype=torch.float32).eval()
ids = torch.tensor([M.encode("The capital of France is")])
print("tokens:", ids[0].tolist())
with torch.no_grad():
    a, b = ours(ids), ref(ids).logits
print(f"max difference in scores {(a - b).abs().max().item():.1e}; same next token: {a[0, -1].argmax().item() == b[0, -1].argmax().item()}")
start = time.time()
print(repr(M.generate(ours, "The capital of France is", most=20)), f"20 tokens in {time.time() - start:.1f}s")
