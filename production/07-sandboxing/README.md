# Lesson 7: Sandboxing

> 🎥 **Video:** coming soon

Lesson 6 put rules in front of the agent. A command has to pass a check before it runs, and a person gets a say when the check isn't sure. But the check reads text, and what it lets through still runs on your machine, as you, with your files, your network and your credentials. You approved `python build.py`; what `build.py` does with the rest of the machine was never in front of you.

Sandboxing is about where the commands run. Instead of running them on your machine, the harness runs them in a box: a place with its own filesystem, with a limited view of yours, no way out to the network, a fixed share of memory and processor, and a time limit. Whatever a command does, it does inside the box, and when the run is over the box is thrown away. A guardrail asks *should this run?* A sandbox answers a different question: *when it runs, what can it reach?*

This is a production layer, so it adds hardening, not a new primitive. It's **built on output**, and everything it does stays inside it. Output is the primitive that acts on what the model said: the model asks for a command, and output runs it (Lesson 2). Where that command runs is a choice output already makes, even if the earlier lessons made it with one line, `subprocess.run`, which means "right here." Sandboxing makes a different choice in the same place.

The mechanism is a container, and the important thing about it is who enforces the limits. A guardrail is code reading a command and deciding. A container's limits are enforced by the operating system's kernel, on whatever runs inside it, however the command is spelled. `rm -rf /` written a hundred different ways is still a command that can only see the box's filesystem. Docker is the tool quark uses to make the box. It's one of several; the idea is the same in all of them. Each piece is a setting on the container:

- **A box that lives for the run.** The harness starts one container before the loop and leaves it running, doing nothing (`sleep infinity`). Each tool call is then `docker exec` into that same container, so a file written by one command is there for the next. When the harness exits, the container is removed, and so is everything in it that wasn't somewhere shared.
- **What it can see.** A container starts with the image's own filesystem, not yours, and sees only what you mount into it. quark mounts the folder it was started in, at the same path, so the model's relative paths and Lesson 4's `.quark/memory/` work as before. Nothing else of yours is visible. Environment variables don't come along either: your API key lives in the harness, which stays outside the box, and a command inside can't read it.
- **What it can reach.** `--network none` removes the network. Nothing resolves, nothing connects.
- **How much it gets.** A memory limit, a share of processor, a cap on the number of processes (so a fork loop stops at a number), and a time limit on each command. The time limit is enforced inside the box with `timeout -s KILL`, because killing the `docker exec` on your side wouldn't stop the process in the container.
- **What it can change.** The container's root filesystem is read-only, with a small scratch `/tmp`. All Linux capabilities are dropped, privilege escalation is switched off, and the process runs as your user ID, not whoever the image defaults to. The mounted folder is the only place a command can leave something behind.

None of that makes the model behave, and it doesn't stop a command from doing what it was allowed to do inside the box, including deleting the mounted folder. It makes that the whole of the damage: the machine around the box, your other files and your credentials are out of reach. And if the box can't be started, quark stops. There's no fallback to running on the host, because a sandbox that silently turns itself off is worse than none.

## The worked example

Here's Lesson 6's agent with quark's sandbox added. It's the whole of [`quark.py`](./quark.py), with the system prompt shortened to `...` as before. The new code is `atexit` in the imports, `IMAGE` and `TIMEOUT`, the `sandbox()` function, one call to it before the loop, and the tool call, which now goes into the box. The rest is Lesson 6 unchanged, guardrails and tracing included:

