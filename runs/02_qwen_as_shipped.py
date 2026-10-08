# /// script
# dependencies = ["torch", "numpy", "tokenizers", "safetensors", "huggingface_hub", "jinja2", "transformers"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Qwen3-0.6B as Qwen ships it, every part loaded into our code: first checked against Qwen's reference tooling, then run.
Run from the repo: uv run --script runs/02_qwen_as_shipped.py"""
import sys, time, torch
sys.path.insert(0, ".")
import model as M
from transformers import AutoTokenizer, AutoModelForCausalLM

NAME = "Qwen/Qwen3-0.6B"
qwen = M.Release(NAME)

# ── check: the same text, the same tokens, the same predictions as the reference ──
reference = AutoTokenizer.from_pretrained(NAME)
bash = {"type": "function", "function": {"name": "bash", "description": "Run a shell command",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
conversations = [
    ([{"role": "user", "content": "Hi!"}], None),
    ([{"role": "system", "content": "You are quark."}, {"role": "user", "content": "Make a folder called stone."}], [bash]),
    ([{"role": "user", "content": "Count the lines in a.txt into count.txt."},
      {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "bash", "arguments": {"command": "wc -l < a.txt > count.txt"}}}]},
      {"role": "tool", "content": "(no output)"}], [bash]),
    ([{"role": "user", "content": "2+2?"}, {"role": "assistant", "content": "<think>\nEasy.\n</think>\n\n4"}, {"role": "user", "content": "And 3+3?"}], None),
]
for messages, tools in conversations:
    for thinking in (False, True):
        ours = qwen.chat(messages, tools, thinking)
        theirs = reference.apply_chat_template(messages, tools=tools, add_generation_prompt=True, enable_thinking=thinking, tokenize=False)
        assert ours == theirs, (ours, theirs)
        assert qwen.encode(ours) == reference.encode(theirs, add_special_tokens=False)
print(f"chat template and tokenizer: identical to the reference on {2 * len(conversations)} conversations, tools, tool results and thinking included")
ids = torch.tensor([qwen.encode(qwen.chat(*conversations[2], True))])
with torch.no_grad():
    ours, theirs = qwen.model(ids), AutoModelForCausalLM.from_pretrained(NAME, dtype=torch.float32)(ids).logits
print(f"model: largest difference in its scores {(ours - theirs).abs().max():.1e}, same most likely token at all {ids.shape[1]} positions:",
      bool((ours.argmax(-1) == theirs.argmax(-1)).all()))
print("generation settings:", qwen.settings, "\n")


# ── run it: what does it say? ──
def ask(messages, tools=None, thinking=False, **sampling):
    start, text = time.time(), qwen.chat(messages, tools, thinking)
    reply = qwen.generate(text, most=1200 if thinking else 400, **sampling)
    print(f"[thinking {'on' if thinking else 'off'}, {len(qwen.encode(reply))} tokens in {time.time() - start:.0f}s]")
    for m in messages[-1:]:
        print(f"> {m['content']}")
    print(f"< {reply}\n", flush=True)
    return reply


torch.manual_seed(0)
off = dict(temperature=0.7, top_p=0.8, top_k=20)        # Qwen's advice with thinking off; with it on, its generation settings
ask([{"role": "user", "content": "Hi! Who are you?"}], **off)
ask([{"role": "user", "content": "Explain what a file system is to a ten-year-old."}], **off)
ask([{"role": "user", "content": "Write a two-line poem about the sea."}], **off)
cats = [{"role": "user", "content": "Give me three names for a pet cat."}]
cats.append({"role": "assistant", "content": ask(cats, **off)})
cats.append({"role": "user", "content": "Make them all start with the letter M."})
ask(cats, **off)
ask([{"role": "user", "content": "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?"}], thinking=True)
ask([{"role": "user", "content": "What does the command `du -sh *` do?"}], thinking=True)
ask([{"role": "system", "content": "You are quark, an agent. You act through bash, in /work."},
     {"role": "user", "content": "Count the lines in notes.txt and write the number to count.txt."}], tools=[bash], **off)
ask([{"role": "system", "content": "You are quark, an agent. You act through bash, in /work."},
     {"role": "user", "content": "Count the lines in notes.txt and write the number to count.txt."}], tools=[bash], thinking=True)
