#!/bin/sh
# Builds the IEEE short version. The summary table reuses the Codex cells and the
# bibliography from the full paper, so TEXINPUTS and BIBINPUTS point two levels up.
cd "$(dirname "$0")"
TEXINPUTS="../../:" BIBINPUTS="../../:" latexmk -pdf -interaction=nonstopmode short.tex