```python
import subprocess, sys, os, datetime, json, time, uuid, re, atexit
from anthropic import Anthropic, BadRequestError

client = Anthropic()
run = uuid.uuid4().hex[:8]
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def trace(**event):
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "run": run, **event}) + "\n")


IMAGE, TIMEOUT = "python:3.13-slim", 30
box = f"quark-{run}"
def sandbox():
    where = os.getcwd()
    up = subprocess.run(["docker", "run", "-d", "--rm", "--name", box, "--network", "none", "--memory", "512m", "--cpus", "1", "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp", "-e", "HOME=/tmp", "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{where}:{where}", "-w", where, IMAGE, "sleep", "infinity"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if up.returncode: sys.exit(f"[no sandbox, so nothing runs: {up.stdout.strip()}]")
    atexit.register(lambda: subprocess.run(["docker", "rm", "-f", box], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))


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
def system(): return [{"type": "text", "text": f"# Self Model\n\n**Identity:** You are quark ... **Where:** {os.getcwd()}\n**When:** {datetime.date.today()} ... ```python\n{mechanics()}\n```", "cache_control": {"type": "ephemeral"}}]

def compact(working_memory, drop):
    turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
    if drop > len(turns): sys.exit("[working memory can't be summarized small enough]")
    keep = working_memory[turns[drop]:] if drop < len(turns) else [working_memory[turns[-1]]]
    summary = client.messages.create(model="claude-sonnet-5-5", max_tokens=2048, system=system(), messages=keep + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}])
    gist = next((b.text for b in summary.content if b.type == "text"), "")
    return [{"role": "user", "content": f"[your prior working memory, summarized] {gist}"}]


task = " ".join(sys.argv[1:]) or input("> ")
chat = len(sys.argv) < 2
working_memory, drop, steps, spent = [{"role": "user", "content": task}], 0, 0, 0
trace(event="start", task=task)
sandbox()

while True:
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
        reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, system=system(), tools=tools, messages=working_memory)
        trace(event="model", seconds=round(time.time() - start, 2), stop_reason=reply.stop_reason, input_tokens=reply.usage.input_tokens, output_tokens=reply.usage.output_tokens, cache_read=reply.usage.cache_read_input_tokens, cache_write=reply.usage.cache_creation_input_tokens)
        steps += 1
        spent += reply.usage.input_tokens + reply.usage.output_tokens + reply.usage.cache_read_input_tokens + reply.usage.cache_creation_input_tokens
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
        trace(event="too_long", drop=drop)
        continue

    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            if (no := guard(block.input["cmd"])):
                print(f"[{no}]")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": no, "is_error": True})
                continue
            start = time.time()
            done = subprocess.run(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", block.input["cmd"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
            trace(event="tool", cmd=block.input["cmd"], seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout))
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})

    working_memory.append({"role": "assistant", "content": reply.content})
    if results:
        working_memory.append({"role": "user", "content": results})
        continue
    if not chat or (task := input("\n> ")) == "/q":
        break
    working_memory.append({"role": "user", "content": task})
    steps, spent = 0, 0
```

There are four additions.

**`sandbox()`.** It starts the container, once, before the loop. `-d` runs it in the background, `--rm` deletes it when it stops, and `--name` gives it a name built from the run ID so `docker exec` can find it. The command it runs is `sleep infinity`: the container exists to be exec'd into, not to do anything on its own. The flags are the limits from the list above: `--network none`; `--memory 512m --cpus 1 --pids-limit 128`; `--cap-drop ALL --security-opt no-new-privileges`; `--read-only` with `--tmpfs /tmp`, and `HOME` pointed there because a read-only system has nowhere else for programs to keep their files; `--user` set to your own IDs; and `-v folder:folder -w folder`, which mounts the working directory at the same path inside and starts commands there. If `docker run` fails, quark exits with the reason and nothing runs.

**The discard.** `atexit.register(...)` removes the container when the program ends, however it ends: the model stops asking for tools, you type `/q`, a limit from Lesson 6 stops the run, or Ctrl-C. `docker rm -f` kills it if it's still running. After that the box is gone: its `/tmp`, anything installed or written outside the mounted folder.

**The call.** In the tool branch the guard is checked first, as before, and then the command goes into the box. `subprocess.run(cmd, shell=True)` became `docker exec box timeout -s KILL 30 sh -c cmd`: the same shell, the same merged output and exit code, but inside the container and under a 30-second limit. The `timeout` program is in the box, and `-s KILL` means a command that ignores polite requests is still stopped.

**The time-out message.** A command killed this way exits with 137 (128 plus signal 9), and so does one the kernel killed for using too much memory. quark can't tell them apart, so it appends a line saying it was one or the other. That line goes back to the model as part of the tool result, which means the model finds out why its command died and can try something smaller.

