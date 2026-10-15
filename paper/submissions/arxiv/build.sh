#!/bin/sh
# Builds arxiv.tar.gz from the full paper. arXiv compiles the sources itself and does not run
# BibTeX reliably, so the compiled bibliography (main.bbl) is included.
set -e
cd "$(dirname "$0")/../.."
latexmk -pdf -interaction=nonstopmode main.tex
rm -rf submissions/arxiv/src && mkdir -p submissions/arxiv/src
cp main.tex main.bbl references.bib submissions/arxiv/src/
cp -r sections minimal submissions/arxiv/src/
tar -czf submissions/arxiv/arxiv.tar.gz -C submissions/arxiv/src .
rm -rf submissions/arxiv/src
ls -la submissions/arxiv/arxiv.tar.gz
