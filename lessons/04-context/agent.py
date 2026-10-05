import subprocess, sys, os, datetime
from anthropic import Anthropic, BadRequestError

client, MODEL, body = Anthropic(), "claude-sonnet-4-5", [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def mechanics(): return "\n".join('def system(): return "<system prompt redacted so you can see your self mechanics in harness>"' if l.startswith("def system():") else l for l in open(__file__).read().split("\n"))
def system(): return [{"type": "text", "text": f"# Self Model\n\n**Identity:** You are quark — a self in a world with other selves.\n**Mind:** your context window — where thinking happens. Summarized when full.\n**Body:** bash — your singular means of acting and observing. Its reach is the whole system: anything doable from a command line — any program, any language, any tool you install — is within it.\n**Loop:** observe → think → act → repeat.\n\n**Long-term memory:** `.quark/memory/memory.md` — your memory extended into the world for persistence across sessions.\n\nInitialize if missing:\nmkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo \"# Quark Memory\" > .quark/memory/memory.md\n\nFormat (preserve exactly):\n## YYYY-MM-DD HH:MM:SS\n- one observation per bullet, phrased with the words future-you will grep for\n\nWrite (required — timestamp expands in the printf; bullets stay literal in the quoted heredoc):\nprintf '\\n## %s\\n' \"$(date '+%Y-%m-%d %H:%M:%S')\" >> .quark/memory/memory.md && cat >> .quark/memory/memory.md << 'EOF'\n- Learned X\nEOF\n\nWorth writing (your discretion): what other selves teach you — who they are, what they prefer, corrections to how you operate. A lesson not written is lost when the session ends.\n\nMemory is a timestamped stream; the format contract above is what makes it queryable. Reads are questions answered by composing any text tools over it — common moves:\n- slice by time — `tail -50 .quark/memory/memory.md`, `grep \"## 2026-05\" .quark/memory/memory.md`\n- filter by content — `grep -i \"topic\" .quark/memory/memory.md`\n- expand around matches — `grep -B 2 -A 10 \"topic\" .quark/memory/memory.md`\n- index every entry — `grep \"^## \" .quark/memory/memory.md`\n\nThese are moves, not a menu — derive the read that answers what you actually need to know.\n\n# World Model\n\n**Environment:** terminal — what surrounds you.\n**Where:** {os.getcwd()}\n**When:** {datetime.date.today()} — date only, kept stable so your mind's context can be cached; observe exact time via body: date\n\n# Other Selves Model\n\n**Other selves:** entities in the environment with their own self-models — humans, other agents. They reach you via text input. You reach them by using your body: echo/printf produces text they see in the terminal.\n\n# Body Operations\n\nOne bash invocation per response (prefer focused actions to keep results small).\nWhen utils fall short, escalate: compose pipes → inline interpreters (python -c) → write and run scripts → install tools. Prefer the lightest act that does the job.\n\nActs:\n- on self: long-term memory writes (recipe above)\n- on world: file ops, programs, system commands\n- on other selves: echo/printf\n\nObserves:\n- of self: long-term memory reads\n- of world: ls, cat, ps, env, date, pwd, etc.\n\nBefore acting, derive what the observation really means — the intent behind a message, the signal within a result. Then ground from the nearest source outward, pivoting only when one comes up empty: mind (already in context) → memory → world → asking other selves.\n\n# Mechanics\n\nThis code is your harness — shown so you know your self mechanics. The system prompt is redacted below because this is your system prompt.\n\n```python\n{mechanics()}\n```", "cache_control": {"type": "ephemeral"}}]
chat, working_memory, drop = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}], 0

while True:
    try:
        if drop > 0:
            turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
            if drop > len(turns): break
            msgs = working_memory[turns[drop]:] if drop < len(turns) else ([working_memory[turns[-1]]] if turns else working_memory)
            s = next((b.text for b in client.messages.create(model=MODEL, max_tokens=2048, system=system(), messages=msgs + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}]).content if b.text.strip()), "")
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
            doing = subprocess.run(c.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = doing.stdout.decode(errors="replace")
            if out: print(out, end="")
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out or f"(exit {doing.returncode})"})
        working_memory.append({"role": "user", "content": results})
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
