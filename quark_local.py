# /// script
# dependencies = ["torch", "numpy", "tokenizers", "safetensors", "huggingface_hub"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""quark, with our own model in place of Sonnet: the same loop, a different model interface.
Commands run in a throwaway container that can see only the folder it works in: a small model makes big mistakes.
Run it: uv run quark_local.py checkpoints/reason.pt"""
import sys, os, re, subprocess, torch
import model as M

INSTRUCTIONS = ("You are quark, an agent. You act through bash, in {where}. "   # short: a small model can't use a long prompt
                "Run a command by writing <bash>command</bash>, and you will see what it prints. When the task is done, say so in plain words.")


def turn(role, text):                                    # the chat format: who is speaking, then what they say
    return f"<|im_start|>{role}\n{text}<|im_end|>\n"


def load(path):                                          # a trained checkpoint, in the model we built
    model = M.Model()
    model.load_state_dict({k: v.float() for k, v in torch.load(path).items()})
    return model


def capture_input():
    return input("\n> ")


def transcript(conversation):                            # the model reads text, so the context is text: the whole chat so far
    return turn("system", INSTRUCTIONS.format(where="/work")) + "".join(turn(role, content) for role, content in conversation)


def assemble_context(conversation):
    return transcript(conversation) + "<|im_start|>assistant\n"


def request_response(model, context, temperature=0.0):
    return M.generate(model, context, most=200, stop=("<|im_end|>", "<|endoftext|>"), temperature=temperature)


def run(command, where):                                 # in a container: no network, only this folder, ten seconds
    ran = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{where}:/work", "-w", "/work",
                          "python:3.13-slim", "timeout", "10", "sh", "-c", command], capture_output=True, text=True)
    return (ran.stdout + ran.stderr).strip()[:2000] or "(no output)"


def handle_output(response, where, quiet=False):        # the model asks for a tool by writing <bash>…</bash>
    if not quiet:
        print("< " + response.replace("\n", "\n  "))
    command = re.search(r"<bash>(.*?)</bash>", response, re.S)
    return run(command.group(1), where) if command else None


def session(model, ask, where, temperature=0.0, turns=6, quiet=True):   # one request, worked until it answers
    conversation = [("user", ask)]
    for _ in range(turns):
        response = request_response(model, assemble_context(conversation), temperature)
        conversation.append(("assistant", response))
        result = handle_output(response, where, quiet)
        if result is None:
            break                                        # done: hand back to the person
        conversation.append(("tool", result))            # a tool ran: go again
    return conversation


def control_flow(model):
    conversation = []
    while True:
        conversation.append(("user", capture_input()))
        while True:
            response = request_response(model, assemble_context(conversation))
            conversation.append(("assistant", response))
            result = handle_output(response, os.getcwd())
            if result is None:
                break
            print("  " + result.replace("\n", "\n  "))
            conversation.append(("tool", result))


if __name__ == "__main__":
    control_flow(load(sys.argv[1]))
