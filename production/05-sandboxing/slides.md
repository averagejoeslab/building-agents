---
marp: true
theme: default
paginate: true
header: "Lesson 5 · Sandboxing"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Sandboxing

### A hands-on course in building agents by building their harness
Lesson 5

<!-- The first production layer. We have a harness that works; now we start making it safe to run anywhere. -->

---

# It runs every command, as you

Since Lesson 2, every command the model asks for runs:

- on your machine
- as you, with your files, your network and your credentials
- and nothing asks first

The setup warned you to run it somewhere you can afford to lose. This layer makes that true wherever it runs.

<!-- Be honest about where we are: the harness is powerful and completely unguarded. The production layers start by fixing where commands run. -->

---

# Sandboxing decides where commands run

Instead of your machine, the harness runs them in a box:

- its own filesystem, and a limited view of yours
- no way out to the network
- a fixed share of memory and processor, and a time limit
- thrown away when the run is over

It doesn't decide whether a command *should* run. It decides what a command can reach *when* it runs.

<!-- Whatever a command does, it does inside the box. Keep the "where, not whether" distinction: whether is next lesson. -->

---

# Built on output: same place, a different choice

- Output acts on what the model said: the model asks for a command, output runs it (Lesson 2)
- `subprocess.run` was already a choice of where: it means "right here"
- Sandboxing makes a different choice in the same place
- A production layer adds hardening, not a new primitive

<!-- Everything sandboxing does stays inside output. Where a command runs is a choice output always made, the earlier lessons just made it with one line. -->

---

# The kernel enforces the walls

- A guardrail is code reading a command and deciding
- A container's limits are enforced by the operating system's kernel
- They hold on whatever runs inside, however the command is spelled
- `rm -rf /` written a hundred different ways can still only see the box's filesystem

Docker is the tool quark uses to make the box. It's one of several; the idea is the same in all of them.

<!-- This is the key point about who enforces the limits. Text checks can be dodged by respelling a command; the kernel doesn't read the text at all. -->

---

# Every limit is a setting on the container

- **Lives for the run:** started before the loop, idle (`sleep infinity`); each tool call is a `docker exec`
- **Sees:** only the folder quark started in, at the same path; your environment stays out, API key included
- **Reaches:** nothing (`--network none`)
- **Gets:** 512 MB of memory, a share of processor, 128 processes, 30 seconds a command
- **Changes:** read-only root, a scratch `/tmp`, no capabilities, your user ID

<!-- Same path mount means relative paths and Lesson 4's .quark/memory work as before. A file written by one command is there for the next, because it's the same container. The time limit is enforced inside the box with timeout -s KILL, because killing docker exec on your side wouldn't stop the process in the container. -->

---

# The damage stops at the wall

- It doesn't make the model behave
- A command can still do what's allowed inside, including deleting the mounted folder
- The machine around the box, your other files and your credentials are out of reach
- If the box can't be started, quark stops: there's no fallback to the host

<!-- A sandbox that silently turns itself off is worse than none. That's why a failed docker run exits instead of running on the host. -->

---

# The box: one container for the whole run

Lesson 4's `quark.py` plus 10 lines. `atexit` joins the imports, and the box goes in the output section (abridged: `...` stands for the flags on the last slide):

```python
IMAGE, TIMEOUT = "python:3.13-slim", 30
box = f"quark-{os.getpid()}"
def sandbox():
    where = os.getcwd()
    up = subprocess.run(["docker", "run", "-d", "--rm", ..., IMAGE, "sleep", "infinity"], ...)
    if up.returncode: sys.exit(f"[no sandbox, so nothing runs: {up.stdout.strip()}]")
    atexit.register(lambda: subprocess.run(["docker", "rm", "-f", box], ...))
```

`sandbox()` is called once, at the top of `# ── control flow ──`.

<!-- -d runs it in the background, --rm deletes it when it stops, --name comes from the process ID so docker exec can find it. atexit removes it however the program ends: the model finishes, /q, or Ctrl-C. Anything written outside the mounted folder goes with it. -->

---

# One line moves the command into the box

`subprocess.run(cmd, shell=True)` became this (abridged):

```python
done = subprocess.run(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT),
                       "sh", "-c", block.input["cmd"]], ...)
if done.returncode == 137: done.stdout += f"\n(killed: ran over {TIMEOUT} seconds or ...)"
```

- Same shell, same merged output and exit code, but in the box under a 30-second limit
- `-s KILL`: a command that ignores polite requests is still stopped
- Exit 137 is a time-out *or* out of memory; quark can't tell, so it tells the model both

<!-- 137 is 128 plus signal 9. That line goes back with the result, so the model finds out why its command died. -->

---

# Everything else is Lesson 4's, on purpose

- The prompt still tells the model bash reaches "the whole system"; inside the box, that's true
- The model finds out how big the box is by running into its walls
- Telling it up front would be a decision about context, and this layer doesn't make it
- The episode is still written by the harness, outside the box

<!-- Resist the urge to explain the box to the model in the prompt. That's a context change, and each layer adds only its own thing. -->

---

# Run it: one write works, three hit walls

In a scratch folder: write `hello.txt`, then try `/etc`, example.com and the API keys. The model's one long command and its answer are cut (shortened):

```
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
/.dockerenv
```

<!-- /etc is read-only. There's no network, so the name didn't even resolve. There are no keys, because the harness's environment stays with the harness. It says it's root because I was root when I ran it: --user passes on whoever you are. -->

---

# Afterwards: no box, and only what it was allowed to leave

> Being root didn't let me write to `/etc`, because the filesystem is read-only. The network is cut off as well. The sandbox limits what I can do, not the user account.

