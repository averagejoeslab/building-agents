# building-agents rebuild spec

A planning document for the reframe of this repo around **harness engineering** as the consolidating 2026 terminology for what the curriculum actually teaches.

---

## Goal

Reframe building-agents so its terminology matches what the modules actually build, and so a reader immediately understands:

1. **Model development** — training/fine-tuning the model itself. *(Out of scope.)*
2. **Harness engineering** — the runtime around a model that turns it into an autonomous agent. ***(What this repo teaches.)***
3. **Agentic engineering** — the broader practice of using agents to build products, software, and workflows.

The substance of the curriculum does not change. The framing does.

## Why now

The term "harness" has consolidated as the industry name for "everything around the model that makes it an agent." Verified sources:

- Anthropic Engineering — *Effective harnesses for long-running agents* (2025-11-26)
- Anthropic Engineering — *Harness design for long-running application development* (2026-03-24)
- LangChain — *The Anatomy of an Agent Harness* (2026-03-10) — gives the formula `Agent = Model + Harness`.
- Martin Fowler / Birgitta Böckeler — *Harness engineering for coding agent users* (2026-04-02).
- Addy Osmani — *Agent Harness Engineering* (2026-04-19).
- O'Reilly Radar — Addy Osmani — *Agent Harness Engineering* (2026-05-15).
- Anthropic product — **Claude Managed Agents** — explicitly positions itself as *"the harness and infrastructure for running Claude as an autonomous agent."*

These sources converge on:

> **Agent = Model + Harness.** The harness is every piece of code, configuration, and execution logic that isn't the model itself — state, tools, execution, feedback loops, constraints, observability.

The building-agents modules are an *exact enumeration* of harness components. Adopting the term is not a rebrand toward something contested — it's aligning with the term that already won.

## The new mental model

```
┌──────────────────────────────────────────────────────────┐
│  AGENTIC ENGINEERING                                     │
│  The practice of using agents to build software.         │
│  (You doing this work with Claude Code is this.)         │
├──────────────────────────────────────────────────────────┤
│  HARNESS ENGINEERING                  ← this repo        │
│  The runtime around a model.                             │
│  Control flow, memory, tools, sandbox, guardrails,       │
│  observability, evals, performance.                      │
├──────────────────────────────────────────────────────────┤
│  MODEL DEVELOPMENT                    ← out of scope     │
│  Training and fine-tuning the model.                     │
└──────────────────────────────────────────────────────────┘
```

One-line:

> A model is intelligence. A harness is the runtime that turns intelligence into an agent. Agentic engineering is the practice of using those agents to build software.

## What changes

### Root `README.md`

- **Title/intro**: reframe as a harness-engineering curriculum that sits inside agentic engineering.
- **New section: "The three layers"** — mental model with the stack.
- **New section: "What is harness engineering?"** — `Agent = Model + Harness`. The existing 9-bullet discipline list moves here, correctly labelled.
- **Reframe section: "What is agentic engineering?"** — recast as the broader practice; harness engineering is its substrate.
- **New section: "Scope"** — explicit `✓ / ✗` of what's covered and what isn't.
- **Keep**: agentic systems, workflows-vs-agents, workflow/agent patterns, purist stance, "what agents look like", setup, content table, license.
- **New section: "Built using a harness"** — meta note that this repo is being built with Claude Code (a coding-agent harness) running on a model. Live illustration of all three layers.
- **Content table**: add a "Harness component" column.

### Every module README (`modules/01-` through `modules/10-`)

- Add a short anchor line in the intro naming the **harness component** the module builds.
- Keep all code, diagrams, and pedagogy unchanged.

| # | Module | Harness component |
|---|---|---|
| 1 | What is an agent? | (concept — defines Model + Harness, names the three primitives) |
| 2 | An LLM call | **Model interface** — the harness's one external dependency |
| 3 | Add a loop | **Control flow** — the body that runs the model continuously |
| 4 | Add memory | **Memory + context management** — what the harness persists, prunes, recalls |
| 5 | Add tools | **Tool/action layer** — how the harness gives the model effects on the world |
| 6 | Add sandboxing | **Execution environment** — where dangerous tools run safely |
| 7 | Add guardrails | **Safety constraints** — approval gates, loop bounds, retry |
| 8 | Add observability | **Structured tracing** — what the harness reports about its own activity |
| 9 | Add evaluation | **Test infrastructure** — how you measure whether your harness produces a good agent |
| 10 | Add performance | **Production hardening** — caching, threading, structured prompts, `assemble()` |

### `examples/README.md`

- Open paragraph relabels the checkpoints as harness builds (each script is a harness at a different stage of construction).
- Table gains a "Harness component" column matching the module list.

### `evals/README.md`

- Slim language update to call this the "harness test harness" — a harness for testing the harness you built.

### `presentation/` deck

- **Slide rename**: "What is agentic engineering?" → "The three layers". Render via existing `Radial` component but with the new center label or replace with a stacked-layer diagram.
- **New slide**: "What is harness engineering?" — `Agent = Model + Harness` callout + the 9-component list (using the existing radial structure with relabeled center).
- **Discipline slide reposition**: same 9 spokes, center label changes from "Agentic Engineering" → "Harness Engineering". Subtitle clarifies this is the practice substrate.
- **Module title slides**: each "Module N — X" gets the "harness component" anchor line that matches the README.
- **Closing slide**: update "what's next" framing to acknowledge harness engineering as the curriculum's name.

### Code & checkpoints

**No changes.** All Python, all diagrams, all `examples/*.py`, all `presentation/src/components/*.tsx` stay as-is. Pedagogy line stays. The "agents vs workflows" framing stays — that's still about *control-flow shape inside a harness*.

## Implementation order

1. Write `spec.md` *(this file)*. ✓
2. Rewrite root `README.md` end to end.
3. Add the harness-component anchor line to each of modules 1–10.
4. Update `examples/README.md`.
5. Update `evals/README.md`.
6. Update presentation:
   - `src/slides/01-orientation.tsx` — replace `DisciplineSlide` with three-layer + harness slide.
   - `src/slides/02-what-is-an-agent.tsx` — adjust intro framing.
   - `src/slides/05-closing.tsx` — update closing copy.
   - `Deck.tsx` — wire in new slide(s) if needed.
7. Build presentation (`npm run build`) to verify clean.
8. Single commit + push.
9. Delete `spec.md` *(or keep it as the historical reframe record — TBD).*

## Out of scope for this rebuild

- **No code changes** to `examples/*.py`. The harnesses already exist; the relabel is a documentation change.
- **No new modules**. The 10-module structure is correct.
- **No structural moves**. Directories stay where they are.
- **No mass renames** to file names (the checkpoint filenames already describe what each is).

## Acceptance criteria

A reader who skims the root README in 60 seconds should leave knowing:

1. This repo teaches **harness engineering**.
2. That work sits inside **agentic engineering**.
3. **Model development** is a separate layer the repo doesn't cover.
4. The 10 modules each build one component of the harness.
5. The end state is a production-shaped coding-agent harness.

A reader who skims a single module's intro paragraph should know which **harness component** that module adds, regardless of whether they read M1.
