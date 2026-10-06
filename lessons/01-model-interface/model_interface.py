from anthropic import Anthropic

client = Anthropic()

request = {
    "model": "claude-sonnet-5-5",
    "max_tokens": 16384,
    "messages": [{"role": "user", "content": "What's in this directory?"}],
}
output = client.messages.create(**request)              # one request out, one response back, all at once

for block in output.content:
    print(f"[{block.type}]", getattr(block, "text", ""))
print("stop_reason:", output.stop_reason)
print("tokens in:", output.usage.input_tokens)
print("tokens out:", output.usage.output_tokens)
