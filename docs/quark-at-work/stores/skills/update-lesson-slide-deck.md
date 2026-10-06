---
name: update-lesson-slide-deck
description: bring a lesson's Marp slides.md (lessons/NN-*/slides.md, production decks too) into line with its README.md and code; audit every slide for claims, code excerpts, numbers, outputs, order, one idea per slide
---
1. Read the lesson's README.md and every .py in the lesson dir completely (cat -n the code so excerpts can cite line ranges), then read the old slides.md. Also read AGENTS.md (conventions, "Real output only", voice). Keep a copy of the old deck (cp to /tmp).
2. Audit the old deck slide by slide: list what is stale (old code, old names such as reply/task, old line counts), what is not in the lesson at all (invented claims, e.g. product lists, "five primitives" recaps, "of 4" counts), paraphrases that change meaning, and wrong order. The README is the source of truth; the deck follows the README's order: opening, worked example (code, then one slide per piece the README explains), Run it (command, real output, one slide per field), Going further (list, product, fuller file, its pieces, its run), What to take away (rule, never-does, what's missing with the diagram, next).
3. Rewrite the deck keeping the Marp front matter, header, style block and `<!-- _class: title -->` first and last slides exactly. One idea per slide, exactly one `#` heading per slide. Reuse README wording for claims.
4. Code on slides must be exact source lines: pull them with python from the .py file or README by line range (R[a-1:b]) instead of retyping. No `...` inside a code block; use contiguous ranges, or several small blocks on one slide. For long lines add `<style scoped>\npre code { white-space: pre-wrap; font-size: 0.7em; }\n</style>` at the top of that slide (display wraps, text unchanged). Real output may be shown only as exact README lines; say when shortened.
5. Write the deck in several appends (cat >> with heredoc or python) because a response is capped at 16384 tokens.
6. Run the checker (script below) from the repo root: `python3 /tmp/check_deck.py lessons/NN-name`. Hard failures (code line not in source, number not in source, empty slide, headings != 1) must be zero; fix every "PROSE NOT IN README", "OUT OF ORDER" by using README wording or move the slide. Remaining hits that are only punctuation splits or disclosures (e.g. "signature shortened") are acceptable; justify them. The title slide legitimately has 2 headings.
7. Render check: `npx --yes @marp-team/marp-cli <deck> -o /tmp/out.html` works offline; count `<section` equals slides. PNG export fails (no browser), so overflow cannot be seen: say so.
8. Tell the user what changed: stale code/names, removed claims, fixed wording, reordering, splits, additions, and what could not be verified. Do not touch other decks or README warnings unless asked (README line "decks ... made from an earlier 48-line version" and the AGENTS.md to-do stay until all four decks are done).
9. Checker script (save to /tmp/check_deck.py; recreate if missing):

```python
#!/usr/bin/env python3
"""usage: check_deck.py <lesson_dir>   (e.g. lessons/01-model-interface)
Audits <lesson_dir>/slides.md against README.md and the lesson's .py files."""
import re, sys, glob, os
d = sys.argv[1]
readme = open(f"{d}/README.md").read()
code = {os.path.basename(f): open(f).read() for f in glob.glob(f"{d}/*.py")}
src_lines = set()
for t in [readme, *code.values()]: src_lines |= set(t.splitlines())
def norm(s): return re.sub(r"\s+", " ", re.sub(r"[*`_]|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", s)).strip().lower()
R = norm(readme)
deck = open(f"{d}/slides.md").read()
body = deck.split("\n---\n", 1)[1]                       # after front matter
def split_slides(text):                                  # '---' inside a code fence is not a separator
    out, cur, fence = [], [], False
    for l in text.split("\n"):
        if l.startswith("```"): fence = not fence
        if l == "---" and not fence: out.append("\n".join(cur)); cur = []
        else: cur.append(l)
    out.append("\n".join(cur)); return out
