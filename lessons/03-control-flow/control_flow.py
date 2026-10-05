import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS = 10

def run(block):
    done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return {"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"}

messages = [{"role": "user", "content": " ".join(sys.argv[1:]) or input("> ")}]

for step in range(1, MAX_STEPS + 1):
    reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=4096, tools=tools, messages=messages)
    messages.append({"role": "assistant", "content": reply.content})
    for block in reply.content:
        if block.type == "text": print(block.text)
    if reply.stop_reason == "refusal":
        print("[stopped: the model declined]"); break
    calls = [b for b in reply.content if b.type == "tool_use"]
    if not calls:
        print(f"[done in {step} steps]"); break
    print(f"[step {step}: running {len(calls)} command{'s at once' if len(calls) > 1 else ''}]")
    for c in calls: print(f"$ {c.input['cmd']}")
    with ThreadPoolExecutor() as pool:
        messages.append({"role": "user", "content": list(pool.map(run, calls))})
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
