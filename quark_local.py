# /// script
# dependencies = ["torch", "numpy", "tokenizers", "safetensors", "huggingface_hub", "jinja2"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""quark, with a model we run ourselves in place of Sonnet: the same loop and tool, a different model interface.
The interface speaks the model's own format: its chat template shows it the conversation and the bash tool, and it asks
for a command by writing <tool_call>{"name": "bash", "arguments": {"command": "…"}}</tool_call>.
Commands run in a throwaway container that can see only the folder it works in: a small model makes big mistakes.
Run it: uv run quark_local.py Qwen/Qwen3-0.6B [think] [coached]"""
import sys, os, re, json, datetime, subprocess
import model as M

bash = {"type": "function", "function": {"name": "bash", "description": "Run a shell command",          # quark.py's tool
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
NO_THINKING = dict(temperature=0.7, top_p=0.8, top_k=20)  # Qwen's advice with thinking off; with it on, its generation settings
INSTRUCTIONS = {
    "plain": "You are quark, an agent. You act through bash, in /work. Today is {today}.",          # quark.py's, word for word
    "coached": """You are quark, an agent: a small language model in a harness on this computer. You act only through your bash tool, in /work. Today is {today}.

How your tool works:
- Each command runs in a new shell in /work, with no network, for at most ten seconds. Variables and cd do not carry over to the next command.
- You see what the command printed. "(no output)" means it ran and printed nothing.

How to work:
- Look before you act: list or read the files when you are unsure.
- Do the task yourself. Nobody else will check or fix anything for you.
- Write exactly what was asked into a file, and nothing more.
- Check the result before you say you are done. If it is wrong, fix it.
- When it is done, say what you did in one sentence.""",                                          # what a small model can't guess
}


def capture_input():
    return input("\n> ")


def assemble_context(model, conversation, thinking, prompt="plain"):   # instructions and quark.py's tool, in the model's own chat format
    instructions = INSTRUCTIONS[prompt].format(today=datetime.date.today())
    return model.chat([{"role": "system", "content": instructions}] + conversation, tools=[bash], thinking=thinking)


def request_response(model, context, thinking):
    return model.generate(context, most=1500, **({} if thinking else NO_THINKING))


def run(command, where):                                 # in a container: no network, only this folder, ten seconds
    ran = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{where}:/work", "-w", "/work",
                          "python:3.13-slim", "timeout", "10", "sh", "-c", command], capture_output=True, text=True)
    return (ran.stdout + ran.stderr).strip()[:2000] or "(no output)"


def handle_output(response, where, show=print):         # its words, and each <tool_call> it wrote, run
    calls, results = [], []
    for raw in re.findall(r"<tool_call>(.*?)</tool_call>", response, re.S):
        try:
            command = json.loads(raw)["arguments"]["command"]
        except (ValueError, KeyError, TypeError):        # it wrote a call we can't read: say so, as an API would
            results.append({"role": "tool", "content": "error: a tool call must be JSON with a command"})
            show(f"! unreadable tool call: {raw.strip()[:200]}")
            continue
        show(f"$ {command}")
        calls.append({"type": "function", "function": {"name": "bash", "arguments": {"command": command}}})
        results.append({"role": "tool", "content": run(command, where)})
    words = re.sub(r"<tool_call>.*?</tool_call>", "", response, flags=re.S).strip()   # its thinking stays: the template decides
    if words.split("</think>")[-1].strip():
        show("< " + words.split("</think>")[-1].strip().replace("\n", "\n  "))
    return {"role": "assistant", "content": words, "tool_calls": calls}, results


def session(model, ask, where, thinking=False, prompt="plain", turns=8, show=lambda line: None):   # one request, worked until it answers
    conversation = [{"role": "user", "content": ask}]
    for _ in range(turns):
        reply, results = handle_output(request_response(model, assemble_context(model, conversation, thinking, prompt), thinking), where, show)
        conversation += [reply] + results
        if not results:
            break                                        # done: hand back to the person
    return conversation


def control_flow(model, thinking, prompt):
    conversation = []
    while True:
        conversation.append({"role": "user", "content": capture_input()})
        while True:
            reply, results = handle_output(request_response(model, assemble_context(model, conversation, thinking, prompt), thinking), os.getcwd())
            conversation += [reply] + results
            if not results:
                break                                    # done: hand back to the person
            for result in results:
                print("  " + result["content"].replace("\n", "\n  "))


if __name__ == "__main__":
    control_flow(M.Release(sys.argv[1]), "think" in sys.argv, "coached" if "coached" in sys.argv else "plain")
