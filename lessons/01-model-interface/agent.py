import sys
from anthropic import Anthropic

client, MODEL = Anthropic(), "claude-sonnet-4-5"
working_memory = [{"role": "user", "content": "What's in this directory?"}]

with client.messages.stream(model=MODEL, max_tokens=4096, messages=working_memory) as stream:
    for ev in stream:
        if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
    saying = stream.current_message_snapshot
print()
