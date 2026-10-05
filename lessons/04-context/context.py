import subprocess, sys, os, json, glob, datetime
from anthropic import Anthropic

client = Anthropic()
MODEL = "claude-sonnet-5-5"
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
LIMIT, KEEP = 50_000, 4_000

def system():
    skills = "\n".join(f"- {p}: {open(p).readline().strip()}" for p in sorted(glob.glob(".quark/skills/*.md"))) or "(none yet)"
    return f"""You are quark, an agent whose body is bash. You're in {os.getcwd()}, and today is {datetime.date.today()}.
Past sessions are logged one message per line in .quark/episodes.jsonl. Search it when the past matters.
Skills: before a task one of these covers, read it with cat and follow it.
{skills}"""

def remember(message):
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/episodes.jsonl", "a") as f: f.write(json.dumps(message, default=lambda b: b.model_dump()) + "\n")

def trim(text):
    return text if len(text) <= KEEP else f"{text[:KEEP // 2]}\n[... {len(text) - KEEP} characters cut ...]\n{text[-KEEP // 2:]}"

def fit(working_memory):
    if client.messages.count_tokens(model=MODEL, system=system(), tools=tools, messages=working_memory).input_tokens < LIMIT: return working_memory
    turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
    if len(turns) < 2: return working_memory
    old, recent = working_memory[:turns[-1]], working_memory[turns[-1]:]
    summary = client.messages.create(model=MODEL, max_tokens=2048, messages=old + [{"role": "user", "content": "Summarize this session so far into a gist that preserves what matters for continuing."}])
    gist = next((b.text for b in summary.content if b.type == "text"), "")
    print(f"[working memory over {LIMIT} tokens: summarized {turns[-1]} messages]")
    return [{"role": "user", "content": f"[earlier in this session, summarized] {gist}"}] + recent

def add(working_memory, message):
    working_memory.append(message); remember(message)

task = " ".join(sys.argv[1:]) or input("> ")
chat = len(sys.argv) < 2
working_memory = []
add(working_memory, {"role": "user", "content": task})

while True:
    working_memory = fit(working_memory)
    reply = client.messages.create(model=MODEL, max_tokens=16384, system=system(), tools=tools, messages=working_memory)
    results = []
    for block in reply.content:
        if block.type == "text": print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": trim(done.stdout) or f"(exit {done.returncode})"})
    add(working_memory, {"role": "assistant", "content": reply.content})
    if results:
        add(working_memory, {"role": "user", "content": results}); continue
    if not chat or (task := input("\n> ")) == "/q": break
    add(working_memory, {"role": "user", "content": task})
