#!/bin/sh
# Builds arxiv.tar.gz from the full paper. arXiv compiles the sources itself and does not run
# BibTeX reliably, so the compiled bibliography (main.bbl) is included. The evidence document goes
# in anc/, which arXiv publishes as an ancillary file beside the paper.
set -e
cd "$(dirname "$0")/../.."
latexmk -pdf -interaction=nonstopmode main.tex
latexmk -pdf -interaction=nonstopmode evidence.tex
rm -rf submissions/arxiv/src && mkdir -p submissions/arxiv/src
cp main.tex main.bbl references.bib submissions/arxiv/src/
cp -r sections minimal submissions/arxiv/src/
mkdir -p submissions/arxiv/src/anc && cp evidence.pdf submissions/arxiv/src/anc/evidence.pdf
tar -czf submissions/arxiv/arxiv.tar.gz -C submissions/arxiv/src .
rm -rf submissions/arxiv/src
ls -la submissions/arxiv/arxiv.tar.gz
