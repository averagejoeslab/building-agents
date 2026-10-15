# Submissions

One version of the paper per venue, each built from the same `../sections/` files. Edit the paper in `../sections/` and rebuild; only the drivers, styles and the short version's own prose live here.

| Folder | Venue | What it builds | Status |
|---|---|---|---|
| `arxiv/` | [arXiv](https://arxiv.org/submit), cs.AI (cs.SE cross-list) | `arxiv.tar.gz`: the full paper's sources with the compiled bibliography | ready to upload |
| `icse-workshops/` | [AGENTVERIFY 2027](https://agentverify2027.github.io/) (papers due 6 Nov 2026) and [AGENT'27](https://conf.researchr.org/home/icse-2027/agent-2027) (due 13 Nov 2026), both ICSE 2027 workshops | `short.pdf`: a five-page IEEE two-column position paper, references included | ready for AGENT'27; confirm AGENTVERIFY's page limit on its HotCRP site first |
| `tmlr/` | [TMLR](https://jmlr.org/tmlr/) | `full.pdf`: the full paper in the TMLR style, anonymized; `supplementary.zip`: Appendix B as a PDF plus the evidence and minimal-harness sources | ready to upload |

## Build

Each folder has a `build.sh`; run it from anywhere. The short version and the TMLR version read the shared sections and bibliography through `TEXINPUTS`, so they need no copies.

```bash
paper/submissions/arxiv/build.sh            # arxiv.tar.gz
paper/submissions/icse-workshops/build.sh   # short.pdf
paper/submissions/tmlr/build.sh             # full.pdf, supplementary.pdf, supplementary.zip
```

## arXiv

Upload `arxiv/arxiv.tar.gz`. arXiv compiles the sources itself and does not run BibTeX reliably, so the tarball carries `main.bbl`. Choose **cs.AI** as the primary category, cross-list **cs.SE**, and pick the **CC BY 4.0** license, which is the license this repository gives the paper. Post to arXiv first: AGENT'27 is single-anonymous and TMLR allows preprints, so an arXiv version blocks nothing.

## ICSE 2027 workshops (AGENT'27 and AGENTVERIFY 2027)

`icse-workshops/short.tex` is the IEEE conference template (`IEEEtran.cls`, included) with its own condensed sections in `icse-workshops/sections/`; the summary table reuses the Codex cells from `../sections/`, and the bibliography is the shared `references.bib`. The result is five pages including references, the AGENT'27 limit for short papers (position papers are explicitly welcome there). Review is single-anonymous, so the author block stays.

- **AGENT'27:** submit `short.pdf` at <https://icse2027-agent.hotcrp.com/> by 13 November 2026 (AoE). Full papers may run to 8 pages if the longer form is wanted.
- **AGENTVERIFY 2027:** abstracts 1 November, papers 6 November 2026 (AoE), at <https://icse2027-agentverify.hotcrp.com/>. The workshop page states no page limit or template; as an ICSE workshop it will almost certainly be the IEEE template, but confirm before submitting.

The condensed prose is a separate copy, so a change to the position in `../sections/` must be carried into `icse-workshops/sections/` by hand.

## TMLR

`tmlr/full.tex` compiles the full paper with the mandatory TMLR style file (`tmlr.sty`, `tmlr.bst`, `fancyhdr.sty`, included). TMLR review is double-blind, and `build.sh` anonymizes the build:

- the style file prints *Anonymous authors* in place of the author block until `[preprint]` or `[accepted]` is passed;
- the one bibliography entry naming the author (the companion book and repository) is replaced in a generated copy of `references.bib`;
- Appendix B, the fifty pages of evidence, is moved out of the paper into `supplementary.pdf`, and the paper's Appendix B becomes a one-paragraph pointer to it;
- `supplementary.zip` holds that PDF, the `evidence/` Markdown files it was generated from, and the `minimal/` harnesses of Appendix A.

Before uploading, check `full.pdf` once more for anything identifying (the build already checks that the author's name, lab and domains do not appear in the text). Upload `full.pdf` as the submission and `supplementary.zip` as supplementary material at <https://openreview.net/group?id=TMLR>. There is no deadline and no page limit; the main text is 18 pages.

For the camera-ready, change `\usepackage{tmlr}` to `\usepackage[accepted]{tmlr}` in `full.tex`, restore the real `references.bib` entry (delete the anonymizing step in `build.sh`), and add the OpenReview link the style file asks for.
