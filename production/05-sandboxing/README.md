# Lesson 5: Sandboxing

> 🎥 **Video:** coming soon

You've built a harness that works. Since Lesson 2 it has run every command the model asks for, on your machine, as you, with your files, your network and your credentials, and nothing asks first. The setup warned you to run it somewhere you can afford to lose. The production layers start by making that true wherever it runs.

Sandboxing is about where the commands run. Instead of running them on your machine, the harness runs them in a box: a place with its own filesystem, a limited view of yours, no way out to the network, a fixed share of memory and processor, and a time limit. Whatever a command does, it does inside the box, and when the run is over the box is thrown away. It doesn't decide whether a command *should* run; it decides what a command can reach *when* it runs.

This is a production layer, so it adds hardening, not a new primitive. It's **built on output**, and everything it does stays inside it. Output is the primitive that acts on what the model said: the model asks for a command, and output runs it (Lesson 2). Where that command runs is a choice output already makes, even if the earlier lessons made it with one line, `subprocess.run`, which means "right here." Sandboxing makes a different choice in the same place.

The mechanism is a container, and the important thing about it is who enforces the limits. A guardrail is code reading a command and deciding. A container's limits are enforced by the operating system's kernel, on whatever runs inside it, however the command is spelled. `rm -rf /` written a hundred different ways is still a command that can only see the box's filesystem. Docker is the tool this lesson uses to make the box. It's one of several; the idea is the same in all of them. Each piece is a setting on the container:

- **A box that lives for the run.** The harness starts one container before the first command and leaves it running, doing nothing (`sleep infinity`). Each command is then `docker exec` into that same container, so a file written by one command is there for the next. When the harness exits, the container is removed, and so is everything in it that wasn't somewhere shared.
- **What it can see.** A container starts with the image's own filesystem, not yours, and sees only what you mount into it. Environment variables don't come along either: your API key lives in the harness, which stays outside the box, and a command inside can't read it.
- **What it can reach.** The box sits on a network of its own that has no route off it. Nothing resolves, nothing connects. Unlike no network at all, a way out can be added to it for one command and taken away again.
- **How much it gets.** A memory limit, a share of processor, a cap on the number of processes (so a fork loop stops at a number), and a time limit on each command. The time limit is enforced inside the box with `timeout -s KILL`, because killing the `docker exec` on your side wouldn't stop the process in the container.
- **What it can change.** The container's root filesystem is read-only, with a small scratch `/tmp`. All Linux capabilities are dropped, and the process runs as a user you choose, not whoever the image defaults to. Whatever you mount is the only other place a command can leave something behind.

None of that makes the model behave, and it doesn't stop a command from doing what it was allowed to do inside the box, including deleting a folder you mounted. It makes that the whole of the damage: the machine around the box, your other files and your credentials are out of reach. And if the box can't be started, nothing runs. There's no fallback to running on the host, because a sandbox that silently turns itself off is worse than none.

## The concept

Here's the idea with nothing around it: a locked box, a few fixed commands that walk into its walls, and one decision about lending it a way out. There's no agent and no main model in it at all, in [`sandboxing.py`](./sandboxing.py):

