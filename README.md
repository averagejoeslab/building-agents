# building-agents

**A curriculum in harness engineering: how to build the harness around a model.**

> **Agent = Model + Harness.**
> The model is the intelligence — Claude, GPT, Gemini, whatever sits behind an API. The harness is everything else: the code, configuration, and execution logic that wraps the model and gives it a loop, a body to act with, memory, a sense of where and when it is, and a way for a human to stop it. A raw model is not an agent. The harness is what turns it into one.

I am Chase Dovey, and I conduct research on agentic systems. Most of that work is building harnesses around models. That's a skill worth having right now: the industry is in a race to see who has *the best harness* — Claude Code, Cursor, Codex, and every agent pitched at a conference are, underneath, a harness wrapped around someone else's model. To me the best harness is the one you build yourself, because you understand every line of it and can change it to fit your needs.

This repo teaches you to build one. Not by describing harnesses in the abstract, but by building a real one — **[quark](./examples/quark.py)**, a complete, working agent harness in 81 lines of Python — one component at a time, starting from a single LLM call.

## What harness engineering is (and isn't)

There are three disciplines involved in agentic systems. This repo is about the middle one.

| Discipline | What it produces | In this repo |
|---|---|---|
| **Model development** | A trained model you call over an API. Pretraining, fine-tuning, RLHF — the work of a handful of labs with GPUs and data pipelines. | Out of scope. [Background reading](./docs/the-model.md) if you want to know what's inside the model you're wrapping. |
| **Harness engineering** | An *agent*: the model wrapped in a loop, a body, memory, and control. | **This is the curriculum.** |
| **Agentic engineering** | Products built *with* agents — you orchestrating an agent to write software. | [Where you go after the curriculum.](#after-the-harness-agentic-engineering) |

The model you get from model development can do exactly one thing: given some text, predict the text that comes next. On its own it cannot run a command, read a file, remember yesterday, know what time it is, decide when a task is finished, or be interrupted. Every one of those is something the harness gives it. That's the job.

## The harness you'll build: quark

quark is an agentic organism: one bash tool, one loop, streaming responses, interruptible at any moment, self-compacting when its context fills up, persistent memory across sessions, and the ability to read its own source code. It's small enough to read in five minutes and complete enough to do real work in your terminal.

Its anatomy is the harness, component by component:

| Harness component | What quark does | Module |
|---|---|---|
| **Model interface** | Streams each response event by event, so the harness can act *between* events | [2](./modules/02-an-llm-call/) |
| **Control flow** | One `while True` loop, bound to an environment (the terminal) | [3](./modules/03-add-a-loop/) |
| **Body (tools)** | A single bash tool, run as a subprocess whose output is drained as it arrives | [4](./modules/04-add-a-body/) |
| **Self model (system prompt)** | Tells the model what it is, where it is, who it's talking to, and how to act | [5](./modules/05-add-a-self-model/) |
| **Working memory (context management)** | When the context window overflows, drops the oldest turns and summarizes the rest | [6](./modules/06-add-working-memory/) |
| **Long-term memory (persistence)** | A markdown file the model writes and greps with its own body, taught entirely by the prompt | [7](./modules/07-add-long-term-memory/) |
| **Interrupts (human control)** | ESC stops the model mid-sentence or kills a running command, and the conversation stays valid | [8](./modules/08-add-interrupts/) |
| **Self-knowledge** | The harness embeds its own source code in the prompt, so the model knows how it works | [9](./modules/09-add-self-knowledge/) |
| **Prompt caching (performance)** | The system prompt is kept byte-stable and cached, so the big prefix is paid for once | [10](./modules/10-add-caching/) |
| **Execution environment** *(beyond quark)* | The body runs in a locked-down container: no network, read-only system, one shared directory | [11](./modules/11-add-a-sandbox/) |

Four rules shaped every line of it, and they're the rules this curriculum teaches:

1. **Minimum lines, maximum function.** Every line earns its place.
2. **The model handles what it can; code handles what it must.** Anything that can be taught in the system prompt — how to keep memory, how to use bash well, when to ask — lives in the prompt. Code is reserved for what can't be delegated: the loop, the conversation's invariants, error recovery, terminal control.
3. **Bounded blast radius on failure.** Every API call, subprocess, and keystroke has a failure path that leaves the conversation valid for the next turn.
4. **Cognitive alignment.** The code and the prompt share one vocabulary — self, world, other selves, mind, body, working and long-term memory, saying, doing — so when the model reads its own implementation, it finds the same words it was taught.

## Curriculum

Each module adds one harness component and ends in a runnable checkpoint in [`examples/`](./examples/). Each checkpoint is the previous one plus that component, and the last one *is* quark — byte for byte.

| # | Module | Harness component | Checkpoint | Lines |
|---|---|---|---|---|
| 1 | [What is an agent?](./modules/01-what-is-an-agent/) | (concept — Model + Harness) | [`01_toy.py`](./examples/01_toy.py) | 52 |
| 2 | [An LLM call](./modules/02-an-llm-call/) | Model interface | [`02_stream.py`](./examples/02_stream.py) | 12 |
| 3 | [Add a loop](./modules/03-add-a-loop/) | Control flow | [`03_loop.py`](./examples/03_loop.py) | 15 |
| 4 | [Add a body](./modules/04-add-a-body/) | Tools / action | [`04_body.py`](./examples/04_body.py) | 34 |
| 5 | [Add a self model](./modules/05-add-a-self-model/) | System prompt | [`05_self_model.py`](./examples/05_self_model.py) | 35 |
| 6 | [Add working memory](./modules/06-add-working-memory/) | Context management | [`06_working_memory.py`](./examples/06_working_memory.py) | 49 |
| 7 | [Add long-term memory](./modules/07-add-long-term-memory/) | Persistence | [`07_long_term_memory.py`](./examples/07_long_term_memory.py) | 49 |
| 8 | [Add interrupts](./modules/08-add-interrupts/) | Human control | [`08_interrupts.py`](./examples/08_interrupts.py) | 80 |
| 9 | [Add self-knowledge](./modules/09-add-self-knowledge/) | Self-knowledge | [`09_self_knowledge.py`](./examples/09_self_knowledge.py) | 81 |
| 10 | [Add caching](./modules/10-add-caching/) | Performance | [`quark.py`](./examples/quark.py) | 81 |
| 11 | [Add a sandbox](./modules/11-add-a-sandbox/) | Execution environment | [`11_sandbox.py`](./examples/11_sandbox.py) | 85 |

Read the module, then run the checkpoint. Diff any checkpoint against the one before it and you'll see exactly the lines that module added — nothing else changes. Module 10 completes quark; Module 11 goes one step past it and moves quark's body into a sandbox (it needs Docker).

The model is Claude (`claude-sonnet-4-5`), because Anthropic is where the harness vocabulary consolidated and the Claude API is what I work with day to day. The harness itself is model-agnostic: point the client at another provider's Anthropic-compatible endpoint and almost nothing in these modules changes.

## Setup

You'll need:

- macOS or Linux (quark uses `termios` for terminal control; on Windows, use WSL)
- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/) for dependency management
- An [Anthropic API key](https://console.anthropic.com), exported in your shell:

```sh
export ANTHROPIC_API_KEY=sk-ant-...
cd examples
uv run 02_stream.py
```

The checkpoints read the key from the environment and nothing else — there's no `.env` file.

## A note on safety

From Module 4 on, the agent executes whatever bash the model produces — **immediately, with your user privileges, no confirmation step**. That is the design: bash is the agent's body. Treat it accordingly: run it in a container or in a directory you can afford to lose, don't point it at production credentials, and once you reach Module 8, keep ESC handy. [Module 11](./modules/11-add-a-sandbox/) shows how to put the body in a sandbox properly.

## What this curriculum leaves out

quark is a complete harness for one person in one terminal, and Module 11 sandboxes its body. Production harnesses add more layers on top of the same shape, and once you've built quark you'll know where each one plugs in:

- **Approval gates** — ask before running a command. The natural place is right before `subprocess.Popen` in the tool loop.
- **Stronger isolation** — Module 11 uses Docker, which shares your machine's kernel. For untrusted workloads, the same harness can target gVisor, a microVM, or a disposable VM; only the line that starts the sandbox changes.
- **Observability** — structured traces of every model call and command, written beside the loop.
- **Evaluation** — a suite of tasks run against the harness, scored, and compared across changes.

## Background reading

- [Agentic systems: workflows and agents](./docs/agentic-systems.md) — the control-flow shapes agentic systems take, and why this repo builds an autonomous agent.
- [The model: what the harness wraps](./docs/the-model.md) — the forward pass, the training pipeline, and inference; plus system prompt learning, the one training-adjacent paradigm a harness owns.

## After the harness: agentic engineering

Once you've built a harness, the natural question is what to do with the agent. There are two directions, and both are worth pursuing.

**Outward** — point the agent at the next codebase and use it to build other software. Peter Steinberger built **openclaw** by directing coding agents to produce most of the implementation, then embedded an agent harness inside openclaw itself, so the product ships with its own agent.

**Recursive** — point the agent at its own harness. quark reads its own source on every turn; ask it to improve itself. This repo is built the same way: Claude Code (a harness running on Claude) writes modules and ships commits while I drive. Anthropic does the model development, the Claude Code team does the harness engineering, and I do the agentic engineering — every layer of the stack is visible in the work itself.

You might have heard the phrase "vibe coding" (a Karpathy coinage). The way I think about it, vibe coding is the casual end of agentic engineering — ask the agent for something and accept what it gives you. Agentic engineering is the disciplined version: thinking carefully about what to ask, what tools to provide, and how to verify what comes back.

> [!NOTE]
> The term *harness* in this sense was consolidated through 2025–2026 by Anthropic ([effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents); [harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)), LangChain ([*The Anatomy of an Agent Harness*](https://www.langchain.com/blog/the-anatomy-of-an-agent-harness)), Martin Fowler ([Birgitta Böckeler, *Harness engineering for coding agent users*](https://martinfowler.com/articles/harness-engineering.html)), [Addy Osmani](https://addyosmani.com/blog/agent-harness-engineering/), and [O'Reilly Radar](https://www.oreilly.com/radar/agent-harness-engineering/).

## Start building

**→ [Module 1: What is an agent?](./modules/01-what-is-an-agent/)**

## License

Released under MIT — use it however you find useful. If you end up building something interesting with it I'd love to hear about it.
