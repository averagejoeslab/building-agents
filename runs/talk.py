# /// script
# dependencies = ["torch", "numpy", "tokenizers", "safetensors", "huggingface_hub"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Can it hold a conversation? Single questions, follow-ups that need the earlier turns, and talking around a command.
Run from the repo: uv run --script runs/talk.py checkpoints/instruct.pt   (or base, for the pre-trained weights)"""
import sys
sys.path.insert(0, ".")
import model as M, quark_local as Q
from quark_local import turn

model = M.load_real() if sys.argv[1] == "base" else Q.load(sys.argv[1])
SYSTEM = turn("system", Q.INSTRUCTIONS.format(where="/work"))

CONVERSATIONS = [
    ("plain", ["Explain what a file system is to a ten-year-old."]),
    ("plain", ["I have a job interview tomorrow and I'm nervous. Any advice?"]),
    ("plain", ["Write a two-line poem about the sea."]),
    ("plain", ["What is the difference between a list and a tuple in Python?"]),
    ("plain", ["Hi! Who are you?"]),
    ("follow-up", ["Give me three names for a pet cat.", "Make them all start with the letter M."]),
    ("follow-up", ["What is the capital of Japan?", "What is it famous for?"]),
    ("follow-up", ["Explain recursion in one paragraph.", "Now say that in one sentence."]),
    ("agent", ["Clean up this folder."]),
    ("agent", ["What does the command `du -sh *` do? Don't run it."]),
    ("agent", ["How many files are in this folder? Tell me in a sentence."]),
]


def reply(text):
    return M.generate(model, text + "<|im_start|>assistant\n", most=200, stop=("<|im_end|>", "<|endoftext|>"))


for kind, asks in CONVERSATIONS:
    text = SYSTEM if kind == "agent" else ""
    print(f"── {kind} " + "─" * 60)
    for ask in asks:
        text += turn("user", ask)
        answer = reply(text)
        if "<bash>" in answer:                           # it asked for a tool: show it a real result and let it go on
            text += turn("assistant", answer) + turn("tool", "notes.txt\nreport.md\nold.log\nscratch.tmp")
            print(f"> {ask}\n< {answer}\n[tool] notes.txt report.md old.log scratch.tmp")
            answer = reply(text)
        text += turn("assistant", answer)
        print(f"> {ask}\n< {answer}\n", flush=True)