`docker ps -a` lists no containers. The folder holds:

```
hello.txt
notes.txt
```

Lesson 4's memories still work: `.quark/` lives in the mounted folder, on the host.

<!-- The quote is the model's own summary. A fact saved during a sandboxed run lands in .quark/memory/memory.md on the host, where the next session finds it. -->

---

# A killed command doesn't take the run with it

A copy with `TIMEOUT` set to 5 (shortened):

```
$ sleep 60

(killed: ran over 5 seconds or out of memory)
$ python3 -c 'x = bytearray(2*1024**3); x[:] = b"a"*len(x)'
Killed

(killed: ran over 5 seconds or out of memory)
$ ls
hello.txt
notes.txt
```

<!-- The sleep hit the time limit. The 2 GB allocation hit the 512 MB memory limit, probably; the message can't say which, and the model said so. The third command still worked. -->

---

# Going further: what else a sandbox can be

- **The box:** a container, gVisor, a Firecracker micro-VM, a full VM, or the OS's own process sandbox
- **What it sees and reaches:** a read-only mount or a copy; an allow list, or a proxy that adds credentials
- **What it gets, and how long it lives:** disk, output, time per run; one box per command, run or session
- **How results get out:** a shared folder, a person says yes, or a patch or pull request
- **Where it runs:** next to the harness, or somewhere else entirely

<!-- The stronger the wall, the more it costs in startup and setup. The network is where most of the risk is, and most of the difficulty. -->

---

# It can be a product on its own

Hosted sandboxes like **E2B**, **Modal** and **Daytona** start an isolated machine on request, with a way to run commands in it and read files out.

If you're sending your agent's commands to one of those, it's this layer, and the choices on the last slide are theirs.

<!-- Same layer, someone else's box. -->

---

# `sandboxing.py`: the box works on a copy

Lesson 3's agent loop, so the sandbox is all there is to look at:

- `start()` copies the project in, leaving out everything in `KEEP_OUT`
- Stricter `LIMITS`: runs as `nobody`, with small sized scratch disks
- No way out: a network of its own with no route off it, until one is lent
- Each command's output is cut at `MAX_OUT` characters
- `review()` lists what changed in the box and asks; only a `y` copies it to `./sandbox-out`

```python
KEEP_OUT = [".env", ".git", ".venv", ".quark", "__pycache__"]  # never copied in
```

<!-- No memory, no tracing, no guardrails in this file. The difference from quark: there the box could change the real folder at once; here the person decides what, if anything, crosses over. -->

---

# The model deleted the files; the host still has them

The task: write `stats.py`, then delete `data.csv` and `notes.txt`, and look for `.env`. I answered `y` to `review()`. The folder afterwards, then `sandbox-out` (shortened):

```
.env
data.csv
notes.txt
sandbox-out
---
result.txt
stats.py
7.0
```

<!-- The model's rm removed the box's copy, and the box is gone. It looked for .env and didn't find it, because it was never copied in. One limit: review() lists created or changed files, not deleted ones. -->

---

# Asking Jev: does it need the network?

<style scoped>pre { font-size: 0.8em; }</style>

Jev is a second model that writes no text: send it a state and typed questions, get typed answers with a confidence.

```python
def needs(cmd):
    # Jev's answer only decides whether to ask. No answer, and the box stays shut.
    try: answer = jev.system_one({"command": cmd}, {"needs": NEEDS}).choices["needs"]
    except Exception: return "no answer", 0.0
    return answer.choice, answer.confidence
```

- `network`, and at least `SURE` (0.9): you're asked; a `y` connects the box to `bridge` for that one command
- Anything else, unsure, or no answer: the closed box, as before

<!-- Asking Jev is a model-interface act; lending the way out is output. Jev never opens anything: it only decides whether you're asked. It costs about $0.00002 a question and takes about a fifth of a second. -->

---

# A way out for one command

The task: fetch a page from an Ubuntu mirror, then check again. I answered `y`, then `n` (shortened):

```
$ python3 - <<'EOF'
import urllib.request, re
...
[Jev: network, 1.00]
it needs the network: allow it for this one command? [y/N] y
Title: Index of /ubuntu

$ cat title.txt; python3 -c "
...
[Jev: network, 1.00]
it needs the network: allow it for this one command? [y/N] n
Index of /ubuntu
...
urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>
```

<!-- With the y, the mirror was reachable for that one command and the title was saved. The n ran in the closed box: the name didn't even resolve. With no key, Jev gives no answer, nobody is asked, and the run is what --network none would give. -->

---

# The rule: run commands where they can't do lasting damage

- Make the box before the loop
- Aim the tool at it in place of `subprocess.run` on the host
- Limit what it can see, reach, use and change with the operating system, not with checks on the text of a command
- Throw it away when the run ends

<!-- That's the whole layer in four steps. -->

---

# What sandboxing never does

It sits inside output, changing where a tool runs, and leaves the other primitives alone:

- **Model interface:** still talks to the model from outside the box; the API key never goes in
- **Control flow:** the same loop
- **Input:** still brings back what a command printed, the same way
- **Context:** untouched; the model finds the walls by walking into them

<!-- Nothing about the box is put in front of the model. -->

---

# What's missing: deciding whether it runs

- The box limits what a command can reach, not whether it runs
- Inside it everything still runs unasked, including `rm -rf` on the mounted folder: your real project
- Nothing lets you say no to one command, or break in while it works
- Nothing stops a run that loops forever, spending your money one call at a time

<!-- Deciding what's allowed to run, and when to stop, is next. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Next: Guardrails

Lesson 6
