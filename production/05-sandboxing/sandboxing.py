import subprocess, sys, os, uuid, atexit
from anthropic import Anthropic
from typesafe_sdk import TypeSafeClient, TypeSafeError, Choice
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS = 10
box = f"quark-{uuid.uuid4().hex[:8]}"

# What the box is made of, and how much it gets.
IMAGE = "python:3.13-slim"
LIMITS = [
    "--network", box,                                     # no way out: a network of its own, with no route off it
    "--memory", "256m", "--cpus", "1", "--pids-limit", "64",  # no hogging
    "--cap-drop", "ALL", "--security-opt", "no-new-privileges",  # no powers
    "--user", "65534:65534", "-e", "HOME=/tmp",           # nobody, not root
    "--read-only",                                        # the system can't change
    "--tmpfs", "/tmp:size=32m", "--tmpfs", "/work:size=64m,mode=1777",  # the only places that can, and how much
    "-w", "/work",
]
KEEP_OUT = [".env", ".git", ".venv", ".quark", "__pycache__"]  # never copied in
TIMEOUT, MAX_OUT = 20, 4_000

# Jev, a second model that writes nothing and only decides: does this command need a way out?
try: jev = TypeSafeClient(timeout=5)                     # reads TYPESAFE_API_KEY
except TypeSafeError: jev = None                         # no key, no Jev: the box just stays shut
NEEDS = Choice(instructions="To work, what does the shell command in `command` need beyond reading and writing files in the current folder?",
    criteria={"nothing": "it works inside the current folder with no network",
              "network": "it must reach the internet or another machine: downloads, installs from a registry, clones, web requests",
              "outside": "it must change things outside the current folder: home directory, system paths, other processes"})
SURE = 0.9

def docker(*args, **kw):
    return subprocess.run(["docker", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)

def ask(question):
    try: return read(question).strip().lower() == "y"
    except EOFError: return False

def start():
    docker("network", "create", "--internal", box)        # internal: no route out until one is lent
    atexit.register(lambda: docker("network", "rm", box))
    up = docker("run", "-d", "--rm", "--name", box, *LIMITS, IMAGE, "sleep", "infinity")
    if up.returncode: sys.exit(f"[no sandbox, so nothing runs: {up.stdout.strip()}]")
    atexit.register(lambda: docker("rm", "-f", box))
    # Copy the project in, minus anything that shouldn't be there. The box works on a copy.
    tar = subprocess.Popen(["tar", "-c", *[f"--exclude={n}" for n in KEEP_OUT], "."], stdout=subprocess.PIPE)
    docker("exec", "-i", box, "tar", "-x", "-C", "/work", "--no-same-owner", stdin=tar.stdout)
    docker("exec", box, "touch", "/tmp/start")

def needs(cmd):
    # Jev's answer only decides whether to ask. No answer, and the box stays shut.
    try: answer = jev.system_one({"command": cmd}, {"needs": NEEDS}).choices["needs"]
    except Exception: return "no answer", 0.0
    return answer.choice, answer.confidence

def run_in_box(cmd):
    need, sure = needs(cmd)
    print(f"[Jev: {need}, {sure:.2f}]")
    lend = need == "network" and sure >= SURE and ask("it needs the network: allow it for this one command? [y/N] ")
    if lend: docker("network", "connect", "bridge", box)  # a way out, for this command only
    # Output goes to the box's small /tmp first, so a command that prints forever can't fill the harness's memory.
    script = f'timeout -s KILL {TIMEOUT} sh -c "$0" >/tmp/out 2>&1; code=$?; head -c {MAX_OUT} /tmp/out; exit $code'
    try: done = docker("exec", box, "sh", "-c", script, cmd)
    finally:
        if lend: docker("network", "disconnect", "bridge", box)
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
    if ask("copy them to ./sandbox-out? [y/N] "):
        os.makedirs("sandbox-out", exist_ok=True)
        pack = subprocess.Popen(["docker", "exec", "-i", box, "tar", "-c", "-T", "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        pack.stdin.write("\n".join(changed).encode()); pack.stdin.close()
        subprocess.run(["tar", "-x", "-C", "sandbox-out", "--no-same-owner"], stdin=pack.stdout)
        print(f"[copied {len(changed)} files to ./sandbox-out; the rest is discarded]")
    else:
        print("[discarded]")

input = " ".join(sys.argv[1:]) or read("> ")
messages = [{"role": "user", "content": input}]
start()

for step in range(1, MAX_STEPS + 1):
    output = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)
    messages.append({"role": "assistant", "content": output.content})
    if output.stop_reason == "refusal":
        print("[stopped: the model declined]")
        break
    input = []
    for block in output.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            out = run_in_box(block.input["cmd"])
            print(out)
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
    if not input:
        print(f"[done in {step} steps]")
        break
    messages.append({"role": "user", "content": input})
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")

review()
