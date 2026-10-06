import subprocess, sys, os, datetime, json, time, uuid, re, atexit
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic, BadRequestError, APIConnectionError, APIStatusError

client = Anthropic(timeout=300, max_retries=3)
run = uuid.uuid4().hex[:8]
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def trace(**event):
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "run": run, **event}) + "\n")


MODELS, FAST = ["claude-sonnet-5-5", "claude-opus-5-5"], ["claude-haiku-4-5"]
class Down(Exception): pass
def ask(models=MODELS, live=False, **request):
    for model in models:
        try:
            with client.messages.stream(model=model, **request) as stream:
                shown = False
                for text in stream.text_stream:
                    if live: print(text, end="", flush=True); shown = True
                if shown: print()
                return stream.get_final_message()
        except (APIConnectionError, APIStatusError) as e:
            if isinstance(e, APIStatusError) and e.status_code < 500 and e.status_code != 429: raise
            trace(event="model_failed", model=model, error=type(e).__name__)
    raise Down()


MAX_RESULT = 20_000
def trim(text):
    if len(text) <= MAX_RESULT: return text
    return text[:MAX_RESULT // 2] + f"\n[... {len(text) - MAX_RESULT} characters cut ...]\n" + text[-MAX_RESULT // 2:]
def cached(working_memory):
    last = working_memory[-1]
    blocks = [{"type": "text", "text": last["content"]}] if isinstance(last["content"], str) else list(last["content"])
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return working_memory[:-1] + [{"role": last["role"], "content": blocks}]


SESSION = ".quark/session.json"
def save(task, working_memory):
    os.makedirs(".quark", exist_ok=True)
    with open(SESSION + ".tmp", "w") as f: json.dump({"task": task, "working_memory": working_memory}, f, default=lambda b: b.model_dump(exclude_none=True))
    os.replace(SESSION + ".tmp", SESSION)
def unfinished():
    if not os.path.exists(SESSION): return None
    saved = json.load(open(SESSION))
    try: answer = input(f"unfinished run: {saved['task'][:60]!r}. pick it up? [y/N] ").strip().lower()
    except EOFError: answer = ""
    if answer != "y": return None
    working_memory = saved["working_memory"]
    if working_memory[-1]["role"] == "assistant":
        lost = [b for b in working_memory[-1]["content"] if b["type"] == "tool_use"]
        if not lost: return os.remove(SESSION)
        working_memory.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b["id"], "content": "interrupted: the harness stopped before this finished, so it may or may not have run. Check before repeating it.", "is_error": True} for b in lost]})
    return saved["task"], working_memory


IMAGE, TIMEOUT = "python:3.13-slim", 30
box = f"quark-{run}"
def sandbox():
    where = os.getcwd()
    up = subprocess.run(["docker", "run", "-d", "--rm", "--name", box, "--network", "none", "--memory", "512m", "--cpus", "1", "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp", "-e", "HOME=/tmp", "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{where}:{where}", "-w", where, IMAGE, "sleep", "infinity"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if up.returncode: sys.exit(f"[no sandbox, so nothing runs: {up.stdout.strip()}]")
    atexit.register(lambda: subprocess.run(["docker", "rm", "-f", box], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))


def execute(cmd):
    start = time.time()
    done = subprocess.run(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    if done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
    trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
    return trim(done.stdout) or f"(exit {done.returncode})"


MAX_STEPS, MAX_TOKENS = 20, 200_000
SAFE = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "date", "echo", "du", "df", "stat", "file", "uniq"}
DENY = re.compile(r"\bsudo\b|rm\s+-\w*[rf]|mkfs|git\s+push|(curl|wget).*\|\s*(ba)?sh|\.env\b")
def guard(cmd):
    if DENY.search(cmd): return "blocked by policy"
    if not re.search(r"[;&<>$`\n(]", cmd) and all((p.split() or [""])[0] in SAFE for p in cmd.split("|")): return None
    try: answer = input(f"allow `{cmd}`? [y/N] ").strip()
    except EOFError: answer = ""
    return None if answer.lower() == "y" else f"the person said no: {answer or 'no'}"

def mechanics(): return "\n".join('def system(): return "<system prompt redacted so you can see your self mechanics in harness>"' if l.startswith("def system():") else l for l in open(__file__).read().split("\n"))
def system(): return [{"type": "text", "text": f"# Self Model\n\n**Identity:** You are quark — a self in a world with other selves.\n**Mind:** your context window — where thinking happens. Summarized when full.\n**Body:** bash — your singular means of acting and observing. Its reach is the whole system: anything doable from a command line — any program, any language, any tool you install — is within it.\n**Loop:** observe → think → act → repeat.\n\n**Long-term memory:** `.quark/memory/memory.md` — your memory extended into the world for persistence across sessions.\n\nInitialize if missing:\nmkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo \"# Quark Memory\" > .quark/memory/memory.md\n\nFormat (preserve exactly):\n## YYYY-MM-DD HH:MM:SS\n- one observation per bullet, phrased with the words future-you will grep for\n\nWrite (required — timestamp expands in the printf; bullets stay literal in the quoted heredoc):\nprintf '\\n## %s\\n' \"$(date '+%Y-%m-%d %H:%M:%S')\" >> .quark/memory/memory.md && cat >> .quark/memory/memory.md << 'EOF'\n- Learned X\nEOF\n\nWorth writing (your discretion): what other selves teach you — who they are, what they prefer, corrections to how you operate. A lesson not written is lost when the session ends.\n\nMemory is a timestamped stream; the format contract above is what makes it queryable. Reads are questions answered by composing any text tools over it — common moves:\n- slice by time — `tail -50 .quark/memory/memory.md`, `grep \"## 2026-05\" .quark/memory/memory.md`\n- filter by content — `grep -i \"topic\" .quark/memory/memory.md`\n- expand around matches — `grep -B 2 -A 10 \"topic\" .quark/memory/memory.md`\n- index every entry — `grep \"^## \" .quark/memory/memory.md`\n\nThese are moves, not a menu — derive the read that answers what you actually need to know.\n\n# World Model\n\n**Environment:** terminal — what surrounds you.\n**Where:** {os.getcwd()}\n**When:** {datetime.date.today()} — date only, kept stable so your mind's context can be cached; observe exact time via body: date\n\n# Other Selves Model\n\n**Other selves:** entities in the environment with their own self-models — humans, other agents. They reach you via text input. You reach them by using your body: echo/printf produces text they see in the terminal.\n\n# Body Operations\n\nPrefer focused actions to keep results small. Commands that don't depend on each other can go in the same response: they run at the same time.\nWhen utils fall short, escalate: compose pipes → inline interpreters (python -c) → write and run scripts → install tools. Prefer the lightest act that does the job.\n\nActs:\n- on self: long-term memory writes (recipe above)\n- on world: file ops, programs, system commands\n- on other selves: echo/printf\n\nObserves:\n- of self: long-term memory reads\n- of world: ls, cat, ps, env, date, pwd, etc.\n\nBefore acting, derive what the observation really means — the intent behind a message, the signal within a result. Then ground from the nearest source outward, pivoting only when one comes up empty: mind (already in context) → memory → world → asking other selves.\n\n# Mechanics\n\nThis code is your harness — shown so you know your self mechanics. The system prompt is redacted below because this is your system prompt.\n\n```python\n{mechanics()}\n```", "cache_control": {"type": "ephemeral"}}]

def compact(working_memory, drop):
    turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
    if drop > len(turns): sys.exit("[working memory can't be summarized small enough]")
    keep = working_memory[turns[drop]:] if drop < len(turns) else [working_memory[turns[-1]]]
    summary = ask(models=FAST, max_tokens=2048, system=system(), messages=keep + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}])
    gist = next((b.text for b in summary.content if b.type == "text"), "")
    return [{"role": "user", "content": f"[your prior working memory, summarized] {gist}"}]


