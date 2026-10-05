import subprocess, sys
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

chat = len(sys.argv) < 2
messages = [{"role": "user", "content": " ".join(sys.argv[1:]) or input("> ")}]

while True:
    reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=4096, tools=tools, messages=messages)

    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})

    messages.append({"role": "assistant", "content": reply.content})
    if results:
        messages.append({"role": "user", "content": results})
        continue
    if not chat or (task := input("\n> ")) == "/q":
        break
    messages.append({"role": "user", "content": task})
