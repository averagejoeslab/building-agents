# harness-engineering

**A hands-on course in building agents by building their harness.**

Created by **Chase Dovey** · [Average Joes Lab](https://github.com/averagejoeslab)

This repo has three parts, in the order to read them:

1. **[The course](#what-is-harness-engineering).** What a harness is made of, then ten lessons that build one: four primitives, then six production layers. Start here.
2. **[The paper](#the-paper).** The course's thesis, written up and tested against Claude Code, OpenAI Codex and opencode.
3. **[quark at work](#quark-at-work).** The harness you build in Lesson 4, 48 lines long, doing real work on this repo: it wrote the production lessons and every slide deck.

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

The course is **the primitives**, Lessons 1–4: they build a working harness, and they're the part to learn first. **The production layers**, Lessons 5–10, come after. They harden that harness for running unattended, and every one of them folds back into the primitives you already built.

The example throughout is [quark](https://github.com/averagejoeslab/quark), my own agent. It's one way to build each primitive, not the only way. Each primitive lesson explains the primitive, walks through quark's version, has you run it, then shows what else the primitive can do, with a second example that does more.

### The primitives

| # | Lesson | You build | Slides | Video |
|---|---|---|---|---|
| 1 | [Model interface](./lessons/01-model-interface/) | how the harness interfaces with the model: one call, and its reply | [slides](./lessons/01-model-interface/slides.md) | 🎥 coming soon |
| 2 | [Input and output](./lessons/02-input-and-output/) | how inputs are gathered, and how outputs are handled: shown to a person or run as a tool | [slides](./lessons/02-input-and-output/slides.md) | 🎥 coming soon |
| 3 | [Control flow](./lessons/03-control-flow/) | how information flows: the loop that sends a result back and goes again | [slides](./lessons/03-control-flow/slides.md) | 🎥 coming soon |
| 4 | [Context](./lessons/04-context/) | what the request holds: who it is, what's happened, what it remembers | [slides](./lessons/04-context/slides.md) | 🎥 coming soon |

Lesson 4's `quark.py` is the finished harness. By then you've built quark, and you can take apart any harness someone hands you.

### The production layers

A harness that works isn't yet a harness you'd run unattended. The production layers add hardening: things that make it watchable, safe, fast and dependable. None of it is a new primitive. Each layer folds back into the primitives it's built on, and each lesson shows where:

| # | Lesson | What it adds | Built on | Slides | Video |
|---|---|---|---|---|---|
| 5 | [Observability](./production/05-observability/) | traces, logs and costs for every step, so you can see what the agent did and why | control flow | [slides](./production/05-observability/slides.md) | 🎥 coming soon |
| 6 | [Guardrails](./production/06-guardrails/) | approvals, interrupts, step and spending limits, policies on what may run | control flow | [slides](./production/06-guardrails/slides.md) | 🎥 coming soon |
| 7 | [Sandboxing](./production/07-sandboxing/) | tools that run somewhere they can't do lasting damage | output | [slides](./production/07-sandboxing/slides.md) | 🎥 coming soon |
| 8 | [Resilience](./production/08-resilience/) | retries, backups and recovering from a failure partway through a task | model interface, output | [slides](./production/08-resilience/slides.md) | 🎥 coming soon |
| 9 | [Performance](./production/09-performance/) | prompt caching, streaming, keeping requests small, running work at the same time | context, model interface, output | [slides](./production/09-performance/slides.md) | 🎥 coming soon |
| 10 | [Evaluation](./production/10-evaluation/) | tests that measure whether the agent does its job, and catch it getting worse | the whole harness | [slides](./production/10-evaluation/slides.md) | 🎥 coming soon |

## Setup

Everything you need to run the lessons.

macOS or Linux · Python 3.13+ · [uv](https://docs.astral.sh/uv/) · an Anthropic API key.

Put your key in a `.env` file at the root of the repo (it's gitignored), and tell uv to load it:

```bash
cp .env.example .env        # then add your key to .env
export UV_ENV_FILE=.env
```

> [!WARNING]
> From Lesson 2 on, the agent runs shell commands the model writes, with no confirmation. Run it somewhere you can afford to lose.

**→ [Start with Lesson 1](./lessons/01-model-interface/)**

## The paper

**[*Five Primitives Are All You Need: Building an Agent Harness*](./paper/five-primitives-are-all-you-need.md)** · [PDF](./paper/latex/main.pdf) · [supplement](./paper/decomposition-study.md)

The paper is the course's thesis, written up for people who want the argument rather than the lessons:

- **The claim:** an agent is a model wrapped in a harness, and every harness is made of five primitives. It builds the case the way Lessons 1–4 do: one primitive at a time, from a single API call to a working agent.
- **Production:** every production concern folds back into those five primitives instead of adding a sixth, as Lessons 5–10 show one layer at a time.
- **Beyond the course:**
  - **A test on real harnesses.** It takes apart three production coding agents, Claude Code, OpenAI Codex and opencode, part by part. Nothing in them needs a sixth primitive. The [supplement](./paper/decomposition-study.md) has the evidence for every assignment, with file and line or doc link.
  - **Rules for the hard cases,** such as where a tool call's effect lands, backup models versus routing, and who a file is for.
  - **The case study** that the next section shows in full.

It's a preprint draft. [`paper/README.md`](./paper/README.md) explains how to build the PDF and what's left before submission.

## quark at work

This is the proof. Lesson 4's `quark.py` is 48 lines: the five primitives and nothing else. Here it is doing real work on this repo: it made the slides for all ten lessons and wrote the six production lessons, in four runs. Each run started with empty working memory, so what it knew beyond the task came from what earlier runs wrote down.

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
| [Model interface](./lessons/01-model-interface/slides.md) | 28 |
| [Input and output](./lessons/02-input-and-output/slides.md) | 41 |
| [Control flow](./lessons/03-control-flow/slides.md) | 48 |
| [Context](./lessons/04-context/slides.md) | 60 |

We checked them against the lessons. Every line count, demo result and setting matched; one code excerpt had dropped the `anthropic.` prefix from three exception names, which we fixed by hand. A later read of every slide found nothing invented in these four decks, but 22 slides were tightened by hand: shortened code now says it's shortened, a few lines that put something under the wrong primitive were corrected, and wording that simplified the code too far was fixed. To present one: `npx @marp-team/marp-cli -p lessons/01-model-interface/slides.md`.

**Run 3: write the six production lessons.**

The production lessons were one-paragraph stubs. quark wrote each one in its own session, in order, so each lesson's `quark.py` could start from the one before. A short shell script ran the sessions one after another with this prompt, filling in the lesson each time:

<details>
<summary>the prompt</summary>

```text
Write Lesson {n}: {title}, one of the production layers of the harness-engineering course, in production/{slug}/. Its README.md is a coming-soon stub; replace it with the real lesson. Start from your long-term memory of how this course is built and taught, and read any files you need, including the previous lessons.

Follow the course's method:
- A production layer adds hardening, not a new primitive. Say which primitives this layer is built on, explain the mechanism before the code, and keep everything inside those primitives.
- production/{slug}/quark.py is {previous lesson's quark.py} plus this layer and nothing else. Also write a fuller example, production/{slug}/{file}, that shows more of what this layer can be.
- Lay out the README like the primitive lessons: an opening explanation with no heading, then '## The worked example', '## Run it', '## Going further' (what else this layer can be, a product built around it, then the fuller example and its run) and '## What to take away' (the rule, a 'Notice what {title} never does.' line naming the primitives it leaves alone, what's still missing, and a link to the next lesson). Keep the video placeholder at the top.
- Run both files for real and paste their real output into the README. Never invent output.

The Anthropic API key is already in your environment as ANTHROPIC_API_KEY. Never print, echo or save environment variables or the key. Your responses are capped at 16384 tokens, thinking included, and a response that runs past the cap is cut off and nothing in it happens. So work in small steps: think briefly, do one short action per response, and write long files in several parts: create the file, then append to it. To stop a process, use its PID, never pkill -f or killall with a name pattern: your own command line contains these lesson paths, so a pattern can kill you. When you're done, save what you built to long-term memory.
```

</details>

What it wrote, all of it run for real:

| Lesson | README | `quark.py` | Fuller example | Built on |
|---|---|---|---|---|
| [5 Observability](./production/05-observability/) | 344 lines | 59 lines | `observability.py`, 84 | control flow |
| [6 Guardrails](./production/06-guardrails/) | 420 | 83 | `guardrails.py`, 98 | control flow |
| [7 Sandboxing](./production/07-sandboxing/) | 448 | 94 | `sandboxing.py`, 87 | output |
| [8 Resilience](./production/08-resilience/) | 640 | 135 | `resilience.py`, 112 | model interface, output |
| [9 Performance](./production/09-performance/) | 533 | 159 | `performance.py`, 100 | context, model interface, output |
| [10 Evaluation](./production/10-evaluation/) | 522 | 196 | `evaluation.py`, 122 | the whole harness |

Along the way it started Docker's daemon when it found it wasn't running, built a stand-in API that fails on purpose to test retries, killed its own test runs to test recovery, and caught a regression with the evaluation it wrote.

It didn't go smoothly, and the failures were the course's own lessons:

- **Lesson 5 stopped twice without writing anything.** A trace of each response showed why: with thinking on, 4,096 output tokens wasn't enough to think and then write a file. One response hit `max_tokens` partway through a tool request, and the harness crashed with `KeyError: 'cmd'`, the gap Lesson 2 describes. We raised `max_tokens` to 16,384 across the course, and it went through.
- **Lesson 8 killed itself.** To test crash recovery, quark ran `pkill -9 -f 08-resilience/quark.py` to kill its test agent. Its own command line contained that path, so it killed quark too. Its Docker container outlived it, the leftover Lesson 7 had warned about. We added "stop processes by PID, never by name" to the prompt and ran Lesson 8 again; it picked up the `quark.py` it had already written and finished the lesson.

We reviewed every lesson against the course's method before it was committed: each `quark.py` is the previous one plus exactly one layer, each lesson stays on the primitives it names, and every output is from a real run. Two things were changed by hand then: Lesson 6 now says what was typed at an interrupt prompt, and Lesson 9's fuller example calls per-task model routing control flow, as Lesson 3 does. A later line-by-line read, re-running every lesson's code and checking its claims against the API documentation, changed a few more: Lesson 9's framing of which model a request goes to and of printing a streamed reply, its minimum cacheable prompt size, and Lesson 8's statement of the SDK's default retries. Every lesson's demos reproduced.

**Run 4: a new session makes their slides from memory.**

```bash
uv run lessons/04-context/quark.py "Using what's in your long-term memory, and without rereading the lesson files, create the slides I'll present while recording a video for each of the six production lessons, Lessons 5 to 10. Write each deck as Marp markdown to slides.md inside that lesson's folder, in the same style as the decks you made for the primitive lessons, following the lesson's flow, with one idea per slide. One change since you wrote them: in review, Lesson 9's per-task model routing in performance.py was relabeled as control flow (routing, from Lesson 3), not the model interface, so present it that way. Your responses are capped at 16384 tokens, thinking included, so write each deck in several parts if it's long."
```

quark read its memory and the start and end of one earlier deck to match the format, then wrote the six decks without opening a lesson file. Then it answered:

<details>
<summary>quark's reply</summary>

```text
I wrote all six decks as Marp markdown, one `slides.md` in each lesson's folder. I couldn't render them because the Marp CLI isn't installed. I did check that the front matter and code fences are balanced and that no slide runs past 11 lines.

| Lesson | File | Slides |
|---|---|---|
| 5 Observability | `production/05-observability/slides.md` | 53 |
| 6 Guardrails | `production/06-guardrails/slides.md` | 64 |
| 7 Sandboxing | `production/07-sandboxing/slides.md` | 71 |
| 8 Resilience | `production/08-resilience/slides.md` | 71 |
| 9 Performance | `production/09-performance/slides.md` | 91 |
| 10 Evaluation | `production/10-evaluation/slides.md` | 91 |

- **Source:** I wrote them from long-term memory only and didn't open any lesson README or code. I did look at the front matter and ending of my Lesson 3 deck so the format matched. That means the same front matter, a header per lesson, a centered title slide and a closing "Next:" slide. Lesson 10 ends on "Back to the course" because there's no Lesson 11.
- **Flow:** each deck follows its README order. That is the problem, where it lives, the worked `quark.py`, running it, "Going further" with the richer file, the take-away rule, what the lesson never does, and what's missing.
- **Lesson 9 relabel:** the router in `performance.py` (`route()` with the quick, standard and deep tiers) is presented as control flow, as Lesson 3's routing pattern. It sits on its own slides, which contrast it with Lesson 1's outage fallback and explain why it's decided once per task (the cache is per model). The "built on" slide lists context, model interface and output, with routing flagged separately as control flow. The closing slide now says Performance never does input, and that `quark.py` never touches control flow.
- **Lesson 9 compaction model:** I kept the fixed small model that `quark.py` uses for compaction under model interface. That is one hard-coded choice, not a decision. If your review relabeled that too, it's a one-slide change.

My memory notes don't have every detail, so I inferred these. Please check them against the source before recording:
- **Lesson 6:** the order of checks in `guard()` (deny, then safe, then ask).
- **Lesson 8:** the exact modes of the fake-failure test server.
- **Lesson 9:** how `compact()` calls `ask()` (`live=False`, `models=FAST`).
- **Lesson 10:** what the `rename` case does and what "hasty" means.

The Lesson 9 README and the root README table may still describe the router as model interface. I didn't edit them.
```

</details>

| Lesson | Slides |
|---|---|
| [Observability](./production/05-observability/slides.md) | 53 |
| [Guardrails](./production/06-guardrails/slides.md) | 64 |
| [Sandboxing](./production/07-sandboxing/slides.md) | 69 |
| [Resilience](./production/08-resilience/slides.md) | 71 |
| [Performance](./production/09-performance/slides.md) | 91 |
| [Evaluation](./production/10-evaluation/slides.md) | 88 |

We checked the four details it flagged and every code line on the slides against the lessons, and its guesses about `guard()`'s order, the stand-in's modes and `compact()`'s call were right. Then a full read of every slide against its lesson found more, and this is the part to learn from. Writing from memory, quark had filled gaps with things that never happened: a few slides describe runs that aren't in the lessons, quote cache numbers no run produced, or reverse which model was benched. Others simplified the code until they misstated it, or put a mechanism under the wrong primitive. 47 slides were corrected by hand and 5 invented ones were removed, so every slide now matches its lesson. Memory is a summary, and a summary can be wrong in ways that read as confident; that's why the review step exists.

Everything quark printed is in [`docs/quark-at-work/`](./docs/quark-at-work/), including the failed attempts: [run 1](./docs/quark-at-work/run-1-read-and-remember.txt), [run 2](./docs/quark-at-work/run-2-make-slides.txt), run 3 for lessons [5](./docs/quark-at-work/run-3-lesson-05.txt), [6](./docs/quark-at-work/run-3-lesson-06.txt), [7](./docs/quark-at-work/run-3-lesson-07.txt), [8](./docs/quark-at-work/run-3-lesson-08.txt), [9](./docs/quark-at-work/run-3-lesson-09.txt) and [10](./docs/quark-at-work/run-3-lesson-10.txt), the [two](./docs/quark-at-work/run-3-lesson-05-attempt-1-silent-stop.txt) [silent stops](./docs/quark-at-work/run-3-lesson-05-attempt-2-silent-stop.txt) and the [traced crash](./docs/quark-at-work/run-3-lesson-05-attempt-3-traced-crash.txt), the [run that killed itself](./docs/quark-at-work/run-3-lesson-08-attempt-1-killed-itself.txt) and the [Lesson 9 session we stopped](./docs/quark-at-work/run-3-lesson-09-attempt-1-stopped.txt) because it was building on it, [run 4](./docs/quark-at-work/run-4-make-production-slides.txt), and the [memory file](./docs/quark-at-work/memory.md) as it stands after all four runs.

The paper's case study (§8) reads these failures through the primitives: each one lands on a specific primitive or layer.

### How Claude Code and quark worked together

Two agents did this work, at different levels. [Claude Code](https://claude.com/claude-code) worked with me on the course: the README, the four primitive lessons, and every decision about how the course teaches. Then it operated quark, and quark did the writing: the slides for all ten lessons and the six production lessons. Later it ran the paper's decomposition study under my direction and helped draft the paper.

What Claude Code did, run by run:

- **Set up each run.** It wrote the prompts, and ran Lesson 4's `quark.py` from the repo root with a shell command, the way a person would. quark got a task, its own memory and a bash tool; nothing else.
- **Kept the key safe.** Before asking quark to read "every file", it moved `.env` out of the repo, so the key reached quark through the environment and could never land in a transcript. Every transcript was searched for the key before it was committed.
- **Ran the production lessons as a loop.** A short script ran one quark session per lesson and stopped if a lesson didn't produce a `quark.py`. That's a workflow around an agent, Lesson 3's control flow one level up.
- **Diagnosed failures without changing quark.** When Lesson 5 kept stopping, it wrapped quark's model calls to log each response's `stop_reason`, found the cut-off, and fixed the cause in the course's code, not with a workaround. When Lesson 8 killed itself, it read the transcript, found the `pkill`, cleaned up the leftover container and restarted from Lesson 8. (It then killed its own shell command the same way, with `pkill -f`. The lesson applies to everyone.)
- **Reviewed before anything was committed.** It diffed each `quark.py` against the one before, read every README against the course's method, traced demo output back to the commands that produced it, tested the one path quark hadn't (summarizing Sonnet 5.5's thinking blocks on Haiku), and checked that every code block matches its file and every link resolves. It fixed a few small things by hand, and this page says which.
- **Checked the slides.** It rendered the decks with Marp, checked every number and code line against the lessons, and looked at the slides as images.

quark never saw Claude Code. From its side, someone gave it a task in a terminal, the same as anyone running it would.

## How to cite

If you use this course, its code or its framework, please cite the paper:

```bibtex
@misc{dovey2026fiveprimitives,
  author       = {Chase Dovey},
  title        = {Five Primitives Are All You Need: Building an Agent Harness},
  year         = {2026},
  organization = {Average Joes Lab},
  howpublished = {\url{https://github.com/averagejoeslab/building-agents}},
  note         = {Companion course: harness-engineering}
}
```

GitHub's **Cite this repository** button gives the same, from [`CITATION.cff`](./CITATION.cff).

## License

© 2026 Chase Dovey, Average Joes Lab.

- **Code** (every `.py` file, and the code shown in the lessons): [MIT](./LICENSE). Use it for anything, keeping the copyright notice.
- **Content** (the lessons' text, slides, paper, docs, diagrams and videos): [CC BY-NC-SA 4.0](./LICENSE-CONTENT). Share and adapt it with credit to Chase Dovey, Average Joes Lab, for non-commercial use, under the same license. Commercial use, such as a book or a paid course, needs permission.