slides = split_slides("\n" + body)
bad = 0; last = -1
for n, s in enumerate(slides, 1):
    s = re.sub(r"<!--.*?-->|<style.*?</style>", "", s, flags=re.S)
    heads = re.findall(r"^#{1,6} .*", re.sub(r"```.*?```", "", s, flags=re.S), re.M)
    if not s.strip(): print(f"slide {n}: EMPTY"); bad += 1; continue
    if len(heads) != 1: print(f"slide {n}: {len(heads)} headings"); bad += 1
    fences = re.findall(r"```(\w*)\n(.*?)```", s, re.S)
    for lang, blk in fences:
        for l in blk.splitlines():
            if l.strip() and l not in src_lines and norm(l) not in R:
                print(f"slide {n}: CODE LINE NOT IN SOURCE: {l[:90]}"); bad += 1
    prose = re.sub(r"```.*?```", "", s, flags=re.S)
    for l in prose.splitlines():
        if l.startswith("#"): continue                      # titles are labels, not claims
        l = re.sub(r"^([-*]|\d+\.)\s+", "", l.strip())
        if not l: continue
        for sent in re.split(r"(?<=[.!?:])\s+", l):
            k = norm(sent).rstrip(".:")
            if not k: continue
            pos = R.find(k, max(0, last - 20))
            if pos >= 0: last = pos
            elif R.find(k) >= 0: print(f"slide {n}: OUT OF ORDER: {sent[:80]}")
            else: print(f"slide {n}: PROSE NOT IN README (review): {sent[:100]}")
    for num in re.findall(r"\b\d[\d,_]*\b", prose):
        if num not in readme and not any(num in c for c in code.values()): print(f"slide {n}: NUMBER {num} NOT IN SOURCE"); bad += 1
print(f"{len(slides)} slides checked; hard failures: {bad}")
```
10. Method that worked for Lesson 2 (and pitfalls): write a small python generator (/tmp/g/gen.py) that loads each .py and README into line lists and builds slides with helper C(file, (a,b), ...) returning fenced blocks from exact 1-based line ranges; one slide per README sentence group, in README order. Pitfalls: (a) README line ranges for output blocks must stop before the closing fence, or the unclosed fence swallows later slides (symptom: Marp section count < slide count; compare `<h1` titles to the deck's titles); (b) quote README sentences with the README's own lead words (e.g. "`# ── input ──` gathers what goes to the model."), because a generic phrase can match a later README sentence (the rule at the end) and make every following slide "OUT OF ORDER"; (c) keep README's order for definitions (Input, Output, then the afferent/efferent sentence); (d) don't split one README sentence across slides in a different order; (e) the title slide is subtitle "A hands-on course in building agents by building their harness" plus "Lesson N" (no "of 4"), last slide "Next: <lesson>" plus "Lesson N+1", matching the Lesson 1 deck; (f) checker leftovers that are fine: title slide 2 headings, "(Shortened: ...)" disclosures, and sentences with a [`file.py`](./file.py) link (link-stripping artifact).
11. Lessons 2-4 pitfalls (Lesson 4 deck, 110 slides): (a) the generator must read the Marp front matter from the saved /tmp copy of the old deck, never from the deck it overwrites (a second run otherwise loses the closing `---` and duplicates the title slide), and write `head + "\n---\n\n" + slides joined by "\n\n---\n\n"`; (b) README line ranges for code and output exclude the fence lines (check with `cat -n`); (c) helper P(n, start, next_start) slices a README line by phrases, so prose is copied, never retyped; drop the bold lead (`**Working memory.**`) into the slide title; strip relative links `[x](./x)` but external links may stay; (d) outputs containing `---` (skill files) need the fence-aware checker above; (e) split any slide whose code is over about 14 lines after wrapping (check lines // 95) into contiguous ranges with their own titles; (f) the shell is sh, so no `<( )` process substitution; (g) context.py line n corresponds to README line n+479 in Lesson 4; (h) last slide for Lesson 4 is "Next: Observability" / "Lesson 5", after a slide with the README's closing sentence.
