# presentation

Slidev deck walking the building-agents curriculum end to end — from the top-level README's framing through Module 10.

## Run

```bash
cd presentation
npm install
npm run dev
```

Opens at `http://localhost:3030`.

## Build static site

```bash
npm run build
```

Output lands in `presentation/dist/`.

## Export to PDF

```bash
npm run export
```

Requires Playwright Chromium (Slidev prompts to install on first run).

## Edit

Everything is in [`slides.md`](./slides.md). Slides are separated by `---`. Per-slide frontmatter (layout, transition) sits between `---` blocks.

Theme: Slidev `default`. Code highlighter: Shiki.
