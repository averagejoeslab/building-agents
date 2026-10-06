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
- Lessons 1–4 are the primitives, built outward from the model: 1 model interface, 2 input and output, 3 control flow, 4 context. Lessons 5–10 are the production layers in `production/`.
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

**Fuller examples** (`model_interface.py`, `input_output.py`, `control_flow.py`, `workflow.py`, `context.py`) are standalone files showing what else a primitive can be. They don't follow the `quark.py` lineage and still use names like `task` and `reply`. Whether to rename them to `input`/`output` is an open decision for Chase.

## Real output only

- Every output shown in a lesson, the README or the paper comes from a real run of that exact code. Never invent, edit or "tidy" output. You may shorten it, but say so (for example, a shortened `signature`).
- Real output is history: if it mentions something since changed (such as Lesson 9's run saying production lessons are "coming soon"), leave it.
- Code listings in READMEs must match their files line for line. The only exception is Lesson 4's system prompt, shown as `...` in the listing and in full in a `<details>` block. Quick check:
  ```bash
  python3 - <<'PY'
  import re, glob, os
  for r in sorted(glob.glob("lessons/*/README.md")):
      files = {f: open(f).read().splitlines() for f in glob.glob(os.path.dirname(r) + "/*.py")}
      for b in re.findall(r"```python\n(.*?)```", open(r).read(), re.S):
          lines = b.rstrip("\n").splitlines()
          best = max(files, key=lambda f: sum(l in files[f] for l in lines))
          print(r, os.path.basename(best), [l for l in lines if l not in files[best]][:3])
  PY
  ```
- **Line counts are quoted in many places:** 9, 33, 46 and 234 lines (82 of code, 152 of prompt), and the 1,949 total in Lesson 4's demo.
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

- [`docs/quark-at-work/`](./docs/quark-at-work/) holds the verbatim transcripts and the memory file from the four runs that wrote the production lessons and all ten slide decks. They were made with the earlier 48-line Lesson 4 harness.
- **They're evidence:**
  - Never edit a transcript.
  - Anything changed by hand afterwards in the lessons or slides is disclosed in the README's quark-at-work section. Keep that disclosure current if you change more.
  - The paper's §8 and Appendix D read these runs; keep them consistent.

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

## Artifacts and who they're for

| Path | For | Purpose |
|---|---|---|
| `README.md` | readers | Entry point: thesis, lesson tables, setup, how to present the slides, the paper, the proof, citation, license. |
| `lessons/01–04/` | learners | The primitives. Each README is the lesson; `quark.py` is the lineage; other `.py` files are fuller examples. |
| `lessons/*/slides.md`, `production/*/slides.md` | presenters | Marp decks for teaching each lesson in a workshop or video. Written by quark from memory, corrected by hand. |
| `lessons/*/slides.pdf`, `production/*/slides.pdf` | presenters | Each deck rendered by Marp, so it opens and presents straight from GitHub. Regenerate after any `slides.md` change: `CHROME_PATH=<chromium> npx @marp-team/marp-cli <dir>/slides.md --pdf -o <dir>/slides.pdf --allow-local-files`. Then check every page fits: no word below y=482pt or right of x=901pt in `pdftotext -bbox` (page number excepted). A slide that overflows needs a `<style scoped>` block (smaller font), never changed text. |
| `production/05–10/` | learners | The production layers, written by quark (run 3). |
| `docs/the-model.md`, `assets/*.svg` | learners | Optional deep dive on what's inside the model; the SVGs illustrate it. |
| `docs/quark-at-work/` | readers checking the proof | Verbatim transcripts and memory from the four runs. |
| `paper/agent-harness-primitives.md`, `paper/latex/main.pdf` | paper readers | The paper, in Markdown and typeset. |
| `paper/decomposition-study.md` | paper readers | Supplement with the evidence for §7. |
| `paper/references.bib`, `CITATION.cff` | citers | Citation data. |
| `paper/latex/*` (sources), `paper/arxiv/`, `paper/arxiv-source.zip` | creators | Build inputs and the arXiv upload. |
| `pyproject.toml`, `.env.example`, `.gitignore` | learners and creators | Setup. |
| `AGENTS.md`, `CLAUDE.md` | creators | This file, and the pointer to it. |

## Work still to do

- **Move the production lessons onto the current Lesson 4 harness.**
  - Lessons 5–10 build on the earlier 48-line `quark.py`, before episodic and procedural memory.
  - When done, update the README's production note, the paper (§6, §9.3 limitations, Appendix C) and the lessons' line counts.
- **Regenerate the Lesson 1–4 slide decks.** They still show the 48-line code and the old names (`task`, `reply`) and line counts. The README warns presenters; remove that warning when they're current.
- **Decide on the fuller examples' naming** (`task`/`reply` vs `input`/`output`); see above.
- **Terminal polish belongs in a production lesson, not in the primitives.** Candidates:
  - a "thinking…" indicator;
  - a clean Ctrl-C exit;
  - `stdin=subprocess.DEVNULL` so interactive commands fail fast instead of hanging.
- **Record the videos;** every lesson has a "coming soon" placeholder.
- **Rename the repo** to `harness-engineering`, then update URLs in the README, `CITATION.cff`, the paper, `build.py` (`REPO`) and `METADATA.txt`.
- **Finish the arXiv submission** (checklist above).
