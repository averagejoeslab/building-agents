# harness-engineering

**A hands-on course in building agents by building their harness.**

Created by **Chase Dovey** · [Average Joes Lab](https://github.com/averagejoeslab)

This repo has three parts, in the order to read them:

1. **[The course](#what-is-harness-engineering).** What a harness is made of, then ten lessons that build one: four that build its five primitives, then six production layers. Start here.
2. **[The paper](#the-paper).** The course's thesis, written up and tested against Claude Code, OpenAI Codex and opencode.
3. **[quark at work](#quark-at-work).** The harness you build in Lesson 4 doing real work on this repo, from its own memory across ten sessions: it brought the slides in line with the lessons, made their PDFs, reviewed the paper and weighed in on the order of the production lessons. It's the paper's case study.

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

The lessons go the other way and build it back up, one primitive at a time, in a different order from the list above: outward from the model. Lesson 1 calls the model and nothing else. Lessons 2–4 each add what the last one was missing (input and output, then control flow, then context), and each one's `quark.py` is the previous lesson's plus that.

The course is **the primitives**, Lessons 1–4: they build a working harness, and they're the part to learn first. **The production layers**, Lessons 5–10, come after. They harden that harness for running unattended, and every one of them folds back into the primitives you already built.

The example throughout is [quark](https://github.com/averagejoeslab/quark), my own agent. It's one way to build each primitive, not the only way. Each primitive lesson explains the primitive, walks through quark's version, has you run it, then shows what else the primitive can do, with a second example that does more.

### The primitives

| # | Lesson | You build | Slides | Video |
|---|---|---|---|---|
| 1 | [Model interface](./lessons/01-model-interface/) | how the harness interfaces with the model: one call, and its reply as it streams back | [slides](./lessons/01-model-interface/slides.pdf) · [md](./lessons/01-model-interface/slides.md) | 🎥 coming soon |
| 2 | [Input and output](./lessons/02-input-and-output/) | how inputs are gathered, and how outputs are handled: shown to a person or run as a tool | [slides](./lessons/02-input-and-output/slides.pdf) · [md](./lessons/02-input-and-output/slides.md) | 🎥 coming soon |
| 3 | [Control flow](./lessons/03-control-flow/) | how information flows: the loop that sends a result back and goes again | [slides](./lessons/03-control-flow/slides.pdf) · [md](./lessons/03-control-flow/slides.md) | 🎥 coming soon |
| 4 | [Context](./lessons/04-context/) | what the request holds: who it is, what's happened, what it remembers | [slides](./lessons/04-context/slides.pdf) · [md](./lessons/04-context/slides.md) | 🎥 coming soon |

Lesson 4's `quark.py` is the finished harness. By then you've built quark, and you can take apart any harness someone hands you.

**Presenting a lesson.** Each lesson has a slide deck for teaching it to a room, as a PDF you can open and present straight from GitHub, and as the [Marp](https://marp.app) Markdown it's made from. To present from the Markdown instead: `npx @marp-team/marp-cli -p lessons/01-model-interface/slides.md`.

### The production layers

A harness that works isn't yet a harness you'd run unattended. The production layers add hardening: things that make it safe, watchable, dependable and fast. None of it is a new primitive. Each layer folds back into the primitives it's built on, and each lesson shows where. They build on the harness you finish Lesson 4 with: each lesson's `quark.py` is the one before it plus that layer, and nothing else.

The order is the order you'd want them in. First the box, so the agent can't do lasting damage; then the gate in front of it; then a record of both; then surviving failures, then cost and speed, and last, a way to tell whether any of it still works.

| # | Lesson | What it adds | Built on | Slides | Video |
|---|---|---|---|---|---|
| 5 | [Sandboxing](./production/05-sandboxing/) | commands that run in a box where they can't do lasting damage | output | [slides](./production/05-sandboxing/slides.pdf) · [md](./production/05-sandboxing/slides.md) | 🎥 coming soon |
| 6 | [Guardrails](./production/06-guardrails/) | allow, ask or deny before each command, step and token limits, and ESC to stop it thinking, saying or acting | control flow | [slides](./production/06-guardrails/slides.pdf) · [md](./production/06-guardrails/slides.md) | 🎥 coming soon |
| 7 | [Observability](./production/07-observability/) | a trace of every step, its time, tokens and outcome, for the person running it | control flow | [slides](./production/07-observability/slides.pdf) · [md](./production/07-observability/slides.md) | 🎥 coming soon |
| 8 | [Resilience](./production/08-resilience/) | retries, a backup model, keeping what an interrupt cut short, and picking a crashed session back up from its episode | model interface, output | [slides](./production/08-resilience/slides.pdf) · [md](./production/08-resilience/slides.md) | 🎥 coming soon |
| 9 | [Performance](./production/09-performance/) | prompt caching, smaller requests, a faster model for summaries, commands run at the same time | context, model interface, output | [slides](./production/09-performance/slides.pdf) · [md](./production/09-performance/slides.md) | 🎥 coming soon |
| 10 | [Evaluation](./production/10-evaluation/) | tests that measure whether the agent does its job, and catch it getting worse | the whole harness | [slides](./production/10-evaluation/slides.pdf) · [md](./production/10-evaluation/slides.md) | 🎥 coming soon |

Every lesson shows its idea on its own first, in a small file, then quark's version of it, then the other things it could be. From Lesson 5 on, each layer also asks [Jev](./production/05-sandboxing/#asking-jev), a small model that makes decisions instead of writing text, one question about its job: what a command needs from the box, whether it only reads, whether a tool failed, whether a failure will pass, how big a request is, and whether the agent finished. It's a way to see where a second model fits in a harness, and what it can and can't be trusted with.

## Setup

Everything you need to run the lessons.

macOS or Linux · Python 3.13+ · [uv](https://docs.astral.sh/uv/) · an Anthropic API key. The production lessons (5–10) also need [Docker](https://docs.docker.com/get-docker/), and they ask [Jev](https://docs.typesafe.ai), a small decision model, so they use a TypeSafe key too; without one, quark decides the old way.

Put your key in a `.env` file at the root of the repo (it's gitignored), and tell uv to load it:

```bash
cp .env.example .env        # then add your keys to .env
export UV_ENV_FILE=.env
```

> [!WARNING]
> From Lesson 2 on, the agent runs shell commands the model writes, with no confirmation. Run it somewhere you can afford to lose.

**→ [Start with Lesson 1](./lessons/01-model-interface/)**

## The paper

**[*Agent = Harness(Model): Five Mechanistic Primitives of LLM Agent Harnesses*](./paper/agent-harness-primitives.md)** · [PDF](./paper/latex/main.pdf) · [supplement](./paper/decomposition-study.md)

The paper is the course's thesis, written up for people who want the argument rather than the lessons:

- **The claim:** an agent is a model wrapped in a harness, and every harness is made of five primitives. It builds the case the way Lessons 1–4 do: one primitive at a time, from a single API call to a working agent.
- **Production:** every production concern folds back into those five primitives instead of adding a sixth, as Lessons 5–10 show one layer at a time.
- **Beyond the course:**
  - **A test on real harnesses.** It takes apart three production coding agents, Claude Code, OpenAI Codex and opencode, part by part. Nothing in them needs a sixth primitive. The [supplement](./paper/decomposition-study.md) has the evidence for every assignment, with file and line or doc link.
  - **Rules for the hard cases,** such as where a tool call's effect lands, backup models versus routing, and who a file is for.
  - **A case study:** the ten runs in [quark at work](#quark-at-work), read through the primitives, failures included.

It's a preprint. [`paper/README.md`](./paper/README.md) lists the paper's files.

## quark at work

This is the proof. It's the `quark.py` you finish Lesson 4 with, nothing added, doing real work on this repo. These runs came just before quark started streaming, so their `quark.py` is 234 lines and prints each response once it's complete. Apart from that, and the decoding fix described under [Writing AGENTS.md](#writing-agentsmd), it's the same as today's 239 lines. In ten sessions, it:
- brought the four primitive lessons' slide decks into line with the lessons;
- turned all ten decks into PDFs;
- reviewed the paper;
- weighed in on the order of the production lessons;
- answered questions about what it had done.

Each session started with empty working memory. Anything it knew beyond the prompt came from its three memory stores: the facts it had written down, the skills it had saved, and the record of every earlier session. So most prompts were kept short on purpose, to make it use them.

| Run | What it was asked | Calls | Minutes | Memory it leaned on |
|---|---|---|---|---|
| 1 | Read the README and Lessons 1–4 the way a learner would, and remember what matters | 13 | 1.0 | none yet; wrote 32 facts |
| 2a | Bring Lesson 1's deck into line with the lesson, and keep the method | 22 | 4.1 | semantic; wrote a skill |
| 2b | "Now do the same for Lesson 2's slides." | 17 | 2.6 | procedural, semantic |
| 2c | "Now do the same for Lesson 3's slides." | 9 | 1.7 | procedural, semantic |
| 2d | "Now do the same for Lesson 4's slides." | 24 | 3.9 | procedural, semantic |
| 3 | Make a PDF of every deck, and check every slide fits | 37 | 5.6 | semantic; wrote a skill |
| 4 | Review the paper: true to the course, academic in tone | 63 | 5.6 | semantic |
| 5 | Recommend the order of the production lessons | 5 | 0.9 | semantic |
| 6a | "What have you done in this repo across your sessions?" | 4 | 0.4 | episodic, all three |
| 6b | "Which slides overflowed, and how did you find out?" | 6 | 0.4 | episodic, procedural |

"Calls" counts calls to the model. Its prompt asks for one bash command per response; seven of its 200 calls ran more than one.

### Learning the course

```bash
uv run lessons/04-context/quark.py "Read this repo the way a learner would: the top-level README.md first, then each primitive lesson in lessons/ in order, its README.md and every .py file. Skip .git, .venv, assets/, docs/, paper/, production/ and the slides for now. Learn the course well enough to teach each lesson and to check other material against it later, and keep what's worth keeping in your memory. Then tell me in a few sentences what the course is."
```

quark checked its memory, found it empty, then read in a learner's order: the README, then each lesson's README and code. It wrote 32 facts to semantic memory, one per line and filed under a subject, such as `- lesson 3 (control flow): what's missing is context: the agent knows nothing about where, when, who, or past sessions, and messages grows unbounded`. It also noticed something we'd missed: Lesson 4's README said the system prompt was 152 lines, and it counted about 148. It wrote that down too, and it mattered three sessions later.

### Bringing the slides in line

The decks for Lessons 1–4 had been made from an earlier version of the code. Run 2a got a full prompt:

```bash
uv run lessons/04-context/quark.py "Lesson 1's slide deck, lessons/01-model-interface/slides.md, was written from an earlier version of the course and is out of date. Bring it into line with the lesson as it is now: every claim, code excerpt, number and output on a slide must match the lesson's README.md and code exactly, in the same order as the lesson, one idea per slide, keeping the deck's Marp format. Check every slide, and tell me what you changed. I'll ask the same for the other three decks, so keep the method somewhere you can follow it next time."
```

It checked every old slide against the lesson. It found stale code, a wrong line count, and claims the lesson never makes. Then it rebuilt the deck in the README's order, pulling code into the slides by line range from the real files instead of retyping it. It wrote a checker script that flags any code line, number or sentence on a slide that isn't in the lesson. Then it saved the whole method, checker included, as a skill: `update-lesson-slide-deck`, *"bring a lesson's Marp slides.md … into line with its README.md and code"*. It named and described the skill for the class of task, not for Lesson 1.

Runs 2b, 2c and 2d each got one line: *"Now do the same for Lesson N's slides."* A new session has no idea what "the same" means. Each one found out the same way: the skill was in the index in its prompt, so its first command was to read it, along with its notes about the decks. Then it followed it. Runs 2b and 2d also made the skill better, each adding the pitfall it hit that time. In 2b, for example, copying a README range that ends on a closing code fence swallows the slides after it.

### Making the PDFs

```bash
uv run lessons/04-context/quark.py "Make a PDF of every slide deck in this repo, all ten, next to each slides.md, so people can open and present them straight from GitHub. Look at the PDFs to check every slide fits on its page, and fix any deck whose slides overflow without changing what they say."
```

quark can't see images, and Marp needs a browser it didn't know it had. It went looking, found Chromium where Playwright keeps it, and pointed Marp at it. "Look at the PDFs" it solved in three ways:
- It measured each slide in a headless browser.
- It read the position of every word on every PDF page with `pdftotext -bbox`.
- It counted dark pixels in the page margins.

It also proved its checker worked: it ran the checker on the PDFs from before its fixes and confirmed it caught the overflow. Five slides ran off the page, in the Lesson 2 and Lesson 4 decks. It fixed each by shrinking only the font, so no slide says anything different. It saved the method as a second skill, `render-marp-decks-to-pdf`, and added how to regenerate the PDFs to [`AGENTS.md`](./AGENTS.md).

### Reviewing the paper

```bash
uv run lessons/04-context/quark.py "Review the paper, paper/agent-harness-primitives.md, with its supplement. Check two things: that everything it says about the course is true of the course as it is now (code, line counts, runs, what the lessons and slides contain), and that it is written in an academic tone throughout, unlike the conversational lessons. Fix only what is wrong or not academic, without restructuring it, in the Markdown, which is the source of truth. Then rebuild the PDF and the arXiv bundle the way AGENTS.md describes."
```

The fact from run 1 came back. quark counted the prompt in `quark.py` again: lines 34 to 181, which is 148 lines, with 86 of code. The paper said 82 and 152, everywhere. We had the split wrong, and quark corrected it. It also found:
- Two production features the paper credited to a lesson's `quark.py` but which only exist in the fuller example files.
- A paragraph about the original slide decks that no longer described the current ones.
- A trace in an appendix shown as if it were complete.
- Two wrong cross-references in the supplement.

On tone, it found the paper already academic, apart from one heading and one contraction. It rebuilt the PDF and the arXiv bundle, compiled the bundle from the zip to check it, and listed what it couldn't verify for the author.

### Ordering the production lessons

At the time, the production lessons were in a different order (observability, guardrails, sandboxing, resilience, performance, evaluation), so the lesson numbers in quark's answer below follow that order. We asked for a recommendation, and gave it my view to argue with: sandboxing, guardrails, resilience, performance, evaluation, observability.

<details>
<summary>quark's recommendation</summary>

```text
My recommendation is to keep the current order: Observability, Guardrails, Sandboxing, Resilience, Performance, Evaluation. I partly disagree with Chase. I think his instinct about safety is sound, but his order costs more than it gains. I changed no files.

Where I agree with Chase
- The danger starts earlier than Lesson 5. From Lesson 2 the agent runs model-written shell commands with no confirmation, and Lesson 5 only watches.
- Sandboxing is the strongest control. The kernel enforces it however a command is spelled, while a guardrail only reads text.
- Evaluation then Observability has one natural link. Lesson 10 says an eval "tells you that something got worse, and doesn't say why: that's what Lesson 5's traces are for".

Why I'd still keep Observability first
1. It's the lowest-risk, smallest layer. It adds only trace() calls and changes no behaviour.
2. Later layers use it. Every later quark.py carries trace(). Lesson 8's retries "only show up when it reads the trace", Lesson 9's cache savings are visible only through Lesson 5's cache counts, and Lesson 10's quark.py reads .quark/traces.jsonl. Placing Observability last would make the eval lesson depend on a lesson not yet taught.
3. You can't judge a change you can't see.

Why Guardrails before Sandboxing
1. Lesson 6's gap motivates Lesson 7: the check reads text, and approval fatigue sets in.
2. Lesson 7's code keeps guard() running before the box.
3. Lesson 7 is the first lesson that needs Docker. Putting it first would force Docker onto the whole sequence.
4. Guardrails' step and token limits and the interrupt work without a container.

The case for Chase's order
If the goal is "safe to run unattended first", his order works. It would mean rewriting every quark.py from Lesson 5 on, and the "What's missing" links that chain 5→6→7→8→9→10. That's a lot of rework for a gain I think is small.

One cheap way to honour his worry without reordering: Lesson 5 could say in its opening that the agent can still run anything, and that Lesson 6 is the fix.
```

This is shortened; [the transcript](./docs/quark-at-work/run-5-order-the-production-lessons.txt) has it in full.

I went with neither order exactly: sandboxing, guardrails, observability, resilience, performance, evaluation. Safety comes first, as I'd proposed, and observability comes before the layers whose effects only a trace can show, as quark argued. Its other objection, the cost of rewriting every layer's `quark.py`, went away because they were being rebuilt on the current harness anyway.

</details>

### Remembering what happened

The last two sessions asked about the past and nothing else. For run 6a, *"What have you done in this repo across your sessions, in order, and what did you leave for the author to decide?"*, it read its facts and skill index, then listed every earlier episode by its first line, the input that opened it, and read how each one ended. It answered with all eight earlier sessions in order, each with its start time, and the open questions it had left for the author.

For run 6b, *"In the session where you made the PDFs, which slides overflowed, and how did you find out, given that you can't see images?"*, it went from its PDF skill to the episodes that mention Marp. Inside the right session it found the step where it had measured the original PDFs. It answered with the five slides, the exact point where each one ran off its 960×540 page, and the three ways it had checked, including the test that showed the checker could catch overflow at all.

### Writing AGENTS.md

Later, on today's 239-line `quark.py`, I gave quark one more job. I deleted [`AGENTS.md`](./AGENTS.md), the file that tells an agent how this repo works, emptied its memory, and asked it to read the whole repo and its history and write the file again: *"…everything an agent needs to work in this repo… It's for understanding the repo, not a to-do list. Change no other file."*

It crashed three times first. Each time, after a dozen to fifty commands of reading, it ran something like `grep … | cut -c1-140` on files full of `─`. `cut` counts bytes, so it split a three-byte character in half, and Lesson 4's `quark.py` couldn't decode the output and died. Adding a warning to the prompt didn't help: the third attempt got one and cut lines by bytes anyway. The fault was the harness's, not the model's. Upstream quark decodes with `errors="replace"`, so a stray byte becomes `�`, and the course now does the same from Lesson 2 on. With that fix, the fourth attempt, with the original prompt, read the README, every lesson, the paper and its build, the decks, the proof and the git history in 40 calls and about five minutes, and wrote the `AGENTS.md` that's in the repo now. It changed no other file.

It also found two mistakes of mine and only described them, as told: the `errors="replace"` change had leaked into the README listings of three fuller examples whose files don't have it, and the arXiv bundle hadn't been rebuilt. Both were real, and both are fixed. I fixed three of its lines by hand: the two bullets that described those mistakes, which were no longer true once they were fixed, and an evaluation timing it got wrong (it said about 25 seconds a case; the lesson shows five to seven).

The transcripts of all four attempts and its memory afterwards are in [`docs/quark-at-work/agents-md/`](./docs/quark-at-work/agents-md/).

### What we checked, and what we fixed by hand

We reviewed everything quark changed before it was merged.

**What held up.**
- **Slides:** every code line on the four rebuilt decks is a line from the lesson's own files, and every number on them is in the lesson.
- **Paper:** each of its corrections was right. We checked the line counts, and the guardrails and evaluation code, ourselves.
- **Safety:** it never printed or read the API key. We searched every transcript and memory file for it.
- **Production decks:** it left their text alone; it only added their PDFs.

**What we fixed by hand.**
- **The 86/148 split outside the paper.** quark only changed the paper, as asked, and pointed out that Lesson 4's README, its deck and `AGENTS.md` still said 82/152. We changed them.
- **Two unreadable slides.** Marp shrinks a code block until its longest line fits. On one Lesson 1 slide and one Lesson 4 slide, a single very long line of output shrank to a size no one could read. quark's check measured whether anything ran off the page, not whether it could be read, so it missed them. We showed one as a quote and shortened the other, saying so on the slide.
- A few slides elsewhere had code at about 6 points. The decks have since been rewritten, and none is that small now.

**Where its memory slipped.**
- **A fact it didn't replace.** After run 2d finished the last deck, its notes still said Lesson 4's deck was out of date. The prompt says to replace a fact when it changes, and it added new facts instead.
- **A note where a skill edit belonged.** It noticed in run 3 that a step in its slide skill was wrong (it said PDFs couldn't be made), and wrote that down as a fact instead of fixing the skill.
- **A wrong inference.** Run 2d said Lesson 1's deck "hasn't been touched". We had committed that deck mid-run, so `git status` didn't show it as changed, and quark read that as untouched.
- **A small misremembering.** Run 6a said the top-level README still had the old line count; it never did.

Memory is a summary, and a summary can be wrong in ways that read as confident. That's why the review step exists.

**Since these runs.** The decks quark rebuilt matched their lessons but weren't made to be presented: 50 to 110 slides each, many with a single sentence. They've since been rewritten for teaching to a room, shorter and with speaker notes, and the production lessons have been rebuilt in a new order. What's above is the work as quark did it; the transcripts are the record.

### The earlier version at work

Before episodic and procedural memory, a 48-line version of this harness did larger jobs on the repo. In four runs it wrote the first versions of the six production lessons and the first slide decks for all ten lessons, and failed instructively along the way: a response cut off mid-tool-request, and an agent that killed itself with `pkill -f`. The production lessons have since been rebuilt on the current harness, in a new order, but much of their explanation is still its writing. The transcripts, the failed attempts and its memory file are in [`docs/quark-at-work/earlier-version/`](./docs/quark-at-work/earlier-version/).

Everything quark printed in the runs above is in [`docs/quark-at-work/`](./docs/quark-at-work/), one file per run. Its memory stores as they stand after run 6b are in [`docs/quark-at-work/stores/`](./docs/quark-at-work/stores/): the facts, the two skills, and the ten episode files, which hold every message of every session exactly as quark saw it.

### How Claude Code and quark worked together

Two agents did this work, at different levels. [Claude Code](https://claude.com/claude-code) worked with me on the course: the README, the four primitive lessons, and every decision about how the course teaches. Then it operated quark, and quark did the work above. Claude Code also ran the paper's decomposition study under my direction, helped draft the paper, rebuilt the production lessons on the current harness, and rewrote the slide decks for presenting.

What Claude Code did:
- **Set up each run.** It started from empty memory stores and wrote the prompts. It ran Lesson 4's `quark.py` from the repo root with a shell command, the way a person would. quark got a task, its memory and a bash tool; nothing else.
- **Kept the key safe.** It moved `.env` out of the repo, so the key reached quark only through the environment, and searched every transcript and memory file for it before committing.
- **Reviewed before merging.** It checked every slide's code and numbers against the lessons, looked at the rendered pages, verified each change to the paper against the code, and made the hand fixes listed above.
- **Got in the way twice.** It committed quark's work while a session was still running, which is what confused run 2d. And while re-rendering a deck it ran `pkill -f marp-cli`, which matched its own shell command and killed it: the same mistake the earlier quark made, and the reason `AGENTS.md` says to stop processes by PID.

quark never saw Claude Code. From its side, someone gave it a task in a terminal, the same as anyone running it would.

## How to cite

If you use this course, its code or its framework, please cite the paper:

```bibtex
@misc{dovey2026agentharness,
  author       = {Chase Dovey},
  title        = {Agent = Harness(Model): Five Mechanistic Primitives of LLM Agent Harnesses},
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
