# agenteng

A framework-free, code-first curriculum for building the **harness** of an autonomous coding agent — the runtime around a model that turns it into an agent.

## What are agentic systems?

The idea of agentic systems comes from cognitive science — systems that can act on their own, without human intervention. In modern agentic systems, this agency is provided by an LLM coordinating calls to accomplish a goal without supervision.

## Types of agentic systems

In my opinion, agentic systems come in two forms — **workflows** and **agents** — as defined in Anthropic's [*Building Effective Agents*](https://www.anthropic.com/engineering/building-effective-agents). The distinction is about *what shape the system's control flow takes*.

**Workflows** — systems where LLMs and tools are orchestrated through **predefined code paths**. Prescriptive code paths define the sequence of steps that will be taken to accomplish a goal.

```mermaid
flowchart LR
    In[Input] --> W1[LLM] --> W2[LLM] --> W3[LLM] --> Out[Output]
```

**Agents** — systems where **LLMs dynamically direct their own path through the control flow**. The model decides the sequence of steps to take to accomplish a goal; no prescriptive code paths are followed and the model exercises its probability distribution to determine the next step.

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

### Common agent patterns

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

## Composition

By composing the above workflows and agent patterns, you can build multi-agent systems, multi-workflow systems, or systems that mix both.

> [!NOTE]
> **Whether to use multi-agent composition at all is a live disagreement in the field.** Anthropic embraces it ([multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system); Claude Code subagents). Cognition argues *against* it in [*Don't Build Multi-Agents*](https://cognition.ai/blog/dont-build-multi-agents), making the case for a single-threaded linear agent with shared context — citing reliability and debuggability. Cursor 2.0 takes a third path: parallel independent agents on separate Git worktrees, no supervisor. The right composition depends on whether sub-tasks share context, run in parallel, and need to surface partial state — there is no default answer.

## The Average Joes Lab stance: purist agents only

We believe in the [Anthropic model](https://www.anthropic.com/engineering/building-effective-agents): **a real agent has autonomy over its own control flow** where the model decides what tool to call, what to do with the result, and when the task is done. Building for purist agents is the focus of this repository.

Workflows are outside the scope of what follows.

```mermaid
flowchart LR
    A[Agent<br/>model decides] -->|freeze the path| W[Workflow<br/>code decides]
    W -.cannot derive.-> A
```

The primitives are the same — LLM calls, tools, context, memory. An agent's control flow is the model making those choices live; a workflow's control flow is you making them in advance. The building blocks transfer; how you orchestrate them into a fixed sequence is its own discipline.

For most production systems a workflow is more reliable, cheaper, and easier to evaluate — build a workflow if you can. But the interesting engineering problems — designing tools the model will use well, managing an open-ended context, making a non-deterministic loop reliable, evaluating a trajectory you can't enumerate — are agent problems. If you want a workflow, compose the primitives from this content into the sequence your problem needs.

## What agents look like

Production examples:

- **Coding agents** — [Claude Code](https://claude.com/claude-code), [Cursor](https://cursor.com), [Devin](https://devin.ai), [Aider](https://aider.chat), [nanoagent](https://github.com/averagejoeslab/nanoagent). The model opens files, edits them, runs tests, iterates.
- **Research agents** — [OpenAI Deep Research](https://openai.com/index/introducing-deep-research/), Claude's research mode. The model searches, synthesizes, digs deeper.
- **Task completion agents** — [SWE-agent](https://swe-agent.com), browser-use agents. The model manipulates a filesystem or GUI to complete a task.

In each case, the next action depends on what the previous action produced. The paths can't be enumerated in advance.

> [!IMPORTANT]
> Most systems marketed as "agents" in 2026 are workflows. That's often the right answer. This content is about the case when it isn't.

---

## Building and using agentic systems

Building agentic systems takes work at three distinct layers. Each is a discipline of its own:

```
┌──────────────────────────────────────────────────────────┐
│  AGENTIC ENGINEERING                                     │
│  Using agents to build software, products, and more      │
│  agents.                                                  │
├──────────────────────────────────────────────────────────┤
│  HARNESS ENGINEERING                  ← this repo        │
│  The runtime around a model that makes it an agent.      │
├──────────────────────────────────────────────────────────┤
│  MODEL DEVELOPMENT                                       │
│  Building, training, and fine-tuning the model itself.   │
└──────────────────────────────────────────────────────────┘
```

> A model is intelligence. A harness is the runtime that turns intelligence into an agent. Agentic engineering is the practice of using that agent to build software.

You don't have to work at all three layers to ship something useful — most engineers operate at one layer and consume what the layer below produces. This repo focuses squarely on the middle layer: **harness engineering**. The next three sections unpack each layer so you know where this curriculum fits.

## Model development

The bottom of the stack: producing a large language model. This repo doesn't teach model development — the harness assumes a model already exists and is accessible by API — but a one-page orientation helps anchor what the model layer actually contains.

### What a modern LLM is made of

A large language model is a probabilistic next-token predictor built from a small set of architectural primitives:

- **Tokenizer** — chops raw text into sub-word tokens via byte-pair encoding (BPE) or similar. Vocabularies are typically 30k–200k entries.
- **Token embeddings** — each token ID maps to a learned vector (often 2,048–16,384 dimensions in modern models).
- **Positional information** — added to the embeddings so the model knows token order (rotary position embeddings / RoPE, ALiBi, or learned position vectors).
- **The transformer block** — the workhorse. Each block contains **multi-head self-attention** (every token attends to every other token in the context), a **feed-forward network** (per-token nonlinear transformation, often with SwiGLU), **residual connections**, and **layer normalization** (RMSNorm is now common). Modern frontier models stack 60–120 of these blocks.
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

1. **Pretraining.** The expensive step. The model learns to predict the next token over a massive web-scale corpus (trillions of tokens). This is where it acquires syntax, facts, reasoning patterns, and a general sense of how language works. Takes thousands of GPUs and months of wall-clock time.
2. **Supervised fine-tuning (SFT).** Train on curated instruction/response pairs so the model learns to *follow instructions* rather than just continuing arbitrary text. Much smaller dataset; much smaller compute.
3. **Preference tuning (RLHF or DPO).** Train on human-rated comparisons of model outputs so the model learns what counts as a *good* response. This is where helpfulness, honesty, and safety behaviours are instilled.
4. **(Optional) Specialty fine-tuning.** Additional training on domain-specific data (code, math, tool use) for sharper task performance.

### Inference

Calling the model API runs a forward pass through every layer, producing a probability distribution over the vocabulary. A token is sampled — modulated by **temperature** (randomness), **top-k** (only the k highest-probability tokens), and **top-p** / **nucleus** (smallest set of tokens whose probabilities sum to p). Repeat until an end-of-sequence token or max length is reached.

### Why model development is its own discipline

It requires distributed training infrastructure, data curation pipelines, dedicated evaluation suites, and capital that does not pencil out for most projects. Frontier-model training is a multi-billion-dollar effort. The harness layer above assumes that effort has happened upstream and the model is now a callable service.

## Harness engineering

The middle layer — and the focus of this repo.

> **Agent = Model + Harness.**
> The harness is every piece of code, configuration, and execution logic that isn't the model itself — state, tools, execution, feedback loops, constraints, observability. A raw model is not an agent until a harness gives it those things.

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

**Each of these is one module in this curriculum.** The modules build cumulatively, one harness component at a time, until you reach a production-shaped coding-agent harness.

> [!NOTE]
> The term *harness* in this sense was consolidated through 2025–2026 by Anthropic ([effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents); [harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)), LangChain ([*The Anatomy of an Agent Harness*](https://www.langchain.com/blog/the-anatomy-of-an-agent-harness)), Martin Fowler ([Birgitta Böckeler, *Harness engineering for coding agent users*](https://martinfowler.com/articles/harness-engineering.html)), [Addy Osmani](https://addyosmani.com/blog/agent-harness-engineering/), and [O'Reilly Radar](https://www.oreilly.com/radar/agent-harness-engineering/). The framing has converged: harness = everything except the model.

## Agentic engineering

The top layer. Once a model is wrapped in a harness, you have an **agent** — and an agent is a building block for the next thing.

**Agentic engineering** is the practice of *using* agents — combining models with harnesses, then using the result — to build software, products, workflows, and sometimes more agents. The agent stops being the artifact and becomes the tool.

What that looks like in practice:

- A developer uses Claude Code (Claude + the Claude Code harness) to ship a feature in their codebase — that's agentic engineering.
- A team builds a customer-support product by orchestrating multiple agents — using the agent layer as the primitive instead of writing the loop themselves.
- A researcher runs a coding agent to author an evaluation suite for a different agent — agentic engineering produces the test artifact.
- **You read this repo, build a harness, then turn around and use the resulting agent to build whatever comes next.** That's the loop the three layers close.

### The recursive moment

This repo is being built using Claude Code — itself a coding-agent harness — running on Claude (the model). The author drives that agent to write modules, build the deck, write code, ship commits. That's a live instance of the three-layer stack at work:

1. Anthropic does **model development** to produce Claude.
2. The Claude Code team does **harness engineering** to build Claude Code.
3. The repo's author does **agentic engineering** to build this curriculum *using* that agent.

What this curriculum teaches is how to do the middle layer — so you can build harnesses like Claude Code from first principles, and then use the agents you build to do the top-layer work on whatever comes next.

## Scope

| | |
|---|---|
| ✓ | Building the harness around a model accessed via API |
| ✓ | The full set of harness components — 10 modules, one runnable checkpoint each |
| ✗ | Training or fine-tuning the model itself *(model development)* |
| ✗ | Using a finished coding agent to ship product features *(agentic engineering, downstream of this)* |
| ✗ | Multi-agent orchestration as a primary focus *(mentioned in context only)* |

## Setup

- Assumed programming experience (I will use Python as the example language)
- [Python 3.13 or newer](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) for dependency management
- An [Anthropic API key](https://console.anthropic.com) (or other model provider API key)

## Content

The curriculum is one straight line: start with a single LLM call and build outward, one harness component at a time, until you reach a production-shaped coding-agent harness. Each module pairs a prose explanation with a runnable checkpoint in [`examples/`](./examples/) — the file's name describes what the system has become at that step.

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

Modules 1-5 are written end-to-end. Modules 6-10 are stubbed; their checkpoints in [`examples/`](./examples/) already implement what each one will describe — feel free to run those in the meantime.

## License

MIT
