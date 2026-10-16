#!/bin/sh
# Builds short-anon.pdf (the AGENTVERIFY 2027 submission, double-blind) and short.pdf (the same paper with the author block).
# The summary table reuses the Codex cells and the bibliography from the full paper, so TEXINPUTS
# and BIBINPUTS point two levels up.
set -e
cd "$(dirname "$0")"


export TEXINPUTS="../../:" BIBINPUTS="../../:"
latexmk -pdf -interaction=nonstopmode short.tex
latexmk -pdf -interaction=nonstopmode short-anon.tex

# Double-blind check for the anonymized build.
if command -v pdftotext >/dev/null; then
  if pdftotext short-anon.pdf - | grep -i -q 'dovey\|average joes\|averagejoeslab\|odovey'; then
    echo "ANONYMITY CHECK FAILED: identifying text in short-anon.pdf" >&2; exit 1
  fi
  echo "anonymity check passed"
fi
