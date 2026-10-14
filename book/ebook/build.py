# Builds book/Building-Agents.pdf from book/*.md. From the repo root:
#   uv run --with markdown --with pypdf book/ebook/build.py book book/Building-Agents.pdf
# Fonts: Source Serif 4 and Inter (SIL Open Font License), from Google Fonts.
# Builds the Building Agents e-book: book/*.md → front.html + body.html → PDFs (via print.js) → one PDF with bookmarks.
# Usage: uv run --with markdown --with pypdf build.py BOOK_DIR OUT_PDF
import glob, html, json, os, re, subprocess, sys
import markdown
from pypdf import PdfReader, PdfWriter

BOOK, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "tmp"); os.makedirs(TMP, exist_ok=True)

CSS = """
@page { size: 6in 9in; margin: 0.8in 0.75in 0.85in 0.75in; }
@page cover { margin: 0; }
:root { --ink: #1d1d1f; --soft: #5b5b60; --rule: #d9d6cf; --accent: #8a3b12; --paper: #ffffff; }
html { background: var(--paper); }
body { font-family: 'Source Serif 4', Georgia, serif; font-size: 10.6pt; line-height: 1.5; color: var(--ink);
       margin: 0; hyphens: auto; -webkit-hyphens: auto; text-rendering: optimizeLegibility; }
p { margin: 0 0 0.62em; text-align: justify; orphans: 2; widows: 2; }
h1, h2, h3, h4, .sans { font-family: 'Inter', 'DejaVu Sans', sans-serif; }
a { color: inherit; text-decoration: none; border-bottom: 0.5pt solid var(--rule); }
strong { font-weight: bold; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 0.8em; background: #f3f1ec; padding: 0.05em 0.25em; border-radius: 2px; }
blockquote { margin: 0.8em 0 1em; padding: 0.5em 0.9em; border-left: 2pt solid var(--accent); background: #faf8f4; break-inside: avoid; }
blockquote p { text-align: left; margin: 0 0 0.3em; }
blockquote p:last-child { margin-bottom: 0; }
ul, ol { margin: 0 0 0.8em; padding-left: 1.3em; }
li { margin: 0 0 0.3em; }
li p { margin: 0; text-align: left; }
table { width: 100%; border-collapse: collapse; margin: 0.9em 0 1.1em; font-size: 8.4pt; line-height: 1.35; break-inside: avoid; }
th, td { text-align: left; vertical-align: top; padding: 0.35em 0.45em; border-bottom: 0.5pt solid var(--rule); }
th { font-family: 'Inter', sans-serif; font-weight: 600; font-size: 7.6pt; letter-spacing: 0.02em; color: var(--soft); border-bottom: 0.8pt solid var(--ink); }
pre { font-family: 'DejaVu Sans Mono', monospace; font-size: 7pt; line-height: 1.42; background: #f6f4ef; border-left: 2pt solid #d9d6cf;
      padding: 0.6em 0.75em; margin: 0.6em 0 1em; white-space: pre-wrap; tab-size: 4; overflow-wrap: anywhere; break-inside: avoid; }
.ln { display: block; min-height: 1.42em; }
pre code { background: none; padding: 0; font-size: 1em; border-radius: 0; }
figure { margin: 1em 0 1.2em; break-inside: avoid; }
figure img { width: 100%; display: block; }
figcaption { font-size: 8.4pt; line-height: 1.4; color: var(--soft); margin-top: 0.5em; font-style: italic; }
.chapter-body h2 { font-size: 13pt; font-weight: 600; margin: 1.6em 0 0.6em; break-after: avoid; }
td code, th code { font-size: 0.86em; }
thead { display: table-header-group; }
tr, td, th { break-inside: avoid; }
h2, h3, h4, .chapter-head { break-after: avoid; }
figure, blockquote, pre, table { break-before: auto; }
hr { border: 0; border-top: 0.5pt solid var(--rule); margin: 1.4em 0; }

/* chapters */
.chapter { break-before: page; }
.chapter-head { padding-top: 0.9in; margin-bottom: 1.6em; }
.chapter-num { font-family: 'Inter', sans-serif; font-size: 8pt; letter-spacing: 0.22em; text-transform: uppercase; color: var(--accent); margin-bottom: 0.7em; }
.chapter-title { font-family: 'Inter', sans-serif; font-weight: 600; font-size: 22pt; line-height: 1.12; letter-spacing: -0.01em; margin: 0; }
.chapter-rule { width: 2.2em; border-top: 1.5pt solid var(--accent); margin-top: 1em; }
h3 { font-size: 11pt; font-weight: 600; margin: 1.5em 0 0.5em; break-after: avoid; }
h4 { font-size: 10pt; font-weight: 600; margin: 1.2em 0 0.4em; break-after: avoid; }
h3 + p, h4 + p { break-before: avoid; }

/* parts */
.part { break-before: page; break-after: page; height: 7.2in; display: flex; flex-direction: column; justify-content: center; text-align: center; }
.part-num { font-family: 'Inter', sans-serif; font-size: 9pt; letter-spacing: 0.3em; text-transform: uppercase; color: var(--accent); }
.part-title { font-family: 'Inter', sans-serif; font-weight: 300; font-size: 28pt; margin: 0.35em 0 0; }
.part-rule { width: 3em; border-top: 1pt solid var(--ink); margin: 1.1em auto 0; }

/* front matter */
.cover { page: cover; break-after: page; position: relative; width: 6in; height: 9in; margin: 0; padding: 0; background: #14161a; color: #f4efe6; overflow: hidden; }
.cover-inner { position: absolute; left: 0.7in; right: 0.7in; top: 1.35in; }
.cover-kicker { font-family: 'Inter', sans-serif; font-size: 8pt; letter-spacing: 0.32em; text-transform: uppercase; color: #d98a52; }
.cover-title { font-family: 'Inter', sans-serif; font-weight: 700; font-size: 44pt; line-height: 0.98; letter-spacing: -0.02em; margin: 0.35em 0 0; }
.cover-sub { font-family: 'Source Serif 4', serif; font-style: italic; font-size: 13pt; line-height: 1.4; color: #cfc8bc; margin-top: 0.9em; max-width: 3.9in; }
.cover-author { position: absolute; left: 0.7in; bottom: 0.8in; font-family: 'Inter', sans-serif; font-size: 10pt; letter-spacing: 0.06em; }
.cover-author span { display: block; color: #9a9389; font-size: 8pt; letter-spacing: 0.12em; text-transform: uppercase; margin-top: 0.4em; }
.cover-loop { position: absolute; right: -1.1in; top: 4.1in; width: 4.6in; height: 4.6in; }
.titlepage { break-after: page; height: 7.2in; display: flex; flex-direction: column; justify-content: center; text-align: center; }
.titlepage h1 { font-family: 'Inter', sans-serif; font-weight: 700; font-size: 30pt; margin: 0; letter-spacing: -0.01em; }
.titlepage .sub { font-style: italic; color: var(--soft); margin-top: 0.6em; font-size: 11.5pt; }
.titlepage .by { font-family: 'Inter', sans-serif; margin-top: 2.6em; font-size: 10pt; letter-spacing: 0.06em; }
.titlepage .lab { font-family: 'Inter', sans-serif; color: var(--soft); font-size: 8pt; letter-spacing: 0.14em; text-transform: uppercase; margin-top: 0.4em; }
.copyright { break-after: page; height: 7.2in; display: flex; flex-direction: column; justify-content: flex-end; font-size: 8.2pt; color: var(--soft); line-height: 1.5; }
.copyright p { text-align: left; margin-bottom: 0.7em; }
.toc { break-after: page; }
.toc h2 { font-family: 'Inter', sans-serif; font-weight: 600; font-size: 20pt; margin: 0.15in 0 0.7em; }
.toc-part { font-family: 'Inter', sans-serif; font-size: 7.4pt; letter-spacing: 0.2em; text-transform: uppercase; color: var(--accent); margin: 0.6em 0 0.15em; }
.toc-row { display: flex; align-items: baseline; font-size: 9.2pt; margin: 0.02em 0; }
.toc-row .n { width: 1.7em; color: var(--soft); font-family: 'Inter', sans-serif; font-size: 8.5pt; }
.toc-row .t { flex: 0 1 auto; }
.toc-row .dots { flex: 1; border-bottom: 0.6pt dotted #b9b4aa; margin: 0 0.4em; transform: translateY(-0.25em); }
.toc-row .p { font-family: 'Inter', sans-serif; font-size: 8.5pt; color: var(--soft); }
.preface h2 { font-family: 'Inter', sans-serif; font-weight: 600; font-size: 20pt; margin: 0.15in 0 0.8em; }
.preface { break-after: page; }
.marker { position: absolute; font-size: 3px; color: #fff; }
"""

