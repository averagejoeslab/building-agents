"""Table of the wider set from the WIDE-*.md summary tables: python3 wide_table.py > ../sections/deconstruction-wide.tex
Each WIDE file ends with a two-column table, Primitive | Design decision; this collects them into one table, one row per harness."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from to_latex import inline, WIDE, HERE

PRIMS = ["Input", "Context", "Model interface", "Output", "Control flow"]

def summary(path):
    text = open(path).read()
    name = text.split("\n", 1)[0].lstrip("# ").strip()
    m = re.search(r"\*\*Version:\*\*\s*(.+?)\s*(?:·|\n)", text)
    version = m.group(1).strip() if m else ""
    cells = {}
    for line in text[text.index("## Summary"):].split("\n"):
        if line.startswith("|") and not re.match(r"^\|\s*-", line) and not line.startswith("| Primitive"):
            k, v = [c.strip() for c in line.strip("|").split("|")[:2]]
            cells[k] = v
    return name, version, [cells.get(p, "") for p in PRIMS]

rows = []
for slug in WIDE:
    p = os.path.join(HERE, f"WIDE-{slug}.md")
    if os.path.exists(p):
        rows.append(summary(p))

print(r"\begin{table}[p]")
print(r"\centering")
print(r"\scriptsize")
print(r"\setlength{\tabcolsep}{3pt}")
print(r"\renewcommand{\arraystretch}{1.15}")
print(r"\caption{Thirteen more harnesses by primitive, read from their sources or documentation at summary level. Each cell is the design decision that harness made within the primitive; the evidence for each is in Appendix~\ref{app:evidence}, which also gives the pinned commit or documentation date.}")
print(r"\label{tab:wide}")
print(r"\begin{tabularx}{\linewidth}{@{}>{\bfseries\raggedright\arraybackslash}p{1.7cm}YYYYY@{}}")
print(r"\toprule")
print(" & " + " & ".join(r"\prim{%s}" % p for p in PRIMS) + r" \\")
print(r"\midrule")
for name, version, cells in rows:
    short = re.sub(r"\s*\(.*?\)\s*", " ", name).strip()
    print(inline(short) + " & " + " & ".join(inline(c) for c in cells) + r" \\")
    print(r"\addlinespace")
print(r"\bottomrule")
print(r"\end{tabularx}")
print(r"\end{table}")
