import subprocess, sys, os, datetime, select
from anthropic import Anthropic, BadRequestError

client, MODEL, body = Anthropic(), "claude-sonnet-4-5", [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def system(): return f"# Self Model\n\n**Identity:** You are quark — a self in a world with other selves.\n**Mind:** your context window — where thinking happens. Summarized when full.\n**Body:** bash — your singular means of acting and observing. Its reach is the whole system: anything doable from a command line — any program, any language, any tool you install — is within it.\n**Loop:** observe → think → act → repeat.\n\n# World Model\n\n**Environment:** terminal — what surrounds you.\n**Where:** {os.getcwd()}\n**When:** {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n\n# Other Selves Model\n\n**Other selves:** entities in the environment with their own self-models — humans, other agents. They reach you via text input. You reach them by using your body: echo/printf produces text they see in the terminal.\n\n# Body Operations\n\nOne bash invocation per response (prefer focused actions to keep results small).\nWhen utils fall short, escalate: compose pipes → inline interpreters (python -c) → write and run scripts → install tools. Prefer the lightest act that does the job.\n\nActs:\n- on world: file ops, programs, system commands\n- on other selves: echo/printf\n\nObserves:\n- of world: ls, cat, ps, env, date, pwd, etc.\n\nBefore acting, derive what the observation really means — the intent behind a message, the signal within a result. Then ground from the nearest source outward, pivoting only when one comes up empty: mind (already in context) → world → asking other selves."
chat, working_memory, drop = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}], 0

while True:
    try:
        if drop > 0:
            turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
            if drop > len(turns): break
            msgs = working_memory[turns[drop]:] if drop < len(turns) else ([working_memory[turns[-1]]] if turns else working_memory)
            while True:
                try:
                    if s := next((b.text for b in client.messages.create(model=MODEL, max_tokens=2048, system=system(), messages=msgs + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}]).content if b.text.strip()), None): break
                except BadRequestError: raise
                except Exception: select.select([], [], [], 1)
            working_memory = [{"role": "user", "content": f"[your prior working memory, summarized] {s}"}]; drop = 0; continue
        with client.messages.stream(model=MODEL, max_tokens=4096, system=system(), tools=body, messages=working_memory) as stream:
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
            doing = subprocess.Popen(c.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            chunks = []
            while doing.poll() is None:
                if select.select([doing.stdout], [], [], 0.05)[0]:
                    if chunk := os.read(doing.stdout.fileno(), 65536): chunks.append(chunk)
                    else: select.select([], [], [], 0.05)
            while select.select([doing.stdout], [], [], 0.1)[0] and (chunk := os.read(doing.stdout.fileno(), 65536)): chunks.append(chunk)
            out = b"".join(chunks).decode(errors="replace")
            if out: print(out, end="")
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out or f"(exit {doing.returncode})"})
        working_memory.append({"role": "user", "content": results})
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