LOOP_SVG = """<svg class="cover-loop" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<circle cx="100" cy="100" r="78" fill="none" stroke="#d98a52" stroke-width="1.2" stroke-dasharray="2 5" opacity=".75"/>
<circle cx="100" cy="100" r="54" fill="none" stroke="#f4efe6" stroke-width=".6" opacity=".35"/>
<circle cx="100" cy="100" r="16" fill="#d98a52" opacity=".9"/>
<circle cx="100" cy="22" r="5" fill="#f4efe6"/><circle cx="167.5" cy="139" r="5" fill="#f4efe6"/><circle cx="32.5" cy="139" r="5" fill="#f4efe6"/>
</svg>"""

def md(text):
    text = re.sub(r"\\>", "&gt;", text)
    out = markdown.markdown(text, extensions=["tables", "sane_lists", "fenced_code"])
    out = out.replace('src="figures/', 'src="file://' + os.path.join(os.path.abspath(BOOK), "figures") + '/')   # figures, from the book's folder
    out = re.sub(r"<pre><code([^>]*)>(.*?)</code></pre>", lambda m: "<pre><code" + m[1] + ">" + "".join(
        f'<span class="ln" style="padding-left:{len(line) - len(line.lstrip(" ")) + 4}ch;text-indent:-{len(line) - len(line.lstrip(" ")) + 4}ch">{line}</span>'
        for line in m[2].rstrip("\n").split("\n")) + "</code></pre>", out, flags=re.S)   # wrapped lines hang
    return re.sub(r"<p>(<img [^>]+>)</p>\s*<p><em>(.+?)</em></p>", r'<figure>\1<figcaption>\2</figcaption></figure>', out, flags=re.S)

