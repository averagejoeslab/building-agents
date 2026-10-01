# examples

Runnable checkpoints for the [building-agents curriculum](../README.md): the [quark](./quark.py) harness, built one component at a time. Read a module first, then run its checkpoint.

Each file is self-contained — no imports between scripts — so you can open any one and see the entire harness at that stage. Each checkpoint is the previous one plus exactly one harness component; diff any two neighbors to see what that component costs:

```bash
diff 06_working_memory.py 07_long_term_memory.py
```

## Setup (once)

```bash
uv sync                               # installs the one dependency: anthropic
export ANTHROPIC_API_KEY=sk-ant-...   # read from the environment; there is no .env file
```

macOS or Linux (or WSL) — from Module 4 on, the checkpoints use POSIX `select`, and from Module 8 on, `termios` for terminal control.

## Checkpoints

| Script | Module | Harness component added | Lines |
|---|---|---|---|
| [`01_toy.py`](./01_toy.py) | [1](../modules/01-what-is-an-agent/) | *(toy)* model + one tool + a loop, in plain Python | 52 |
| [`02_stream.py`](./02_stream.py) | [2](../modules/02-an-llm-call/) | **Model interface** — one streamed call, read event by event | 12 |
| [`03_loop.py`](./03_loop.py) | [3](../modules/03-add-a-loop/) | **Control flow** — the loop, bound to the terminal; one-shot or chat | 15 |
| [`04_body.py`](./04_body.py) | [4](../modules/04-add-a-body/) | **Body** — the bash tool, a drained subprocess, the cutoff guard | 34 |
| [`05_self_model.py`](./05_self_model.py) | [5](../modules/05-add-a-self-model/) | **Self model** — the structured system prompt | 35 |
| [`06_working_memory.py`](./06_working_memory.py) | [6](../modules/06-add-working-memory/) | **Working memory** — reactive compaction on context overflow | 49 |
| [`07_long_term_memory.py`](./07_long_term_memory.py) | [7](../modules/07-add-long-term-memory/) | **Long-term memory** — a memory file, taught by the prompt (no code) | 49 |
| [`08_interrupts.py`](./08_interrupts.py) | [8](../modules/08-add-interrupts/) | **Interrupts** — ESC stops speech or kills a command; history stays valid | 80 |
| [`09_self_knowledge.py`](./09_self_knowledge.py) | [9](../modules/09-add-self-knowledge/) | **Self-knowledge** — the harness's own source in the prompt | 81 |
| [`quark.py`](./quark.py) | [10](../modules/10-add-caching/) | **Caching** — a byte-stable, cache-marked system prompt. This is quark. | 81 |

## Running

```bash
uv run 03_loop.py                          # chat mode: prompts you until /q
uv run quark.py "what's in this directory?"   # one-shot: works on the task, then exits
```

> [!WARNING]
> From `04_body.py` on, the agent runs whatever bash the model writes — immediately, with your privileges, no confirmation. Run it in a container or a directory you can afford to lose. From `08_interrupts.py` on, ESC stops it mid-act.

## State

From Module 7 on, the agent keeps long-term memory in `.quark/memory/memory.md`, relative to the directory you run it from. It's a plain markdown file — read it, edit it, delete it. `.quark/` is gitignored.
