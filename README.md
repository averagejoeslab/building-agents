# harness-engineering

**A hands-on course in building agents by building their harness.**

## What is harness engineering?

I'm not going to give you a definition. People are bad at saying what they mean and good at showing it, and I'm no exception. I've seen it at conferences: talk after talk, people use different words for the same thing — framework, scaffold, runtime, orchestration layer — while the thing itself is still evolving. The words don't line up, but when they show you how it works, it's the same thing every time. A definition only says what something is; a mechanism shows it.

So instead of saying what I mean, I'll show you: what an agent is made of, and what each part does.

An agent works by two mechanistic primitives:

- **The model** predicts. Given tokens, it produces the tokens most likely to come next: **TokensOut = Model(TokensIn)**.
- **The harness** does everything else. It decides how inputs are gathered, how they're presented to the model, how it interfaces with the model, how the model's outputs are handled, and how information flows between all of them.

> **Agent = Harness(Model)**

The model goes inside; the harness wraps it. Harness engineering is the work of building that second primitive.

The first primitive is built by **model development**: training data, compute, and the methods to train and evaluate a model. If you want to know how a model works inside, read [the model deep dive](./docs/the-model.md). It's optional. This repo is about the harness.

## What is a harness made of?

Five mechanistic primitives. Control flow is one of them, and the other four sit inside it:

```
control flow          how information flows between the other four: run once, a chat loop, an agent loop, a workflow
├── input             how inputs are gathered, from a person or the world
├── context           what the request holds, and how inputs are presented in it
├── model interface   how the harness interfaces with the model
└── output            how the model's outputs are handled: shown to a person, or run as tools
```

Anything you build around a model that does these five things is a harness. How you build each one is up to you. Control flow shows this most clearly: run the other four once and you have a single call. Loop and hand back after every reply and you have a chatbot. Keep looping while the model asks to use tools and you have an agent. Claude Code, Cursor, Codex, and the harness you'll build here are all these five primitives with different choices made.

Input and output are built independently, but they're two ends of the same exchange, so this repo teaches them together.

## How this repo teaches

You've just watched the method. Take a thing and ask, *what is it, and by what mechanistic primitives does it work?* An agent is a model and a harness. A harness is control flow, input, context, model interface and output. Ask once more and the answers stop being shared: one harness reads a terminal, another a Slack channel. That's where taking apart ends.

The lessons go the other way and build it back up, one primitive at a time, in a different order from the list above: outward from the model. Lesson 1 calls the model and nothing else. Lessons 2–4 each add the primitive the last one was missing, and each one's `quark.py` is the previous lesson's plus that primitive.

The course has two parts. **The primitives**, Lessons 1–4, build a working harness. **The production layers**, Lessons 5–10, harden it for running unattended.

