# building-agents

**Build your own agent by building the harness around a foundational model.** Agent = Model + Harness — and this repo teaches you how to construct the *harness* half end-to-end. Along the way it sets the record straight on three disciplines that the current industry hype keeps conflating: model development, harness engineering, and agentic engineering.

## Why I made this

I've spent a long time researching agentic systems, and a large portion of that work has been building harnesses — the runtimes that turn a model into an agent. Right now most of the industry conversation is a race to claim *the best harness*: every vendor, every framework, every newsletter pitching their loop, their memory layer, their tool registry as the one you should adopt.

My view is the opposite: **the best harness is the one you build yourself.** Not because the off-the-shelf ones are bad, but because a harness you constructed from primitives is one you understand — you know which trade-offs were made, you know which knobs exist, you know what to change when the model misbehaves. That understanding is what this repo is for.

It also gives me a chance to put down what I believe is the correct framing for what people mean (and often don't mean) when they say "agentic engineering."

## The three disciplines

The industry uses "agentic engineering" as a catchall for three distinct disciplines stacked on top of each other. They depend on each other, but they aren't the same skill.

- **Model development.** Training the foundational model itself. The work that produces GPT, Claude, Gemini, Llama. Done by a small number of labs with capital, GPUs, and data-pipeline expertise. The output is a model you can call by API.

- **Harness engineering.** Wrapping that model in code, state, tools, sandboxing, guardrails, observability, and a loop — everything required to turn intelligence into an agent. *Agent = Model + Harness.* This is the layer that produced Claude Code, Cursor, Devin, Aider.

- **Agentic engineering.** Using an agent — a model wrapped in a harness — to build software, products, infrastructure, or more agents. The agent stops being the artifact and becomes the tool you ship with.

This repo teaches the middle one. The other two are explained in depth below so you can place them.

## What an agentic system is

Before going into the three layers in depth, a brief grounding in what "agentic system" actually means — because the harness exists to *produce one*, and the shape of the system you're targeting determines what the harness has to do.

The idea comes from cognitive science: systems that can act on their own, without human intervention. In modern agentic systems, the agency is provided by an LLM coordinating calls to reach a goal without supervision.

### Two shapes: workflows and agents

In my opinion, agentic systems come in two forms, as defined in Anthropic's [*Building Effective Agents*](https://www.anthropic.com/engineering/building-effective-agents). The distinction is about *what shape the system's control flow takes*.

**Workflows** — LLMs and tools orchestrated through **predefined code paths**. Prescriptive code paths define the sequence of steps that will be taken to accomplish a goal.

```mermaid
flowchart LR
    In[Input] --> W1[LLM] --> W2[LLM] --> W3[LLM] --> Out[Output]
```

**Agents** — **LLMs dynamically direct their own path through the control flow**. The model decides the sequence of steps; no prescriptive code paths are followed and the model exercises its probability distribution to determine the next step.

```mermaid
flowchart LR
    In[Input] --> A1[LLM]
    A1 --> A2{Tool?}
    A2 -->|yes| A3[Execute] --> A1
    A2 -->|no| Out[Output]
```

### Common workflow patterns

**Prompt chaining** — LLM → LLM → LLM, fixed order. Example: outline → draft → polish.

```mermaid
flowchart LR
    In[Input] --> A[LLM 1] --> B[LLM 2] --> C[LLM 3] --> Out[Output]
```

**Routing** — Classify input → dispatch to one of N handlers. Example: support tickets routed to billing / technical / refunds.

```mermaid
flowchart LR
    In[Input] --> R[Router LLM]
    R --> H1[Handler A]
    R --> H2[Handler B]
    R --> H3[Handler C]
    H1 --> Out[Output]
    H2 --> Out
    H3 --> Out
```

**Parallelization** — Run N LLM calls in parallel → aggregate. Example: N perspectives on one question.

```mermaid
flowchart LR
    In[Input] --> A[LLM]
    In --> B[LLM]
    In --> C[LLM]
    A --> Agg[Aggregate]
    B --> Agg
    C --> Agg
    Agg --> Out[Output]
```

**Orchestrator-workers** — One LLM splits work → workers handle sub-tasks. Example: research report with multiple sections.

```mermaid
flowchart LR
    In[Input] --> O[Orchestrator LLM]
    O --> W1[Worker LLM]
    O --> W2[Worker LLM]
    O --> W3[Worker LLM]
    W1 --> S[Synthesize]
    W2 --> S
    W3 --> S
    S --> Out[Output]
```

**Evaluator-optimizer** — Generator → Evaluator → loop until good. Example: draft with a quality-gate loop.

```mermaid
flowchart LR
    In[Input] --> G[Generator LLM]
    G --> E[Evaluator LLM]
    E -->|good| Out[Output]
    E -->|refine| G
```

### The agent pattern

Workflows are a catalog of orchestration shapes. Agents are **one pattern** — an autonomous loop — and that's the whole list. What varies between agents in practice is the *harness around the model*: the environment, memory and context management, the toolkit, and whether one of the tools happens to be another agent.

**Autonomous agent** — an LLM in a loop with tools, choosing what to do next based on what it observes. This is the pattern this repo builds.

```mermaid
flowchart LR
    In[Input] --> LLM[LLM]
    LLM --> Q{Tool call?}
    Q -->|yes| Act[Execute tool<br/>+ observe result]
    Act --> LLM
    Q -->|no| Out[Output]
```

### Composition

By composing the above workflows and agent patterns, you can build multi-agent systems, multi-workflow systems, or systems that mix both.

> [!NOTE]
> **Whether to use multi-agent composition at all is a live disagreement in the field.** Anthropic embraces it ([multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system); Claude Code subagents). Cognition argues *against* it in [*Don't Build Multi-Agents*](https://cognition.ai/blog/dont-build-multi-agents), making the case for a single-threaded linear agent with shared context — citing reliability and debuggability. Cursor 2.0 takes a third path: parallel independent agents on separate Git worktrees, no supervisor. The right composition depends on whether sub-tasks share context, run in parallel, and need to surface partial state — there is no default answer.

### The Average Joes Lab stance: purist agents only

We believe in the [Anthropic model](https://www.anthropic.com/engineering/building-effective-agents): **a real agent has autonomy over its own control flow** where the model decides what tool to call, what to do with the result, and when the task is done. Building harnesses for purist agents is the focus of this repo.

Workflows are outside the scope of what follows.

```mermaid
flowchart LR
    A[Agent<br/>model decides] -->|freeze the path| W[Workflow<br/>code decides]
    W -.cannot derive.-> A
```

The primitives are the same — LLM calls, tools, context, memory. An agent's control flow is the model making those choices live; a workflow's control flow is you making them in advance. The building blocks transfer; how you orchestrate them into a fixed sequence is its own discipline.

For most production systems a workflow is more reliable, cheaper, and easier to evaluate — build a workflow if you can. But the interesting engineering problems — designing tools the model will use well, managing an open-ended context, making a non-deterministic loop reliable, evaluating a trajectory you can't enumerate — are agent problems.

### What agents look like

- **Coding agents** — [Claude Code](https://claude.com/claude-code), [Cursor](https://cursor.com), [Devin](https://devin.ai), [Aider](https://aider.chat), [nanoagent](https://github.com/averagejoeslab/nanoagent). The model opens files, edits them, runs tests, iterates.
- **Research agents** — [OpenAI Deep Research](https://openai.com/index/introducing-deep-research/), Claude's research mode. The model searches, synthesizes, digs deeper.
- **Task completion agents** — [SWE-agent](https://swe-agent.com), browser-use agents. The model manipulates a filesystem or GUI to complete a task.

In each case, the next action depends on what the previous action produced. The paths can't be enumerated in advance.

> [!IMPORTANT]
> Most systems marketed as "agents" in 2026 are workflows. That's often the right answer. This content is about the case when it isn't.

---

## The journey from nothing to agentic engineering, in depth

You now have a working picture of what an agentic system is. The rest of this README walks the three disciplines in order — model development → harness engineering → agentic engineering — so you can see how you actually get from *nothing* to *shipping software with agents you built*.

## 1. Model development (in depth)

The bottom of the stack. This repo doesn't teach model development — the harness assumes the model already exists and is consumed by API — but a one-page orientation grounds what the model layer actually contains.

### What a modern LLM is made of

A large language model is a probabilistic next-token predictor built from a small set of architectural primitives:

- **Tokenizer** — chops raw text into sub-word tokens via byte-pair encoding (BPE) or similar. Vocabularies are typically 30k–200k entries.
- **Token embeddings** — each token ID maps to a learned vector, often 2,048–16,384 dimensions in modern models.
- **Positional information** — added to the embeddings so the model knows token order (rotary position embeddings / RoPE, ALiBi, or learned position vectors).
- **The transformer block** — the workhorse. Each block contains **multi-head self-attention** (every token attends to every other token in the context), a **feed-forward network** (per-token nonlinear transformation, often with SwiGLU), **residual connections**, and **layer normalization** (RMSNorm is common). Modern frontier models stack 60–120 of these blocks.
- **The output head** — projects the final hidden state to a distribution over the vocabulary; the next token is sampled from that distribution.

### How a model is trained

```mermaid
flowchart LR
    A[Web-scale corpus<br/>trillions of tokens] --> B[Pretraining<br/>next-token prediction]
    B --> C[Base model]
    C --> D[Supervised fine-tuning<br/>instruction data]
    D --> E[Preference tuning<br/>RLHF / DPO]
    E --> F[Released model]
```

1. **Pretraining.** The expensive step. The model learns to predict the next token over a massive web-scale corpus (trillions of tokens). This is where it acquires syntax, facts, reasoning patterns, and a general sense of how language works. Thousands of GPUs, months of wall-clock time.
2. **Supervised fine-tuning (SFT).** Train on curated instruction/response pairs so the model learns to *follow instructions* rather than just continuing arbitrary text. Much smaller dataset, much smaller compute.
3. **Preference tuning (RLHF or DPO).** Train on human-rated comparisons of model outputs so the model learns what counts as a *good* response. This is where helpfulness, honesty, and safety behaviours are instilled.
4. **(Optional) Specialty fine-tuning.** Additional training on domain-specific data (code, math, tool use) for sharper task performance.

### Inference

Calling the model API runs a forward pass through every layer, producing a probability distribution over the vocabulary. A token is sampled — modulated by **temperature** (randomness), **top-k** (only the k highest-probability tokens), and **top-p / nucleus** (smallest set of tokens whose probabilities sum to p). Repeat until an end-of-sequence token or max length is reached.

### Why it's its own discipline

Model development requires distributed training infrastructure, data curation pipelines, dedicated evaluation suites, and capital that does not pencil out for most projects. Frontier-model training is a multi-billion-dollar effort. The harness layer above assumes that effort has happened upstream and the model is now a callable service.

**What you take away:** the model is a *callable substrate*. It can complete text. It cannot read files, run commands, remember anything across sessions, or stop when it's done. To get any of that, you need the next layer.

## 2. Harness engineering (in depth) — what this repo teaches

The middle layer. **This is what we build in this repo.** And we do it the only way the discipline really sticks: by building one harness end-to-end, from a single LLM call to a production-shaped runtime, one component at a time.

> **Agent = Model + Harness.**
> The harness is every piece of code, configuration, and execution logic that isn't the model itself — state, tools, execution, feedback loops, constraints, observability.

The discipline of harness engineering covers:

- **Selecting the model** — which model the harness wraps.
- **Building the control flow** — the loop that drives the model continuously.
- **Architecting memory** — what's remembered, when, and how it's retrieved.
- **Managing context** — the context window is a budget of tokens; what goes in, what gets evicted.
- **Designing tools** — what capabilities the harness exposes, at what granularity, with what error semantics.
- **Handling safety / guardrails** — sandboxing, approval gates, loop bounds, input/output detection.
- **Setting up observability** — structured traces of every LLM call, tool call, and state transition.
- **Building evaluations** — benchmarking the harness's behaviour and catching regressions.
- **Optimizing the system** — prompt caching, tool caching, threading, structured prompts.

Each of these is one module in this curriculum. The modules build cumulatively — every checkpoint in [`examples/`](./examples/) is a runnable harness at a different stage of construction.

> [!NOTE]
> The term *harness* in this sense was consolidated through 2025–2026 by Anthropic ([effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents); [harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)), LangChain ([*The Anatomy of an Agent Harness*](https://www.langchain.com/blog/the-anatomy-of-an-agent-harness)), Martin Fowler ([Birgitta Böckeler, *Harness engineering for coding agent users*](https://martinfowler.com/articles/harness-engineering.html)), [Addy Osmani](https://addyosmani.com/blog/agent-harness-engineering/), and [O'Reilly Radar](https://www.oreilly.com/radar/agent-harness-engineering/). The framing has converged: harness = everything except the model.

**What you take away:** once you've stacked these nine components around a model, you have an *agent* — something that can run on its own, take actions, recover from mistakes, and stop when it's done. That agent is now a tool. The next discipline is about using it.

## 3. Agentic engineering (in depth)

The top layer. Once you've built an agent — a model wrapped in a harness — what do you do with it? Two things, both called agentic engineering.

### Use the agent to keep developing itself

Point the agent at the curriculum it was built from. Have it write a new module. Have it refactor one of the harness components. Have it improve its own tracing, tighten its own evals, raise its own performance. The harness becomes its own development tool.

The recursive nature is the point: this repo is itself being built using Claude Code — a coding-agent harness — running on Claude. The author drives that agent to write modules, build the deck, ship commits. Every layer of the stack is visible in the act of producing the repo:

1. Anthropic does **model development** to produce Claude.
2. The Claude Code team does **harness engineering** to build Claude Code.
3. The author does **agentic engineering** to build this curriculum *using* that agent.

What this curriculum teaches you is how to do step 2 — so you can do steps 1 and 3 with intent, knowing what each layer contains.

### Use the agent to develop other products

The more visible flavor of agentic engineering: take the agent and point it at the next codebase. Ship features. Build infrastructure. Author tooling.

A concrete example: **Peter Steinberg built [openclaw](#) by directing existing coding agents to produce most of its implementation.** He didn't write every line — he directed agents to write them. And once openclaw was working, he embedded an agent harness *inside* the project itself, so openclaw users get an agent as part of the product. Two halves of agentic engineering captured in one project: agents produced the artifact, and the artifact ships with an agent.

That's the shape of mature agentic engineering: it compounds. Each agent you build with becomes a building block for the next thing. Each thing you ship can itself include an agent.

If "vibe coding" (Karpathy's term) is the casual end of this — *give in to the vibes, accept what the model produces* — agentic engineering is the disciplined version. Same essential move (have AI write the code), but with thought about what to ask, what tools to provide, how to verify the result, and how to fit it into a delivery process you trust.

---

## The curriculum

The repo's content lives here. The path: **use Claude as the model**, **build a harness around it one component at a time**, and **end with an agent you understand**. From there, you can either keep developing the agent itself or point it at the next product — i.e. do agentic engineering with a harness you own.

Each module pairs a prose explanation with a runnable checkpoint in [`examples/`](./examples/) — the file's name describes what the system has become at that step.

| # | Module | Harness component | Checkpoint |
|---|---|---|---|
| 1 | [What is an agent?](./modules/01-what-is-an-agent/) | (concept — Model + Harness) | *(no code)* |
| 2 | [An LLM call](./modules/02-an-llm-call/) | **Model interface** | [`llm_call_sync.py`](./examples/llm_call_sync.py), [`llm_call_async.py`](./examples/llm_call_async.py) |
| 3 | [Add a loop](./modules/03-add-a-loop/) | **Control flow** | [`stateless_chatbot.py`](./examples/stateless_chatbot.py) |
| 4 | [Add memory](./modules/04-add-memory/) | **Memory + context management** | [`stateful_chatbot.py`](./examples/stateful_chatbot.py) |
| 5 | [Add tools](./modules/05-add-tools/) | **Tool / action layer** | [`agent.py`](./examples/agent.py) |
| 6 | [Add sandboxing](./modules/06-add-sandboxing/) | **Execution environment** *(stubbed)* | [`sandbox_agent.py`](./examples/sandbox_agent.py) |
| 7 | [Add guardrails](./modules/07-add-guardrails/) | **Safety constraints** *(stubbed)* | [`safe_agent.py`](./examples/safe_agent.py) |
| 8 | [Add observability](./modules/08-add-observability/) | **Structured tracing** *(stubbed)* | [`traced_agent.py`](./examples/traced_agent.py) |
| 9 | [Add evaluation](./modules/09-add-evaluation/) | **Test infrastructure** *(stubbed)* | [`evals/`](./evals/) |
| 10 | [Add performance](./modules/10-add-performance/) | **Production hardening** *(stubbed)* | [`production_agent.py`](./examples/production_agent.py) |

Modules 1–5 are written end-to-end. Modules 6–10 are stubbed; their checkpoints in [`examples/`](./examples/) already implement what each one will describe — feel free to run those in the meantime.

## Scope

| | |
|---|---|
| ✓ | Building the harness around a model accessed via API |
| ✓ | The full set of harness components — 10 modules, one runnable checkpoint each |
| ✓ | Orientation on the layers below (model development) and above (agentic engineering) |
| ✗ | Training or fine-tuning the model itself *(model development)* |
| ✗ | A practical course on using a finished coding agent to ship product features *(agentic engineering downstream)* |
| ✗ | Multi-agent orchestration as a primary focus *(mentioned in context only)* |

## Setup

- Assumed programming experience (I will use Python as the example language)
- [Python 3.13 or newer](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) for dependency management
- An [Anthropic API key](https://console.anthropic.com) (or other model provider API key)

## License

MIT
