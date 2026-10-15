# Agent = Harness(Model): Five Mechanistic Primitives, and What Is Not One

A position paper by Chase Dovey (Average Joes Lab).

**[Read the PDF](./main.pdf)**

An LLM agent is a model wrapped in a harness, and every harness is built from five mechanistic primitives: **Input**, **Context**, **Model interface**, **Output** and **Control flow**. Everything else said about a harness is either a *design decision* within a primitive or a *production concern* asked of every primitive. The paper defines the five (each by what it does and what it never does), separates the three levels, and tests the claim by deconstructing six harnesses from their primary sources at pinned versions: Claude Code, Codex CLI, opencode, pi, Hermes Agent, and a LangGraph workflow. The minimal harnesses the definitions came from are in Appendix A; the evidence for every assignment is in Appendix B and in [`evidence/`](./evidence/).

## Layout

| Path | What it is |
|---|---|
| `main.tex` | Preamble and section order |
| `sections/*.tex` | One file per section; `deconstruction-*.tex` are the per-harness subsections and the summary table |
| `sections/appendix-b.tex` | Generated from `evidence/` by `evidence/to_latex.py` |
| `evidence/EVIDENCE-*.md` | The deconstruction of each harness: every assignment with a file-and-line or page-and-section citation at the pinned version |
| `evidence/BRIEF.md` | The definitions, rules and output format the deconstruction followed |
| `minimal/` | The five minimal harnesses reproduced in Appendix A (copies of `harness/1_model_interface.py` to `harness/quark.py`) |
| `references.bib`, `main.bbl` | Bibliography, and its compiled form (included in the arXiv tarball) |
| `main.pdf` | The compiled paper |
| `submissions/` | One build per venue: arXiv, AGENTVERIFY 2027, TMLR |

## Build

```bash
cd paper
python3 evidence/to_latex.py > sections/appendix-b.tex   # only if the evidence changed
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
