---
name: render-marp-decks-to-pdf
description: make PDFs of Marp slide decks (slides.md) next to each deck and check that no slide overflows its page; fix overflow without changing slide text
---
1. Find a browser: `ls /opt/pw-browsers/*/chrome-linux/chrome` (or chromium/chrome on PATH); export CHROME_PATH to it. Marp CLI runs via `npx --yes @marp-team/marp-cli`, no install needed.
2. For each deck: `npx --yes @marp-team/marp-cli <dir>/slides.md --pdf -o <dir>/slides.pdf --allow-local-files`. Check `pdfinfo` page count equals the number of slides.
3. Check overflow in the PDF itself (not by measuring the HTML export, which lays code blocks out differently and gives wrong answers): `pdftotext -bbox <pdf> -`, per page ignore the page number (bottom right) and header; flag any word with yMax > 482pt or xMax > 901pt (page is 960x540pt, Marp padding 78px). Also pixel-check with `pdftoppm -r 48 -gray` for ink in the bottom band, right and left margins (tables and boxes).
4. Validate the checker on the pre-fix deck (render an original copy from git) so you know it catches overflow.
5. Fix only with a `<style scoped>` block at the top of the slide (`section { font-size: 24px; }`, `table { font-size: 0.7em; }`, for code set `pre { font-size: 0.6em; line-height: 1.25; }`, since pre line height follows the pre, not the code). Never change slide text. Re-render and recheck.
6. Beware: another process may commit work in the repo mid-session; compare against `git show HEAD~N:` rather than assuming HEAD is the original.
7. Note how the PDFs are regenerated in AGENTS.md (creator info), not in reader files.
