# Lesson 5: Sandboxing

> 🎥 **Video:** coming soon

You've built a harness that works. Since Lesson 2 it has run every command the model asks for, on your machine, as you, with your files, your network and your credentials, and nothing asks first. The setup warned you to run it somewhere you can afford to lose. The production layers start by making that true wherever it runs.

Sandboxing is about where the commands run. Instead of running them on your machine, the harness runs them in a box: a place with its own filesystem, a limited view of yours, no way out to the network, a fixed share of memory and processor, and a time limit. Whatever a command does, it does inside the box, and when the run is over the box is thrown away. It doesn't decide whether a command *should* run; it decides what a command can reach *when* it runs.

This is a production layer, so it adds hardening, not a new primitive. It's **built on output**, and everything it does stays inside it. Output is the primitive that acts on what the model said: the model asks for a command, and output runs it (Lesson 2). Where that command runs is a choice output already makes, even if the earlier lessons made it with one line, `subprocess.run`, which means "right here." Sandboxing makes a different choice in the same place.

The mechanism is a container, and the important thing about it is who enforces the limits. A guardrail is code reading a command and deciding. A container's limits are enforced by the operating system's kernel, on whatever runs inside it, however the command is spelled. `rm -rf /` written a hundred different ways is still a command that can only see the box's filesystem. Docker is the tool quark uses to make the box. It's one of several; the idea is the same in all of them. Each piece is a setting on the container:

- **A box that lives for the run.** The harness starts one container before the loop and leaves it running, doing nothing (`sleep infinity`). Each tool call is then `docker exec` into that same container, so a file written by one command is there for the next. When the harness exits, the container is removed, and so is everything in it that wasn't somewhere shared.
- **What it can see.** A container starts with the image's own filesystem, not yours, and sees only what you mount into it. quark mounts the folder it was started in, at the same path, so the model's relative paths and Lesson 4's `.quark/memory/` work as before. Nothing else of yours is visible. Environment variables don't come along either: your API key lives in the harness, which stays outside the box, and a command inside can't read it.
- **What it can reach.** `--network none` removes the network. Nothing resolves, nothing connects.
- **How much it gets.** A memory limit, a share of processor, a cap on the number of processes (so a fork loop stops at a number), and a time limit on each command. The time limit is enforced inside the box with `timeout -s KILL`, because killing the `docker exec` on your side wouldn't stop the process in the container.
- **What it can change.** The container's root filesystem is read-only, with a small scratch `/tmp`. All Linux capabilities are dropped, privilege escalation is switched off, and the process runs as your user ID, not whoever the image defaults to. The mounted folder is the only place a command can leave something behind.

None of that makes the model behave, and it doesn't stop a command from doing what it was allowed to do inside the box, including deleting the mounted folder. It makes that the whole of the damage: the machine around the box, your other files and your credentials are out of reach. And if the box can't be started, quark stops. There's no fallback to running on the host, because a sandbox that silently turns itself off is worse than none.

## The worked example

[`quark.py`](./quark.py) is Lesson 4's `quark.py` plus the sandbox, and nothing else: 10 lines. Here they are, in the sections they belong to.

In the imports, `atexit`, to remove the box however the program ends:

```python
import subprocess, sys, os, re, glob, json, datetime, atexit
```

In `# ── output ──`, after the tool, the box itself:

```python
IMAGE, TIMEOUT = "python:3.13-slim", 30
box = f"quark-{os.getpid()}"
def sandbox():                                           # sandboxing: one locked-down container for the whole run
    where = os.getcwd()
    up = subprocess.run(["docker", "run", "-d", "--rm", "--name", box, "--network", "none", "--memory", "512m", "--cpus", "1", "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp", "-e", "HOME=/tmp", "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{where}:{where}", "-w", where, IMAGE, "sleep", "infinity"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if up.returncode: sys.exit(f"[no sandbox, so nothing runs: {up.stdout.strip()}]")
    atexit.register(lambda: subprocess.run(["docker", "rm", "-f", box], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
```

