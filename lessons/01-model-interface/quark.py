from anthropic import Anthropic

client = Anthropic()
reply = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=16384,
    messages=[{"role": "user", "content": "What's in this directory?"}],
)
print(reply.model_dump_json(indent=2))
