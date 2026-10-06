import sys
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
task = " ".join(sys.argv[1:]) or input("> ")
reply = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=16384,
    tools=tools,
    messages=[{"role": "user", "content": task}],
)
print(reply.model_dump_json(indent=2))
