import subprocess, sys
from anthropic import Anthropic

client, MODEL, body = Anthropic(), "claude-sonnet-5-5", [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
chat, working_memory = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}]

while True:
    with client.messages.stream(model=MODEL, max_tokens=4096, tools=body, messages=working_memory) as stream:
        for ev in stream:
            if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
        saying = stream.current_message_snapshot
    print()
    working_memory.append({"role": "assistant", "content": saying.content})
    calls = [b for b in saying.content if b.type == "tool_use"]
    if not calls:
        if not chat or (u := next(filter(str.strip, iter(lambda: input("\n> "), None)))) == "/q": break
        working_memory.append({"role": "user", "content": u})
        continue
    results = []
    for c in calls:
        if "cmd" not in (c.input or {}) or (saying.stop_reason == "max_tokens" and c is calls[-1]):
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": "[your doing was cut off before it was fully formed — it never reached the world]"}); continue
        print(f"$ {c.input['cmd']}")
        doing = subprocess.run(c.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = doing.stdout.decode(errors="replace")
        if out: print(out, end="")
        results.append({"type": "tool_result", "tool_use_id": c.id, "content": out or f"(exit {doing.returncode})"})
    working_memory.append({"role": "user", "content": results})
