import sys
from anthropic import Anthropic

client = Anthropic()
task = " ".join(sys.argv[1:]) or input("> ")
reply = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": task}],
)
print(reply.model_dump_json(indent=2))
