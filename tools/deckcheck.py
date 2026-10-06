#!/usr/bin/env python3
"""usage: deckcheck.py <lesson_dir>   e.g. lessons/01-model-interface or production/05-sandboxing
Checks <dir>/slides.md against the lesson's README.md and .py files, and <dir>/slides.pdf for layout."""
import re, sys, glob, os, subprocess

d = sys.argv[1].rstrip("/")
readme = open(f"{d}/README.md").read()
code = "\n".join(open(f).read() for f in glob.glob(f"{d}/*.py"))
source_lines = set(readme.splitlines()) | set(code.splitlines())
deck = open(f"{d}/slides.md").read()

# split into slides on --- lines outside code fences, after the front matter
body = deck.split("\n---\n", 1)[1]
slides, cur, fence = [], [], False
for line in body.split("\n"):
    if line.startswith("```"): fence = not fence
    if line.strip() == "---" and not fence:
        slides.append("\n".join(cur)); cur = []
    else:
        cur.append(line)
slides.append("\n".join(cur))

problems = 0
for n, s in enumerate(slides, 1):
    visible = re.sub(r"<!--.*?-->|<style.*?</style>", "", s, flags=re.S)
    abridged = "abridged" in visible.lower()
    headings = re.findall(r"^# .*", re.sub(r"```.*?```", "", visible, flags=re.S), re.M)
    if len(headings) != 1:
        print(f"slide {n}: {len(headings)} level-1 headings"); problems += 1
    for block in re.findall(r"```\w*\n(.*?)```", visible, re.S):
        for l in block.splitlines():
            if l.strip() and l not in source_lines and l.strip() not in ("...",) and not abridged:
                print(f"slide {n}: code line not in source: {l[:90]}"); problems += 1
    prose = re.sub(r"```.*?```", "", visible, flags=re.S)
    for num in re.findall(r"(?<![\w.])\d[\d,.]*\d(?![\w])|(?<![\w.])\d(?![\w.])", prose):
        if num not in readme and num not in code and num.rstrip(".") not in readme:
            print(f"slide {n}: number {num} not in README or code"); problems += 1
print(f"{len(slides)} slides in the deck")

pdf = f"{d}/slides.pdf"
if not os.path.exists(pdf) or os.path.getmtime(pdf) < os.path.getmtime(f"{d}/slides.md"):
    print("slides.pdf is missing or older than slides.md: render it"); problems += 1
else:
    xml = subprocess.run(["pdftotext", "-bbox", pdf, "-"], capture_output=True, text=True).stdout
    pages = xml.split("<page ")[1:]
    print(f"{len(pages)} pages in the PDF")
    if len(pages) != len(slides):
        print("page count differs from slide count"); problems += 1
    for i, p in enumerate(pages, 1):
        words = re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', p)
        for x0, y0, x1, y1, w in words:
            x0, y0, x1, y1 = map(float, (x0, y0, x1, y1))
            if w.strip() == str(i) and y0 > 480: continue          # page number
            if y1 > 525 or x1 > 945:
                print(f"page {i}: text off the page: {w[:40]}"); problems += 1; break
        small = [float(y1) - float(y0) for x0, y0, x1, y1, w in words if w.strip()]
        if small and min(small) < 9:
            print(f"page {i}: text smaller than 9pt ({min(small):.1f}pt)"); problems += 1
print(f"problems: {problems}")
