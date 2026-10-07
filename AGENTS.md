# AGENTS.md

Everything an agent needs to work in this repo: what it is, how it is laid out, the rules every change must keep, how to run and check each part, and what is easy to get wrong. It describes the repo as it is. Read it before touching anything; [`CLAUDE.md`](./CLAUDE.md) points here.

This file is for the people and agents who **build** the repo. The READMEs, lessons, slides, paper and `docs/` are for **readers** (learners, presenters, paper readers, people checking the proof). Keep creator information (conventions, build steps, decisions, caveats) here, and keep it out of the reader-facing files. Where a reader needs to know about a limit, say so in the reader's terms in their file.

## What this is

*harness-engineering* is a hands-on course in building agents by building their harness, by **Chase Dovey, Average Joes Lab**. The GitHub repo is `averagejoeslab/building-agents` (a rename to `harness-engineering` is planned; the old name is in the README, `CITATION.cff`, the paper, `paper/latex/build.py`'s `REPO`, and `paper/arxiv/METADATA.txt`). It began in May 2026 as an LLM-internals write-up (now `docs/the-model.md`) and became the course in October 2026.

Three parts, in the order a reader meets them (the top-level README says the same):

1. **The course.** An explanation of what a harness is made of, then ten lessons that build one: Lessons 1–4 are the four-step build of the five primitives (`lessons/`), Lessons 5–10 are six production layers (`production/`).
2. **The paper.** *Agent = Harness(Model): Five Mechanistic Primitives of LLM Agent Harnesses*, the course's thesis written up and tested against Claude Code, OpenAI Codex and opencode (`paper/`). A preprint; a conceptual framework with no experiments.
3. **quark at work.** The Lesson 4 harness doing real work on this repo across ten sessions, as proof (`docs/quark-at-work/`). It is the paper's case study.

It is not a Python package: no build system, two dependencies (`anthropic`, and `typesafe-sdk` for Jev in the production lessons), no tests. The "tests" are real runs, line-for-line listing checks and a deck checker (see "Checking").

**Who it's for.** Learners (people building a first agent), presenters (teaching a lesson to a room or on video), paper readers, people checking the quark-at-work proof, and citers. The agent the course teaches from is [quark](https://github.com/averagejoeslab/quark) (`averagejoeslab/quark`, upstream). Lessons 1–4 leave out some of upstream's hardening: the ESC interrupt arrives in Lesson 6, and keeping partial work, retries and a backup model in Lesson 8. [nanoagent](https://github.com/averagejoeslab/nanoagent) (TypeScript) is the second harness Lesson 4's ending suggests taking apart.

**Licenses.** Code (every `.py` file, and code shown in lessons) is MIT (`LICENSE`). Content (lesson text, slides, paper, docs, diagrams, videos) is CC BY-NC-SA 4.0 (`LICENSE-CONTENT`); commercial use needs permission (a book is planned). Credit Chase Dovey, Average Joes Lab, wherever there is a byline. `CITATION.cff` and the BibTeX in the README must agree.

## The thesis

- **TokensOut = Model(TokensIn)** and **Agent = Harness(Model)**. The model predicts; the harness does everything else. Model development is out of scope (`docs/the-model.md` is an optional deep dive).
- **Five mechanistic primitives:** control flow, which contains the other four (input, context, model interface, output). Each is defined by what it does *and* what it never does, so they are mutually exclusive. One pass: `person or world ─► input ─► context ─► request ─► model interface ─► response ─► output ─► person or world`, with a tool's result re-entering as input; control flow decides what happens at the end (go again, hand back, stop).
- **The method:** don't define, show the mechanism. Ask "what is it, and by what mechanistic primitives does it work?" until the answers stop being shared, then build back up, outward from the model. The deficiency at each step is exactly the next primitive: that is the argument and the lesson order.
- **Production layers add no sixth primitive.** Each of Lessons 5–10 is hardening that folds back into the primitives it is built on, and each lesson says which. Layers are not independent of each other (the paper's §6 says so), but each element has one home.
- **Where something goes** is decided by function, not location, using the paper's §3 definitions and §4 boundary rules: the tool channel (the call is output, its effect lands in the primitive it changes), backup vs routing (keyed to *failure* → model interface; keyed to *the work* → control flow), streaming (receiving is model interface, rendering is output), parallelism (several tool calls = output; several model calls = control flow), the reader of an artifact (for the model → context; for the operator → observability; for the user → output), the consumer of a person's answer, model-authored programs, bundles, nested agents. Use them when deciding where new code or text belongs; do not invent a sixth primitive.

## Layout

```
README.md                 entry point: thesis, lesson tables, setup, how to present, paper, quark at work, citation, license
AGENTS.md  CLAUDE.md      this file; CLAUDE.md just points here
CITATION.cff  LICENSE  LICENSE-CONTENT
pyproject.toml  .env.example  .gitignore  (uv.lock and .venv are present but gitignored)
lessons/01-model-interface/ 02-input-and-output/ 03-control-flow/ 04-context/
production/05-sandboxing/ 06-guardrails/ 07-observability/ 08-resilience/ 09-performance/ 10-evaluation/
    each: README.md (the lesson), <concept>.py (the idea on its own), jev_<concept>.py (production only: the same plus Jev), quark.py (the lineage), slides.md, slides.pdf
docs/the-model.md         optional deep dive on what's inside the model (illustrated by assets/*.svg)
docs/quark-at-work/       run-*.txt transcripts, stores/ (memory, skills, episodes), earlier-version/
paper/                    the paper (Markdown is source of truth), supplement, bib, latex/ build, arxiv/ upload bundle
tools/deckcheck.py        checks a deck against its lesson and its rendered PDF
```

| Path | For | What it is |
|---|---|---|
| `README.md` | readers | Entry point and the quark-at-work account. |
| `lessons/*/README.md`, `production/*/README.md` | learners | The lessons. First-person, conversational. |
| `*/quark.py` | learners | The lineage: each is the previous lesson's plus one primitive or layer. Run by readers, quoted in READMEs, slides and paper. |
| `*/<concept>.py` | learners | The concept on its own: a small standalone file named for the lesson's idea (`model_interface.py`, `input.py` and `output.py`, `control_flow.py`, `context.py`, `sandboxing.py`, `guardrails.py`, `observability.py`, `resilience.py`, `performance.py`, `evaluation.py`), shown before quark's implementation. In the production lessons the concept file has no Jev; `jev_<concept>.py` beside it is the same file plus only its Jev lines, so a diff of the two shows exactly what Jev adds. |
| `*/slides.md`, `*/slides.pdf` | presenters | A Marp deck to teach the lesson, and its PDF, openable straight from GitHub. |
| `docs/the-model.md`, `assets/` | learners | Optional model deep dive and its diagrams. |
| `docs/quark-at-work/` | proof checkers | Transcripts and stores of the ten runs; `earlier-version/` has four runs of an earlier 48-line harness. |
| `paper/agent-harness-primitives.md`, `paper/latex/main.pdf`, `paper/decomposition-study.md` | paper readers | The paper (Markdown and typeset) and the supplement with the evidence for §7. |
| `paper/references.bib`, `CITATION.cff` | citers | Citation data. |
| `paper/latex/*.tex`, `build.py`, `paper/arxiv/`, `paper/arxiv-source.zip` | creators | Build inputs and the arXiv upload. |
| `tools/deckcheck.py` | creators | Deck checker. |

The lessons' order: 1 model interface, 2 input and output (taught together: two ends of one exchange through tools), 3 control flow, 4 context; then 5 sandboxing, 6 guardrails, 7 observability, 8 resilience, 9 performance, 10 evaluation. Chase chose the production order: containment, then the gate, then a record of both, then recovery, cost, and finally measurement. It was reordered once (an earlier order had observability first); some historical files still show the old one (see "Easy to get wrong").

## Invariants every change must keep

### The lineage

- Each lesson's `quark.py` is the previous lesson's `quark.py` plus that lesson's primitive or layer, and **nothing else**. Lesson 5 starts from Lesson 4's. Check by diffing consecutive files (`diff lessons/04-context/quark.py production/05-sandboxing/quark.py`).
- A module's new code belongs to its primitive only, in the section named for it.
- Current sizes, quoted in many places (see "Numbers quoted everywhere"):

| File | Lines | Added |
|---|---|---|
| `lessons/01-model-interface/quark.py` | 12 | |
| `lessons/02-input-and-output/quark.py` | 38 | |
| `lessons/03-control-flow/quark.py` | 51 | |
| `lessons/04-context/quark.py` | 239 (91 of code, a 148-line system prompt) | |
| `production/05-sandboxing/quark.py` | 268 | +29 |
| `production/06-guardrails/quark.py` | 334 | +66 |
| `production/07-observability/quark.py` | 352 | +18 |
| `production/08-resilience/quark.py` | 395 | +43 |
| `production/09-performance/quark.py` | 420 | +25 |
| `production/10-evaluation/quark.py` | 469 | +49 |

- The 148 is the prompt's text inside `system()`'s f-string (file lines 41–188); the 91 is everything else.

### Code conventions (every `.py` file)

- **Section headings in `quark.py`**, in this order, kept from lesson to lesson, each padded with `─` to 78 characters: `# ── model interface ──`, `# ── output: the one tool ──`, `# ── context ──`, `# ── input ──`, `# ── control flow ──`. Lesson 10 adds `# ── evaluation: a harness around this one ──` between context and input, so `--eval` is caught before anything is read.
- **One model-interface function, `call(each=..., **request)`**, and everything calls the model through it (the main call and compaction's summary). It always streams (`client.messages.stream`); `each(event)` gets each piece. Lesson 1 introduces streaming; later lessons don't re-introduce it.
- **Generic names only.** What comes in is `input` (from a person *or* the world: the tool-results list is also `input`); what comes back is `output`. Never `task`, `user_input`, `reply`, `results` as identifiers. English in prompts and comments may still say "task". Where a concept file reads from a person with Python's `input()`, it binds `read = input` once after the imports so the name `input` stays free. 
- **`read(prompt)` is input from a person**: Enter on an empty line prints a fresh `> ` and sends nothing; EOF (Ctrl-D) returns `/q`; `/q` at the first prompt exits before any call. `chat = len(sys.argv) < 2`: input on the command line runs once to completion; none means chat.
- **`max_tokens=16384`** for the main call everywhere (room for thinking plus a tool request); compaction's summary uses 2048. **The model is `claude-sonnet-5-5`**; the backup in `MODELS` is `claude-opus-5-5`; the fast model for summaries is `claude-haiku-4-5`.
- **Command output decodes with `errors="replace"`** from Lesson 2 on (a command that printed half a UTF-8 character crashed the harness three times). Lesson 8 no longer adds it.
- Commands run through bash with stderr merged into stdout. A result that is empty reports `(exit N)`.

### Lesson 4's design (argued out; do not reverse without asking Chase)

- **Working memory** is the `working_memory` list of messages sent in full on every call.
- **Episodic memory** is written by the harness, never the model: one `.quark/episodes/<start>.jsonl` per session, one line per message, in exactly the shape of working memory. The model's output is written **before** any tool runs. The first line is always the opening input. The model only reads it.
- **Semantic memory** (`.quark/memory/memory.md`) has no code: the prompt gives exact commands. It is timeless (no timestamps; when a fact was learned is episodic), one fact per line as `- <subject>: <fact>`, **distilled** (the general truth, not a record of the moment), and a changed fact replaces the old line.
- **Procedural memory** is `.quark/skills/<name>.md` with `name`/`description` front matter, **generalized** (the method with placeholders, named for the class of task). `skills()` is harness code that puts the header index in the prompt on every call.
- **Every store in the prompt gets the same parts:** store, initialize, format, an exact write recipe with placeholders (quoted heredocs), what's worth writing, read moves, rules. Read moves are "moves, not a menu".
- **Recall ladder:** semantic → procedural → episodic, most distilled to most complete.
- **Compaction is lazy:** only after the API says "prompt is too long" (`BadRequestError`); no token counting, no `LIMIT`. `drop` counts up and `compact()` drops that many oldest turns and summarizes the rest; the summary points at the episode file, so nothing is lost. (Lesson 4's "Other things we could do" describes the alternatives in prose: counting tokens against a budget, cutting long results, one shared log, a first-line skill index. `context.py` is the concept file: working memory saved to `.quark/working_memory.json` and a dated system prompt.)
- **The full system prompt stays** (Self Model, Memory, World Model, Other Selves Model, Body Operations, Mechanics); Chase wanted the long version. It uses `cache_control` and carries the **date but not the time** so the cache can hit.
- **`mechanics()`** shows the model its own file with `system()` replaced by a one-line placeholder, using the regex `^def system\(\):.*?(?=^def )`. So `def system()` must stay directly followed by another top-level `def` (it is `compact`), and anything inside the f-string that is a literal brace must be doubled (`{{ }}`, as in the episode-format lines) or the file breaks. Any edit to `quark.py` changes the prompt the model sees, because the file is in it.

### The production layers' design

- **Sandboxing** (output): one container per run, started by `sandbox()` at the top of control flow; every command is `docker exec ... timeout -s KILL 30 sh -c`; an internal Docker network (a way out lent for one command, Lesson 5's Jev question), memory/CPU/PID limits, read-only root, all caps dropped, `--user` is the caller; the working folder is mounted **at the same path** so relative paths and Lesson 4's `.quark/` work through the box. The API key lives in the harness, outside. **No fallback to the host if Docker fails**: it exits. Exit 137 is reported as "killed: ran over N seconds or out of memory" (the two can't be told apart). The prompt is not changed to describe the box (though the model can read `sandbox()` in its own file through Lesson 4's `mechanics()`, so it may see the walls before walking into them).
- **Guardrails** (control flow, with input and one line in `call()`): `guard()` allows (only `SAFE` read-only programs, no `; & < > $` backtick, newline or `(`, every pipe stage checked), denies (`DENY` regex: sudo, recursive/forced rm, mkfs, git push, piped downloads, `.env`) or asks through Lesson 2's `read()` (blank Enter re-asks, Ctrl-D and `/q` are no; what the person typed goes back to the model). A refusal is a tool result with `is_error`. Limits `MAX_STEPS`/`MAX_TOKENS` are checked before each call, reset per person turn, and hand back in chat or end a one-shot run.
- **The interrupt** (Lesson 6, made immediate by streaming): ESC stops thinking, saying or acting. Ctrl-C has no code (it just kills the program); `/q` is the graceful exit. `watch()`/`listening()` live in `# ── input ──`; the keyboard is watched only around the model call and commands, never while `read()` waits, and not at all when stdin isn't a terminal (pipes, evaluation). After ESC the model gets `[other self interrupted what you were saying — acknowledge]` or `…doing…`; unrun commands get `[your doing never reached the world]`; a stopped command is killed with `kill -9 -1` **inside the box** (every command, never the box: its PID 1 can't be killed that way). Lesson 6 drops the partials; Lesson 8 keeps whole blocks (text that started, signed thinking, tool requests answered as never run) and a stopped command keeps what it printed. To demo ESC, drive a pseudo-terminal; a pipe can't send keys.
- **Observability** (control flow): `trace()` appends one JSON line to `.quark/traces.jsonl` carrying `ts`, `episode` (linking the operator's record to the model's) and the event. Events: `start` (with `resumed` from Lesson 8), `model`, `tool`, `refused`, `stopped`, `too_long`, `interrupted`, from Lesson 8 `model_failed`, and from Lesson 9 `routed`; tool records carry Jev's `failed` from Lesson 7. It only reads; it never changes what is sent or run.
- **Resilience** (model interface, output): the backup model lives in `call()`; the SDK does retries (`max_retries=3`, `timeout=300`); only transient failures (connection, timeout, 429, 5xx) move to the next model; everything else is raised, notably "prompt is too long", which compaction waits for. If all fail, `Down` ends the run with a message. **There is no save file:** `unfinished()` reads the newest episode back into working memory and continues in that same file; a tool request with no result gets "interrupted... may or may not have run" as an error result. A request cut off by `max_tokens`, or with no `cmd`, is never run.
- **Performance** (context, model interface, output): `cached()` marks the last message (on a copy); `trim()` keeps the first and last 10,000 characters of a result over `MAX_RESULT`; `call(models=FAST)` for compaction; `execute()` runs allowed commands in a thread pool after the guard has asked every question in order; results go back in request order with their ids; one ESC stops all. One prompt line changes (several commands may go in one response).
- **Evaluation** (outside the harness): `evaluate()` runs the real `quark.py` per case in a fresh temp folder with `y\n` x 50 on stdin (the guard's policy still blocks what it blocks), grades the leftover world with a shell `check`, reads steps and tokens from the child's trace, appends to `.quark/evals.jsonl` and flags `REGRESSED` when a case passed last time. Failed cases keep their folder. Exit status 1 if anything failed. A task that begins with `--eval` can't be given to quark.
- **Concept files** (Chase's decision: each lesson teaches the idea in isolation, then quark's implementation, then other things we could do, in words) don't follow the `quark.py` lineage: each is the smallest runnable code for its idea, 10–50 lines, and some don't call the main model at all. They use the same names (`input`, `output`, `read = input`). There are no other example files: what a primitive or layer could also be is prose, with no code and no runs. Their recorded runs stand, so don't change a concept file without re-running it and updating its README.
- **Jev in the production lessons** (Chase's decision: in each production `jev_<concept>.py` and in each production `quark.py`, never in a plain concept file; not in Lessons 1–4, which show only the primitives). Jev is TypeSafe's decision model (`typesafe-sdk`, key `TYPESAFE_API_KEY`, docs at docs.typesafe.ai, the paper's reference [26]): it writes no text; it answers typed questions (`Noul` yes/no, `Choice`, `Score`) with probabilities and a confidence. In `quark.py`, Lesson 5 adds `jev`, `SURE = 0.9` and `ask(state, question)` (the answer dict, or `None` with no key, an error or a timeout) in `# ── model interface ──`; each production lesson adds only its own question, and acts only on a confident answer:
  - 5 sandboxing: `NEEDS` (nothing / network / outside). The box sits on an internal Docker network; `lend()` asks the person when Jev is sure a command needs the network, and `bridge()` connects it for that one command.
  - 6 guardrails: `KIND` (read / write / delete / other) in `guard()`, after `DENY` and `SAFE`: a sure read runs without asking; otherwise the question shows Jev's answer. (`other` was added to Chase's read/write/delete because without it Jev called `curl` a read at 1.00.)
  - 7 observability: `FAILED`; every `tool` trace record carries `failed` beside `exit`, never instead of it.
  - 8 resilience: `FAILURE` (transient / permanent / partial); one more try for a sure transient failure of a command Jev is sure only reads; a partial one is flagged to the model.
  - 9 performance: `SIZE` (lookup / edit / work) and `route()` pick the model list per person turn (traced as `routed`; below 0.7 the usual tier); a command lent the network runs on its own, outside the pool.
  - 10 evaluation: `judges()`: Jev and the main model (through `call()`) each say whether the agent completed the task, from the files before and after; printed beside the shell check, flagged when they disagree; the check alone grades. Jev misses counting, as its docs warn.
  Every Jev call falls back to the old behavior on any failure (ask the person, no flag, no retry, the usual model, no verdict); quark runs without the key. Never fail open. The call is a model-interface act; acting on the answer belongs to the layer's own primitive, and each README says which. Lesson 5's `### Asking Jev` introduces Jev for the course; later lessons link back to `../05-sandboxing/#asking-jev`. Known weak spots (its docs' "jaggedness" page): literal reading, counting and arithmetic, indirection, irrelevant detail, adversarial text in the state.

## Documentation conventions

### Lesson READMEs

- Same layout: a `> 🎥 **Video:** coming soon` placeholder; an opening explanation with no heading; `## The concept` (the concept file, what it shows, its run); in Lessons 5–10, `## The concept with Jev` (`jev_<concept>.py`: the Jev lines it adds, what Jev is asked and what the code does with the answer, a run where Jev's decision matters and one without a key; Lesson 5 keeps `### Asking Jev` here); `## quark's implementation` (the lines `quark.py` adds and why, with `### Run it` for its runs; Lesson 6 adds `### The interrupt`); `## Other things we could do` (prose only: what else the primitive or layer can be, a product that is it alone, other designs); `## What to take away`: **The rule**, then "Notice what X never does." (lowercase) naming the other primitives, then **What's missing**, which motivates the next lesson, then `**→ [Lesson N: ...](../NN-name/)**`. Lesson 2 uses `## Input`, `## Output` (its two concept files) and `## Together` (quark.py) in place of the first two. Lesson 4 ends differently, by design: no "What's missing", a closing "You've built a harness" section that sends the reader to take apart another harness, then on to Lesson 5. Lesson 10 ends with a link back to the course README.
- Production lessons say what they are **built on** and that they add hardening, not a new primitive, and what the lesson never does to the other primitives.
- Lesson 4's README shows the system prompt as `...` in the listing (`def system():  # instructions: the prompt is shown in full below` and `"""..."""`) and in full in a `<details>` block. That is the only sanctioned difference between a README listing and its file.

### Voice

- **The README, lessons, slides:** conversational, first person from Chase where a person speaks, plain words, short sentences. Show, then name.
- **The paper:** academic. No "you", no jokes, claims scoped to what's shown. Don't let one voice leak into the other when moving material.
- The README's quark-at-work section is written in the author's "we"/"I" and reports failures plainly; keep it that way.

### Real output only

- Every output shown in a lesson, the README or the paper comes from a real run of that exact code. Never invent, edit or "tidy" it. You may shorten it, but say so ("shortened", "abridged").
- Real output is history: if it mentions something since changed (an old line count, a "coming soon", a directory listing with files that no longer exist), leave it. Where a recorded run is on an older tree, the lesson says so.
- **Code listings in READMEs match their files line for line** (except as above). If a `.py` changes, every README, slide and paper listing of it changes, and demos that depend on it are re-run.
- Demos that touch memory start from empty `.quark/` so the output matches the story the README tells.

### Numbers quoted everywhere

If a `quark.py` changes length, update every quote and re-run the demos that print it:
- the lesson's README (the intro to `## quark's implementation`, and demo output such as Lesson 3's `wc -l` listing and Lesson 9's mention of 239);
- the top-level README ("today's 239 lines" etc.);
- the paper: abstract, §5 headings and §5.5 table, §6 table (net lines), conclusion, Appendix A headings, Appendix C headings, and `paper/latex/*.tex`, `paper/arxiv/*`, `METADATA.txt`;
- the decks.

**The 234-line version is a historical artifact, not a stale number.** The ten quark-at-work runs used the 234-line harness (86 of code, 148 of prompt) from before streaming; the README's quark-at-work section, paper §8 and Appendix D, the transcripts and the stores correctly say 234 and 86. Don't "fix" them.

### Slides

- **Purpose:** a presenter teaches the lesson to a room. The fewest slides that carry the ideas (10 decks, 18–25 slides each now); the README is the full text, the deck isn't.
- **Shape:** the lesson's own order. Title; the problem; the idea and what it's built on; the mechanism; the code this lesson adds; the concept file and one run; in production lessons, the Jev lines and one run; quark's code and one or two telling runs; other things we could do, in words; the rule, what it never does, what's missing, next.
- **Rules:** Marp (`marp: true`, `theme: default`, `paginate: true`, header `"Lesson N · Title"`, a `title` class on the first slide); one `#` heading per slide; at most 5 bullets; a speaker note in an HTML comment on most slides; code copied exactly from the source (a line shortened to fit goes on a slide that says "(abridged)"); run output exact, cut only with "(shortened)"; never shrink text below 0.8em with `<style scoped>`; nothing on a slide that isn't in the lesson.
- The first four decks were originally rebuilt by quark (50–110 slides, one idea each) and have since been rewritten for presenting. Slide links in the README point at the PDFs.

### The paper

- `paper/agent-harness-primitives.md` is the source of truth. `paper/latex/abstract.tex`, `body.tex` and `appendix.tex` are generated from it; `main.tex`, `fig-path.tex`, `fig-tree.tex` and `build.py` are hand-written.
- **Framing:** a conceptual framework in the manner of CoALA, no experiments; a follow-up would measure which primitive drives performance (§9.5). Don't add measurements.
- **References:** only ones the paper uses, each cited for something specific. Numbers in the text map to BibTeX keys in `KEYS` in `build.py`; adding or reordering a reference means updating it (and `references.bib`).
- **The AI-use disclosure** separates three roles: object of study (quark), research instrument (Claude Code for the decomposition study), writing tool (Claude Code). Keep it precise when the work changes. No AI system is an author.
- **External claims are partly unverified:** the venue of reference [4] (Zhang et al.), the product URLs in §7.5 (found by search), and the file:line evidence for Codex and opencode against pinned commits (spot-check). Claude Code was analyzed from documentation only. Don't strengthen these claims without checking.

### Disclosure of what quark did

The README's "What we checked, and what we fixed by hand" lists every change made by hand to what quark produced (the 86/148 split outside the paper, two unreadable slides) and where its memory slipped. Keep it current if you change more of quark's work.

## Running, checking and building

### Setup and running the course

- macOS or Linux, Python 3.13+, [uv](https://docs.astral.sh/uv/), an Anthropic API key. `cp .env.example .env`, add the key, `export UV_ENV_FILE=.env`. `TYPESAFE_API_KEY` is for Jev in Lessons 5–10; quark falls back without it. **Never commit `.env` or a key.** Before letting an agent read "every file", move `.env` out of the repo and pass the key through the environment; search transcripts and outputs for `sk-ant` and `apikey_` (TypeSafe's key prefix) before committing (the only matches in the tree are the word itself and `sk-ant-...`).
- **Lessons 1–4:** from the repo root, `uv run lessons/NN-name/quark.py "<input>"` (or no input for a chat; `/q` or Ctrl-D quits). Same for the concept files. Each call is a real API call that costs money.
- **Lessons 5–10 need Docker running** (the first run pulls `python:3.13-slim`) and run in a **scratch folder, not in this repo**, because the box mounts the current folder and quark writes `.quark/` there: `cd /tmp/demo && uv run --project /path/to/building-agents /path/to/building-agents/production/NN-name/quark.py "<input>"`. Evaluation: `quark.py --eval [case ...]` (four cases, about six to nine seconds each, judges included, real model calls; results go to `.quark/evals.jsonl` in the folder you ran in). Each lesson's README says where to run its concept file.
- **quark runs model-written shell commands with no confirmation** from Lesson 2 on, directly on your machine until Lesson 5 puts them in a box; Lesson 6's guard then asks before anything not known to be safe. Run the early lessons somewhere disposable. `.quark/` is gitignored demo state; clear it before a sequence of memory demos. This working copy's own `.quark/` is the state of whichever agent is working in it: don't commit it and don't assume it is empty.
- **Stop processes by PID, never `pkill -f` / `killall` with a pattern** that can match lesson paths or your own command line: quark killed itself that way, and so did the agent operating it. Containers left by a killed harness (`atexit` can't run after `kill -9`) need `docker rm -f`.

### Checking

- **Lineage:** diff consecutive `quark.py` files; each diff should be exactly what that lesson's README says it adds.
- **README listings against files** (prints, per README, the best-matching file and up to three lines it doesn't contain; expected output is only Lesson 4's two `system()` lines and `resilience.py`'s `flaky.py` stand-in, which has no file):
  ```bash
  python3 - <<'PY'
  import re, glob, os
  for r in sorted(glob.glob("lessons/*/README.md") + glob.glob("production/*/README.md")):
      files = {f: open(f).read().splitlines() for f in glob.glob(os.path.dirname(r) + "/*.py")}
      for b in re.findall(r"```python\n(.*?)```", open(r).read(), re.S):
          lines = b.rstrip("\n").splitlines()
          best = max(files, key=lambda f: sum(l in files[f] for l in lines))
          print(r, os.path.basename(best), [l for l in lines if l not in files[best]][:3])
  PY
  ```
- **A deck:** `python3 tools/deckcheck.py <dir>` (e.g. `lessons/01-model-interface`, `production/05-sandboxing`) checks `slides.md` against the lesson's README and `.py` files and `slides.pdf` for layout: one `#` heading per slide, code lines not in the source, numbers not in the lesson, text off the page, text under 9pt, PDF page count equal to slide count, and PDF older than `slides.md` (by mtime, so a fresh checkout or a touch can trip it). Needs `pdftotext`. All ten decks currently report `problems: 0`. Marp shrinks a code block until its longest line fits, so a long line becomes unreadable without leaving the page (the 9pt check catches it), and text pushed past the bottom edge can be clipped out of the PDF so no check sees it: **always look at the rendered pages**.
- **The paper:** read the diff of every number against the code; the build must complete (below).

### Building

- **A deck's PDF** (after any `slides.md` change, then run the checker):
  ```bash
  export CHROME_PATH=$(ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome | head -1)   # or any Chrome
  npx @marp-team/marp-cli --no-stdin <dir>/slides.md --pdf -o <dir>/slides.pdf --allow-local-files < /dev/null
  python3 tools/deckcheck.py <dir>
  ```
  Present from Markdown with `npx @marp-team/marp-cli -p <dir>/slides.md`. Fix overflow with a `<style scoped>` block on that slide (smaller table/code font, never below 0.8em), never by changing what the slide says.
- **The paper's PDF** (Markdown → LaTeX → `paper/latex/main.pdf`): needs pandoc 3.x and TeX Live (`pdflatex`, `bibtex`, tikz, pifont, listings, booktabs; Debian: `texlive-latex-recommended texlive-latex-extra texlive-pictures`). pandoc is not installed in every environment (`pip install pypandoc-binary` gives a binary). Then `python3 paper/latex/build.py /path/to/pandoc`. `build.py` splits out code (fenced and inline) first so citations, rules and `%` inside code are untouched, converts the prose, strips TeX comments everywhere except listings, then runs pdflatex, bibtex, pdflatex, pdflatex. `main.tex` maps the non-ASCII characters used in listings (→ ← ▲ ┘ © …) with `literate`; add a mapping if new code uses another. `.aux/.log/.out/.blg` are gitignored; `main.bbl` and `main.pdf` are tracked.
- **The arXiv bundle** (`paper/arxiv/`, `paper/arxiv-source.zip`; flat, self-contained, arXiv doesn't run BibTeX):
  1. Rebuild the paper.
  2. Copy `paper/latex/*.tex` and `references.bib` into `paper/arxiv/`.
  3. Set `\bibliography{references}` in `arxiv/main.tex` (the `latex/` copy uses `../references`; that line is the only intended difference in `main.tex`).
  4. Run pdflatex/bibtex there to regenerate `main.bbl`.
  5. Check `\pdfoutput=1` is the first line and there are no TeX comments.
  6. Re-zip. `paper/arxiv/METADATA.txt` holds the submission form fields (abstract under 1,920 characters, currently 1,713; comments with the page count, currently 40); update it when the abstract or page count changes. Submission is in progress.

## The proof: quark at work

- `docs/quark-at-work/` holds the ten current runs of the (234-line) Lesson 4 `quark.py`: `run-1` … `run-6b` transcripts, and `stores/` (`memory/memory.md`, `skills/`, `episodes/`): quark's memory after the last run. It is `stores/`, not `.quark/`, because `.gitignore` ignores every `.quark/`. `earlier-version/` holds four runs of an earlier 48-line harness that wrote the first versions of the production lessons and decks, with its failures (a response cut off mid-tool-request; an agent that killed itself with `pkill -f`).
- **They are evidence: never edit a transcript or a store.**
- The paper's §8 and Appendix D describe the ten current runs; keep them consistent with the transcripts and stores.
- **To produce new proof:** start from empty stores (move the repo's `.quark/` aside), move `.env` out of the repo, run `PYTHONUNBUFFERED=1 uv run lessons/04-context/quark.py "<prompt>" < /dev/null` from the repo root and save stdout. Keep prompts short where the point is to show memory at work. **Don't commit while a session is running**: quark reads `git status`, and a mid-run commit misled it once. Tell it not to print or save environment variables.

## Easy to get wrong

- **Changing `lessons/04-context/quark.py` or any later `quark.py` ripples.** Every later file embeds the earlier one; every line count, listing, deck, demo, the paper's appendices and the arXiv bundle quote it; and because `mechanics()` puts the file into the model's prompt, even a comment changes behavior and the cached prompt. Change the earliest file that needs it, then re-derive everything downstream by diffing.
- **Don't add to a lesson what belongs to another.** A feature that looks convenient (a step limit in Lesson 3, telling the model about the box in Lesson 5, a save file in Lesson 8) is usually a deliberate omission: the README's "What's missing" is the next lesson's reason to exist. Check the lesson's "Notice what X never does".
- **Don't "fix" real output or history.** Old directory listings, the 234-line runs, quark's 3,335-line count in Lesson 4, "coming soon" in a recorded run, `AGENTS.md` appearing in a recorded `ls` are all correct as records. Re-run instead of editing.
- **Voice leaks.** Moving a sentence from a lesson into the paper (or back) without changing register.
- **A listing and its file drift apart.** Some lines are shared word for word by a `quark.py` and a concept file (the `subprocess.run` line, for one), so a search-and-replace across READMEs can change the wrong listing. Run the listing check above after any README or `.py` edit.
- **The arXiv bundle lags the paper** unless you re-sync it: `paper/arxiv/*.tex` and the zip are copies. Rebuild and re-sync the bundle whenever the paper changes, and re-check METADATA's page count.
- **Regenerated artifacts are tracked.** `slides.pdf` (10), `paper/latex/*.tex`, `main.pdf`, `main.bbl`, `arxiv/` and the zip are committed and must be regenerated after their sources change, in the same change.
- **Run location.** Lessons 5–10 must be run from a scratch folder (the box mounts the cwd and writes `.quark/` and traces there). Running one from the repo root mounts the whole repo read-write into the container and drops state into this repo's `.quark/`. Lesson 10's `--eval` logs into the cwd too.
- **Docker and the API are real dependencies.** No lesson from 5 on works without Docker; nothing works without a key; every demo costs money. If Docker fails to start the box, quark exits on purpose.
- **ESC cannot be tested through a pipe;** the watcher is off when stdin isn't a terminal. Use a pseudo-terminal. And ESC stops the `docker exec` side, not the box: killing the box would leave the next command nowhere to run.
- **Sandboxing is not the guard.** The box limits what a command can reach; the guard decides whether it runs; neither makes the model behave. A regex check can be spelled around, which is why the box comes first in the order. Don't describe either as more than it is.
- **The meaning of `stop_reason`.** A streamed response stopped by ESC has `stop_reason` of `None` (the harness uses that to detect an interrupt). A cut-off tool request has no `cmd`. Thinking blocks need their `signature` to be sent back; unsigned thinking is dropped.
- **Tool results must all be answered, in order, with their ids**, including refusals, cut-offs, interrupts and never-started commands; the API rejects a request with a tool request that has no result.
- **Cache keys.** Putting a timestamp (or anything that changes per call) early in the system prompt makes every call a cache miss. The date is in; the time is out on purpose. A cache belongs to one model, so switching models restarts it.
- **Memory maintenance is quark's weak spot** (the quark-at-work account says so): it appended a fact instead of replacing one, and wrote a skill correction as a fact. If you work as quark in this repo, replace changed facts and fix skills in place.
- **git state can mislead.** A deck committed mid-session no longer shows in `git status`; don't read "not modified" as "not touched". Compare against `git show <rev>:<path>`.
- **Marp and PDFs.** A deck that "passes" the checker can still have a slide at 4pt or a clipped bottom edge; open the PDF. The checker needs PDF mtime ≥ `slides.md` mtime.
- **Don't invent a sixth primitive or a seventh layer** to make a hard case fit; use the paper's boundary rules, and if a case genuinely fits none of the five, that is a finding to take to Chase (the lessons say so to readers too).