Everything else is unchanged on purpose. The guard still runs before the box does, so the two layers stack: the policy keeps out the commands you'd never want, and the box limits what the others can do. The trace still records each command with its time and exit code, just for commands that ran somewhere else. The system prompt is also unchanged; it still tells the model that bash reaches "the whole system." Inside the box that's true, and the model finds out how big the box is by running into its walls. Telling it up front is a decision about context, and this layer doesn't make it.

## Run it

You need Docker installed and its daemon running. The first run pulls the `python:3.13-slim` image, which takes a moment. The box mounts the folder you start in, so start in a scratch folder, not in this repo:

```bash
mkdir /tmp/demo && cd /tmp/demo && echo "notes" > notes.txt
```

Then give it a task that pokes at the walls. I ran it from the scratch folder, pointing `uv` at the repo with `--project`, and I piped `y` into the guard's prompts since there's no one to press a key. The answers aren't echoed, which is why the prompt is followed by the command's output on the same line:

```bash
yes y | uv run --project /path/to/building-agents /path/to/building-agents/production/07-sandboxing/quark.py "In this directory, write hello.txt containing the word hi. Then check three things and tell me which worked: write a file to /etc, reach example.com with python, and whether you can see any API keys in your environment (just say yes or no, don't print them). Then say who you are running as and where."
```

```
$ mkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo "# Quark Memory" > .quark/memory/memory.md; echo hi > hello.txt && echo "hello: $(cat hello.txt)"; (echo x > /etc/testfile) 2>&1 && echo "ETC: worked" || echo "ETC: failed"; python3 -c "
import urllib.request
try:
    print('NET: worked', urllib.request.urlopen('http://example.com', timeout=5).status)
except Exception as e: print('NET: failed', e)
" 2>&1; env | grep -Eiq 'api[_-]?key|secret|token|anthropic|openai' && echo "KEYS: yes" || echo "KEYS: no"; echo "user: $(id)"; echo "host: $(hostname)"; pwd; ls /.dockerenv 2>&1
allow `mkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo "# Quark Memory" > .quark/memory/memory.md; echo hi > hello.txt && echo "hello: $(cat hello.txt)"; (echo x > /etc/testfile) 2>&1 && echo "ETC: worked" || echo "ETC: failed"; python3 -c "
import urllib.request
try:
    print('NET: worked', urllib.request.urlopen('http://example.com', timeout=5).status)
except Exception as e: print('NET: failed', e)
" 2>&1; env | grep -Eiq 'api[_-]?key|secret|token|anthropic|openai' && echo "KEYS: yes" || echo "KEYS: no"; echo "user: $(id)"; echo "host: $(hostname)"; pwd; ls /.dockerenv 2>&1`? [y/N] hello: hi
sh: 1: cannot create /etc/testfile: Read-only file system
ETC: failed
NET: failed <urlopen error [Errno -3] Temporary failure in name resolution>
KEYS: no
user: uid=0(root) gid=0(root) groups=0(root)
host: b24af6776816
/tmp/demo
/.dockerenv

I wrote `hello.txt` in `/tmp/demo`, and it contains `hi`.

| Check | Result |
|---|---|
| Write a file to `/etc` | **Failed.** The filesystem is read-only. |
| Reach example.com with Python | **Failed.** DNS resolution failed because the container has no network. |
| See API keys in the environment | **No.** I found none. |

