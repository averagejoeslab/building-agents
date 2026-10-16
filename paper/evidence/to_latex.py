"""Appendix B from the evidence files: python3 to_latex.py > ../sections/appendix-b.tex
Each EVIDENCE-*.md is one harness, in the fixed structure of BRIEF.md; this turns it into LaTeX, escaping as it goes."""
import re, sys, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = ["claude-code", "codex", "opencode", "pi", "hermes", "langgraph"]
WIDE = ["swe-agent", "openhands", "aider", "cline", "gemini-cli", "goose", "openai-agents", "google-adk", "autogen", "crewai", "smolagents", "cursor", "copilot"]

def esc(text):                                            # LaTeX-escape plain text
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"),
                 ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")):
        text = text.replace(a, b)
    for a, b in (("–", "--"), ("—", "---"), ("→", r"$\rightarrow$"), ("←", r"$\leftarrow$"), ("≤", r"$\leq$"), ("≥", r"$\geq$"), ("∈", r"$\in$"), ("…", r"\ldots{}"),
                 ("×", r"$\times$"), ("−", "-"), ("·", r"$\cdot$"), ("≈", r"$\approx$"), ("’", "'"), ("‘", "`"), ("“", "``"), ("”", "''"), ("✓", "yes"), ("✗", "no"), ("∞", r"$\infty$"), ("→", r"$\rightarrow$"), ("α", r"$\alpha$"), ("″", "''"), ("′", "'")):
        text = text.replace(a, b)
    return text

def inline(text):                                         # `code`, **bold**, *italic*, [text](url)
    out, i = [], 0
    for m in re.finditer(r"`([^`]*)`|\*\*(.+?)\*\*|\*(.+?)\*|\[([^\]]+)\]\((https?://[^)]+)\)", text):
        out.append(esc(text[i:m.start()]))
        if m.group(1) is not None: out.append(r"\texttt{" + re.sub(r"([/_:.\-(])", lambda c: c.group(1) + r"\allowbreak{}", esc(m.group(1))) + "}")
        elif m.group(2) is not None: out.append(r"\textbf{" + inline(m.group(2)) + "}")
        elif m.group(3) is not None: out.append(r"\emph{" + inline(m.group(3)) + "}")
        else: out.append(r"\href{" + m.group(5) + "}{" + esc(m.group(4)) + "}")
        i = m.end()
    out.append(esc(text[i:]))
    return "".join(out)

def convert(path):
    lines = open(path).read().split("\n")
    out, mode, table = [], None, []
    def close():
        nonlocal mode, table
        if mode == "list": out.append(r"\end{itemize}")
        if mode == "table":
            head, rows = table[0], [r for r in table[1:] if not re.match(r"^\|?\s*-", r)]
            cells = [c.strip() for c in head.strip("|").split("|")]
            n = len(cells)
            out.append(r"\begin{longtable}{@{}" + ("p{2.1cm}" + "p{2.6cm}" * (n - 2) + "X" if False else "") + "}")
            out.pop()
            widths = {2: "p{0.28\\linewidth}p{0.66\\linewidth}", 4: "p{0.13\\linewidth}p{0.17\\linewidth}p{0.36\\linewidth}p{0.26\\linewidth}", 5: "p{0.18\\linewidth}" * 5}
            out.append(r"\begin{longtable}{@{}" + widths.get(n, "p{%.2f\\linewidth}" % (0.94 / n) * n) + "@{}}")
            out.append(r"\toprule " + " & ".join(r"\textbf{" + inline(c) + "}" for c in cells) + r" \\ \midrule \endhead")
            for r in rows:
                cs = [c.strip() for c in r.strip("|").split("|")]
                cs += [""] * (n - len(cs))
                out.append(" & ".join(inline(c) for c in cs[:n]) + r" \\")
            out.append(r"\bottomrule \end{longtable}")
            table = []
        mode = None
    for line in lines:
        s = line.rstrip()
        if s.startswith("# "):
            close(); out.append(r"\subsection{" + inline(s[2:]) + "}"); continue
        if s.startswith("### "):
            close(); out.append(r"\paragraph{" + inline(s[4:]) + "}"); continue
        if s.startswith("## "):
            close(); out.append(r"\subsubsection*{" + inline(s[3:]) + "}"); continue
        if s.startswith("|"):
            if mode != "table": close(); mode = "table"
            table.append(s); continue
        if re.match(r"^\s*[-*] ", s):
            if mode != "list": close(); mode = "list"; out.append(r"\begin{itemize}")
            depth = (len(s) - len(s.lstrip())) // 2
            out.append(("  " * depth) + r"\item " + inline(s.lstrip()[2:])); continue
        if not s.strip():
            if mode == "list": close()
            elif mode == "table": close()
            out.append(""); continue
        if mode == "list":                                # a continuation line inside a bullet
            out.append(inline(s.strip())); continue
        close(); out.append(inline(s))
    close()
    return "\n".join(out)

print(r"\section{Evidence for the Deconstruction}")
print(r"\label{app:evidence}")
print(r"Every assignment in \S\ref{sec:deconstruction}, with its evidence. For harnesses with published source, a citation is a path and a line range at the pinned commit; for a harness read from documentation it is a page and section heading on the date read. The same files are published in the repository under \texttt{paper/evidence/}. \textbf{Path conventions} are given at the start of each harness; \textbf{not found} means the mechanism was looked for and not found, not that it is absent. The first six harnesses are deconstructed in full; the thirteen that follow at summary level, two to five components per primitive.")
print(r"\small")
for name in ORDER:
    path = os.path.join(HERE, f"EVIDENCE-{name}.md")
    if os.path.exists(path):
        print(convert(path)); print()
print(r"\subsection*{The wider set, at summary level}")
for name in WIDE:
    path = os.path.join(HERE, f"WIDE-{name}.md")
    if os.path.exists(path):
        print(convert(path)); print()
print(r"\normalsize")
