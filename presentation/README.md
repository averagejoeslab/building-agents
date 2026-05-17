# presentation

Spectacle intro deck for the [building-agents](../) curriculum. Covers the orientation material plus Modules 1-3 (what is an agent → an LLM call → add a loop).

About 22 slides total. Designed for a 25-30 minute talk that introduces the agent concept and lands on the chatbot before tools come in.

## Develop

```bash
cd presentation
npm install
npm run dev
```

The deck opens at `http://localhost:5173`. Spectacle keyboard nav:

- `→` / `Space` — next slide
- `←` — previous slide
- `O` — overview mode
- `Alt-P` — presenter mode (notes)
- `F` — fullscreen

## Build

```bash
npm run build
```

Outputs a static SPA to `dist/`. Deploy anywhere — GitHub Pages, Vercel, Netlify, a tarball.

## Structure

```
src/
  main.tsx              # React entry
  Deck.tsx              # composes the slide order
  theme.ts              # colors, fonts, sizes
  components/
    Mermaid.tsx         # renders mermaid diagrams inline
  slides/
    00-cover.tsx
    01-orientation.tsx          # what is agentic engineering, workflows vs agents
    02-what-is-an-agent.tsx     # Module 1
    03-llm-call.tsx             # Module 2
    04-add-a-loop.tsx           # Module 3
    05-closing.tsx              # roadmap + thanks
```

## Code stays in sync with the curriculum

The slides import the actual `examples/llm_call_sync.py`, `examples/llm_call_async.py`, and `examples/stateless_chatbot.py` files via Vite's `?raw` loader:

```tsx
import chatbotCode from "@examples/stateless_chatbot.py?raw";

<CodePane language="python">{chatbotCode}</CodePane>
```

So when the example files change, the slides update on the next build. No copy-paste drift.

The `@examples` alias points at the sibling `../examples/` directory; see `vite.config.ts`.

## Adding more modules

Each module gets its own `src/slides/NN-name.tsx` file exporting a handful of slide components, then gets added to `Deck.tsx`'s composition. The pattern:

1. **Title card** — module number, headline, the "becomes" label
2. **Concept** — 2-4 bullet slides framing what this module adds
3. **Code reveal** — import the runnable checkpoint with `?raw` and show it in a `CodePane`
4. **Diagram** — Mermaid for any control-flow shape
5. **Bridge** — what's still missing, gestures at the next module

If you grow it past Module 3, the deck pattern scales linearly.
