# The paper

**Agent = Harness(Model): Five Mechanistic Primitives of LLM Agent Harnesses** by Chase Dovey, Average Joes Lab.

| File | What it is |
|---|---|
| [`agent-harness-primitives.md`](./agent-harness-primitives.md) | The paper. This is the source of truth. |
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

- [ ] **Reference [4].** Check the venue and track for "Stop Comparing LLM Agents Without Disclosing the Harness" directly on arXiv or the ICML site. It couldn't be loaded from where the paper was drafted.
- [ ] **Every reference earns its place.** Each one is cited for something the paper uses: the closest prior framework (CoALA), a name to tell apart (*Agent Primitives*), the workflow/agent line (Schluntz and Zhang), the premise and the disclosure schema (Zhang et al.), an independent decomposition that lands inside the five (Fan et al.), the source for each product claim, and the three harnesses studied. Keep it that way: don't add a reference you don't use.
- [ ] **Product URLs in §7.5.** They were found by searching each vendor's own docs. Open each one once.
- [ ] **The study's evidence.** Spot-check the Codex and opencode file:line evidence in the supplement against the pinned commits, and the Claude Code doc links.
- [ ] **The whole paper.** Read it end to end in your own voice.
- [x] **arXiv packaging.** `arxiv/` is the flat upload folder and `arxiv-source.zip` is the same files zipped. `main.tex` starts with `\pdfoutput=1`, `main.bbl` is included because arXiv doesn't run BibTeX, and there are no TeX comments. After changing the paper, rebuild, copy `latex/*.tex` and `references.bib` into `arxiv/`, point `\bibliography` at `references`, re-run BibTeX there, and re-zip.
