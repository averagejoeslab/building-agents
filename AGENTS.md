# AGENTS.md

This file is for the people and agents who **build** this repo. Everything a **reader** needs lives in the READMEs, the lessons, the slides, the paper and `docs/`. Keep it that way:

- **Reader information** goes in the reader-facing files: what to learn, how to run it, how to present it, what the paper argues, what quark did. Anyone working through the course, reading the paper, teaching from the slides or checking the proof should never need this file.
- **Creator information** goes here: conventions, invariants, how to build and check things, decisions already made, and work still to do. Don't put to-dos, build steps or "still to do" notes in reader-facing files. Where a reader needs to know about a gap (for example, slides that show an older version of the code), say so in the reader's terms and keep the to-do here.

## The project

- **What it is:** *harness-engineering*, a hands-on course on building agents by building their harness. The GitHub repo is `averagejoeslab/building-agents`; it will be renamed to `harness-engineering`.
- **Author and credit:** Chase Dovey, Average Joes Lab. Credit him by name in anything that carries a byline.
- **Licenses:** code (every `.py` file, and code shown in the lessons) is MIT ([`LICENSE`](./LICENSE)). Content (lesson text, slides, paper, docs, diagrams, videos) is CC BY-NC-SA 4.0 ([`LICENSE-CONTENT`](./LICENSE-CONTENT)). Commercial use, such as a book or paid course, needs permission. A book is planned.
- **Citation:** [`CITATION.cff`](./CITATION.cff) and the BibTeX in the README must agree.
- **Example agent:** quark ([averagejoeslab/quark](https://github.com/averagejoeslab/quark)) is the upstream agent the course teaches from. The course version leaves out quark's hardening (ESC interrupt, retrying the summary on network failure), and Lesson 4 says so.
- **Second harness for readers:** [averagejoeslab/nanoagent](https://github.com/averagejoeslab/nanoagent), a small TypeScript agent that Lesson 4's ending suggests as the first harness to take apart.

## The thesis

- **TokensOut = Model(TokensIn)** and **Agent = Harness(Model)**.
- **Five mechanistic primitives:** control flow, with input, context, model interface and output inside it. Each is defined by what it does *and* what it never does, so they're mutually exclusive. The paper's §3 has the definitions and §4 the boundary rules (place by function, the tool channel, backup vs routing by trigger, who reads it, who uses an answer, model-written programs, bundles, nesting). Use them when deciding where anything goes.
- **The method:** don't define, show the mechanism. Ask "what is it, and by what mechanistic primitives does it work?" until the answers stop being shared, then build back up.
- **Production layers add no sixth primitive.** Lessons 5–10 harden the harness; each folds back into the primitives it's built on.

## Voice

- **The repo, the lessons and the book:** conversational, first person from Chase, plain words, short sentences. Show, then name.
- **The paper:** academic. No "you", no jokes, claims scoped to what's shown.
- Don't let one voice leak into the other when moving material between them.

## The course: invariants

**Order and structure.**
- Lessons 1–4 are the primitives, built outward from the model: 1 model interface, 2 input and output, 3 control flow, 4 context. Lessons 5–10 are the production layers in `production/`, in this order (Chase's decision): 5 sandboxing, 6 guardrails, 7 observability, 8 resilience, 9 performance, 10 evaluation. Containment first, then the gate, then the record of both, then recovery, cost, and measurement.
- Lesson 5's `quark.py` starts from Lesson 4's `quark.py`; each later one is the previous plus its layer.
- Each lesson's `quark.py` is the previous lesson's `quark.py` plus that lesson's primitive (or layer) and nothing else. Diff consecutive files to check.
- Each module isolates its primitive: a module's new code belongs to its primitive only.
- Every lesson README has the same layout:
  - a video placeholder;
  - an opening explanation with no heading;
  - `## The worked example` (Lesson 2 uses `## Input`, `## Output`, `## Together`);
  - `## Run it`;
  - `## Going further`: what else the primitive can be, a product that is that primitive alone, then the fuller example file and its run;
  - `## What to take away`: **The rule**, then "Notice what X never does." naming the other primitives, then **What's missing**, which motivates the next lesson, then a link to the next lesson.

**Code conventions in `quark.py`.**
- Section headings, kept from lesson to lesson: `# ── model interface ──`, `# ── output: the one tool ──`, `# ── context ──`, `# ── input ──`, `# ── control flow ──`. Each is padded with `─` to 78 characters.
- One model-interface function, `call(**request)`. Everything calls the model through it.
- **Generic names only.** What comes in is `input` (from a person or from the world: the tool results list is also `input`). What comes back is `output`. Never `task`, `user_input`, `reply`, `results` in the `quark.py` files. Input isn't assumed to be a task.
- `read(prompt)` is input from a person:
  - Enter on an empty line prints a fresh `> ` and sends nothing;
  - EOF (Ctrl-D) returns `/q`;
  - `/q` at the first prompt exits before any call.
- `chat = len(sys.argv) < 2`: input on the command line runs once to completion; none means chat.
- `max_tokens=16384` everywhere, so a response with thinking has room to finish a tool request.
- The model is `claude-sonnet-5-5`.

**Lesson 4's design decisions.** These were argued out; don't reverse them without asking Chase.
- **Four memories:**
  - **Working memory** is the messages in context.
  - **Episodic** is written by the harness, never the model. It's one `.quark/episodes/<start>.jsonl` per session, one line per message, in exactly the structure of working memory. The model's output is written *before* tools run. The first line is always the opening input.
  - **Semantic** is timeless: no timestamps (when a fact was learned is episodic). It's one fact per line, `- <subject>: <fact>`. Facts are *distilled*: the general truth, not a record of the moment. A changed fact replaces the old line.
  - **Procedural** is skills in `.quark/skills/<name>.md` with `name`/`description` front matter. Skills are *generalized*: the method with placeholders, named for the class of task. `skills()` puts the index in the prompt every call.
- **Every store in the prompt gets the same parts:** store, initialize, format, an exact write recipe with placeholders (quoted heredocs), what's worth writing, read moves, rules. The read moves are "moves, not a menu."
- **Recall ladder:** semantic → procedural → episodic, most distilled to most complete. Episodic is at the bottom.
- **Compaction is lazy:** only after the API says "prompt is too long". There's no token counting and no `LIMIT` in quark. The summary points to the episode file. `context.py` exists to show the alternatives (`fit()` counting tokens against `LIMIT`, `trim()`, one shared episode log, first-line skill index).
- **The full system prompt stays:** Self Model, Memory, World Model, Other Selves Model, Body Operations (with Acts/Observes), Mechanics. Chase wanted the long versions kept.
- `mechanics()` shows the model its own file with `system()` redacted.

**The production layers' design decisions.**
- **Sandboxing:** one container per run, started at the top of control flow; the working folder is mounted at the same path, so Lesson 4's `.quark/` memories work through the box. No fallback to the host if Docker fails.
- **Guardrails:** `guard()` asks through Lesson 2's `read()` (so a blank Enter re-asks, Ctrl-D is no). Limits are per person-turn.
- **Observability:** each trace record carries `episode`, linking the operator's record (trace) to the model's (episode). Records start, model, tool, refused, stopped, too_long, and (from Lesson 8) model_failed.
- **Resilience:** the backup model lives in Lesson 1's `call()`. There is no save file: `unfinished()` reads the newest episode back into working memory and continues in that same file. Unanswered tool requests get the "may or may not have run" result. Listed as built on model interface and output; the read-back is context's record, and the paper says so (§6).
- **Performance:** `call(models=..., live=...)` streams; text is printed live, so the loop no longer prints text blocks. One prompt line changes (parallel commands). Compaction uses `FAST`.
- **Evaluation:** its section sits before `# ── input ──` so `--eval` is caught before anything is read. Cases run the real file in a temp folder, with `y` answered fifty times.

**Fuller examples** (`model_interface.py`, `input_output.py`, `control_flow.py`, `workflow.py`, `context.py`) are standalone files showing what else a primitive can be. They don't follow the `quark.py` lineage and still use names like `task` and `reply`. Whether to rename them to `input`/`output` is an open decision for Chase.

## Real output only

- Every output shown in a lesson, the README or the paper comes from a real run of that exact code. Never invent, edit or "tidy" output. You may shorten it, but say so (for example, a shortened `signature`).
- Real output is history: if it mentions something since changed (such as Lesson 9's run saying production lessons are "coming soon"), leave it.
- Code listings in READMEs must match their files line for line. The only exception is Lesson 4's system prompt, shown as `...` in the listing and in full in a `<details>` block. Quick check:
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
- **Line counts are quoted in many places:** 9, 33, 46 and 234 lines (86 of code, 148 of prompt), and the 1,949 total in Lesson 4's demo. Production `quark.py`: 244, 267, 279, 308, 332, 370 (net +10, +23, +12, +29, +24, +38), quoted in each production README and in the paper's §6 table and Appendix C.
  - They appear in the lesson READMEs (including demo output) and the top-level README.
  - In the paper: the abstract, §5 headings, §5.5, §6, the conclusion, Appendix A/B, and `paper/arxiv/METADATA.txt`.
  - If a `quark.py` changes length, re-run the demos and update every one of them.

## Running the code

- **Setup:** uv, Python 3.13+, `cp .env.example .env`, add the key, `export UV_ENV_FILE=.env`. Run everything from the repo root: `uv run lessons/NN-name/file.py`.
- **Never commit `.env` or a key.**
  - Before letting an agent read "every file", move `.env` out of the repo and pass the key through the environment.
  - Search every transcript and output for `sk-ant` before committing.
- `.quark/` is gitignored: it's demo state. Clear it before re-running a sequence of memory demos so the output matches the story the README tells.
- **quark runs model-written shell commands with no confirmation.**
  - Run it somewhere disposable.
  - Stop processes by PID, never `pkill -f`/`killall` with a pattern that matches lesson paths: quark killed itself that way, and so did the agent operating it.

## The proof: quark at work

- [`docs/quark-at-work/`](./docs/quark-at-work/) holds the current proof: the terminal transcript of each of the ten runs of the 234-line Lesson 4 `quark.py` (`run-*.txt`), and its memory stores after the last run (`stores/`: `memory/memory.md`, `skills/`, `episodes/`). The folder is `stores/`, not `.quark/`, because `.gitignore` ignores every `.quark/`.
- The paper's §8 (case study) and Appendix D are about the ten current runs; keep them consistent with the transcripts and stores.
- [`docs/quark-at-work/earlier-version/`](./docs/quark-at-work/earlier-version/) holds the four runs of the earlier 48-line harness that wrote the first versions of the production lessons and slide decks. The README mentions them briefly; the paper no longer does.
- **Running quark for new proof:**
  - Start from empty stores: move the repo's `.quark/` aside.
  - Move `.env` out of the repo.
  - Run `uv run lessons/04-context/quark.py "<prompt>" < /dev/null` from the repo root with `PYTHONUNBUFFERED=1`, and save stdout.
  - Keep prompts short where the point is to show memory at work.
  - Don't commit while a session is running: quark reads `git status`, and a commit mid-run misled it once.
- **They're evidence:**
  - Never edit a transcript or a store.
  - Anything changed by hand afterwards in what quark made is disclosed in the README's quark-at-work section ("What we checked, and what we fixed by hand"). Keep that disclosure current if you change more.

## The paper

- [`paper/agent-harness-primitives.md`](./paper/agent-harness-primitives.md) is the source of truth.
  - The LaTeX in `paper/latex/` (`abstract.tex`, `body.tex`, `appendix.tex`) is generated from it.
  - `main.tex`, `fig-*.tex` and `build.py` are written by hand.
- **Framing:** a conceptual framework in the manner of CoALA, with no experiments. A follow-up paper will measure which primitive drives performance differences (the paper's §9.5 future work). Don't add measurements to this one.
- **References:** only the ones the paper actually uses. Each is cited for something specific:
  - the closest prior framework (CoALA);
  - a name to tell apart (*Agent Primitives*);
  - the workflow/agent line (Schluntz and Zhang);
  - the premise and the disclosure schema (Zhang et al.);
  - an independent decomposition (Fan et al.);
  - the source for each product claim;
  - the three harnesses studied.
  
  Citation numbers map to BibTeX keys in `KEYS` in `build.py`; adding or reordering a reference means updating it.
- **The AI-use disclosure** separates three roles: object of study, research instrument, writing tool. Keep it precise when the work changes.
- **Build:**
  ```bash
  pip install pypandoc-binary          # a pandoc 3.x binary; or install pandoc
  apt-get install texlive-latex-recommended texlive-latex-extra texlive-pictures
  python3 paper/latex/build.py /path/to/pandoc
  ```
  - `build.py` converts the Markdown with pandoc, then post-processes only the prose. It splits out code (fenced blocks and inline code) first, so citations, rules and `%` comments inside code are left alone.
  - It strips TeX comments everywhere except listings, then runs pdflatex, bibtex, pdflatex, pdflatex.
  - `main.tex` maps the non-ASCII characters used in listings (→ ← ▲ ┘ © and others) with `literate`; add a mapping if new code uses another one.
- **arXiv bundle** (`paper/arxiv/`, `paper/arxiv-source.zip`):
  1. After changing the paper, rebuild.
  2. Copy `latex/*.tex` and `references.bib` into `arxiv/`.
  3. Set `\bibliography{references}` there (the repo copy uses `../references`).
  4. Run pdflatex/bibtex in `arxiv/` to regenerate `main.bbl`, which arXiv needs because it doesn't run BibTeX.
  5. Check `\pdfoutput=1` is the first line and there are no TeX comments.
  6. Re-zip.

  `arxiv/METADATA.txt` holds the form fields (abstract under 1,920 characters, comments with the page count); update it when the abstract or page count changes.
- **Submission status:** the arXiv submission is in progress (`submit/8117661`). Before submitting, verify:
  - [ ] **Reference [4].** Check the venue and track of "Stop Comparing LLM Agents Without Disclosing the Harness" on arXiv or the ICML site. It couldn't be loaded where the paper was drafted.
  - [ ] **Product URLs in §7.5.** They were found by search; open each once.
  - [ ] **The study's evidence.** Spot-check the Codex and opencode file:line evidence in the supplement against the pinned commits, and the Claude Code doc links.
  - [ ] **The whole paper,** read end to end by Chase.

## Slides

- **Purpose:** a presenter teaches the lesson to a room. Clear and concise, the fewest slides that carry the ideas: about 12–22 per deck. The README is the full text; the deck isn't.
- **Shape:** the lesson's own order. Title; the problem; the idea and what it's built on; the mechanism; the code this lesson adds; one or two telling runs; going further on one slide plus the fuller example; the rule, what it never does, what's missing, next.
- **Rules:** one `#` heading per slide; at most 5 bullets; a speaker note on most slides; code copied exactly from the source (a line shortened to fit must be on a slide that says "(abridged)"); run output exact, cut only with "(shortened)"; never shrink text below 0.8em with `<style scoped>`; nothing on a slide that isn't in the lesson.
- **Render and check:**
  ```bash
  export CHROME_PATH=$(ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome | head -1)   # or any Chrome
  npx @marp-team/marp-cli --no-stdin <dir>/slides.md --pdf -o <dir>/slides.pdf --allow-local-files < /dev/null   
  python3 tools/deckcheck.py <dir>
  ```
  The checker reports code lines not in the source, numbers not in the lesson, text off the page, and text under 9pt. Marp shrinks a code block until its longest line fits, so a long line becomes unreadable without running off the page: the 9pt check is what catches it. Text pushed past the bottom edge can be clipped out of the PDF entirely, so no check sees it: always look at the pages.

## Artifacts and who they're for

| Path | For | Purpose |
|---|---|---|
| `README.md` | readers | Entry point: thesis, lesson tables, setup, how to present the slides, the paper, the proof, citation, license. |
| `lessons/01–04/` | learners | The primitives. Each README is the lesson; `quark.py` is the lineage; other `.py` files are fuller examples. |
| `lessons/*/slides.md`, `production/*/slides.md` | presenters | Marp decks for teaching each lesson in a workshop or video, rewritten to be presented: concise, with speaker notes in `<!-- -->` comments. See "Slides" below. |
| `lessons/*/slides.pdf`, `production/*/slides.pdf` | presenters | Each deck rendered by Marp, so it opens and presents straight from GitHub. Regenerate after any `slides.md` change, then run the checker (see "Slides" below). |
| `production/05–10/` | learners | The production layers, each on the previous lesson's `quark.py`. First written by the earlier quark; rebuilt on the current harness by Claude Code, keeping much of that text. The fuller examples (`sandboxing.py` and the rest) are standalone and unchanged, so their recorded runs still stand. |
| `docs/the-model.md`, `assets/*.svg` | learners | Optional deep dive on what's inside the model; the SVGs illustrate it. |
| `docs/quark-at-work/` | readers checking the proof | Transcripts and memory stores from the ten current runs; `earlier-version/` has the earlier four. |
| `paper/agent-harness-primitives.md`, `paper/latex/main.pdf` | paper readers | The paper, in Markdown and typeset. |
| `paper/decomposition-study.md` | paper readers | Supplement with the evidence for §7. |
| `paper/references.bib`, `CITATION.cff` | citers | Citation data. |
| `paper/latex/*` (sources), `paper/arxiv/`, `paper/arxiv-source.zip` | creators | Build inputs and the arXiv upload. |
| `pyproject.toml`, `.env.example`, `.gitignore` | learners and creators | Setup. |
| `AGENTS.md`, `CLAUDE.md` | creators | This file, and the pointer to it. |
| `tools/deckcheck.py` | creators | Checks a deck against its lesson and its rendered PDF. |

## Work still to do

- **Decide on the fuller examples' naming** (`task`/`reply` vs `input`/`output`); see above.
- **Terminal polish belongs in a production lesson, not in the primitives.** Candidates:
  - a "thinking…" indicator;
  - a clean Ctrl-C exit;
  - `stdin=subprocess.DEVNULL` so interactive commands fail fast instead of hanging.
- **Record the videos;** every lesson has a "coming soon" placeholder.
- **Rename the repo** to `harness-engineering`, then update URLs in the README, `CITATION.cff`, the paper, `build.py` (`REPO`) and `METADATA.txt`.
- **Finish the arXiv submission** (checklist above).
