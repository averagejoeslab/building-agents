# Purpose of this repo

To document how to build your own agent from scratch, which you can do by building a harness around a model because `Agent = Model + Harness`. Additionally this repo makes clear the differences between: model development, harness engineering, and agentic engineering.

I am Chase Dovey, and I conduct research on agentic systems. Most of that work is building harnesses around models. This is a focus of mine because building your own harness is a valuable skill to have given that the industry currently is in a race to see who has *the best harness*. If you go to any agent/AI conference, meetup, or any other industry event you will likely see vendors pitching their harness, which typically includes their control flow, memory layer, and tool execution layer, etc. To me the best harness is the one you build yourself because you understand the internals, and can change them to fit your needs.

## What is an agentic system?

The idea of agentic systems comes from cognitive science — systems that can act on their own, without human intervention. In modern agentic systems, the agency is provided by an LLM coordinating calls to accomplish a goal without supervision.

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

## Getting Started: The three disciplines

There are three disciplines that lead up to building and using an agent:

- **Model development.** This discipline is responsible for training the models most use today. A small number of labs with capital, GPUs, and data pipelines have the resources to train these models and the output of their work is a model you call via an API endpoint. Examples of these models are GPT, Claude, Gemini, Llama, etc.
- **Harness engineering.** This discipline is responsible for wrapping that model in a control flow, memory layer, tool execution layer, sandboxing, guardrails, observability, etc. When you wrap a model in a harness you get an agent because *Agent = Model + Harness.* The output of this discipline is a harness that wraps a model gives rise to an agent. Examples of these harnesses are Claude Code, Cursor, Codex, Mistral's Vibe, etc.
- **Agentic engineering.** This discipline is responsible for using an agent to build software, products, infrastructure, or more agents. The agent becomes the tool. The output of this discipline is products built by agents orchestrated by humans. Examples of agentic engineering are things like OpenClaw, but could also be a non-AI product that was built by an agent that was orchestrated by a human.

Harness engineering is the primary content of this repo in the [modules](./modules/). We won't cover model development other than in theory because building a foundational model from scratch takes capital, GPUs, and data pipelines most of us don't have, so it's out of reach. Agentic engineering picks up after the curriculum with a section on what to do with the agent you've built.

## Building an agent: a journey through the disciplines

Model development produces a callable model. Harness engineering turns that into an agent. Each discipline in dependency order, ending where the curriculum starts.

### 1. Model development → a callable model

I don't teach this here; the harness consumes the model as a callable API.

#### What a modern LLM is made of

A probabilistic next-token predictor built from a small set of primitives:

- **Tokenizer** — chops raw text into sub-word tokens via byte-pair encoding (BPE) or similar. Vocabularies are typically 30k–200k entries.
- **Token embeddings** — each token ID maps to a learned vector, often 2,048–16,384 dimensions in modern models.
- **Positional information** — added to embeddings so the model knows token order (RoPE, ALiBi, or learned position vectors).
- **Transformer block** — multi-head self-attention (every token attends to every other), feed-forward network (per-token nonlinear, often SwiGLU), residual connections, layer normalization (RMSNorm is common). Frontier models stack 60–120 of these.
- **Output head** — projects the final hidden state to a distribution over the vocabulary; the next token is sampled.

#### Training

```mermaid
flowchart LR
    A[Web-scale corpus<br/>trillions of tokens] --> B[Pretraining<br/>next-token prediction]
    B --> C[Base model]
    C --> D[Supervised fine-tuning<br/>instruction data]
    D --> E[Preference tuning<br/>RLHF / DPO]
    E --> F[Released model]
```

1. **Pretraining.** Predict the next token over trillions of tokens of web-scale data. Acquires syntax, facts, reasoning patterns. Thousands of GPUs, months of wall-clock time.
2. **Supervised fine-tuning (SFT).** Curated instruction/response pairs — learn to follow instructions rather than continue arbitrary text.
3. **Preference tuning (RLHF or DPO).** Human-rated comparisons — learn what counts as a good response. Helpfulness, honesty, safety instilled here.
4. **(Optional) Specialty fine-tuning.** Domain-specific data: code, math, tool use.