files = sorted(glob.glob(os.path.join(BOOK, "[0-9][0-9]-*.md"))) + sorted(glob.glob(os.path.join(BOOK, "[A-Z]-*.md")))
chapters, parts = [], []
body = []
for f in files:
    src = open(f).read()
    m = re.match(r"# (Part [IVX]+): (.+)\n", src)
    if m:
        parts.append((m[1], m[2], len(chapters)))
        body.append(f'<section class="part"><div class="marker">@@PART{len(parts)}@@</div><div class="part-num">{m[1]}</div>'
                    f'<div class="part-title">{html.escape(m[2])}</div><div class="part-rule"></div></section>')
        src = src[m.end():]
    h = re.match(r"\s*## (\d+)\. (.+)\n", src) or re.match(r"\s*# Appendix ([A-Z]): (.+)\n", src)
    num, title = h[1], h[2]
    rest = src[h.end():]
    if num == "A":                                       # the appendices get a part page of their own
        parts.append(("Appendices", "Reference", len(chapters)))
        body.append(f'<section class="part"><div class="marker">@@PART{len(parts)}@@</div><div class="part-num">Appendices</div>'
                    f'<div class="part-title">Reference</div><div class="part-rule"></div></section>')
    chapters.append((num, title))
    label = f"Appendix {num}" if num.isalpha() else f"Chapter {num}"
    body.append(f'<section class="chapter"><div class="chapter-head"><div class="marker">@@CH{num}@@</div>'
                f'<div class="chapter-num">{label}</div><h2 class="chapter-title">{html.escape(title)}</h2>'
                f'<div class="chapter-rule"></div></div><div class="chapter-body">{md(rest)}</div></section>')

def page(content, title="Building Agents"):
    fonts = "file://" + os.path.join(HERE, "fonts", "fonts.css")
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><link rel="stylesheet" href="{fonts}"><title>{title}</title><style>{CSS}</style></head><body>{content}</body></html>'

open(os.path.join(TMP, "body.html"), "w").write(page("".join(body)))

readme = open(os.path.join(BOOK, "README.md")).read()
preface = readme.split("## Preface", 1)[1].split("---", 1)[0]

