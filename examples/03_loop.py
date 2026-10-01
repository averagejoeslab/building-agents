import sys
from anthropic import Anthropic

client, MODEL = Anthropic(), "claude-sonnet-4-5"
chat, working_memory = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}]

while True:
    with client.messages.stream(model=MODEL, max_tokens=4096, messages=working_memory) as stream:
        for ev in stream:
            if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
        saying = stream.current_message_snapshot
    print()
    working_memory.append({"role": "assistant", "content": saying.content})
    if not chat or (u := next(filter(str.strip, iter(lambda: input("\n> "), None)))) == "/q": break
    working_memory.append({"role": "user", "content": u})