#### Inference

A forward pass produces a distribution over the vocabulary. A token is sampled — modulated by **temperature** (randomness), **top-k** (only the k highest-probability tokens), **top-p / nucleus** (smallest set whose probabilities sum to p). Repeat until end-of-sequence or max length.

A callable model can complete text. It can't read files, run commands, remember across sessions, or stop when done. To get any of that, you wrap it in a harness.

### 2. Harness engineering → an agent

This is the layer I teach in this repo. A harness is every piece of code, configuration, and execution logic that isn't the model itself — state, tools, execution, feedback loops, constraints, observability. Wrap a model in one and you have an agent.

The discipline covers:

- **Selecting the model** — which model the harness wraps.
- **Control flow** — the loop that drives the model continuously.
- **Memory** — what's remembered, when, how it's retrieved.
- **Context management** — the context window is a token budget; what goes in, what gets evicted.
- **Tools** — what capabilities the harness exposes, at what granularity, with what error semantics.
- **Safety / guardrails** — sandboxing, approval gates, loop bounds, input/output detection.
- **Observability** — structured traces of every LLM call, tool call, and state transition.
- **Evaluation** — benchmarking harness behaviour, catching regressions.
- **Optimization** — prompt caching, tool caching, threading, structured prompts.

One module per component. Every checkpoint in [`examples/`](./examples/) is a runnable harness at a different stage. Stack the components around a model and you have an agent.

> [!NOTE]
> The term *harness* in this sense was consolidated through 2025–2026 by Anthropic ([effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents); [harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)), LangChain ([*The Anatomy of an Agent Harness*](https://www.langchain.com/blog/the-anatomy-of-an-agent-harness)), Martin Fowler ([Birgitta Böckeler, *Harness engineering for coding agent users*](https://martinfowler.com/articles/harness-engineering.html)), [Addy Osmani](https://addyosmani.com/blog/agent-harness-engineering/), and [O'Reilly Radar](https://www.oreilly.com/radar/agent-harness-engineering/).

---

## Curriculum

The modules below are the harness-engineering work: take Claude as the model and build the harness around it, one component at a time.

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

Modules 1–5 are written end-to-end. Modules 6–10 are stubbed; their checkpoints in [`examples/`](./examples/) already implement what each will describe.

## Agentic engineering in practice

Once you've built the harness from the curriculum, you have an agent: a model wrapped in code, state, tools, and a loop you built and understand. Two things you do with it.

### Develop other products

Point the agent at the next codebase. Peter Steinberg built [openclaw](#) by directing existing coding agents to produce most of its implementation, and embedded an agent harness inside openclaw itself, so the product ships with an agent of its own. Agents produced the artifact; the artifact ships with an agent.

### Develop the agent itself

Point the agent at its own curriculum. Have it write a new module, refactor a harness component, improve its tracing, tighten its evals, raise its performance.

This repo is built that way. Claude Code (a coding-agent harness) running on Claude, driven by me to write modules and ship commits. Every layer is visible:

1. Anthropic does **model development** → Claude.
2. The Claude Code team does **harness engineering** → Claude Code.
3. I do **agentic engineering** → this curriculum.

This curriculum teaches step 2.

"Vibe coding" (Karpathy) is the casual end of this — accept what the model produces. Agentic engineering is the disciplined version: thought about what to ask, what tools to provide, how to verify, how to fit into a delivery process you trust.

## Scope

| | |
|---|---|
| ✓ | Harness around a model accessed via API |
| ✓ | All 10 harness components, one runnable checkpoint each |
| ✓ | Orientation on model development (upstream) and agentic engineering (downstream) |
| ✗ | Training or fine-tuning the model itself |
| ✗ | A practical course on using a finished agent to ship product features |
| ✗ | Multi-agent orchestration as a primary focus |

## Setup

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/) for dependency management
- An [Anthropic API key](https://console.anthropic.com)

## License

MIT
