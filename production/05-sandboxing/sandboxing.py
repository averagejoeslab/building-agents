import subprocess, sys, os, uuid, atexit
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS = 10

# What the box is made of, and how much it gets.
IMAGE = "python:3.13-slim"
LIMITS = [
    "--network", "none",                                  # no way out
    "--memory", "256m", "--cpus", "1", "--pids-limit", "64",  # no hogging
    "--cap-drop", "ALL", "--security-opt", "no-new-privileges",  # no powers
    "--user", "65534:65534", "-e", "HOME=/tmp",           # nobody, not root
    "--read-only",                                        # the system can't change
    "--tmpfs", "/tmp:size=32m", "--tmpfs", "/work:size=64m,mode=1777",  # the only places that can, and how much
    "-w", "/work",
]
KEEP_OUT = [".env", ".git", ".venv", ".quark", "__pycache__"]  # never copied in
TIMEOUT, MAX_OUT = 20, 4_000
box = f"quark-{uuid.uuid4().hex[:8]}"

def docker(*args, **kw):
    return subprocess.run(["docker", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)

def start():
    up = docker("run", "-d", "--rm", "--name", box, *LIMITS, IMAGE, "sleep", "infinity")
    if up.returncode: sys.exit(f"[no sandbox, so nothing runs: {up.stdout.strip()}]")
    atexit.register(lambda: docker("rm", "-f", box))
    # Copy the project in, minus anything that shouldn't be there. The box works on a copy.
    tar = subprocess.Popen(["tar", "-c", *[f"--exclude={n}" for n in KEEP_OUT], "."], stdout=subprocess.PIPE)
    docker("exec", "-i", box, "tar", "-x", "-C", "/work", "--no-same-owner", stdin=tar.stdout)
    docker("exec", box, "touch", "/tmp/start")

def run_in_box(cmd):
    # Output goes to the box's small /tmp first, so a command that prints forever can't fill the harness's memory.
    script = f'timeout -s KILL {TIMEOUT} sh -c "$0" >/tmp/out 2>&1; code=$?; head -c {MAX_OUT} /tmp/out; exit $code'
    done = docker("exec", box, "sh", "-c", script, cmd)
    out = done.stdout
    if len(out) >= MAX_OUT: out += f"\n[output cut at {MAX_OUT} characters]"
    if done.returncode == 137: out += f"\n(killed: ran over {TIMEOUT} seconds, or out of memory)"
    elif done.returncode: out += f"\n(exit {done.returncode})"
    return out or "(no output)"

def review():
    # The box is about to be thrown away. Only what the person picks leaves it.
    changed = docker("exec", box, "find", ".", "-type", "f", "-newer", "/tmp/start").stdout.split()
    if not changed: return print("[the box changed no files; discarded]")
    print("[files changed in the box:]\n" + "\n".join(changed))
    try: answer = input("copy them to ./sandbox-out? [y/N] ").strip().lower()
    except EOFError: answer = ""
    if answer == "y":
        os.makedirs("sandbox-out", exist_ok=True)
        pack = subprocess.Popen(["docker", "exec", "-i", box, "tar", "-c", "-T", "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        pack.stdin.write("\n".join(changed).encode()); pack.stdin.close()
        subprocess.run(["tar", "-x", "-C", "sandbox-out", "--no-same-owner"], stdin=pack.stdout)
        print(f"[copied {len(changed)} files to ./sandbox-out; the rest is discarded]")
    else:
        print("[discarded]")

task = " ".join(sys.argv[1:]) or input("> ")
messages = [{"role": "user", "content": task}]
start()

for step in range(1, MAX_STEPS + 1):
    reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)
    messages.append({"role": "assistant", "content": reply.content})
    if reply.stop_reason == "refusal":
        print("[stopped: the model declined]")
        break
    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            out = run_in_box(block.input["cmd"])
            print(out)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
    if not results:
        print(f"[done in {step} steps]")
        break
    messages.append({"role": "user", "content": results})
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")

review()