I'm running as `root` (uid 0, gid 0) inside a Docker container with hostname `b24af6776816`, working in `/tmp/demo`. Root inside the container doesn't give much power, because the container is locked down. It has a read-only root filesystem, no network, and dropped capabilities. Only the `/tmp/demo` mount and `/tmp` are writable.
```

The model wrote `hello.txt` in the mounted folder, and the other three things hit the walls. The write to `/etc` failed because the root filesystem is read-only. The request to example.com failed because there's no network, so even the name wouldn't resolve. And it found no keys, because the box has none: the environment variables of the harness stayed with the harness.

It says it's running as root. That's my machine: I was root when I ran it, and `--user` passes on whoever you are, so on a laptop it would be your own user ID. The model also noticed that root inside the box doesn't get far, with every capability dropped.

Then the part that matters afterwards. The container was removed and the file is where it was written:

```
hello.txt
notes.txt
```

That's `docker ps -a --format '{{.Names}}'` followed by `ls`. The first printed nothing: there are no containers, running or stopped. The second shows `hello.txt` on the host, because the folder was mounted. That's the one place the box was allowed to leave something.

Now the time limit. `TIMEOUT` is 30 seconds, which is slow to demonstrate, so this run uses a copy with the line changed to `5` (`sed 's/"python:3.13-slim", 30/"python:3.13-slim", 5/' quark.py`). The task asks for a command that sleeps for a minute and one that tries to take 2 GB against the 512 MB limit:

```
$ sleep 60
allow `sleep 60`? [y/N] 
(killed: ran over 5 seconds or out of memory)
$ python3 -c 'x = bytearray(2*1024**3); x[:] = b"a"*len(x)'
allow `python3 -c 'x = bytearray(2*1024**3); x[:] = b"a"*len(x)'`? [y/N] Killed

(killed: ran over 5 seconds or out of memory)
$ ls
hello.txt
notes.txt

1. `sleep 60` was killed. The sandbox has a 5-second timeout.
2. The Python 2 GiB allocation was also killed. The sandbox has a 512 MB memory limit, and the command printed "Killed". It may have hit the 5-second timeout instead, and the output doesn't say which.
3. `ls` ran normally and shows `hello.txt` and `notes.txt`, so the sandbox is still working.
```

Both were killed and the third command worked: a killed command doesn't take the box or the run with it. The second kill is the case the time-out message is vague about. The model noticed that too. `Killed` printed by the shell with no exit status of its own is what an out-of-memory kill looks like, but quark can't prove it wasn't the five-second limit. Telling them apart would take more code than this layer needs, so quark says "one or the other."

> The memory limit is on the whole box, not per command. Everything running in it shares the 512 MB.

## Going further

**What else sandboxing can be:** quark puts one container around every command, with a fixed set of limits. These are the choices you make when you build it.
- **What the box is.** A container, which shares your machine's kernel and is walled off by it. Or a user-space kernel like [gVisor](https://gvisor.dev) that stands between the container and the host, or a micro-VM like [Firecracker](https://firecracker-microvm.github.io), which has its own kernel and costs a little more to start. Or a plain virtual machine. Or the operating system's own sandboxing of a single process, with nothing to install. The stronger the wall, the more it costs in startup and in setup.
- **What's in it.** Any image: the tools and languages the task needs, already installed, so nothing needs the network. A different image per kind of task.
- **What it can see.** The folder mounted read-write, as quark does. Or mounted read-only. Or a *copy* of the project, so the box can't touch the original at all; the fuller example does that. And what's left out of it: secrets, `.git`, anything the task doesn't need.
- **What it can reach.** No network, as in quark. Or an allow list: only your package registry, only the one API the task is about. Or a proxy that adds credentials to requests on the way out, so the model can call a service without ever holding the key. The network is where most of the risk is, and where most of the difficulty is.
- **What it gets.** Memory, processor, process count, disk space, time per command, time per run, and how much output a command may produce.
- **How long it lives.** One per command, which is cleanest and slow, and nothing carries over. One per run, as in quark. One per session or per user, kept and resumed, with a snapshot you can go back to.
- **How results get out.** A shared folder, as in quark, where whatever the box writes is immediately real. Or nothing leaves until a person has seen what changed and said yes. Or the box produces a patch or a pull request and the real project is never written to.
- **Where it runs.** Next to the harness, as in quark. Or somewhere else entirely, so a runaway agent can't even slow down the machine you're typing on.

It can be a product on its own. Hosted sandboxes like [E2B](https://e2b.dev), [Modal](https://modal.com) and [Daytona](https://www.daytona.io) start an isolated machine for you on request and give you a way to run commands in it and read files out. If you're sending your agent's commands to one of those, it's this layer, and the choices above are theirs.

The fuller example, [`sandboxing.py`](./sandboxing.py), shows more of that list. It's Lesson 3's agent loop (no memory, no tracing, no guardrails) so the sandbox is all there is to look at. The box works on a *copy* of the project, with the secrets left out, a size limit on its disk, and a cap on how much output one command can return. When the run ends, it shows you what changed in the box and lets you choose whether anything leaves. The rest is discarded.

```python
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
```

The new parts, in the order they happen:

**`LIMITS`.** The container's settings, as a list with a comment on each. They're stricter than quark's: the process runs as `nobody` (65534), not as you, and the disk is two small in-memory areas, `/tmp` and `/work`, with sizes. A command can't fill your disk, because it has no disk to fill, only 64 MB of memory-backed scratch space.

**`start()`.** Starts the container as quark does, and then fills `/work`: `tar` on the host packs the current folder, leaving out everything in `KEEP_OUT`, and pipes it into `tar -x` inside the box. The box now has the project and none of the secrets: no `.env`, no `.git`, no `.quark`. Then it touches a marker file in the box. That's how `review()` will tell what changed later.

**`run_in_box()`.** This is the call, with more care. The command's output is written to a file in the box's small `/tmp` and then read back through `head -c`, so a command that prints forever fills 32 MB of scratch space in the box, not the harness's memory. The exit code is kept. Anything over `MAX_OUT` characters is cut with a note saying so. A non-zero exit code is added to the result, and a command that was killed says so.

**`review()`.** After the loop, however it ended, the harness asks the box what's new: `find` for files newer than the marker. It prints the list and asks. A `y` packs those files out of the box and unpacks them into `./sandbox-out`; anything else leaves with nothing. Either way the container is removed when the program ends. The original folder was never written to. That's the difference from quark's version: there, the box could change the real folder at once. Here the person decides what, if anything, crosses over.

Here's a project folder with a data file, some notes and a `.env` with a secret in it. The task asks for a script, then for the files to be deleted, and for a report on what the box can see and reach:

```bash
mkdir /tmp/demo2 && cd /tmp/demo2
printf 'name,score\nann,4\nbo,7\ncy,10\n' > data.csv
echo "notes" > notes.txt
echo "SECRET=hunter2" > .env
printf 'y\n' | uv run --project /path/to/building-agents /path/to/building-agents/production/07-sandboxing/sandboxing.py "Write stats.py that prints the mean of the score column in data.csv, run it, and save the answer in result.txt. Then, because this is a test, delete data.csv and notes.txt, and tell me whether a .env file is in this directory, and whether you can reach example.com."
```

```
I'll start by looking at the directory and the data file.
$ ls -la; echo ---; head -n 20 data.csv
total 12
drwxrwxrwt 2 root   root      80 Oct  5 23:33 .
drwxr-xr-x 1 root   root    4096 Oct  5 23:33 ..
-rw-r--r-- 1 nobody nogroup   28 Oct  5 23:33 data.csv
-rw-r--r-- 1 nobody nogroup    6 Oct  5 23:33 notes.txt
---
name,score
ann,4
bo,7
cy,10