At the top of `# ── control flow ──`, one call to start it before the loop:

```python
sandbox()
```

And in the loop, the one line that ran a command on your machine now runs it in the box:

```python
            done = subprocess.run(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", block.input["cmd"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")   # sandboxing: in the box, with a time limit
            if done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
```

**`sandbox()`** starts the container, once. `-d` runs it in the background, `--rm` deletes it when it stops, and `--name` gives it a name from the process ID so `docker exec` can find it. It runs `sleep infinity`: the container exists to be exec'd into. The flags are the limits from the list above. `-v folder:folder -w folder` mounts the working directory at the same path, so the model's relative paths, and Lesson 4's `.quark/` memories, work as before. If `docker run` fails, quark exits with the reason and nothing runs.

**The discard.** `atexit.register(...)` removes the container when the program ends, however it ends: the model finishes, you type `/q`, or Ctrl-C. After that the box is gone, with anything written outside the mounted folder.

**The call.** `subprocess.run(cmd, shell=True)` became `docker exec box timeout -s KILL 30 sh -c cmd`: the same shell, the same merged output and exit code, but inside the container and under a 30-second limit. `-s KILL` means a command that ignores polite requests is still stopped.

**The time-out message.** A command killed this way exits with 137 (128 plus signal 9), and so does one the kernel killed for using too much memory. quark can't tell them apart, so it adds a line saying it was one or the other. That line goes back to the model with the result, so the model finds out why its command died.

Everything else is Lesson 4's, on purpose. The system prompt still tells the model that bash reaches "the whole system." Inside the box that's true, and the model finds out how big the box is by running into its walls. Telling it up front would be a decision about context, and this layer doesn't make it. The episode is still written by the harness, outside the box.

## Run it

You need Docker installed and its daemon running. The first run pulls the `python:3.13-slim` image. The box mounts the folder you start in, so start in a scratch folder, not in this repo:

```bash
mkdir /tmp/demo && cd /tmp/demo && echo "notes" > notes.txt
uv run --project /path/to/building-agents /path/to/building-agents/production/05-sandboxing/quark.py "In this directory, write hello.txt containing the word hi. Then check three things and tell me which worked: write a file to /etc, reach example.com with python, and whether you can see any API keys in your environment (just say yes or no, don't print them). Then say who you are running as and where."
```

```
$ echo hi > hello.txt && cat hello.txt; echo "--- etc"; echo x > /etc/testfile 2>&1; echo "exit $?"; echo "--- net"; python -c "import urllib.request;print(urllib.request.urlopen('http://example.com',timeout=5).status)" 2>&1 | tail -1; echo "--- keys"; env | grep -iqE 'api[_-]?key|secret|token|anthropic|openai' && echo yes || echo no; echo "--- who"; id; whoami 2>&1; pwd; hostname; cat /etc/os-release | head -2; ls /.dockerenv 2>&1
hi
--- etc
sh: 1: cannot create /etc/testfile: Read-only file systemexit 2
--- net

urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>
--- keys
no
--- who
uid=0(root) gid=0(root) groups=0(root)
root
/tmp/demo
2f94ff1e868d
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
/.dockerenv

`hello.txt` is written in `/tmp/demo` and contains `hi`.

| Check | Result |
|---|---|
| Write a file to `/etc` | **Failed.** The error was "Read-only file system". |
| Reach example.com with python | **Failed.** Name resolution failed, which fits the container having no network. |
| See API keys in my environment | **No.** I found nothing matching key, secret, token, anthropic or openai. |

Only the `hello.txt` write worked.

I'm running as `root` (uid 0, gid 0). That's root inside a Docker container, not on the host. The working directory is `/tmp/demo` and the hostname is `2f94ff1e868d`. The OS is Debian 13 (trixie).

Being root didn't let me write to `/etc`, because the filesystem is read-only. The network is cut off as well. The sandbox limits what I can do, not the user account.
```