```python
import subprocess, sys, os, atexit
from typesafe_sdk import TypeSafeClient, TypeSafeError, Choice
read = input                                             # a person's input; the name input is for whatever comes in

box = f"box-{os.getpid()}"
net = f"{box}-net"
try: jev = TypeSafeClient(timeout=5)                     # Jev, a second model that answers typed questions (reads TYPESAFE_API_KEY)
except TypeSafeError: jev = None                         # no key, no Jev: the box just stays shut
NEEDS = Choice(instructions="To work, what does the shell command in `command` need beyond reading and writing files in the current folder?", criteria={"nothing": "it works inside the current folder with no network", "network": "it must reach the internet or another machine: downloads, installs from a registry, clones, web requests", "outside": "it must write outside the current folder: the home directory, system paths"})
SURE = 0.9                                               # how sure Jev must be before its answer counts

def docker(*args):
    return subprocess.run(["docker", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")

docker("network", "create", "--internal", net)           # a network with no way out
up = docker("run", "-d", "--rm", "--name", box, "--network", net, "--memory", "256m", "--pids-limit", "64", "--cap-drop", "ALL", "--read-only", "--tmpfs", "/tmp", "--user", "65534:65534", "python:3.13-slim", "sleep", "infinity")
if up.returncode: sys.exit(f"[no box, so nothing runs: {up.stdout.strip()}]")
atexit.register(lambda: docker("network", "rm", net))
atexit.register(lambda: docker("rm", "-f", box))         # thrown away when the program ends: the box, then its network

def run(cmd):
    print(f"$ {cmd}")
    try: need = jev.system_one({"command": cmd}, {"q": NEEDS}).choices["q"]
    except Exception: need = None                        # no answer: the box stays shut
    if need: print(f"[Jev: {need.choice}, {need.confidence:.2f}]")
    lend = bool(need and need.choice == "network" and need.confidence >= SURE and read("lend it the network for this one command? [y/N] ").lower() == "y")
    if lend: docker("network", "connect", "bridge", box)  # a way out, for this command only
    done = docker("exec", box, "timeout", "-s", "KILL", "5", "sh", "-c", cmd)
    if lend: docker("network", "disconnect", "bridge", box)
    print(f"{done.stdout}(exit {done.returncode})\n")

FETCH = "python3 -c \"import urllib.request as u; print(u.urlopen('http://archive.ubuntu.com/ubuntu/', timeout=10).status)\""
for cmd in sys.argv[1:] or ["id; echo hi > /etc/hello", "sleep 60", "python3 -c 'bytearray(1024**3)'", FETCH, FETCH]:
    run(cmd)
```

Read it from the middle.

**The box.** `docker network create --internal` makes a network with no route off it, and `docker run` starts a container on it that does nothing but wait. Every flag is a wall: 256 MB of memory, at most 64 processes, no Linux capabilities, a read-only root with a scratch `/tmp`, and user 65534, `nobody`. Nothing of yours is mounted, so the box sees none of your files. If the box can't be started, the program exits before anything runs. When the program ends, `atexit` removes the box, then its network.

**`run()`.** Each command goes into the box with `docker exec`, under `timeout -s KILL 5`: five seconds, then it's killed, whether it's polite about it or not. Its output and exit code come back.

**The way out.** Before a command runs, Jev is asked what it needs: `nothing`, `network`, or `outside` (somewhere else on the machine). Only if the answer is `network`, and Jev is at least `SURE` of it, is a person asked. A `y` connects the box to Docker's ordinary `bridge` network for that one command, and the next line disconnects it. Anything else and the command runs in the closed box.

**The commands.** Five fixed ones, each aimed at a wall: write to `/etc`, sleep for a minute, grab a gigabyte of memory, and fetch a page twice. You can pass your own on the command line instead.

Run it from the root of the repo. It needs Docker running; the first run pulls the `python:3.13-slim` image:

```bash
uv run production/05-sandboxing/sandboxing.py
```

Here's a run, where I answered `y` to the first fetch and `n` to the second (the traceback is shortened):

```
$ id; echo hi > /etc/hello
[Jev: outside, 1.00]
uid=65534(nobody) gid=65534(nogroup) groups=65534(nogroup)
sh: 1: cannot create /etc/hello: Read-only file system
(exit 2)

$ sleep 60
[Jev: nothing, 0.94]
(exit 137)

$ python3 -c 'bytearray(1024**3)'
[Jev: nothing, 0.96]
Killed
(exit 137)

$ python3 -c "import urllib.request as u; print(u.urlopen('http://archive.ubuntu.com/ubuntu/', timeout=10).status)"
[Jev: network, 1.00]
lend it the network for this one command? [y/N] y
200
(exit 0)

$ python3 -c "import urllib.request as u; print(u.urlopen('http://archive.ubuntu.com/ubuntu/', timeout=10).status)"
[Jev: network, 1.00]
lend it the network for this one command? [y/N] n
Traceback (most recent call last):
  ...
urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>
(exit 1)
```