The example throughout is [quark](https://github.com/averagejoeslab/quark), my own agent. It's one way to build each primitive, not the only way. Each primitive lesson explains the primitive, walks through quark's version, has you run it, then shows what else the primitive can do, with a second example that does more.

### The primitives

| # | Lesson | You build | Video |
|---|---|---|---|
| 1 | [Model interface](./lessons/01-model-interface/) | how the harness interfaces with the model: one call, and its reply | 🎥 coming soon |
| 2 | [Input and output](./lessons/02-input-and-output/) | how inputs are gathered, and how outputs are handled: shown to a person or run as a tool | 🎥 coming soon |
| 3 | [Control flow](./lessons/03-control-flow/) | how information flows: the loop that sends a result back and goes again | 🎥 coming soon |
| 4 | [Context](./lessons/04-context/) | what the request holds: who it is, what's happened, what it remembers | 🎥 coming soon |

Lesson 4's `quark.py` is the finished harness. By then you've built quark, and you can take apart any harness someone hands you.

### The production layers (coming soon)

A harness that works isn't yet a harness you'd run unattended. The production layers add hardening: things that make it watchable, safe, fast and dependable. None of it is a new primitive. Each piece is built on the primitives you already know, and these lessons will show where:

| # | Lesson | What it adds | Built on | Video |
|---|---|---|---|---|
| 5 | [Observability](./production/05-observability/) | traces, logs and costs for every step, so you can see what the agent did and why | control flow | 🎥 coming soon |
| 6 | [Guardrails](./production/06-guardrails/) | approvals, interrupts, step and spending limits, policies on what may run | control flow | 🎥 coming soon |
| 7 | [Sandboxing](./production/07-sandboxing/) | tools that run somewhere they can't do lasting damage | output | 🎥 coming soon |
| 8 | [Resilience](./production/08-resilience/) | retries, backups and recovering from a failure partway through a task | model interface, output | 🎥 coming soon |
| 9 | [Performance](./production/09-performance/) | prompt caching, streaming, keeping requests small, running work at the same time | context, model interface, output | 🎥 coming soon |
| 10 | [Evaluation](./production/10-evaluation/) | tests that measure whether the agent does its job, and catch it getting worse | the whole harness | 🎥 coming soon |

## quark at work

Lesson 4's `quark.py` is 48 lines. Here it is doing real work on this repo: it made the slides for the four primitive lessons. It took two runs, and the second one started with empty working memory, so everything it knew came from what the first run wrote down.

**Run 1: read the repo and remember it.**

```bash
uv run lessons/04-context/quark.py "Read every file in this repo, skipping .git, .venv and the SVG images in assets/, and summarize what this repo is and what each lesson teaches. Save what you learn to your long-term memory in enough detail that you could teach each of the four primitive lessons later without rereading the files."
```

quark made 10 bash calls. It listed the repo, read the files in batches (the root files, each lesson's README and code, the model deep dive, the production stubs), and after each lesson appended what it had learned to `.quark/memory/memory.md`. That left 25 KB of notes, one timestamped entry per lesson plus one for the deep dive. Then it answered:

<details>
<summary>quark's reply</summary>

```text
I read every file except `.git`, `.venv` and the SVGs in `assets/`, and saved what I learned to `.quark/memory/memory.md`. That covers the root files, `docs/the-model.md`, all of `lessons/01` to `04`, and the six production stubs. For `uv.lock` I only read the header. It's the generated dependency lock, so nothing in it affects the lessons. I haven't run any of the lesson scripts.

## What the repo is
It's **harness-engineering**, a hands-on course on building agents by building their harness, by averagejoeslab (MIT license, Python 3.13 or later, `uv`, and the `anthropic` package). Its thesis:
- **Model:** `TokensOut = Model(TokensIn)`. The model only predicts the next tokens.
- **Agent:** `Agent = Harness(Model)`. The harness is everything around the model.
- **Five primitives:** control flow wraps four others: input, context, model interface and output.

The course builds one example agent, **quark**, outward from the model. Each lesson's `quark.py` is the previous one plus one primitive, and Lesson 4's `quark.py` is the finished harness.

Lessons 1 to 4 are the real content. Lessons 5 to 10 (observability, guardrails, sandboxing, resilience, performance, evaluation) are short "coming soon" stubs. `docs/the-model.md` is optional background on how an LLM works inside.

## The four lessons
1. **Model interface.** This is one request out and one response back. `quark.py` is a single `client.messages.create(...)` call. The response fields that matter are `content`, `stop_reason` and `usage`. `model_interface.py` adds a timeout, retries, a fallback model, streaming and settable thinking options. Nothing real feeds in or handles the reply yet.
2. **Input and output.**
   - **Input:** a task from the command line or a prompt, plus the `tool_result` that returns what a tool printed.
   - **Output:** printing text blocks and running `tool_use` blocks with `subprocess`.
   - **Tools:** the model asks for them and the harness acts. The result is built but never sent back to the model.
   - **`input_output.py`:** a Telegram chat, concurrent tools, timeouts and error results.
3. **Control flow.** `quark.py` wraps Lesson 2 in `while True`. It appends results to `messages` and stops when the model stops asking for tools, which makes it an agent loop with no step limit. `control_flow.py` adds `MAX_STEPS` and handles refusals. `workflow.py` is an evaluator-optimizer workflow where the code decides the order of calls.
4. **Context.** `quark.py` adds working memory, a system prompt built as several "models" (self, world, other selves, body), a view of its own source (`mechanics()`), a memory file (`.quark/memory/memory.md`) and compaction. Compaction only happens after the API says "prompt is too long". `context.py` adds an episode log, skills files, token counting before each call (`fit`) and cutting long tool results (`trim`).

My own system prompt and loop are Lesson 4's `quark.py`, so I'm quark in that form.

The memory file has the details for each lesson: the code, the demos, the "going further" options and each lesson's rule and what it leaves missing. I can teach the lessons from that without rereading the repo.
```

</details>

**Run 2: a new session makes the slides from memory.**

```bash
uv run lessons/04-context/quark.py "Using what's in your long-term memory, and without rereading the lesson files, create the slides I'll present while recording a video for each of the four primitive lessons. Write each deck as Marp markdown to slides.md inside that lesson's folder, following the lesson's flow, with one idea per slide."
```

quark made 7 bash calls. It read its memory file, listed the lesson folders, wrote one deck per lesson, and added a note to its memory that the job was done. It never opened a lesson file. Then it answered:

<details>
<summary>quark's reply</summary>

```text
I wrote a Marp deck to `slides.md` in each of the four lesson folders, using only my memory notes. I haven't rendered them, because the Marp CLI isn't installed, so I don't know how they look yet.

| Lesson | Slides |
|---|---|
| `01-model-interface` | about 30 |
| `02-input-and-output` | about 43 |
| `03-control-flow` | about 50 |
| `04-context` | about 62 |

- **Flow:** each deck follows the lesson's own order. It starts with a title slide and where the last lesson left off. Then it explains the primitive, walks through quark's version, runs it, and covers "Going further" with the richer example file. It ends with "What to take away", what's missing, and a "Next:" slide.
- **Slide style:** each slide has one idea, so a few are only a sentence long and you'll pause on them. Code snippets are short excerpts, not full files. Title and closing slides are centered, and the other slides carry a header with the lesson name and page numbers.
- **Four lesson folders:** I read "four primitive lessons" as the four folders. Lesson 2 covers two primitives, input and output, so it's one deck.

My notes were detailed, but I haven't checked the decks against the actual files, so some details could be slightly off. The ones most worth checking are the line counts, the demo outputs (71, 327, 48 and so on) and the exact code excerpts.

To preview, run `npx @marp-team/marp-cli -p lessons/01-model-interface/slides.md`. That downloads the CLI the first time.
```

</details>

The decks it wrote:

| Lesson | Slides |
|---|---|
| [Model interface](./lessons/01-model-interface/slides.md) | 30 |
| [Input and output](./lessons/02-input-and-output/slides.md) | 43 |
| [Control flow](./lessons/03-control-flow/slides.md) | 50 |
| [Context](./lessons/04-context/slides.md) | 62 |

We checked them against the lessons. Every line count, demo result and setting matched; one code excerpt had dropped the `anthropic.` prefix from three exception names, which we fixed by hand. To present one: `npx @marp-team/marp-cli -p lessons/01-model-interface/slides.md`.

Everything quark printed, and the memory file it wrote, are in [`docs/quark-at-work/`](./docs/quark-at-work/): [run 1](./docs/quark-at-work/run-1-read-and-remember.txt), [run 2](./docs/quark-at-work/run-2-make-slides.txt), [memory](./docs/quark-at-work/memory.md).

## Setup

macOS or Linux · Python 3.13+ · [uv](https://docs.astral.sh/uv/) · an Anthropic API key.

Put your key in a `.env` file at the root of the repo (it's gitignored), and tell uv to load it:

```bash
cp .env.example .env        # then add your key to .env
export UV_ENV_FILE=.env
```

> [!WARNING]
> From Lesson 2 on, the agent runs shell commands the model writes, with no confirmation. Run it somewhere you can afford to lose.

**→ [Start with Lesson 1](./lessons/01-model-interface/)**

## License

MIT.