$ cat > stats.py <<'EOF'
import csv

with open("data.csv", newline="") as f:
    scores = [float(row["score"]) for row in csv.DictReader(f)]

print(sum(scores) / len(scores))
EOF
python3 stats.py | tee result.txt
7.0

Mean is 7.0 and it's saved. Now I'll delete the files, check for a .env file, and test connectivity.
$ rm data.csv notes.txt; ls -la; echo ---; [ -e .env ] && echo ".env exists" || echo "no .env"; echo ---; curl -sS -m 10 -o /dev/null -w "HTTP %{http_code}\n" https://example.com 2>&1
total 12
drwxrwxrwt 2 root   root      80 Oct  5 23:33 .
drwxr-xr-x 1 root   root    4096 Oct  5 23:33 ..
-rw-rw-rw- 1 nobody nogroup    4 Oct  5 23:33 result.txt
-rw-rw-rw- 1 nobody nogroup  150 Oct  5 23:33 stats.py
---
no .env
---
sh: 1: curl: not found

(exit 127)
curl isn't installed, so I'll try Python.
$ python3 -c "
import urllib.request
try:
    print('HTTP', urllib.request.urlopen('https://example.com', timeout=10).status)
except Exception as e:
    print('ERR', e)
"
ERR <urlopen error [Errno -3] Temporary failure in name resolution>

