import sys
from anthropic import Anthropic

client, MODEL = Anthropic(), "claude-sonnet-4-5"
working_memory = [{"role": "user", "content": " ".join(sys.argv[1:]) or "Write three sentences about agents."}]

with client.messages.stream(model=MODEL, max_tokens=4096, messages=working_memory) as stream:
    for ev in stream:
        if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
    saying = stream.current_message_snapshot
print()
print(f"[stop_reason: {saying.stop_reason} · tokens in/out: {saying.usage.input_tokens}/{saying.usage.output_tokens}]")
