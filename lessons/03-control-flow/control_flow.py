import subprocess, sys
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS = 10

task = " ".join(sys.argv[1:]) or input("> ")
messages = [{"role": "user", "content": task}]

for step in range(1, MAX_STEPS + 1):
    reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)
    messages.append({"role": "assistant", "content": reply.content})
    if reply.stop_reason == "refusal":
        print("[stopped: the model declined]")
        break
    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})
    if not results:
        print(f"[done in {step} steps]")
        break
    messages.append({"role": "user", "content": results})
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
