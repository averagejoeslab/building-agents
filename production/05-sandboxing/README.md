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
            done = subprocess.run(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", block.input["cmd"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)   # sandboxing: in the box, with a time limit
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
$ cd /tmp/demo 2>/dev/null; pwd; echo hi > hello.txt && echo "hello ok: $(cat hello.txt)"; (echo x > /etc/testfile) 2>&1 && echo ETC_OK || echo ETC_FAIL; python -c "import urllib.request;print(urllib.request.urlopen('http://example.com',timeout=8).status)" 2>&1 | tail -1; env | grep -iqE 'api[_-]?key|secret|token|anthropic|openai' && echo KEYS_YES || echo KEYS_NO; id; hostname; whoami
/tmp/demo
hello ok: hi
sh: 1: cannot create /etc/testfile: Read-only file system
ETC_FAIL
urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>
KEYS_NO
uid=0(root) gid=0(root) groups=0(root)
d8df059026c0
root

I wrote `hello.txt` in `/tmp/demo`, and it contains `hi`. Of your three checks, only the API key one came out clean.

| Check | Result |
|---|---|
| Write a file to `/etc` | **Failed.** The filesystem is read-only. |
| Reach example.com with python | **Failed.** Name resolution failed because the sandbox has no network. |
| See API keys in the environment | **No.** I searched variable names for key, secret, token, anthropic and openai, and found none. |

I'm running as `root` (uid 0, gid 0). That is root inside a Docker container with hostname `d8df059026c0`, and my working directory is `/tmp/demo`. The container is locked down:
- It has no network.
- Its root filesystem is read-only.
- All capabilities are dropped.
- It has memory, CPU and process limits.

So root here has very little power outside the mounted directory. The mounted directory is the one place I can write.
```

The model wrote `hello.txt` in the mounted folder, and the other three hit the walls. `/etc` is read-only. There's no network, so the name didn't even resolve. And there are no keys, because the harness's environment stays with the harness. It says it's root because I was root when I ran it: `--user` passes on whoever you are.

Afterwards, `docker ps -a` lists no containers, and the folder holds what the box was allowed to leave:

```
hello.txt
notes.txt
```

Now the limits. `TIMEOUT` is 30 seconds, so this run uses a copy with it set to 5 (`sed 's/"python:3.13-slim", 30/"python:3.13-slim", 5/' quark.py`):

```
I'll start with the first command.
$ sleep 60

(killed: ran over 5 seconds or out of memory)
$ python3 -c 'x = bytearray(2*1024**3); x[:] = b"a"*len(x)'
Killed

(killed: ran over 5 seconds or out of memory)
$ ls
hello.txt
notes.txt

I ran the three commands one at a time. The sandbox limits each command to 5 seconds and the container to 512 MB of memory.

1. **`sleep 60`**: The sandbox killed it after 5 seconds, well before the 60 seconds were up. The harness reported "killed: ran over 5 seconds or out of memory".
2. **`python3 -c 'x = bytearray(2*1024**3); ...'`**: It was killed and printed `Killed`. The script tries to allocate 2 GB and then write 2 GB more (`b"a"*len(x)`), so it needs about 4 GB. That is far above the 512 MB limit. The harness's note doesn't say whether the time limit or the memory limit stopped it, but memory is the likely cause.
3. **`ls`**: It ran normally and listed two files in `/tmp/demo`: `hello.txt` and `notes.txt`.
```

Both were killed, and the third command still worked: a killed command doesn't take the box or the run with it. The second kill is the case the message is vague about, and the model said so.

Lesson 4's memories still work, because they live in the mounted folder:

```
$ mkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo "# Quark Memory" > .quark/memory/memory.md; grep -i "short" .quark/memory/memory.md; cat >> .quark/memory/memory.md << 'EOF'
- user: prefers short answers
EOF

Noted: you prefer short answers.
```

The fact is in `.quark/memory/memory.md` on the host, where the next session will find it.

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
read = input                                             # a person's input; the name input is for whatever comes in

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
    try: answer = read("copy them to ./sandbox-out? [y/N] ").strip().lower()
    except EOFError: answer = ""
    if answer == "y":
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
printf 'y\n' | uv run --project /path/to/building-agents /path/to/building-agents/production/05-sandboxing/sandboxing.py "Write stats.py that prints the mean of the score column in data.csv, run it, and save the answer in result.txt. Then, because this is a test, delete data.csv and notes.txt, and tell me whether a .env file is in this directory, and whether you can reach example.com."
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

**The rule:** run the commands somewhere they can't do lasting damage. Make the box before the loop, aim the tool at it in place of `subprocess.run` on the host, and set its limits on what it can see, reach, use and change with the operating system, not with checks on the text of a command. Throw it away when the run ends.

Notice what Sandboxing never does. It sits inside output, changing where a tool runs, and leaves the other primitives alone. The model interface still talks to the model from outside the box; the API key never goes in. Control flow is the same loop. Input still brings back what a command printed, the same way. And context is untouched: nothing about the box is put in front of the model, so the model finds the walls by walking into them.

**What's missing:** the box limits what a command can reach, not whether it runs. Inside the box everything still runs unasked, including `rm -rf` on the mounted folder, which is your real project. Nothing lets you say no to one command, and nothing stops a run that loops forever, spending your money one call at a time. Deciding what's allowed to run, and when to stop, is next.

**→ [Lesson 6: Guardrails](../06-guardrails/)**
