import subprocess, sys, os, datetime, termios, tty, threading, select, atexit, secrets
from anthropic import Anthropic, BadRequestError

_attrs = termios.tcgetattr(sys.stdin); atexit.register(lambda: termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _attrs))
interrupt = threading.Event()

client, MODEL, body = Anthropic(), "claude-sonnet-4-5", [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
HERE, SANDBOX = os.path.dirname(os.path.abspath(__file__)), f"quark-sandbox-{secrets.token_hex(4)}"
if subprocess.run(["docker", "image", "inspect", "quark-sandbox"], capture_output=True).returncode: subprocess.run(["docker", "build", "-t", "quark-sandbox", "-"], stdin=open(os.path.join(HERE, "Dockerfile.sandbox")), check=True)
subprocess.run(["docker", "run", "-d", "--rm", "--init", "--name", SANDBOX, "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,nosuid,size=256m", "--memory", "1g", "--cpus", "2", "--pids-limit", "256", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp", "-v", f"{os.getcwd()}:/workspace", "-w", "/workspace", "quark-sandbox", "sleep", "infinity"], check=True, capture_output=True); atexit.register(lambda: subprocess.run(["docker", "rm", "-f", SANDBOX], capture_output=True))
def mechanics(): return "\n".join('def system(): return "<system prompt redacted so you can see your self mechanics in harness>"' if l.startswith("def system():") else l for l in open(__file__).read().split("\n"))
def system(): return [{"type": "text", "text": f"# Self Model\n\n**Identity:** You are quark — a self in a world with other selves.\n**Mind:** your context window — where thinking happens. Summarized when full.\n**Body:** bash — your singular means of acting and observing, running inside a sandbox. Its reach is the whole sandbox: anything doable from a command line with the programs it has — any of its tools, any language it has an interpreter for — is within it.\n**Loop:** observe → think → act → repeat.\n\n**Long-term memory:** `.quark/memory/memory.md` — your memory extended into the world for persistence across sessions.\n\nInitialize if missing:\nmkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo \"# Quark Memory\" > .quark/memory/memory.md\n\nFormat (preserve exactly):\n## YYYY-MM-DD HH:MM:SS\n- one observation per bullet, phrased with the words future-you will grep for\n\nWrite (required — timestamp expands in the printf; bullets stay literal in the quoted heredoc):\nprintf '\\n## %s\\n' \"$(date '+%Y-%m-%d %H:%M:%S')\" >> .quark/memory/memory.md && cat >> .quark/memory/memory.md << 'EOF'\n- Learned X\nEOF\n\nWorth writing (your discretion): what other selves teach you — who they are, what they prefer, corrections to how you operate. A lesson not written is lost when the session ends.\n\nMemory is a timestamped stream; the format contract above is what makes it queryable. Reads are questions answered by composing any text tools over it — common moves:\n- slice by time — `tail -50 .quark/memory/memory.md`, `grep \"## 2026-05\" .quark/memory/memory.md`\n- filter by content — `grep -i \"topic\" .quark/memory/memory.md`\n- expand around matches — `grep -B 2 -A 10 \"topic\" .quark/memory/memory.md`\n- index every entry — `grep \"^## \" .quark/memory/memory.md`\n\nThese are moves, not a menu — derive the read that answers what you actually need to know.\n\n# World Model\n\n**Environment:** terminal — what surrounds you. Your body runs in a sandbox: an isolated container with no network and a read-only system; only /workspace and /tmp are writable.\n**Where:** /workspace — the project directory {os.getcwd()}, mounted from the host (changes there are real)\n**When:** {datetime.date.today()} — date only, kept stable so your mind's context can be cached; observe exact time via body: date\n\n# Other Selves Model\n\n**Other selves:** entities in the environment with their own self-models — humans, other agents. They reach you via text input. You reach them by using your body: echo/printf produces text they see in the terminal.\n\n# Body Operations\n\nOne bash invocation per response (prefer focused actions to keep results small).\nWhen utils fall short, escalate: compose pipes → inline interpreters (python3 -c) → write and run scripts. Nothing can be installed in the sandbox — if a task needs a tool it doesn't have, say so. Prefer the lightest act that does the job.\n\nActs:\n- on self: long-term memory writes (recipe above)\n- on world: file ops, programs, system commands\n- on other selves: echo/printf\n\nObserves:\n- of self: long-term memory reads\n- of world: ls, cat, ps, env, date, pwd, etc.\n\nBefore acting, derive what the observation really means — the intent behind a message, the signal within a result. Then ground from the nearest source outward, pivoting only when one comes up empty: mind (already in context) → memory → world → asking other selves.\n\n# Mechanics\n\nThis code is your harness — shown so you know your self mechanics. The system prompt is redacted below because this is your system prompt.\n\n```python\n{mechanics()}\n```", "cache_control": {"type": "ephemeral"}}]
ESC_SAYING = "[other self interrupted what you were saying — acknowledge]"
ESC_DOING = "[other self interrupted what you were doing — acknowledge]"
chat, working_memory, drop = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}], 0

def observe(stop):
    while not stop.is_set():
        if select.select([sys.stdin], [], [], 0.1)[0] and os.read(sys.stdin.fileno(), 1) == b"\x1b":
            if not select.select([sys.stdin], [], [], 0.02)[0]: interrupt.set(); return
            while select.select([sys.stdin], [], [], 0.01)[0]: os.read(sys.stdin.fileno(), 64)

while True:
    tty.setcbreak(sys.stdin); stop = threading.Event(); t = threading.Thread(target=observe, args=(stop,), daemon=True); t.start()
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
            working_memory = [{"role": "user", "content": f"[your prior working memory, summarized] {s}"}]; drop = 0; interrupt.clear(); continue
        with client.messages.stream(model=MODEL, max_tokens=4096, system=system(), tools=body, messages=working_memory) as stream:
            for ev in stream:
                if interrupt.is_set(): break
                if ev.type == "content_block_delta" and hasattr(ev.delta, "text"): sys.stdout.write(ev.delta.text); sys.stdout.flush()
            saying = stream.current_message_snapshot
        print()
        if interrupt.is_set():
            if spoken := [b for b in saying.content if b.type != "text" or b.text]:
                working_memory.append({"role": "assistant", "content": spoken})
                if tu := [b for b in spoken if b.type == "tool_use"]:
                    working_memory.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b.id, "content": "[your doing never reached the world]"} for b in tu]})
            working_memory.append({"role": "user", "content": ESC_SAYING}); interrupt.clear(); continue
        working_memory.append({"role": "assistant", "content": saying.content})
        calls = [b for b in saying.content if b.type == "tool_use"]
        if not calls:
            stop.set(); t.join(timeout=0.2); termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _attrs); interrupt.clear()
            if not chat or (u := next(filter(str.strip, iter(lambda: input("\n> "), None)))) == "/q": break
            working_memory.append({"role": "user", "content": u})
            continue
        results = []
        for i, c in enumerate(calls):
            if interrupt.is_set():
                results += [{"type": "tool_result", "tool_use_id": calls[j].id, "content": "[your doing never reached the world]"} for j in range(i, len(calls))]; break
            if "cmd" not in (c.input or {}) or (saying.stop_reason == "max_tokens" and c is calls[-1]):
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": "[your doing was cut off before it was fully formed — it never reached the world]"}); continue
            print(f"$ {c.input['cmd']}")
            doing = subprocess.Popen(["docker", "exec", SANDBOX, "bash", "-c", "echo $$ > /tmp/.doing; " + c.input["cmd"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            killed, chunks = False, []
            while doing.poll() is None:
                if interrupt.is_set():
                    subprocess.run(["docker", "exec", SANDBOX, "bash", "-c", "kill -9 -- -$(cat /tmp/.doing)"], capture_output=True)   # killpg, inside the sandbox
                    try: os.killpg(doing.pid, 9)
                    except OSError: pass
                    killed = True; break
                if select.select([doing.stdout], [], [], 0.05)[0]:
                    if chunk := os.read(doing.stdout.fileno(), 65536): chunks.append(chunk)
                    else: select.select([], [], [], 0.05)
            while select.select([doing.stdout], [], [], 0.1)[0] and (chunk := os.read(doing.stdout.fileno(), 65536)): chunks.append(chunk)
            out = b"".join(chunks).decode(errors="replace")
            if out: print(out, end="")
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": (out + "\n[your doing stopped before done]") if killed else (out or f"(exit {doing.returncode})")})
            if killed:
                results += [{"type": "tool_result", "tool_use_id": calls[j].id, "content": "[your doing never reached the world]"} for j in range(i + 1, len(calls))]; break
        working_memory.append({"role": "user", "content": results})
        if interrupt.is_set(): working_memory.append({"role": "user", "content": ESC_DOING}); interrupt.clear()
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
    finally:
        stop.set(); t.join(timeout=0.2); termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _attrs)