Every command hit a wall. It runs as `nobody`, and `/etc` is read-only. The `sleep` was killed at five seconds, and the gigabyte was killed too, most likely by the 256 MB memory limit, though exit 137 looks the same either way. The same fetch worked once and failed once. With a `y`, the box could reach the mirror for that one command. With an `n`, it couldn't even look the name up.

Jev got all five right. It called the write to `/etc` `outside`, and was sure. That changes nothing here: only `network` ever leads to a question, and the read-only root stopped the write anyway.

### Asking Jev

[Jev](https://docs.typesafe.ai) is a different kind of model from the one that runs an agent. It writes no text and holds no conversation. You send it a *state*, some text or JSON describing the situation, and one or more named questions, each with a type, and in one call it answers every one of them as a value your code can use. There are three types. A **choice** (`Choice`) picks one of the options you name. A **noul** (`Noul`) is a yes-or-no question, answered with the probability that the answer is yes. A **score** (`Score`) places the state on a scale you describe. TypeSafe, who make Jev, call it a "System One" model, after the fast, snap judgments people make without thinking it through.

A choice comes back with the option it picked, the probability of each option, and a **confidence**. The confidence is separate from the answer: the answer says what, the confidence says whether to act on it. Every lesson from here on acts only when Jev is sure, and does the safe old thing when it isn't.

It's cheap and quick enough to ask before every command. It charges by input token, $0.042 a million, and nothing for what comes back, so a question this size costs about $0.00002. Mine took about a fifth of a second. It needs a key of its own, `TYPESAFE_API_KEY`, in your `.env` next to the Anthropic one (`.env.example` has the line). The Python package is `typesafe-sdk`, already in the course's dependencies. Without the key there's no Jev, and every lesson carries on as if it had never asked.

Each option in a question has a sentence saying exactly what it covers, because Jev reads literally. An early `NEEDS` said only "it must reach the internet or another machine", and `pip install requests` came back `network` with a confidence of 0.55, too unsure to act on. Naming downloads, installs, clones and web requests in the option took it to 0.92.

Its weak spots are worth knowing before you trust it with anything. TypeSafe's own docs list them:

- **It reads literally.** It answers the question you wrote, not the one you meant. Put the boundary cases in the options.
- **It doesn't count.** How many lines, how many files, how many times: keep the arithmetic in your code.
- **Indirection costs it.** A question that takes several steps of reasoning is answered less reliably. `npm test` needs the network only if the tests do, and Jev can't know.
- **Text can steer it.** The state is data, and a command written to look harmless can be judged harmless.

That's why, in every lesson, Jev's answer only ever moves the harness toward something a person or a hard limit still controls. Here it only decides whether you're asked. A wrong `network` costs you a question you didn't need; a wrong anything-else costs a command that fails for want of a network. The walls are still the kernel's.

Where does it sit? Asking Jev is a **model-interface** act: it's a second model, called with a request and read back. What's done with its answer belongs to the layer's own primitive. Here that's **output**: lending the box a way out for one command changes where and how the tool runs. Your `y` or `n` is input from a person.

Without the key, the same fetch runs with no Jev line and no question, in the closed box (traceback shortened):

```
$ python3 -c "import urllib.request as u; print(u.urlopen('http://archive.ubuntu.com/ubuntu/', timeout=10).status)"
Traceback (most recent call last):
  ...
urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>
(exit 1)
```

## quark's implementation

[`quark.py`](./quark.py) is Lesson 4's `quark.py` plus the sandbox and its Jev question, and nothing else: 29 lines, 268 in all. Here they are, in the sections they belong to.

In the imports, `atexit`, to remove the box however the program ends, and the Jev client:

```python
import subprocess, sys, os, re, glob, json, datetime, atexit
from typesafe_sdk import TypeSafeClient, Choice
```

In `# ── model interface ──`, after `call()`, Jev:

```python
jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # sandboxing: Jev, a second model that answers typed questions
SURE = 0.9                                               # sandboxing: how sure Jev must be before quark acts on its answer
def ask(state, question):                                # sandboxing: one typed question to Jev; no key, no answer or a timeout is None
    try: return jev.system_one(state, {"q": question}).model_dump()["answers"]["q"]
    except Exception: return None
```

In `# ── output: the one tool ──`, after the tool, the box and the way out:

```python
IMAGE, TIMEOUT = "python:3.13-slim", 30
box = f"quark-{os.getpid()}"
net = f"{box}-net"
def sandbox():                                           # sandboxing: one locked-down container for the whole run
    where = os.getcwd()
    subprocess.run(["docker", "network", "create", "--internal", net], capture_output=True)   # sandboxing: a network with no way out
    up = subprocess.run(["docker", "run", "-d", "--rm", "--name", box, "--network", net, "--memory", "512m", "--cpus", "1", "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp", "-e", "HOME=/tmp", "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{where}:{where}", "-w", where, IMAGE, "sleep", "infinity"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if up.returncode: sys.exit(f"[no sandbox, so nothing runs: {up.stdout.strip()}]")
    atexit.register(lambda: subprocess.run(["docker", "network", "rm", net], capture_output=True))
    atexit.register(lambda: subprocess.run(["docker", "rm", "-f", box], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
NEEDS = Choice(instructions="To work, what does the shell command in `command` need beyond reading and writing files in the current folder?", criteria={"nothing": "it works inside the current folder with no network", "network": "it must reach the internet or another machine: downloads, installs from a registry, clones, web requests", "outside": "it must write outside the current folder: the home directory, system paths"})
def lend(cmd):                                           # sandboxing: Jev is sure it needs the network, and the person agrees
    need = ask({"command": cmd}, NEEDS)
    return bool(need and need["choice"] == "network" and need["confidence"] >= SURE and read(f"`{cmd}` needs the network: allow it for this one command? [y/N] ").lower() == "y")
def bridge(on):                                          # sandboxing: open the box's way out, or close it again
    subprocess.run(["docker", "network", "connect" if on else "disconnect", "bridge", box], capture_output=True)
```

At the top of `# ── control flow ──`, one call to start the box before the loop:

```python
sandbox()
```

And in the loop, the one line that ran a command on your machine now runs it in the box, with the way out around it:

```python
            lent = lend(block.input["cmd"])
            if lent: bridge(True)
            done = subprocess.run(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", block.input["cmd"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")   # sandboxing: in the box, with a time limit
            if done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or out of memory)"
            if lent: bridge(False)
```

**`sandbox()`** is the concept's box, made for an agent. It makes the network with no way out, then starts the container on it, once. `-d` runs it in the background, `--rm` deletes it when it stops, and `--name` gives it a name from the process ID so `docker exec` can find it. Two things differ from the concept. The container runs as *you* (`--user` with your IDs), and `-v folder:folder -w folder` mounts the folder quark was started in, at the same path, so the model's relative paths, and Lesson 4's `.quark/` memories, work as before. The box has to be able to do the work, and the work is in that folder. If `docker run` fails, quark exits with the reason and nothing runs.

**The discard.** The two `atexit.register(...)` lines remove the container, then its network, when the program ends, however it ends short of a `kill -9`, which nothing can catch: the model finishes, you type `/q`, or Ctrl-C. After that the box is gone, with anything written outside the mounted folder.

**The call.** `subprocess.run(cmd, shell=True)` became `docker exec box timeout -s KILL 30 sh -c cmd`: the same shell, the same merged output and exit code, but inside the container and under a 30-second limit. A command killed this way exits with 137 (128 plus signal 9), and so does one the kernel killed for using too much memory. quark can't tell them apart, so it adds a line saying it was one or the other. That line goes back to the model with the result, so the model finds out why its command died.

**`jev`, `SURE` and `ask()`** are how quark asks Jev anything, and every later lesson uses them for its own question. `jev` exists only when there's a key. `ask(state, question)` sends one question and returns Jev's answer as a dictionary, or `None` if there's no key, no answer, an error or a timeout (five seconds). They live in `# ── model interface ──`, because asking a model is a model-interface act, even a model that only decides.

**`lend()` and `bridge()`** are this lesson's Jev question and what's done with the answer. Before each command runs, `lend()` asks `NEEDS` about it, the same question as the concept's. If Jev answers `network` with a confidence of at least 0.9, you're asked, with the command in the question, through Lesson 2's `read()`. Only a `y` lends the box a way out: `bridge(True)` connects it to the `bridge` network, the command runs, and `bridge(False)` disconnects it. `None`, an unsure answer, `nothing`, `outside`, or anything but `y` from you, and the command runs in the closed box. Acting on the answer is output: it changes where the command runs. Your answer is input from a person.

Everything else is Lesson 4's, on purpose. The system prompt still tells the model that bash reaches "the whole system." Inside the box that's true. This layer adds no word about the box to the prompt: that would be a decision about context, and this layer doesn't make it. Nor is the model told when it was lent the network, or refused it. But Lesson 4's `mechanics()` puts quark's own file in the prompt, and `sandbox()` is in that file now, so a model that reads its own code can see the walls before it walks into them. That's Lesson 4's self-knowledge at work, not this layer. The episode is still written by the harness, outside the box.

### Run it

You need Docker installed and its daemon running. The first run pulls the `python:3.13-slim` image. The box mounts the folder you start in, so start in a scratch folder, not in this repo:

```bash
mkdir -p /tmp/d05/demo && cd /tmp/d05/demo && echo "notes" > notes.txt
uv run --project /path/to/building-agents /path/to/building-agents/production/05-sandboxing/quark.py "In this directory, write hello.txt containing the word hi. Then check three things and tell me which worked: write a file to /etc, reach example.com with python, and whether you can see any API keys in your environment (just say yes or no, don't print them). Then say who you are running as and where."
```

```
$ echo hi > hello.txt; cat hello.txt; echo ---; (echo x > /etc/testfile) 2>&1; echo "etc exit: $?"; echo ---; python3 -c "import urllib.request;print(urllib.request.urlopen('http://example.com',timeout=5).status)" 2>&1 | tail -1; echo ---; env | grep -iqE 'api[_-]?key|secret|token' && echo keys-yes || echo keys-no; echo ---; id; hostname; pwd
hi
---
sh: 1: cannot create /etc/testfile: Read-only file system
etc exit: 2
---
urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>
---
keys-no
---
uid=0(root) gid=0(root) groups=0(root)
31dbb284c3b0
/tmp/d05/demo

I wrote `hello.txt` in `/tmp/d05/demo`, and it contains `hi`.

| Check | Result |
|---|---|
| Write a file to `/etc` | **Failed.** The error was "Read-only file system". |
| Reach example.com with Python | **Failed.** The name lookup did not resolve ("Temporary failure in name resolution"), so there is no network access. |
| See API keys in the environment | **No.** I searched for variable names containing api key, secret or token and found none. I printed nothing. |

Only the file write in the current directory worked.

I'm running as `uid=0(root) gid=0(root)` inside a Docker container with hostname `31dbb284c3b0`, and my working directory is `/tmp/d05/demo`. The container is locked down: its root filesystem is read-only, it has no network, and its capabilities are dropped. So "root" here has very little power. The only writable places are the mounted working directory and `/tmp`.
```

The model wrote `hello.txt` in the mounted folder, and the other three hit the walls. `/etc` is read-only. There's no way out, so the name didn't even resolve. And there are no keys, because the harness's environment stays with the harness. It says it's root because I was root when I ran it: `--user` passes on whoever you are. It knew the box was locked down before I said a word, because it had read `sandbox()` in its own file.

Notice what didn't happen: nobody asked me about the network, though one part of that command tries to reach example.com. Jev judges the command as a whole, and this one mostly writes and reads files. Asked about it again separately, Jev said `network` with a confidence of 0.44, giving `network` 0.63 and `outside` 0.37. That's under 0.9, so quark didn't ask, and the command ran in the closed box. That's the direction it's meant to fail in.

Afterwards the box and its network are gone, and the folder holds what the box was allowed to leave:

```
hello.txt
notes.txt
```

Now a task that needs the network. The machine I ran this on lets only a few sites through, so the task fetches a page from an Ubuntu mirror over plain HTTP, then checks again in a separate command. I answered `y` the first time and `n` the second (the traceback is shortened):

```
$ python3 -c "
import urllib.request,re
h=urllib.request.urlopen('http://archive.ubuntu.com/ubuntu/',timeout=10).read().decode()
t=re.search(r'<title>(.*?)</title>',h,re.S|re.I).group(1).strip()
open('title.txt','w').write(t+'\n')
print(t)
"
`python3 -c "
import urllib.request,re
h=urllib.request.urlopen('http://archive.ubuntu.com/ubuntu/',timeout=10).read().decode()
t=re.search(r'<title>(.*?)</title>',h,re.S|re.I).group(1).strip()
open('title.txt','w').write(t+'\n')
print(t)
"` needs the network: allow it for this one command? [y/N] y
Index of /ubuntu

$ cat title.txt; python3 -c "
import urllib.request
r=urllib.request.urlopen('http://archive.ubuntu.com/ubuntu/',timeout=10)
print('reachable, HTTP',r.status)
"
`cat title.txt; python3 -c "
import urllib.request
r=urllib.request.urlopen('http://archive.ubuntu.com/ubuntu/',timeout=10)
print('reachable, HTTP',r.status)
"` needs the network: allow it for this one command? [y/N] n
Index of /ubuntu
Traceback (most recent call last):
  ...
urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>

The fetch worked, but the follow-up reachability check failed.

- **Fetch:** The page title is `Index of /ubuntu`, and it's saved in `title.txt`.
- **Reachability check:** The second command failed with `Temporary failure in name resolution`. DNS lookup failed, so the check never reached the site.

The sandbox has no network by default. The first command must have been given temporary network access, and the second wasn't. So the failure says nothing about whether archive.ubuntu.com is up. It only means this command had no network access.

I can re-run the check if you allow network access for that command.
```

Jev was sure both times, so I was asked both times, and the question shows the whole command, so I know what I'm lending the network to. With the `y`, the box reached the mirror for that one command, and `title.txt` landed in the folder. The `n` ran in the closed box, and the name didn't resolve. Nobody told the model which command got the network. It worked it out from its own code and the results, and said so.

Now the limits. `TIMEOUT` is 30 seconds, so this run uses a copy with it set to 5 (`sed 's/"python:3.13-slim", 30/"python:3.13-slim", 5/' quark.py`):

```
I'll run them one at a time, starting with `sleep 60`.
$ sleep 60

(killed: ran over 5 seconds or out of memory)
$ python3 -c 'x = bytearray(2*1024**3); x[:] = b"a"*len(x)'
Killed

(killed: ran over 5 seconds or out of memory)
$ ls
hello.txt
notes.txt
title.txt

All three commands ran, but the first two were killed.

1. **`sleep 60`**: Killed. The sandbox stops any command that runs longer than 5 seconds, and this one would have run for 60.
2. **`python3 -c 'x = bytearray(2*1024**3); ...'`**: Killed. It tried to allocate and fill 2 GB, and the container's memory limit is 512 MB. The output was just `Killed`. I can't tell whether the memory limit or the 5-second limit stopped it first, because the harness reports both the same way.
3. **`ls`**: Ran normally and listed three files: `hello.txt`, `notes.txt` and `title.txt`.

The first two kills came from the sandbox's limits, not from errors in the commands. The earlier kills didn't affect `ls`.
```

Both were killed, and the third command still worked: a killed command doesn't take the box or the run with it. The second kill is the case the message is vague about, and the model said so.

Lesson 4's memories still work, because they live in the mounted folder. From an empty folder, with "remember that I prefer short answers":

```
$ mkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo "# Quark Memory" > .quark/memory/memory.md; grep -i "short" .quark/memory/memory.md; cat >> .quark/memory/memory.md << 'EOF'
- user: prefers short answers
EOF

Noted. I'll keep answers short.
```

The fact is in `.quark/memory/memory.md` on the host, where the next session will find it.

## Other things we could do

quark puts one container around every command, with a fixed set of limits and one way out it can lend. These are the choices you make when you build it.
- **What the box is.** A container, which shares your machine's kernel and is walled off by it. Or a user-space kernel like [gVisor](https://gvisor.dev) that stands between the container and the host, or a micro-VM like [Firecracker](https://firecracker-microvm.github.io), which has its own kernel and costs a little more to start. Or a plain virtual machine. Or the operating system's own sandboxing of a single process, with nothing to install. The stronger the wall, the more it costs in startup and in setup.
- **What's in it.** Any image: the tools and languages the task needs, already installed, so nothing needs the network. A different image per kind of task.
- **What it can see.** The folder mounted read-write, as quark does. Or mounted read-only. Or a *copy* of the project, so the box can't touch the original at all. And what's left out of it: secrets, `.git`, anything the task doesn't need.
- **What it can reach.** No way out, as in quark, until someone lends one for a command. Or an allow list: only your package registry, only the one API the task is about. Or a proxy that adds credentials to requests on the way out, so the model can call a service without ever holding the key. The network is where most of the risk is, and where most of the difficulty is.
- **What it gets.** Memory, processor, process count, disk space, time per command, time per run, and how much output a command may produce.
- **How long it lives.** One per command, which is cleanest and slow, and nothing carries over. One per run, as in quark. One per session or per user, kept and resumed, with a snapshot you can go back to.
- **How results get out.** A shared folder, as in quark, where whatever the box writes is immediately real. Or nothing leaves until a person has seen what changed and said yes. Or the box produces a patch or a pull request and the real project is never written to.
- **Where it runs.** Next to the harness, as in quark. Or somewhere else entirely, so a runaway agent can't even slow down the machine you're typing on.

It can be a product on its own. Hosted sandboxes like [E2B](https://e2b.dev), [Modal](https://modal.com) and [Daytona](https://www.daytona.io) start an isolated machine for you on request and give you a way to run commands in it and read files out. If you're sending your agent's commands to one of those, it's this layer, and the choices above are theirs.

A few ideas from that list are worth knowing in more detail, because they close gaps quark leaves open.

- **Work on a copy, and let a person decide what leaves.** Instead of mounting the folder, pack it up with `tar`, leave out everything that shouldn't go in (`.env`, `.git`, `.venv`, `.quark`), and unpack it inside the box. Touch a marker file when you start. When the run ends, list the files newer than the marker, show them to the person, and copy out only what they say yes to. The model can `rm` the whole project and the original is untouched. One catch: a file the model *deleted* isn't newer than anything, so a version that copies changes back has to track deletions separately.
- **Give it no disk to fill.** Make the only writable places small in-memory areas with sizes, like `--tmpfs /work:size=64m`. A command can't fill your disk, because it has none.
- **Run as `nobody`.** User 65534 owns nothing, even inside the box, which is what the concept does. quark runs as you because it shares your folder.
- **Cap the output inside the box.** Write a command's output to a file in the box's small `/tmp` and read back only the first few thousand characters with `head -c`, with a note when it was cut. A command that prints forever fills the box's scratch space, not the harness's memory, and the model gets a short result that says it's short.
- **Lend less than everything.** The way out quark lends is the whole network: for that one command, the box can reach anything your machine can. An allow list or a proxy narrows it to the one place the command was going.

## What to take away

**The rule:** run the commands somewhere they can't do lasting damage. Make the box before the loop, aim the tool at it in place of `subprocess.run` on the host, and set its limits on what it can see, reach, use and change with the operating system, not with checks on the text of a command. Throw it away when the run ends.

Notice what sandboxing never does. It sits inside output, changing where a tool runs, and leaves the other primitives alone. The model interface still talks to the model from outside the box; the API key never goes in. Asking Jev is a model-interface act, but it only decides whether you're asked, and the way out it leads to is output's. Control flow is the same loop. Input still brings back what a command printed, the same way, and your `y` or `n` comes through Lesson 2's `read()`. And context is untouched: this layer writes nothing about the box into the request. The model can still read `sandbox()` in its own file, through Lesson 4's `mechanics()`, but that's Lesson 4's doing.

**What's missing:** the box limits what a command can reach, not whether it runs. Inside the box everything still runs unasked, including `rm -rf` on the mounted folder, which is your real project. The only question quark asks is about the network. Nothing lets you say no to any other command, nothing lets you break in while it works, and nothing stops a run that loops forever, spending your money one call at a time. Deciding what's allowed to run, and when to stop, is next.

**→ [Lesson 6: Guardrails](../06-guardrails/)**
