# Agent = Harness(Model): Five Mechanistic Primitives, and What Is Not One

A position paper by Chase Dovey (Average Joes Lab).

**[Read the PDF](./main.pdf)**

An agent is a model wrapped in a harness, and the harness has five parts: **Input**, **Context**, **Model interface**, **Output** and **Control flow**. The paper proposes this as the architecture of every harness and shows each primitive as the smallest program that adds it. Everything else said about a harness is a *design decision* within a primitive or a *production concern* asked of every primitive. The vocabulary lets a result be reported with the harness that produced it, lets research compare primitives by their implementations, and lets debugging isolate a failure to the primitives an implementation touches. The paper deconstructs nineteen harnesses against the five: six from their sources at pinned versions (Claude Code, Codex CLI, opencode, pi, Hermes Agent, a LangGraph workflow) and thirteen more at summary level (SWE-agent, OpenHands, Aider, Cline, Gemini CLI, Goose, OpenAI Agents SDK, Google ADK, AutoGen, CrewAI, smolagents, Cursor, GitHub Copilot's coding agent). It closes with the comparisons of implementations that would both use the framework and test it. The minimal harnesses are in Appendix A, the rules for the cases at the boundaries in Appendix B, and the evidence for every assignment in Appendix C and in [`evidence/`](./evidence/).

## Layout

| Path | What it is |
|---|---|
| `main.tex` | Preamble and section order |
| `sections/*.tex` | One file per section; `deconstruction-*.tex` are the per-harness subsections and the two summary tables |
| `sections/appendix-b.tex`, `sections/deconstruction-wide.tex` | Generated from `evidence/` by `evidence/to_latex.py` and `evidence/wide_table.py` |
| `evidence/EVIDENCE-*.md`, `evidence/WIDE-*.md` | The deconstruction of each harness, in full for the six and at summary level for the thirteen: every assignment with a file-and-line or page-and-section citation at the pinned version |
| `evidence/BRIEF.md` | The definitions, rules and output format the deconstruction followed |
| `minimal/` | The five minimal harnesses reproduced in Appendix A (copies of `harness/1_model_interface.py` to `harness/quark.py`) |
| `references.bib`, `main.bbl` | Bibliography, and its compiled form (included in the arXiv tarball) |
| `main.pdf` | The compiled paper |
| `submissions/` | One build per venue: arXiv, AGENTVERIFY 2027, TMLR |

## Build

```bash
cd paper
python3 evidence/to_latex.py > sections/appendix-b.tex             # only if the evidence changed
python3 evidence/wide_table.py > sections/deconstruction-wide.tex  # only if the wide set changed
latexmk -pdf main.tex
```

## Submitting

`submissions/` holds one build per venue, each from the same `sections/`: an arXiv tarball, a five-page IEEE short version for the AGENTVERIFY 2027 workshop, and an anonymized TMLR version with its supplementary material. See [`submissions/README.md`](./submissions/README.md) for the steps for each venue.

## Checking an assignment

Each harness's evidence file names its pinned commit. To check a citation, clone the repository at that commit and open the file at the cited lines:

```bash
git clone https://github.com/openai/codex && git -C codex checkout <commit from EVIDENCE-codex.md>
```

For Claude Code, the citations are documentation pages and section headings on the date read; the pages may have changed since.

## License

The paper is licensed under [CC BY 4.0](../LICENSE-CC-BY-4.0), and the code in `minimal/` and `evidence/to_latex.py` under the [MIT License](../LICENSE).
