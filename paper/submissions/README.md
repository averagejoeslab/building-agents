# Submissions

One version of the paper per venue, each built from the same `../sections/` files. Edit the paper in `../sections/` and rebuild; only the drivers, styles and the short version's own prose live here.

| Folder | Venue | What it builds | Status |
|---|---|---|---|
| `arxiv/` | [arXiv](https://arxiv.org/submit), cs.AI (cs.SE cross-list) | `arxiv.tar.gz`: the full paper's sources with the compiled bibliography | ready to upload |
| `agentverify/` | [AGENTVERIFY 2027](https://agentverify2027.github.io/cfp.html), an ICSE 2027 workshop, **non-archival option** (abstract 1 Nov, paper 6 Nov 2026) | `short-anon.pdf`: a five-page IEEE position paper, double-blind; `short.pdf`: the same with the author block, for the camera-ready | ready to upload |
| `tmlr/` | [TMLR](https://jmlr.org/tmlr/) | `full.pdf`: the full paper in the TMLR style, anonymized; `supplementary.zip`: Appendix B as a PDF plus the evidence and minimal-harness sources | ready to upload |

## Build

Each folder has a `build.sh`; run it from anywhere. The short version and the TMLR version read the shared sections and bibliography through `TEXINPUTS`, so they need no copies.

```bash
paper/submissions/arxiv/build.sh            # arxiv.tar.gz
paper/submissions/agentverify/build.sh      # short-anon.pdf and short.pdf
paper/submissions/tmlr/build.sh             # full.pdf, supplementary.pdf, supplementary.zip
```

## arXiv

Upload `arxiv/arxiv.tar.gz`. arXiv compiles the sources itself and does not run BibTeX reliably, so the tarball carries `main.bbl`; the evidence document rides along in `anc/` as an ancillary file. Choose **cs.AI** as the primary category, cross-list **cs.SE**, and pick the **CC BY 4.0** license, which is the license this repository gives the paper. Post to arXiv first: TMLR and AGENTVERIFY both allow preprints, so an arXiv version blocks nothing. Once it is live, put the arXiv link in `../README.md`.

## The plan, and why

TMLR's [editorial policies](https://jmlr.org/tmlr/editorial-policies.html) allow no reuse of text, figures or results with any paper "published, accepted for publication, or submitted in parallel at another archival, peer-reviewed venue", and do not accept expanded versions of conference papers. Overlap is allowed with preprints and with venues "publicly declared, in writing, to be non-archival, such as workshops". Both ICSE 2027 agent workshops publish in the IEEE proceedings, which is archival; AGENTVERIFY also offers a non-archival option, AGENT'27 does not. So the paper follows one path:

1. **arXiv** first. Compatible with everything.
2. **AGENTVERIFY 2027** with the **non-archival option**: the five-page version, anonymized. When submitting, ask the chairs (Song Wang, Gias Uddin) to confirm the non-archival status in writing, which is the wording TMLR's policy uses.
3. **TMLR**: the full paper, whenever it is ready. Its disclosure names the preprint and the non-archival workshop version.

AGENT'27 is not used: a paper in its IEEE proceedings would bar the full paper from TMLR.

## AGENTVERIFY 2027

`agentverify/short.tex` is the IEEE conference template (`IEEEtran.cls`, included) with its own condensed sections in `agentverify/sections/`; the summary table reuses the Codex cells from `../sections/`, and the bibliography is the shared `references.bib`. The result is five pages including references. `short-anon.tex` builds the same paper with the author block blanked, and `build.sh` fails if identifying text is found in it.

The [call for papers](https://agentverify2027.github.io/cfp.html): IEEE format, **double-blind**. Full papers up to 8 pages and short papers up to 4, both including references, so the five-page paper goes in as a **full paper**. "Harness engineering for execution, evaluation, and deployment" is a listed topic. Abstracts 1 November, papers 6 November 2026 (AoE), at <https://icse2027-agentverify.hotcrp.com/>; the HotCRP site itself shows 14 November 2026, 06:59 EST (13 November AoE), so meet the 6 November date. Notification 11 December 2026, camera-ready 29 January 2027, workshop in Dublin on 25 April 2027; one author must register and present. Choose the **non-archival option** on submission. Submit `short-anon.pdf`; `short.pdf` is the camera-ready form.

The condensed prose is a separate copy, so a change to the position in `../sections/` must be carried into `agentverify/sections/` by hand.

## TMLR

`tmlr/full.tex` compiles the full paper with the mandatory TMLR style file (`tmlr.sty`, `tmlr.bst`, `fancyhdr.sty`, included). TMLR review is double-blind, and `build.sh` anonymizes the build:

- the style file prints *Anonymous authors* in place of the author block until `[preprint]` or `[accepted]` is passed;
- Appendix C, the evidence, is moved out of the paper into `supplementary.pdf`, and the paper's Appendix C becomes a one-paragraph pointer to it;
- `supplementary.zip` holds that PDF, the `evidence/` Markdown files it was generated from, and the `minimal/` harnesses of Appendix A.

Before uploading, check `full.pdf` once more for anything identifying (the build already checks that the author's name, lab and domains do not appear in the text). Upload `full.pdf` as the submission and `supplementary.zip` as supplementary material at <https://openreview.net/group?id=TMLR>. There is no deadline and no page limit. The paper's "Prior sharing" paragraph discloses the preprint and the non-archival workshop version, which TMLR's policy permits.

For the camera-ready, change `\usepackage{tmlr}` to `\usepackage[accepted]{tmlr}` in `full.tex` and add the OpenReview link the style file asks for.
