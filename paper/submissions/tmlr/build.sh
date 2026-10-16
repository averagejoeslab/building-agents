#!/bin/sh
# Builds the TMLR submission: full.pdf (the paper, anonymized), supplementary.pdf (Appendix B)
# and supplementary.zip (the PDF plus the evidence and minimal-harness sources).
set -e
cd "$(dirname "$0")"


# The supplement is Appendix B compiled on its own; its cross-references to the paper's sections
# are resolved from full.aux, so the paper is built first and the supplement is always rebuilt.
export TEXINPUTS="../../:" BIBINPUTS="../../:"
latexmk -pdf -interaction=nonstopmode full.tex
latexmk -pdf -g -interaction=nonstopmode supplementary.tex

rm -rf supplementary.zip stage && mkdir -p stage/evidence stage/minimal
cp supplementary.pdf stage/
cp ../../evidence/BRIEF.md ../../evidence/EVIDENCE-*.md ../../evidence/WIDE-*.md stage/evidence/
cp ../../minimal/*.py stage/minimal/
cat > stage/README.txt <<'TXT'
Supplementary material, anonymized for review.
  supplementary.pdf   Appendix C: the evidence for every assignment in the deconstruction (Section 5)
  evidence/           the source of Appendix C: one Markdown file per harness, and the brief the deconstruction followed
  minimal/            the five minimal harnesses of Appendix A, one primitive at a time
TXT
(cd stage && zip -qr ../supplementary.zip .)
rm -rf stage

# Double-blind check: the author's name, lab and domains must not appear in the submission.
if command -v pdftotext >/dev/null; then
  for f in full.pdf supplementary.pdf; do
    if pdftotext "$f" - | grep -i -q 'dovey\|average joes\|averagejoeslab\|odovey'; then
      echo "ANONYMITY CHECK FAILED: identifying text in $f" >&2; exit 1
    fi
  done
  echo "anonymity check passed"
fi