def front(pages):
    toc = ['<section class="toc"><h2>Contents</h2>',
           f'<div class="toc-row"><span class="n"></span><span class="t">Preface</span></div>']
    part_at = {start: (pn, pt) for pn, pt, start in parts}
    for i, (num, title) in enumerate(chapters):
        if i in part_at:
            pn, pt = part_at[i]
            toc.append(f'<div class="toc-part">{pn} · {html.escape(pt)}</div>')
        toc.append(f'<div class="toc-row"><span class="n">{num}</span><span class="t">{html.escape(title)}</span>'
                   f'<span class="dots"></span><span class="p">{pages.get(num, "")}</span></div>')
    toc.append("</section>")
    return page(f"""
<section class="cover"><div class="cover-inner"><div class="cover-kicker">From nothing to an agent</div>
<div class="cover-title">Building<br>Agents</div>
<div class="cover-sub">From nothing to a model, a harness, and a model trained in its harness</div></div>
{LOOP_SVG}
<div class="cover-author">Chase Dovey<span>Average Joes Lab</span></div></section>
<section class="titlepage"><h1>Building Agents</h1><div class="sub">From nothing to a model, a harness,<br>and a model trained in its harness</div>
<div class="by">Chase Dovey</div><div class="lab">Average Joes Lab</div></section>
<section class="copyright">
<p><strong>Building Agents</strong><br>From nothing to a model, a harness, and a model trained in its harness<br>First edition</p>
<p>By Chase Dovey · Average Joes Lab<br>cdovey.dev · github.com/averagejoeslab</p>
<p>Every number, quote and result in this book comes from a real run, kept with the code in the building-agents repository: github.com/averagejoeslab/building-agents.</p>
<p>Data sources named in the text keep their own licences: tldr-pages (CC BY 4.0), smol-smoltalk (Apache 2.0), GSM8K (MIT), Hermes function-calling (Apache 2.0), Magicoder OSS-Instruct (MIT), NL2Bash (research data). Qwen3-0.6B and Qwen3-0.6B-Base are released by the Qwen team.</p>
</section>
{"".join(toc)}
<section class="preface"><div class="marker">@@PREFACE@@</div><h2>Preface</h2>{md(preface)}</section>
""")

def render(html_name, pdf_name, numbered, start=1):
    subprocess.run(["node", os.path.join(HERE, "print.js"), os.path.join(TMP, html_name), os.path.join(TMP, pdf_name),
                    "1" if numbered else "0", str(start)], check=True)

def find_markers(pdf):
    found = {}
    for i, p in enumerate(PdfReader(pdf).pages):
        for mk in re.findall(r"@@(PART\d+|CH\w+?|PREFACE)@@", p.extract_text() or ""):
            found.setdefault(mk, i)
    return found

# pass 1: front matter (to count its pages), body (to find where chapters start)
open(os.path.join(TMP, "front.html"), "w").write(front({}))
render("front.html", "front.pdf", False)
render("body.html", "body.pdf", True)
front_n = len(PdfReader(os.path.join(TMP, "front.pdf")).pages)
marks = find_markers(os.path.join(TMP, "body.pdf"))
fmarks = find_markers(os.path.join(TMP, "front.pdf"))
pages = {num: marks[f"CH{num}"] + 1 for num, _ in chapters}
pages["preface"] = ""                                    # front matter: unnumbered
# pass 2: front matter with page numbers
open(os.path.join(TMP, "front.html"), "w").write(front(pages))
render("front.html", "front.pdf", False)
assert len(PdfReader(os.path.join(TMP, "front.pdf")).pages) == front_n, "contents changed the front matter's length"

w = PdfWriter()
for name in ["front.pdf", "body.pdf"]:
    for p in PdfReader(os.path.join(TMP, name)).pages:
        w.add_page(p)
w.add_outline_item("Cover", 0)
w.add_outline_item("Contents", 3)
if "PREFACE" in fmarks: w.add_outline_item("Preface", fmarks["PREFACE"])
part_at = {start: (pn, pt, k + 1) for k, (pn, pt, start) in enumerate(parts)}
parent = None
for i, (num, title) in enumerate(chapters):
    if i in part_at:
        pn, pt, k = part_at[i]
        parent = w.add_outline_item(f"{pn}: {pt}", front_n + marks[f"PART{k}"])
    w.add_outline_item(f"{num}. {title}" if num.isdigit() else f"Appendix {num}: {title}", front_n + marks[f"CH{num}"], parent=parent)
w.add_metadata({"/Title": "Building Agents", "/Author": "Chase Dovey",
                "/Subject": "From nothing to a model, a harness, and a model trained in its harness"})
w.page_mode = "/UseOutlines"
with open(OUT, "wb") as fh: w.write(fh)
print(json.dumps({"front_pages": front_n, "body_pages": len(PdfReader(os.path.join(TMP, 'body.pdf')).pages), "chapter_pages": pages}))
