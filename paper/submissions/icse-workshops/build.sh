#!/bin/sh
# Builds short.pdf (AGENT'27, single-anonymous) and short-anon.pdf (AGENTVERIFY 2027, double-blind).
# The summary table reuses the Codex cells and the bibliography from the full paper, so TEXINPUTS
# and BIBINPUTS point two levels up.
set -e
cd "$(dirname "$0")"

# The anonymized bibliography is the full paper's, with the entry that names the author replaced.
python3 - <<'PY'
import re
bib = open("../../references.bib").read()
anon = """@misc{course,
  author = {Anonymous},
  title  = {Building Agents: companion book and repository},
  year   = {2026},
  note   = {Anonymized for review}
}"""
bib, n = re.subn(r"@\w+\{course,.*?\n\}", anon, bib, count=1, flags=re.S)
assert n == 1, "course entry not found"
open("references-anon.bib", "w").write(bib)
PY

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