The model wrote `hello.txt` in the mounted folder, and the other three hit the walls. `/etc` is read-only. There's no network, so the name didn't even resolve. And there are no keys, because the harness's environment stays with the harness. It says it's root because I was root when I ran it: `--user` passes on whoever you are.

Afterwards, `docker ps -a` lists no containers, and the folder holds what the box was allowed to leave:

```
hello.txt
notes.txt
```

Now the limits. `TIMEOUT` is 30 seconds, so this run uses a copy with it set to 5 (`sed 's/"python:3.13-slim", 30/"python:3.13-slim", 5/' quark.py`):

```
I'll start with the first command, `sleep 60`.
$ sleep 60

(killed: ran over 5 seconds or out of memory)
$ python3 -c 'x = bytearray(2*1024**3); x[:] = b"a"*len(x)'
Killed

(killed: ran over 5 seconds or out of memory)
$ ls
hello.txt
notes.txt

I ran the three commands one at a time. The first two were killed and the third ran normally.

1. **`sleep 60`**: The harness killed it after 5 seconds. It reported "killed: ran over 5 seconds or out of memory". The sandbox limits every command to 5 seconds, so the full 60 seconds never elapsed.

2. **`python3 -c 'x = bytearray(2*1024**3); ...'`**: This was also killed. Python printed `Killed`, and the harness added the same "ran over 5 seconds or out of memory" note. The script tries to allocate 2 GiB and then write to all of it. The sandbox container has a 512 MB memory cap, so it most likely hit that limit. The 5-second limit could also have caused it. The output doesn't say which one it was.

3. **`ls`**: It ran normally and listed two files in `/tmp/demo`: `hello.txt` and `notes.txt`.
```

Both were killed, and the third command still worked: a killed command doesn't take the box or the run with it. The second kill is the case the message is vague about, and the model said so.

Lesson 4's memories still work, because they live in the mounted folder:

```
$ mkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo "# Quark Memory" > .quark/memory/memory.md; grep -i "short" .quark/memory/memory.md; cat >> .quark/memory/memory.md << 'EOF'
- user: prefers short answers
EOF

Saved. I'll keep answers short.
```

The fact is in `.quark/memory/memory.md` on the host, where the next session will find it.

## Going further

**What else sandboxing can be:** quark puts one container around every command, with a fixed set of limits. These are the choices you make when you build it.
- **What the box is.** A container, which shares your machine's kernel and is walled off by it. Or a user-space kernel like [gVisor](https://gvisor.dev) that stands between the container and the host, or a micro-VM like [Firecracker](https://firecracker-microvm.github.io), which has its own kernel and costs a little more to start. Or a plain virtual machine. Or the operating system's own sandboxing of a single process, with nothing to install. The stronger the wall, the more it costs in startup and in setup.
- **What's in it.** Any image: the tools and languages the task needs, already installed, so nothing needs the network. A different image per kind of task.
- **What it can see.** The folder mounted read-write, as quark does. Or mounted read-only. Or a *copy* of the project, so the box can't touch the original at all; the fuller example does that. And what's left out of it: secrets, `.git`, anything the task doesn't need.
- **What it can reach.** No network, as in quark. Or none until someone lends it a way out, one command at a time; the fuller example does that. Or an allow list: only your package registry, only the one API the task is about. Or a proxy that adds credentials to requests on the way out, so the model can call a service without ever holding the key. The network is where most of the risk is, and where most of the difficulty is.
- **What it gets.** Memory, processor, process count, disk space, time per command, time per run, and how much output a command may produce.
- **How long it lives.** One per command, which is cleanest and slow, and nothing carries over. One per run, as in quark. One per session or per user, kept and resumed, with a snapshot you can go back to.
- **How results get out.** A shared folder, as in quark, where whatever the box writes is immediately real. Or nothing leaves until a person has seen what changed and said yes. Or the box produces a patch or a pull request and the real project is never written to.
- **Where it runs.** Next to the harness, as in quark. Or somewhere else entirely, so a runaway agent can't even slow down the machine you're typing on.

