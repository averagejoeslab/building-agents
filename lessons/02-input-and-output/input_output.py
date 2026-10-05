import subprocess, sys, pathlib
from anthropic import Anthropic

client = Anthropic()
tools = [
    {"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}},
    {"name": "read_file", "description": "Read a text file", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
]

def gather():
    if len(sys.argv) > 1: return " ".join(sys.argv[1:])
    if not sys.stdin.isatty(): return sys.stdin.read()
    while not (task := input("> ").strip()): pass
    return task

def run(block):
    try:
        if block.name == "bash":
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            return done.stdout + (f"\n(exit {done.returncode})" if done.returncode else ""), False
        if block.name == "read_file":
            return pathlib.Path(block.input["path"]).read_text(), False
        return f"no tool named {block.name}", True
    except subprocess.TimeoutExpired:
        return "stopped after 30 seconds", True
    except OSError as e:
        return str(e), True

messages = [{"role": "user", "content": gather()}]
with client.messages.stream(model="claude-sonnet-5-5", max_tokens=4096, tools=tools, messages=messages) as stream:
    for text in stream.text_stream: print(text, end="", flush=True)
    reply = stream.get_final_message()
print()

results = []
for block in reply.content:
    if block.type != "tool_use": continue
    if reply.stop_reason == "max_tokens" and block is reply.content[-1]:
        results.append({"type": "tool_result", "tool_use_id": block.id, "content": "cut off before it was finished, so it was not run", "is_error": True}); continue
    print(f"→ {block.name} {block.input}")
    out, failed = run(block)
    print(out)
    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out, "is_error": failed})
