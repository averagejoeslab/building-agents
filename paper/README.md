# The paper

**Five Primitives Are All You Need: Building an Agent Harness** by Chase Dovey, Average Joes Lab.

| File | What it is |
|---|---|
| [`five-primitives-are-all-you-need.md`](./five-primitives-are-all-you-need.md) | The paper. This is the source of truth. |
| [`decomposition-study.md`](./decomposition-study.md) | Supplement: the evidence behind §7, with file-and-line or URL evidence for each harness. |
| [`references.bib`](./references.bib) | BibTeX for every reference. |
| [`latex/main.pdf`](./latex/main.pdf) | The typeset paper. |
| `latex/` | LaTeX source. `main.tex`, the figures and `build.py` are written by hand; `abstract.tex`, `body.tex` and `appendix.tex` are generated from the Markdown. |

## Building the PDF

Edit the Markdown, then rebuild:

```bash
python3 paper/latex/build.py /path/to/pandoc
```

You need pandoc 3.x and a TeX Live with pdflatex, bibtex, TikZ, pifont, listings and booktabs. On Debian or Ubuntu:

```bash
apt-get install texlive-latex-recommended texlive-latex-extra texlive-pictures
pip install pypandoc-binary   # bundles a pandoc binary
```

## Before submitting

Verify these yourself.

- [ ] **References [5] and [9].** Check them directly on arXiv: the venue and track for "Stop Comparing LLM Agents Without Disclosing the Harness", and the full author list for "Code as Agent Harness". These couldn't be loaded from where the paper was drafted.
- [ ] **Product URLs in §7.5.** They were found by searching each vendor's own docs. Open each one once.
- [ ] **The study's evidence.** Spot-check the Codex and opencode file:line evidence in the supplement against the pinned commits, and the Claude Code doc links.
- [ ] **The whole paper.** Read it end to end in your own voice.
- [ ] **arXiv packaging.** arXiv wants a flat source folder. Copy `references.bib` and `latex/main.bbl` next to `main.tex`, and change `\bibliography{../references}` to `\bibliography{references}`. Category: cs.SE, cross-listed to cs.AI. A first-time submitter needs an endorsement.
