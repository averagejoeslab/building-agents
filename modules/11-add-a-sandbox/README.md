# Add a sandbox

> **Harness component: the execution environment.** Where the body's actions actually run. quark runs every command on your machine with your privileges; a sandbox moves the body into an isolated container, so the worst a bad command can reach is the container and the project you chose to share with it.

Module 10 finished quark. This module goes one step past it. Every command quark runs executes **immediately, on your machine, as you** — it can read `~/.ssh`, delete your home directory, install software, or send your files across the network. The model isn't malicious; the problem is that one bad command — a misunderstanding, a typo in a path, or instructions planted in a file the agent read (*prompt injection*) — is irreversible.

A sandbox gives the body a smaller world to live in.

## Why one body makes this easy

Most harnesses have a toolkit — `read`, `write`, `edit`, `bash` — and sandboxing it is awkward: put `bash` in a container and the file tools still reach the host directly. quark has one body, and every action — reading, writing, running, speaking — goes through it. **Sandbox the one tool and you've sandboxed everything the agent can do.** This is the payoff of the design choice in [Module 4](../04-add-a-body/).

## The checkpoint

[`examples/11_sandbox.py`](../../examples/11_sandbox.py) is quark plus the sandbox — 85 lines. Diff it against [`quark.py`](../../examples/quark.py) and you'll see four kinds of change:

1. **Start a container** when the harness starts, and remove it when the harness exits.
2. **Run the body inside it** — `docker exec` instead of a host shell.
3. **Interrupt across the boundary** — ESC must kill the command *inside* the container.
4. **Tell the model the truth** about its new body.