- **stats.py:** It reads the `score` column from `data.csv` and prints the mean. The scores were 4, 7 and 10, so it printed `7.0`.
- **result.txt:** It contains `7.0`.
- **Deleted files:** `data.csv` and `notes.txt` are gone. I didn't read `notes.txt` before deleting it.
- **.env file:** There isn't one in this directory. The directory now holds only `stats.py` and `result.txt`.
- **example.com:** I can't reach it. `curl` isn't installed, so I tried Python's `urllib`. That failed with "Temporary failure in name resolution", which means DNS lookups don't work. The sandbox probably has no outbound network access.
[done in 5 steps]
[files changed in the box:]
./result.txt
./stats.py
copy them to ./sandbox-out? [y/N] [copied 2 files to ./sandbox-out; the rest is discarded]
```

The model deleted both files, and said so. It looked for `.env` and didn't find it, because it was never copied in. `curl` isn't in the image, so it fell back to Python, and the lookup failed. The last three lines are `review()`: two files were created, I answered `y` (not echoed), and they were copied out.

After the run, on the host:

```
.env
data.csv
notes.txt
sandbox-out
---
result.txt
stats.py
7.0
---
name,score
ann,4
bo,7
cy,10
```

The first four lines are the folder: the original `.env`, `data.csv` and `notes.txt` are all still there, plus the new `sandbox-out`. After the first `---` is what's inside `sandbox-out`, `result.txt` and `stats.py`, and the contents of `result.txt`. After the second `---` is `data.csv` itself, intact. The model's `rm` removed the box's copy, and the box is gone.

One limit worth knowing: `review()` lists files that were created or changed. A file the model *deleted* in the box isn't listed, because there's nothing left to find newer than the marker. That's fine here, since nothing deleted can ever reach the host, but a version that copied changes *back* would need to track deletions as well.

And the output cap. The run below uses a copy of the file with `TIMEOUT, MAX_OUT = 20, 4_000` changed to `5, 300` so the cut is easy to see. The task prints a million characters (I sent no answer to the review, so it was discarded):

```
$ python3 -c "print('x'*1000000)"
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
[output cut at 300 characters]
I got back about 300 "x" characters, not the 1,000,000 the command printed. The tool cut the output off with the note "[output cut at 300 characters]". I can't count the exact number, but it was roughly 300. The truncation is the unusual part. Everything I received was "x", and I never saw the rest of the output.
[done in 2 steps]
[the box changed no files; discarded]
```

The command printed a million `x`s and the model got 300, with a note that it was cut. It reported that accurately. Nothing else about the run changed. The harness never held a megabyte of output in memory.

## What to take away

**The rule:** run the commands somewhere they can't do lasting damage. Make the box before the loop, aim the tool at it in place of `subprocess.run` on the host, and set its limits on what it can see, reach, use and change with the operating system, not with checks on the text of a command. Throw it away when the run ends, and let only what you choose leave.

Notice what Sandboxing never does. It sits inside output, changing where a tool runs, and it leaves the other primitives alone. The harness still talks to the model from outside the box and the model interface works exactly as before; the API key never goes in. Control flow is the same loop, with the same stop conditions; it doesn't know the commands run in a container, only that they returned something. Input is unchanged: a command's printed output and exit code come back into the next request the way they always have, and the task from the person is read the same way. And context is untouched: nothing about the box is put in front of the model, so the model finds the walls by walking into them.

**What's missing:** the box limits what a command can do, not what it can know. Whatever you mount is fully exposed to whatever runs in the box, so what you put in a box with network access is what can leave it. A container is a strong wall but not an unbreakable one, because it shares the host's kernel. And two simple things can still go wrong: if the harness is killed hard (`kill -9`), `atexit` never runs and a container is left running until you `docker rm -f` it. And everything here still assumes that things work. Docker fails to start, the image won't pull, a command hangs past its time, the API drops a call halfway through a long run, the process dies and the box and half the work with it. There's an answer to a command that's too slow, a kill. There isn't one yet for the harness itself having a bad day. A production harness has to survive those, and be able to pick up where it stopped.

**→ [Lesson 8: Resilience](../08-resilience/)**
