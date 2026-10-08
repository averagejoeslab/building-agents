# /// script
# dependencies = ["torch", "numpy", "tokenizers", "safetensors", "huggingface_hub", "jinja2", "transformers"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Our model, with Qwen's pre-trained numbers loaded, against Qwen's reference implementation on the same tokens.
Run from the repo: uv run --script runs/01_check_against_reference.py"""
import sys, time, torch
sys.path.insert(0, ".")
import model as M
from transformers import AutoModelForCausalLM

ours = M.load_real().eval()
ref = AutoModelForCausalLM.from_pretrained(M.REAL, dtype=torch.float32).eval()
ids = torch.tensor([M.encode("The capital of France is")])
print("tokens:", ids[0].tolist())
with torch.no_grad():
    a, b = ours(ids), ref(ids).logits
print(f"max difference in scores {(a - b).abs().max().item():.1e}; same next token: {a[0, -1].argmax().item() == b[0, -1].argmax().item()}")
start = time.time()
print(repr(M.generate(ours, "The capital of France is", most=20)), f"20 tokens in {time.time() - start:.1f}s")
