# Agent = Harness(Model): The Five Primitives of Every Agent Harness

A position paper by Chase Dovey (Average Joes Lab).

**[Read the PDF](./main.pdf)**

Every LLM agent is a model wrapped in a harness, and every harness is built from five primitives: **Input**, **Context**, **Model interface**, **Output** and **Control flow**. The paper argues for each primitive's necessity, suggests how production concerns (persistence, safety & security, observability, resilience, performance, evaluation) fold into the primitives, and maps thirteen widely used harnesses onto them, from Claude Code, Codex CLI and Gemini CLI to SWE-agent, OpenHands, Agentless, LangGraph and the OpenAI Agents SDK, arguing that their differences are implementation decisions within the same five primitives.

## Build

```bash
cd paper
latexmk -pdf main.tex
```

## Submit to arXiv

arXiv compiles the sources itself, but doesn't run BibTeX reliably, so the generated `main.bbl` is committed and included:

```bash
cd paper
latexmk -pdf main.tex                                   # refreshes main.bbl
mkdir -p arxiv && cp -r main.tex main.bbl references.bib quark.py sections arxiv/
tar -czf arxiv.tar.gz -C arxiv .
```

Upload `arxiv.tar.gz`. Suggested categories: **cs.AI** (primary), cs.SE, cs.CL. When arXiv asks for a license, choose **CC BY 4.0**, the license this repo gives the paper.

## Layout

| File | What it is |
|---|---|
| `main.tex` | Preamble and section order |
| `sections/*.tex` | One file per section |
| `references.bib`, `main.bbl` | Bibliography, and its compiled form for arXiv |
| `quark.py` | The reference harness reproduced in the appendix (a copy of `harness/quark.py`) |
| `main.pdf` | The compiled paper |

## License

The paper is licensed under [CC BY 4.0](../LICENSE-CC-BY-4.0), and `quark.py` under the [MIT License](../LICENSE).
