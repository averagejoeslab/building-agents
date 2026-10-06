import subprocess
from anthropic import Anthropic

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def call(**request): return client.messages.create(model=MODEL, **request)

# ── output: the one tool ────────────────────────────────────────────────────
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

output = call(max_tokens=16384, tools=tools, messages=[{"role": "user", "content": "What's in this directory?"}]).content

for block in output:                                     # output: show text, run tool requests
    if block.type == "text":
        print(block.text)
    if block.type == "tool_use":
        print(f"$ {block.input['cmd']}")
        done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(done.stdout)
