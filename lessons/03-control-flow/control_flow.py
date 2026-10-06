import subprocess, sys
from anthropic import Anthropic
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS = 10

input = " ".join(sys.argv[1:]) or read("> ")
messages = [{"role": "user", "content": input}]

for step in range(1, MAX_STEPS + 1):
    output = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)
    messages.append({"role": "assistant", "content": output.content})
    if output.stop_reason == "refusal":
        print("[stopped: the model declined]")
        break
    input = []
    for block in output.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            print(done.stdout)
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})
    if not input:
        print(f"[done in {step} steps]")
        break
    messages.append({"role": "user", "content": input})
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