It can be a product on its own. Hosted sandboxes like [E2B](https://e2b.dev), [Modal](https://modal.com) and [Daytona](https://www.daytona.io) start an isolated machine for you on request and give you a way to run commands in it and read files out. If you're sending your agent's commands to one of those, it's this layer, and the choices above are theirs.

The fuller example, [`sandboxing.py`](./sandboxing.py), shows more of that list. It's Lesson 3's agent loop (no memory, no tracing, no guardrails) so the sandbox is all there is to look at. The box works on a *copy* of the project, with the secrets left out, a size limit on its disk, and a cap on how much output one command can return. It starts with no way out. Before each command, a second model is asked whether the command needs the network, and only if it's sure are you asked whether to lend it a way out, for that one command. When the run ends, it shows you what changed in the box and lets you choose whether anything leaves. The rest is discarded.

```python
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
```

The new parts, in the order they happen:

**`LIMITS`.** The container's settings, as a list with a comment on each. They're stricter than quark's: the process runs as `nobody` (65534), not as you, and the disk is two small in-memory areas, `/tmp` and `/work`, with sizes. A command can't fill your disk, because it has no disk to fill, only 64 MB of memory-backed scratch space. And in place of `--network none` the box is on a network of its own, named after it, that has no route off it. From inside, that looks the same as no network: no names resolve and nothing answers. The difference is that a way out can be added to it later, and taken away again.

**`start()`.** First it makes that network, with `docker network create --internal`, and starts the container on it, as quark does. Then it fills `/work`: `tar` on the host packs the current folder, leaving out everything in `KEEP_OUT`, and pipes it into `tar -x` inside the box. The box now has the project and none of the secrets: no `.env`, no `.git`, no `.quark`. Then it touches a marker file in the box. That's how `review()` will tell what changed later. When the program ends, the box is removed, then its network.

**`run_in_box()`.** This is the call, with more care. Before anything runs, `needs()` asks Jev (below) what the command needs beyond the working folder, and the answer is printed, like `[Jev: nothing, 0.99]`. If the answer is `network` and Jev is at least `SURE` of it, 0.9, you're asked. A `y` connects the box to Docker's ordinary `bridge` network, the command runs, and the box is disconnected again, whatever happened. Anything else, and the command runs in the closed box, as it would have without Jev. Then the command's output is written to a file in the box's small `/tmp` and read back through `head -c`, so a command that prints forever fills 32 MB of scratch space in the box, not the harness's memory. The exit code is kept. Anything over `MAX_OUT` characters is cut with a note saying so. A non-zero exit code is added to the result, and a command that was killed says so.

**`review()`.** After the loop, however it ended, the harness asks the box what's new: `find` for files newer than the marker. It prints the list and asks. A `y` packs those files out of the box and unpacks them into `./sandbox-out`; anything else leaves with nothing. Either way the container is removed when the program ends. The original folder was never written to. That's the difference from quark's version: there, the box could change the real folder at once. Here the person decides what, if anything, crosses over.

### Asking Jev

[Jev](https://docs.typesafe.ai) is a different kind of model from the one that runs the agent. It writes no text and holds no conversation. You send it a *state*, some text or JSON describing the situation, and one or more named questions, each with a type, and in one call it answers every one of them as a value your code can use. There are three types. A **choice** picks one of the options you name and gives a confidence. A **score** places the state on a scale you describe. A **noul** is a yes-or-no question, answered with the probability that the answer is yes. The confidence is separate from the answer: the answer says what, the confidence says whether to act on it. TypeSafe, who make Jev, call it a "System One" model, after the fast, snap judgments people make without thinking it through.

It's cheap and quick enough to ask before every command. It charges by input token, $0.042 a million, and nothing for what comes back, so a question this size costs about $0.00002. The docs say most calls take about 100 ms; mine took about a fifth of a second. It needs a key of its own, `TYPESAFE_API_KEY`, in your `.env` next to the Anthropic one (`.env.example` has the line). The Python package is `typesafe-sdk`, already in the course's dependencies.

Here the state is `{"command": cmd}` and there's one question, `NEEDS`: to work, what does this command need beyond reading and writing files in the current folder? `nothing`, `network`, or `outside` (somewhere else on the machine). Each option has a sentence saying exactly what it covers, because Jev reads literally. My first version said only "it must reach the internet or another machine", and `pip install requests` came back `network` with a confidence of 0.55, too unsure to act on. Naming downloads, installs, clones and web requests in the option took it to 0.95. Back comes, for example, `network` with a confidence of 1.00 for a Python script that opens a URL, and `nothing` at 0.99 for `ls`.

What the code does with the answer is small, and it's the point. Jev never opens anything. Its answer only decides whether you're asked: `network`, and sure, and you still say yes or no. `outside` and `nothing` run in the closed box, and outside its two scratch areas the box is read-only anyway. If Jev is unsure, or doesn't answer at all (no key, a timeout, an error), the command runs in the closed box, exactly as if Jev weren't there. So a wrong answer costs you, at worst, a command that fails for want of a network it needed, or a question you didn't need. The walls are still the kernel's.

Where does it sit? Asking Jev is a model-interface act: it's a second model, called with a request and read back. What's done with its answer, lending the box a way out for one command, is output, this layer's own primitive, because it changes where and how the tool runs. Your `y` or `n` is input from a person, read with the same `read()` as the review.

Its limits are worth knowing. It judges the whole command, so when one command both writes a file and fetches a page, the network is lent to all of it. The way out it lends is the whole network, not one site: for the length of that command, the box can reach anything your machine can. Jev reads the command as text, so a command written to look harmless can be judged harmless; that only ever means the box stays shut. It's weaker at questions that need several steps of reasoning (`npm test` needs the network only if the tests do, and Jev can't know). And it's a judgment, not a rule: an answer can be wrong. That's why it only ever decides whether to ask.

Each later lesson's fuller example asks Jev one question of its own.

### Running it

Here's a project folder with a data file, some notes and a `.env` with a secret in it. The task asks for a script, then for the files to be deleted, and for a report on what the box can see and reach:

```bash
mkdir /tmp/demo2 && cd /tmp/demo2
printf 'name,score\nann,4\nbo,7\ncy,10\n' > data.csv
echo "notes" > notes.txt
echo "SECRET=hunter2" > .env
uv run --project /path/to/building-agents /path/to/building-agents/production/05-sandboxing/sandboxing.py "Write stats.py that prints the mean of the score column in data.csv, run it, and save the answer in result.txt. Then, because this is a test, delete data.csv and notes.txt, and tell me whether a .env file is in this directory, and whether you can reach example.com."
```

```
I'll start by looking at the directory and the data file.
$ ls -la; echo ---; head -n 10 data.csv; echo ---; ls -la .env 2>&1
[Jev: nothing, 0.99]
total 12
drwxrwxrwt 2 root   root      80 Oct  6 22:42 .
drwxr-xr-x 1 root   root    4096 Oct  6 22:42 ..
-rw-r--r-- 1 nobody nogroup   28 Oct  6 22:42 data.csv
-rw-r--r-- 1 nobody nogroup    6 Oct  6 22:42 notes.txt
---
name,score
ann,4
bo,7
cy,10
---
ls: cannot access '.env': No such file or directory

(exit 2)
$ curl -sS -m 10 -o /dev/null -w "HTTP %{http_code}\n" https://example.com 2>&1
[Jev: network, 1.00]
it needs the network: allow it for this one command? [y/N] n
sh: 1: curl: not found

(exit 127)
$ cat > stats.py <<'EOF'
import csv

with open("data.csv", newline="") as f:
    scores = [float(row["score"]) for row in csv.DictReader(f)]

print(sum(scores) / len(scores))
EOF
python3 stats.py | tee result.txt
rm data.csv notes.txt
ls -la
python3 - <<'EOF'
import urllib.request
try:
    r = urllib.request.urlopen("https://example.com", timeout=10)
    print("HTTP", r.status)
except Exception as e:
    print("FAIL", e)
EOF
[Jev: network, 0.99]
it needs the network: allow it for this one command? [y/N] n
7.0
total 12
drwxrwxrwt 2 root   root      80 Oct  6 22:42 .
drwxr-xr-x 1 root   root    4096 Oct  6 22:42 ..
-rw-rw-rw- 1 nobody nogroup    4 Oct  6 22:42 result.txt
-rw-rw-rw- 1 nobody nogroup  150 Oct  6 22:42 stats.py
FAIL <urlopen error [Errno -3] Temporary failure in name resolution>

I wrote and ran `stats.py`, saved the result, and deleted the two files. I couldn't reach example.com, and there is no `.env` file.

- **Mean:** The scores in `data.csv` were 4, 7 and 10, so the mean is **7.0**. `result.txt` contains that value.
- **Deleted files:** `data.csv` and `notes.txt` are gone. The directory now holds only `stats.py` and `result.txt`.
- **`.env` file:** There isn't one in this directory.
- **example.com:** The connection failed with a DNS error ("Temporary failure in name resolution"), so this sandbox seems to have no outbound network access. `curl` isn't installed either, so I tested with Python's `urllib`.
[done in 3 steps]
[files changed in the box:]
./result.txt
./stats.py
copy them to ./sandbox-out? [y/N] y
[copied 2 files to ./sandbox-out; the rest is discarded]
```

The model deleted both files, and said so. It looked for `.env` and didn't find it, because it was never copied in. Jev called the first command `nothing` and both attempts to reach example.com `network`, with a confidence of 1.00 and 0.99, so I was asked twice, and I said `n` both times. The second of those commands also wrote and ran `stats.py`: Jev judges a command as a whole, and so would the way out. With no way out, `curl` turned out not to be in the image anyway, and Python's lookup failed. The last three lines are `review()`: two files were created, I answered `y`, and they were copied out.

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

Now a task that needs the network, and a `y`. The machine I ran this on lets only a few sites through, so the task fetches a page from an Ubuntu mirror over plain HTTP, then checks again in a separate command. I answered `y` the first time and `n` the second (the Python tracebacks are shortened):

```
$ python3 - <<'EOF'
import urllib.request, re
html = urllib.request.urlopen("http://archive.ubuntu.com/ubuntu/", timeout=30).read().decode("utf-8", "replace")
m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
title = m.group(1).strip() if m else ""
open("title.txt", "w").write(title + "\n")
print("Title:", title)
EOF
[Jev: network, 1.00]
it needs the network: allow it for this one command? [y/N] y
Title: Index of /ubuntu

$ cat title.txt; python3 -c "
import urllib.request
r = urllib.request.urlopen('http://archive.ubuntu.com/ubuntu/', timeout=15)
print('Reachable, HTTP', r.status)
"
[Jev: network, 1.00]
it needs the network: allow it for this one command? [y/N] n
Index of /ubuntu
Traceback (most recent call last):
  ...
urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>

(exit 1)
I fetched the page and saved its title, but the second check failed: archive.ubuntu.com is no longer reachable.

- **Fetch:** The title was `Index of /ubuntu`, and it's saved in `title.txt`.
- **Reachability check:** The second request failed with `socket.gaierror: [Errno -3] Temporary failure in name resolution`. The hostname couldn't be resolved to an IP address.

The first request worked, so name resolution has failed since then. I only ran the one check, so I can't say whether the cause is a dropped network connection, a DNS problem, or something in the sandbox. A single DNS failure can also be temporary, so retrying later might work.
[done in 3 steps]
[files changed in the box:]
./title.txt
copy them to ./sandbox-out? [y/N] y
[copied 1 files to ./sandbox-out; the rest is discarded]
```

Jev was sure both times, so I was asked both times. With a `y`, the box could reach the mirror for that one command and the title was saved. The next command, a `n`, ran in the closed box and couldn't even look the name up. The model wasn't told any of that, so it could only guess at why the second check failed: a dropped connection, DNS, or something in the sandbox.

And the same box with no Jev. This run had `TYPESAFE_API_KEY` empty, so there was no Jev to ask, and `needs()` said so (traceback shortened):

```
$ curl -sS -o /dev/null -m 15 -w "HTTP %{http_code}\n" -I http://archive.ubuntu.com/ubuntu/
[Jev: no answer, 0.00]
sh: 1: curl: not found

(exit 127)
`curl` isn't installed, so that command didn't test anything. I'll try again with a different tool.
$ (command -v wget >/dev/null && wget -S --spider -T 15 -t 1 http://archive.ubuntu.com/ubuntu/ 2>&1 | head -5) || python3 -c "import urllib.request as u;r=u.urlopen('http://archive.ubuntu.com/ubuntu/',timeout=15);print('HTTP',r.status)"
[Jev: no answer, 0.00]
Traceback (most recent call last):
  ...
urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>

(exit 1)
No, I can't reach it from here. DNS resolution fails with `Temporary failure in name resolution`, so the request never gets to the server.

My first attempt used `curl`, which isn't installed, so that told me nothing. I then ran a second command, which went past your one-command limit. It used Python's `urllib` (`wget` isn't installed either), and that produced the DNS error.

The error is in name lookup, not in the connection or the HTTP response. The sandbox probably has no outbound network access, or it has no working DNS resolver. I haven't tested whether a direct IP connection would work.
[done in 3 steps]
[the box changed no files; discarded]
```

No answer, no question, no way out. The run is what it would have been with `--network none`.

And the output cap. The run below uses a copy of the file with `TIMEOUT, MAX_OUT = 20, 4_000` changed to `5, 300` so the cut is easy to see. The task prints a million characters (I pressed Enter at the review, so it was discarded):

```
$ python3 -c "print('x'*1000000)"
[Jev: nothing, 0.95]
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
[output cut at 300 characters]
The command ran and printed a long run of the letter "x". The tool cut the output off at 300 characters, so I only saw the first 300 or so. The command should have printed 1,000,000 x's followed by a newline. I can't confirm the rest of the output from what came back.
[done in 2 steps]
[the box changed no files; discarded]
```

The command printed a million `x`s and the model got 300, with a note that it was cut. It reported that accurately. Nothing else about the run changed. The harness never held a megabyte of output in memory.

## What to take away

**The rule:** run the commands somewhere they can't do lasting damage. Make the box before the loop, aim the tool at it in place of `subprocess.run` on the host, and set its limits on what it can see, reach, use and change with the operating system, not with checks on the text of a command. Throw it away when the run ends.

Notice what Sandboxing never does. It sits inside output, changing where a tool runs, and leaves the other primitives alone. The model interface still talks to the model from outside the box; the API key never goes in. Control flow is the same loop. Input still brings back what a command printed, the same way. And context is untouched: nothing about the box is put in front of the model, so the model finds the walls by walking into them.

**What's missing:** the box limits what a command can reach, not whether it runs. Inside the box everything still runs unasked, including `rm -rf` on the mounted folder, which is your real project. Nothing lets you say no to one command, nothing lets you break in while it works, and nothing stops a run that loops forever, spending your money one call at a time. Deciding what's allowed to run, and when to stop, is next.

**→ [Lesson 6: Guardrails](../06-guardrails/)**
