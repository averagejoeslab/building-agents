"""Build paper/latex/body.tex and abstract.tex from the Markdown paper, then compile main.pdf.

Usage: python3 paper/latex/build.py [path/to/pandoc]
Needs pandoc (3.x) and a TeX Live with pdflatex, bibtex, tikz, pifont, listings, booktabs.
"""
import re, subprocess, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
MD = HERE.parent / "agent-harness-primitives.md"
PANDOC = sys.argv[1] if len(sys.argv) > 1 else "pandoc"
REPO = "https://github.com/averagejoeslab/building-agents/blob/main/"

KEYS = {1: "sumers2024cognitive", 2: "jin2026agentprimitives", 3: "schluntz2024building", 4: "zhang2026stop",
        5: "fan2026empirical", 6: "litellm", 7: "openrouter", 8: "mem0", 9: "langgraph", 10: "mcp",
        11: "langfuse", 12: "langsmith", 13: "opa", 14: "nemo", 15: "e2b", 16: "daytona", 17: "modal",
        18: "temporal", 19: "braintrust", 20: "promptfoo", 21: "inspect", 22: "codex", 23: "opencode",
        24: "claudecode", 25: "course"}

def cites(m):
    nums = []
    for part in re.split(r",\s*", m.group(1)):
        if re.fullmatch(r"\d+[–-]\d+", part):
            a, b = map(int, re.split(r"[–-]", part)); nums += range(a, b + 1)
        else:
            nums.append(int(part))
    return r"\cite{" + ",".join(KEYS[n] for n in nums) + "}"

def prep(md):
    md = re.sub(r"\n---\n", "\n", md)
    parts = re.split(r"(```.*?```)", md, flags=re.S)
    md = "".join(x if x.startswith("```") else re.sub(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()", cites, x) for x in parts)
    md = re.sub(r"^(#{2,3}) (?:Appendix [A-Z]\. |[A-Z]\.\d+ |\d+(?:\.\d+)*\.? )", r"\1 ", md, flags=re.M)
    md = re.sub(r"```\ncontrol flow          how information flows.*?```", r"\\input{fig-tree}", md, flags=re.S)
    md = re.sub(r"```\nperson or world ─►.*?```", r"\\input{fig-path}", md, flags=re.S)
    md = md.replace("](./decomposition-study.md)", "](" + REPO + "paper/decomposition-study.md)")
    md = md.replace("](../lessons/", "](" + REPO + "lessons/")
    for k, v in {"✔": r"\ding{51}", "✘": r"\ding{55}", "●": r"$\bullet$", "○": r"$\circ$", "→": r"$\rightarrow$", "≤": r"$\le$"}.items():
        md = md.replace(k, v)
    return md

def pandoc(md):
    return subprocess.run([PANDOC, "-f", "markdown-auto_identifiers", "-t", "latex", "--listings", "--wrap=preserve", "--shift-heading-level-by=-1"],
                          input=md, capture_output=True, text=True, check=True).stdout

text = MD.read_text()
abstract = text.split("## Abstract", 1)[1].split("\n---", 1)[0]
body = text.split("## 1. Introduction", 1)[1]
body = "## Introduction" + body
main_part, rest = body.split("## References", 1)
appendices = "## Appendix A" + rest.split("## Appendix A", 1)[1].rsplit("\n---\n", 1)[0]
(HERE / "abstract.tex").write_text(pandoc(prep(abstract)))
body_tex = pandoc(prep(main_part.rstrip().rstrip("-").rstrip()))
(HERE / "appendix.tex").write_text(pandoc(prep(appendices)))
body_tex = body_tex.replace(r"\section{Acknowledgments and disclosure of AI use}", r"\section*{Acknowledgments and disclosure of AI use}")
(HERE / "body.tex").write_text(body_tex)

for cmd in (["pdflatex", "-interaction=nonstopmode", "main.tex"], ["bibtex", "main"],
            ["pdflatex", "-interaction=nonstopmode", "main.tex"], ["pdflatex", "-interaction=nonstopmode", "main.tex"]):
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, errors="replace")
    if r.returncode and cmd[0] != "bibtex":
        print(r.stdout[-3000:]); sys.exit(1)
print("built", HERE / "main.pdf")