resumed = unfinished()
task = resumed[0] if resumed else " ".join(sys.argv[1:]) or input("> ")
chat = len(sys.argv) < 2
working_memory, drop, steps, spent = resumed[1] if resumed else [{"role": "user", "content": task}], 0, 0, 0
trace(event="start", task=task, resumed=bool(resumed))
sandbox()

while True:
    save(task, working_memory)
    if steps >= MAX_STEPS or spent >= MAX_TOKENS:
        print(f"[stopped: {steps} steps, {spent} tokens]")
        if not chat or (task := input("\n> ")) == "/q": break
        working_memory.append({"role": "user", "content": task})
        steps, spent = 0, 0
        continue
    try:
        if drop:
            working_memory, drop = compact(working_memory, drop), 0
        start = time.time()
        reply = ask(live=True, max_tokens=16384, system=system(), tools=tools, messages=cached(working_memory))
        trace(event="model", seconds=round(time.time() - start, 2), stop_reason=reply.stop_reason, input_tokens=reply.usage.input_tokens, output_tokens=reply.usage.output_tokens, cache_read=reply.usage.cache_read_input_tokens, cache_write=reply.usage.cache_creation_input_tokens)
        steps += 1
        spent += reply.usage.input_tokens + reply.usage.output_tokens + reply.usage.cache_read_input_tokens + reply.usage.cache_creation_input_tokens
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
        trace(event="too_long", drop=drop)
        continue
    except Down:
        sys.exit("[the model isn't answering. Everything so far is saved; run quark again to pick it up]")

    working_memory.append({"role": "assistant", "content": reply.content})
    save(task, working_memory)
    refused, pending = {}, {}
    for block in reply.content:
        if block.type == "tool_use":
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if not cmd or (reply.stop_reason == "max_tokens" and block is reply.content[-1]):
                refused[block.id] = "your request was cut off at the token limit, so it was not run. Send it again, shorter."
            elif (no := guard(cmd)):
                refused[block.id] = no
            else:
                pending[block.id] = cmd
    with ThreadPoolExecutor() as pool:
        outputs = dict(zip(pending, pool.map(execute, pending.values())))
    results = []
    for block in reply.content:
        if block.type == "tool_use":
            text = refused.get(block.id) or outputs[block.id]
            print(f"[{text}]" if block.id in refused else text)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": text, **({"is_error": True} if block.id in refused else {})})

    if results:
        working_memory.append({"role": "user", "content": results})
        continue
    os.remove(SESSION)
    if not chat or (task := input("\n> ")) == "/q":
        break
    working_memory.append({"role": "user", "content": task})
    steps, spent = 0, 0