It needs [Docker](https://docs.docker.com/get-docker/) installed and running.

## The image

[`examples/Dockerfile.sandbox`](../../examples/Dockerfile.sandbox):

```dockerfile
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash coreutils findutils grep sed gawk procps ripgrep git python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
```

A small Debian with a shell, the everyday text tools, `git`, `ripgrep`, and `python3` — enough for the escalation gradient in quark's prompt (pipes → `python3 -c` → scripts). That's a deliberate list, because **nothing can be installed later**: the container runs with no network and a read-only system. If your agent needs Node, a compiler, or your project's test runner, add it here. The image *is* the inventory of everything the body can use.

## Starting the sandbox

```python
HERE, SANDBOX = os.path.dirname(os.path.abspath(__file__)), f"quark-sandbox-{secrets.token_hex(4)}"
if subprocess.run(["docker", "image", "inspect", "quark-sandbox"], capture_output=True).returncode: subprocess.run(["docker", "build", "-t", "quark-sandbox", "-"], stdin=open(os.path.join(HERE, "Dockerfile.sandbox")), check=True)
subprocess.run(["docker", "run", "-d", "--rm", "--init", "--name", SANDBOX, ...flags..., "quark-sandbox", "sleep", "infinity"], check=True, capture_output=True); atexit.register(lambda: subprocess.run(["docker", "rm", "-f", SANDBOX], capture_output=True))
```

Three lines:

1. A unique container name per run, so two agents never collide, and the directory the harness lives in (where the Dockerfile is).
2. Build the image the first time — `docker image inspect` fails if it doesn't exist yet. Later runs reuse it. The Dockerfile is piped in on stdin (`-`), which builds with no context at all: nothing from your disk is sent to the build, which is both faster and one less thing to leak.
3. Start one long-lived container that just sleeps (`sleep infinity`); every command will be `exec`'d into it. And register an `atexit` hook that removes it however the harness exits — `/q`, Ctrl+C, or a crash.

The flags are the actual security boundary. Every one is doing work:

| Flag | What it does |
|---|---|
| `--rm` | Delete the container when it stops. |
| `--init` | Run a tiny init process as PID 1 that reaps finished processes. Without it, every command that leaves orphans behind (and every ESC) leaves zombie processes that pile up. |
| `--network none` | No network interface at all. No DNS, no downloads, no sending your code anywhere. |
| `--cap-drop ALL` | Drop every Linux capability: no mounting filesystems, no changing users, no raw sockets. |
| `--security-opt no-new-privileges` | No `setuid` escalation, even from a binary that has the bit set. |
| `--read-only` | The container's own filesystem is read-only. Nothing can be installed or tampered with. |
| `--tmpfs /tmp:rw,nosuid,size=256m` | A small scratch space in memory, for temporary files. |
| `--memory 1g --cpus 2 --pids-limit 256` | Resource caps. A runaway loop or fork bomb hits a ceiling instead of taking down your machine. |
| `--user {uid}:{gid}` | Run as *you* (your user and group IDs), not root — so files the agent creates in your project are owned by you. |
| `-e HOME=/tmp` | Your UID has no home directory inside the image; point `HOME` somewhere writable. |
| `-v {cwd}:/workspace -w /workspace` | Share exactly one host directory — the one you launched from — read-write, as the working directory. |

## The body, inside

```python
            doing = subprocess.Popen(["docker", "exec", SANDBOX, "bash", "-c", "echo $$ > /tmp/.doing; " + c.input["cmd"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
```

The only difference from quark's `Popen` is *where* the command runs: `docker exec` starts `bash -c <cmd>` inside the container, and its output streams back through the same pipe. Everything Module 4 built — the 50ms drain loop, the bounded final drain, the cutoff guard — works unchanged, because from the harness's side it's still a process writing to a pipe.

The `echo $$ > /tmp/.doing` prefix is for interrupts.

## Interrupts across the boundary

Here's the subtle part, and the most instructive bug a sandbox introduces. In quark, ESC does `os.killpg(doing.pid, 9)`: kill the command's whole process group. But `doing` is now the **`docker exec` client** on your host — not the command. Kill the client and the command keeps running inside the container: `sleep 30 | cat` is still there after the client is gone. The kill has to happen where the process actually lives.

Every `docker exec` command starts as the leader of its own process group inside the container, and every stage of a pipeline joins that group — exactly like `start_new_session=True` on the host. So the command records its group ID as its first act (`echo $$ > /tmp/.doing`), and ESC kills that group from inside:

```python
                if interrupt.is_set():
                    subprocess.run(["docker", "exec", SANDBOX, "bash", "-c", "kill -9 -- -$(cat /tmp/.doing)"], capture_output=True)   # killpg, inside the sandbox
                    try: os.killpg(doing.pid, 9)
                    except OSError: pass
                    killed = True; break
```

`kill -9 -- -<pgid>` is `killpg` in shell form: the minus sign means "the whole group." Then the host-side `killpg` cleans up the `docker exec` client too. The result matches quark on the host exactly: ESC stops the current command and its pipeline, while a server the agent deliberately started in the background on an earlier command keeps running.

## Tell the model the truth

The body changed, so the self model has to change with it — this is cognitive alignment from the [README](../../README.md) applied to safety. A prompt that still says *"any tool you install"* would send the model into a wall of failed `apt-get`s. So four lines of the system prompt change:

- **Body:** *"bash — your singular means of acting and observing, running inside a sandbox. Its reach is the whole sandbox: anything doable from a command line with the programs it has…"*
- **Environment:** *"…Your body runs in a sandbox: an isolated container with no network and a read-only system; only /workspace and /tmp are writable."*
- **Where:** *"/workspace — the project directory {host path}, mounted from the host (changes there are real)"*
- **Escalation:** pipes → `python3 -c` → scripts, and *"Nothing can be installed in the sandbox — if a task needs a tool it doesn't have, say so."*

The Mechanics section needs no change: `mechanics()` reads the file it's in, so the model sees the sandbox code automatically. Long-term memory works unchanged too — `.quark/memory/memory.md` is relative to `/workspace`, so it lands in your project directory on the host and survives the container.

## What the sandbox does and doesn't buy you

**Removed:** the rest of your filesystem (`~/.ssh`, other projects, your home directory), the network, installing or modifying software, and runaway resource use.

**Still reachable:** the directory you shared. It's mounted read-write, so the agent can still delete or rewrite your project's files, and anything secret *inside* that directory (a `.env`, credentials in a config file) is readable. Use version control, and launch the agent from a directory that holds only what it needs.

**Still true of any container:** it shares your machine's kernel. Docker isolation is a strong boundary against mistakes and casual misuse, not against a determined attacker with a kernel exploit. For truly untrusted workloads, the same harness can target a stronger runtime (gVisor, a Firecracker microVM, or a disposable cloud VM) — only the `docker run` line changes.

If your agent needs the network (to install packages or call APIs), removing `--network none` is a one-word change. Make it a deliberate one: it reopens the exfiltration path.

## Run it

```bash
cd examples
uv run 11_sandbox.py
```

The first run builds the image (a minute or so). Then try to break out:

```
> try to read ~/.ssh, then try to download https://example.com, then create a file called proof.txt here
```

You should see no `.ssh` to read (inside the sandbox, `~` is the empty scratch directory `/tmp`, and your real home directory doesn't exist at all), the download fail with a name-resolution error, and `proof.txt` appear in your actual project directory. While it's running, `docker ps` shows the `quark-sandbox-…` container; after `/q` (or Ctrl+C) it's gone. The one exit `atexit` can't catch is the harness itself being killed outright (`kill -9`); if that ever leaves a container behind, `docker rm -f $(docker ps -aq --filter name=quark-sandbox)` clears it.

## Where to go from here

The body is contained. The remaining production layers plug into the same loop: **approval gates** right before `docker exec`, **tracing** of every model call and command beside the loop, and **evaluation** suites run against the harness after every change. The [README](../../README.md#what-this-curriculum-leaves-out) sketches where each one goes.

---

Back to the [root README](../../README.md).
