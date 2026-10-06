# Five Primitives Are All You Need: Building an Agent Harness

**Chase Dovey**
Average Joes Lab

October 2026 · Draft

Companion course and code: [harness-engineering](../README.md)

---

## Abstract

People describe LLM agents with words that don't line up: framework, scaffold, runtime, orchestration layer, harness. Recent work argues that this outer layer decides much of how an agent performs, and that comparisons which leave it out mislead. But the field has no shared account of what the layer *is*. This paper gives one. Its starting point is a split into two parts: **the model** is a function, *TokensOut = Model(TokensIn)*, and **the harness** is everything else, so **Agent = Harness(Model)**. I then argue that every harness reduces to **five mechanistic primitives**:

- **control flow** decides what runs, in what order, and when to stop, and wraps the other four;
- **input** gathers what goes to the model, from a person or the world;
- **context** decides what the request holds and how it fits;
- **the model interface** sends the request and gets the response back;
- **output** handles the response, by showing it to a person or running it as a tool.

The reduction uses one method throughout: ask of any agent part *what is it, and by what mechanism does it work?* Then define each primitive as much by what it never does as by what it does.

I check the claim three ways.

1. **Construction.** A working agent, quark, is built outward from a single API call, one primitive per step. It reaches a finished harness of 48 lines of Python.
2. **Closure.** Six production concerns are added on top: observability, guardrails, sandboxing, resilience, performance and evaluation. Each is shown to be hardening *inside* one or more of the five primitives, not a new one. Evaluation is the only layer outside the harness, and it too is built from the primitives.
3. **Case study.** The finished agent wrote much of its own course, running under a second agent. Its failures along the way each landed on a specific primitive.

The result is a small vocabulary that can take apart any harness and place every product in the field. It also turns "what is a harness?" into a claim anyone can test: find a part that fits none of the five.

---

## 1. Introduction

Watch enough talks about agents and a pattern shows up. Speakers use different words for the same thing: the *framework*, the *scaffold*, the *runtime*, the *orchestration layer*, the *harness*. Yet when they show how their system works, the mechanism is the same every time. A model is called. Something decides what goes into the call. Something acts on what comes back. Something decides whether to go again. The words disagree, but the mechanisms don't.

That gap is a practical problem. A team that can't name the parts of its agent can't say which part caused a failure. Readers can't compare two systems whose authors describe them in different terms. And the field keeps meeting the same handful of ideas as new products: memory layers, gateways, tool protocols, tracing platforms, sandboxes, evaluation suites. With no map, it's unclear whether each one is new or an old idea in new clothes.

Interest in the outer layer is now explicit. A run of 2026 papers works on *harness engineering*: harness design for coding agents, harnesses for auditable enterprise agents, deterministic execution constraints, reusable tool primitives, code as a harness. One argues outright that agents shouldn't be compared without disclosing their harness [10–15]. These papers treat the harness as decisive. None of them says what a harness is made of.

This paper's answer is reductive and mechanistic. It is **reductive** because it takes an agent apart until the parts stop being shared across systems. It is **mechanistic** because each part is defined by what it *does* in the path from a request to a response, not by what it's called or which product provides it.

**Contributions.**

1. **A two-part split of agents.** The model is a fixed function and the harness is everything around it: *Agent = Harness(Model)* (§2).
2. **Five primitives of a harness,** each defined positively and negatively, with rules for the cases at their boundaries (§3–4).
3. **A constructive argument that the five are enough:** a working agent built one primitive at a time, where each step's missing piece is exactly the next primitive (§5).
4. **A closure argument that production concerns are not new primitives:** six production layers, each placed inside the primitives it hardens. Each layer comes with code that adds it to the previous version and leaves the other primitives untouched (§6).
5. **A way to take apart existing systems and products,** sorting each under the primitive it implements (§7).
6. **A case study** in which the agent built in this paper wrote much of the course that teaches it. Its failures map onto the primitives and layers (§8).

The paper comes with an open course and code base, [harness-engineering](../README.md). Every code listing and every run quoted here is reproduced there in full, with real output.

---

## 2. Two primitives: the model and the harness

Start with the agent and ask what it is made of. There are two parts.

**The model predicts.** Given a sequence of tokens, it produces the tokens most likely to come next:

> **TokensOut = Model(TokensIn)**

Seen from outside, the model is a function. It has no memory between calls, it can't read a terminal, it can't run a command, and it can't decide to be called again. Everything it knows about the present moment is in the tokens it's given. The model is built by *model development*: training data, compute, and methods to train and evaluate. That is a separate discipline, and this paper treats its output as fixed.

**The harness does everything else.** It decides:

- how inputs are gathered,
- how they're presented to the model,
- how the model is called,
- how the model's outputs are handled,
- how information flows between all of these.

> **Agent = Harness(Model)**

The model goes inside, and the harness wraps it. *Harness engineering* is the work of building the second part.

This split is deliberately blunt, and it has a consequence: anything that isn't the model's weights is harness. A system prompt is harness. A tool is harness. A retry policy is harness. So is a memory store. Two agents built on the same model differ only in their harnesses, and that is why a comparison that leaves out the harness compares the wrong thing.

### 2.1 Method

The method is a single question, applied again and again:

> *What is it, and by what mechanistic primitives does it work?*

Apply it to an agent and you get a model and a harness. Apply it to a harness and you get five primitives (§3). Apply it once more, to a primitive, and the answers stop being shared. One harness's input reads a terminal, another's reads a Slack channel, and a third's reads a webhook. That is where taking apart ends. A primitive, in this sense, is the deepest level at which every harness still has the same parts.

Each primitive is then defined in two ways. The **positive** definition says what it does. The **negative** definition says what it never does, by naming which other primitive owns that job. The negative definitions do most of the work. They make the primitives disjoint, so that any piece of harness code has exactly one home.

---

## 3. The five primitives

```
control flow          how information flows between the other four: run once, a chat loop, an agent loop, a workflow
├── input             how inputs are gathered, from a person or the world
├── context           what the request holds, and how inputs are presented in it
├── model interface   how the harness interfaces with the model
└── output            how the model's outputs are handled: shown to a person, or run as tools
```

One pass through a harness follows a single path:

```
person or world ─► input ─► context ─► request ─► model interface ─► response ─► output ─► person or world
                     ▲                                                              │
                     └─────────────────────────── result ───────────────────────────┘
```

Input gathers what goes in. Context assembles it into a request and makes it fit. The model interface sends the request and receives the response. Output handles the response, by showing it to a person or running a tool. A tool's result comes back as input. Control flow decides what happens at the end of the path: the result goes around again, a person gets a turn, or everything stops.

### 3.1 Model interface

**Does:** sends tokens to the model as a request and gets tokens back as a response.

**Never does:** decide *when* to call (control flow), gather what goes in (input), decide how it's presented (context), or act on what comes back (output).

The model interface is the thinnest primitive, and that follows from where it sits. The other four live on the harness's side. The model interface is the boundary itself: in *Agent = Harness(Model)*, it is the parentheses. Its minimal form is one SDK call. Richer forms vary along a handful of axes:

- where the request goes (a hosted API, a local model, a gateway);
- how it travels (an SDK, raw HTTP, a translation layer between providers);
- which model answers (one, or a backup for when the first is unavailable);
- how the response arrives (all at once, or streamed);
- how many requests go at once (one, or a batch);
- what happens on failure (retry, back off, time out);
- the request's settings (output cap, thinking effort, whether a thinking summary is returned).

All of these concern getting one request there and one response back.

### 3.2 Input

**Does:** gathers what goes to the model, from a **person** (a task, a question, a message) or from **the world** (what happened when a tool ran: its output, its exit code, whether it failed).

**Never does:** decide how what it gathered is laid out in the request (context), send it (model interface), or decide whether to go again (control flow).

Input is the harness's afferent pathway: it carries signals in. Its sources vary (command-line arguments, a prompt, a pipe, a chat app, a webhook, a schedule), and so do its forms (text, images, files). Its one invariant is that it brings something from outside the harness to the edge of the request.

### 3.3 Output

**Does:** handles the model's response, by **showing it** to a person or **running it** as a tool.

**Never does:** decide whether a tool's result goes back to the model (control flow), or what the next request holds (context).

Output is the efferent pathway: it carries actions out. The model can't act, but it can *ask*. Its response can include a request to use a tool, given as a name and arguments in a shape the harness described to it. Output runs the request, and what happened comes back as input: **the model asks; the harness acts.** Output's choices include:

- which tools exist (one general tool or many specific ones);
- where they run (the same machine, a container, a remote host, the provider);
- whether several requests run in sequence or at once;
- when *not* to run (a request cut off mid-generation is incomplete, and running half a command is worse than running none);
- what happens when a tool fails or hangs.

Input and output are built independently, but they are two ends of one exchange, and they meet at the tool. A tool needs both: output to run it, and input to bring its result back.

### 3.4 Control flow

**Does:** **sequences** the other four primitives, passing what one produced to the next, and **terminates**, deciding when to stop or hand back to a person.

**Never does:** send the request (model interface), gather (input), present (context), or handle the response (output).

Control flow is the one primitive that wraps the others. How it arranges them decides what has been built:

| Shape | Arrangement | Who decides what happens next |
|---|---|---|
| Single call | input → call → output, stop | nobody; it's fixed |
| Chat loop | call, show, hand back to the person, repeat | the person |
| Workflow | code lays out the calls: draft, judge, rewrite | the harness's code |
| Agent loop | call; while the model asks for tools, run them, send results back, call again | the model |

In this framing, the line between a *workflow* and an *agent* is a fact about control flow: who decides the next step [3]. Termination is part of the definition and not an afterthought: *a loop with no clear way to end is a bill with no clear way to end.* The minimal agent loop ends when the model stops asking for tools. Richer ones also stop on a step limit, a spending limit, a refusal, or a person saying stop.

### 3.5 Context

**Does:** before every call, **assembles** what the request holds and **fits** it into the space the model can read.

**Never does:** gather inputs (input), send the request (model interface), or decide when to call (control flow).

Every call starts from nothing. The model doesn't know where it's running, what day it is, who it is, what it did a minute ago, or what it was told last week, unless the harness puts it in the request. That's why so much of what people build into harnesses turns out to be context. These components are all ways of deciding what the model sees:

- **instructions:** the system prompt;
- **working memory:** this session;
- **episodic memory:** past sessions;
- **semantic memory:** durable facts;
- **procedural memory:** skills, recipes, playbooks;
- **retrieval:** search results placed in the request;
- **compaction:** a summary in place of history that no longer fits;
- **self-knowledge:** the agent's own description or source.

**Input and context are distinct.** Input brings a thing to the edge of the request. Context decides whether it goes in, where, in what form, and what gets dropped to make room.

### 3.6 Summary

| Primitive | Does | Never does |
|---|---|---|
| Model interface | request out, response back | decide when, gather, present, act |
| Input | gather from a person or the world | present, send, decide to repeat |
| Output | show the response, or run a tool | decide whether results return, shape the next request |
| Control flow | sequence and terminate | send, gather, present, handle |
| Context | assemble and fit the request | gather, send, decide when |

---

## 4. Boundary cases

A taxonomy is only as good as its hard cases. The ones below come up in practice. Each is settled by the negative definitions in §3, not by convention.

**Backup model vs. routing.** A backup model that takes over *because the first is unavailable* is part of the model interface: it changes only how one request gets a response. Choosing a cheaper model for a task *because the task is simple* is routing, a decision about the work, and so it's control flow. Both change which model answers, but they differ in *why*.

**A fixed model for one kind of request.** A harness that always sends its compaction summary to a smaller model is applying a fixed setting of that request, like `max_tokens`. That belongs to the model interface. If the choice is made at run time, per task or per step, it is routing again, and so control flow.

**Streaming.** *Receiving* a response as a stream is the model interface. *Printing* each piece as it arrives is output.

**Parallelism.** Running several *tool requests* from one response at the same time is output: it's how those requests are executed. Making several *model calls* at the same time (fanning out subtasks, or voting) is a way of arranging the work, so it's control flow.

**Memory vs. traces.** An episode log the agent can search in a later session is **context**, because it exists for the model. A trace of every call and tool, kept for a person to read, is **observability** (§6.1), because it exists for the operator. The two files can look the same. What separates them is who reads them.

**A question to a person mid-run.** When a guardrail asks "allow this command? [y/N]", the person's answer is not a new task. It is read as a decision inside control flow. Input is unchanged.

**The "augmented LLM."** The common building block of a model with retrieval, tools and memory [3] is not a primitive. It splits into context (retrieval, memory) and output (tools) around a model interface.

**Tool protocols.** A protocol that packages tools behind a common interface, such as MCP [16], provides output that can be plugged in. Its server is where the tool runs; deciding to call it, and sending its result back, stay where they were.

**Multiple agents.** One agent handing a task to another is a shape of control flow, the outer harness sequencing inner ones. Delegation adds no new primitive. It nests harnesses.

---

## 5. Building it back up: the five are enough

A taxonomy can be complete on paper and still miss something in practice. The constructive test is to build an agent from nothing but the five primitives and see whether anything else is needed. The course does this with quark, the author's agent, built *outward from the model*, one primitive per lesson. Each lesson's `quark.py` is the previous lesson's file plus that primitive and nothing else.

| Step | Adds | `quark.py` | What's still missing |
|---|---|---|---|
| 1 | Model interface | 9 lines | Both ends are stubs: a hard-coded question in, a raw dump out. The model says the next step is `ls`, and nothing can run it. |
| 2 | Input and output | 21 lines | A real task comes in and a tool request is run, but the result never reaches the model. The path ends at output. |
| 3 | Control flow | 30 lines | The loop sends results back, so it is now an agent. But it knows nothing: not where it is, not what day it is, not who it is, not what it was told yesterday. And its history grows without bound. |
| 4 | Context | 48 lines | Nothing is missing. It works, remembers across sessions, knows what it is, and compacts when full. |

Each step's "what's missing" is exactly the next primitive. No step needs anything that isn't one of the five. The finished harness has these parts:

- **Context:** a system prompt written as models of self, world, other selves and body; the agent's own source code embedded as self-knowledge; a semantic memory file the agent reads and writes with its one tool; and reactive compaction triggered by the API's "prompt is too long" error.
- **Output:** a `bash` tool.
- **Input:** a task from the command line or a chat prompt.
- **Control flow:** an agent loop that ends when the model stops asking for tools.

All of it fits in 48 lines (Appendix A).

Each primitive also has a fuller second implementation, to show that the primitive is a space of choices and not a single design:

- a model interface with timeouts, retries, a backup model, streaming and adjustable thinking settings;
- input and output through a Telegram chat, with two tools run concurrently, timeouts, and an incomplete request that is not run;
- control flow with a step limit and refusal handling, plus an evaluator–optimizer workflow in which code, not the model, decides the order;
- context with an episode log, skill files, token counting before each call, and trimming of long tool results.

None of these needed a sixth primitive either.

---

## 6. Closure: production layers fold back into the primitives

A harness that works is not yet a harness you'd run unattended. Production agents add tracing, approvals, sandboxes, retries, caching and evaluation, and each has its own vendors and literature. It's natural to treat each one as a new building block. This paper argues the opposite:

> **Thesis.** Production concerns add *hardening*, not new primitives. Each is a set of changes inside one or more of the five, made where that primitive already acts, and it leaves the others unchanged.

The course tests this layer by layer. Each production lesson's `quark.py` is the previous one plus exactly that layer. Each names the primitives it is built on, and each ends with a *"Notice what [layer] never does"* paragraph listing the primitives it leaves alone. Measured against the previous file, the six additions are small:

| Layer | Built on | Lines added / removed | `quark.py` |
|---|---|---|---|
| — (the primitives) | — | — | 48 |
| Observability | control flow | +12 / −1 | 59 |
| Guardrails | control flow | +26 / −2 | 83 |
| Sandboxing | output | +13 / −2 | 94 |
| Resilience | model interface, output | +53 / −12 | 135 |
| Performance | context, model interface, output | +47 / −23 | 159 |
| Evaluation | the whole harness, from outside | +38 / −1 | 196 |

The sections below say, for each layer, why it lives where it does.

### 6.1 Observability, in control flow

Observability is a record of what the harness did, kept as it does it: every model call, every tool, how long each took and how many tokens each cost. It lives in control flow because **control flow is the only primitive that sees the whole sequence.** The model interface knows about one call and output knows about one tool, but the loop is where a call, the tool it asked for and the next call all happen in order.

The mechanism adds nothing new. It reads what's already there at each turn of the loop: the clock, the `usage` returned with the response, the exit code of the command. It writes one JSON line per event. In a run of three calls, the trace showed the first call writing 2,766 tokens of system prompt to the cache and each later call reading them back. That is Lesson 4's cache mark working, and it couldn't be seen before.

**Never does:** decide what runs next or when to stop. Observability only watches. A wrong trace line is a wrong record, not a wrong agent.

### 6.2 Guardrails, in control flow

Guardrails are rules about what the harness may do, checked before it does it. They live in control flow because a guardrail is a decision at one of the two points where control flow already decides: turning a tool request into a command being run, and turning a result into another call. The mechanism:

- **A gate before each tool:** allow, ask a person, or deny.
- **A refusal returned in the tool-result slot,** marked as an error, so the model can read it and change course.
- **Limits on steps, tokens, dollars and repeated commands,** checked at the top of the loop.
- **An interrupt** that hands the run back to the person.

**Never does:** change what the model asks for, or how an allowed command runs. When a command passes the gate, output runs it exactly as before. A refusal is an ordinary tool result, so context assembles the next request as it always has. Guardrails decide *whether*, never *how*.

### 6.3 Sandboxing, in output

Sandboxing changes *where* a tool runs. That was always a choice output made, only made implicitly by `subprocess.run`, which means "right here". The sandbox:

- starts a container before the loop;
- removes the network;
- caps memory, CPU, process count and time;
- makes the root filesystem read-only and drops all capabilities;
- mounts only the working folder;
- keeps the API key on the harness's side.

Tool calls then become `docker exec` into that container. The key point is *who enforces the limits*. A guardrail is code reading the text of a command. A sandbox's limits are enforced by the kernel, however the command is spelled. A guardrail asks *should this run?* A sandbox answers *when it runs, what can it reach?*

**Never does:** touch the loop, the request, or the model call. The model finds the walls only by walking into them, because telling it about the box in advance would be a decision about context.

### 6.4 Resilience, in the model interface and output

Resilience covers the two places where the harness reaches outside itself and the world can say no.

**In the model interface,** it:

- separates transient failures (dropped connections, timeouts, 429, 5xx, 529 overloaded) from permanent ones (401, 400, 404);
- retries the transient ones with exponential backoff and jitter, honoring `Retry-After`;
- falls back to a backup model once retries are exhausted;
- stops with a message, not a stack trace, when nothing answers.

**In output,** every tool request still gets an answer the model can read: a missing command, a request cut off by the token limit, or bytes that aren't valid text each become a readable result instead of a crash.

**Picking up a killed run.** Resilience also saves the session after every step, writing it atomically. On resume, any tool request left without a result gets one saying *interrupted; this may or may not have run; check before repeating it.* In the course's staged crash, the harness was killed while a command ran inside the container. The command finished anyway. The resumed model, told the outcome was unknown, checked the file system, found the command's output, and did not run it again.

**Never does:** change the loop (a retry happens inside a single call), input, or context. The saved working memory is replayed exactly, and the only new text the model sees is the "interrupted" result.

### 6.5 Performance, in context, the model interface and output

Performance is several small mechanisms, each placed where the time or the tokens are spent.

**Context.**

- *Prompt caching* marks the stable start of the request and the end of the conversation, so each call pays full price only for what is new. In one three-step run, the harness resent about 5,500 tokens per call and paid full price for about 150.
- *Trimming* caps what one tool result can add to working memory.

**Model interface.**

- *Streaming*, so a reply starts arriving at once.
- *A fixed smaller model* for compaction summaries.

**Output.** Concurrent execution of the tool requests the model made together. Three independent 3-second commands took 6.9 s for the whole run, against 13.0 s when run one after another.

**Never does:** change control flow, which makes the same number of calls and steps, or input. Inside each of the three primitives it changes *how*, not *what*. The course's fuller example also routes each task to a model tier based on a small model's estimate of difficulty. The paper labels that part explicitly as control flow (§4), because it is a decision about the work.

### 6.6 Evaluation, outside the harness, built from the primitives

Evaluation is the one layer that sits in none of the five. It treats the agent as a black box: a task goes in and the world is changed. It is built from the primitives themselves:

- an outer **control flow** loop that, for each case, sets up a fresh folder, runs the agent, grades the result, records it, and compares it with the last run;
- the task handed to the agent as **input**, the way a person would hand it over;
- the check run as **output**, a command whose exit status is the grade;
- a model grader reached through the **model interface**.

So evaluation is a second harness wrapped around the first, and it adds no new primitive either.

In the course, lowering the step limit from 20 to 1 kept three of four cases passing. The fourth, which needed to read code before fixing it, was flagged `REGRESSED`, and the command exited 1. Cutting tool results to 20 characters kept every case passing, but one case's tokens rose from 20,255 to 27,245. That is why cost is recorded next to the grade.

**Never does:** rebuild any primitive. *Evaluation runs the primitives; it never rebuilds them.*

### 6.7 What the closure shows

All six layers fit. Four live inside primitives. Resilience and performance each spread across several primitives without needing a new one. Evaluation turns out to be the same five primitives applied one level up. This is why a production harness of 196 lines can still be read with the same five headings as a demo of 48. It's also why each production product in §7 can be placed under a primitive.

The closure is shown here by construction, not proven in general. §9 discusses what would refute it.

---

## 7. Taking apart existing systems

If the primitives are right, every harness and every harness *product* should sort under them. Products in the field turn out to be single primitives, or single production layers, sold separately:

| Product or category | What it is, in these terms |
|---|---|
| LiteLLM, OpenRouter (gateways) | the model interface, whole: provider routing, backups, retries, rate limits |
| MCP servers | output you plug in: tools someone else built, behind one protocol |
| Mem0 and similar memory layers | context: store what to remember, return what's relevant per request |
| LangGraph | control flow: steps and edges laid out as a graph and run (plus checkpointing, i.e. resilience) |
| Langfuse, LangSmith (tracing) | observability, so built on control flow |
| Open Policy Agent, NeMo Guardrails | guardrails, so built on control flow |
| E2B, Modal, Daytona (hosted sandboxes) | sandboxing, so built on output |
| Temporal (durable execution) | resilience: record each step, resume after a crash |
| Braintrust, promptfoo, Inspect | evaluation: run cases, grade, keep history |

Whole agents should sort the same way. Claude Code, Cursor, Codex and quark make different choices within each primitive: which tools, which memory, which loop shape, which approval policy. The claim is that none of them has a part outside the five; checking that against each system part by part is the systematic study proposed in §9.2. The course ends by giving the reader a checklist for taking apart any harness:

```
control flow          what kind of loop? who decides when to stop?
├── input             where do inputs come from: people, the world, both?
├── context           what does the request hold? which memories? how does it fit?
├── model interface   where does the request go, and how does the response come back?
└── output            where do outputs go? which tools, and how are they run?
```

When something doesn't fit at first, the rule is to ask what it *does*. If it decides what the model sees, it's context, whatever it's called. If it acts on what the model said, it's output.

---

## 8. Case study: the harness that wrote its course

The finished 48-line harness was used for real work on the repository that teaches it. A second agent, Claude Code, operated it from a terminal the way a person would. quark never saw Claude Code. Across four runs, quark:

1. read the whole repository and wrote what it learned to its semantic memory file (about 25 KB of notes, one entry per lesson);
2. in a new session with empty working memory, wrote slide decks for the four primitive lessons *from memory alone*, without opening a lesson file;
3. wrote the six production lessons, one session per lesson, each building its `quark.py` from the previous one, running its code for real, and pasting the real output;
4. in another new session, wrote slide decks for the six production lessons, again from memory.

The arrangement is itself an example of the paper's claim. The script that ran one quark session per lesson, stopping if a lesson produced no `quark.py`, is **control flow one level up**: a workflow around an agent.

The interesting results are the failures. Each one maps onto a specific primitive or layer.

**A silent stop, then a crash: model interface and output.** The fifth lesson stopped twice without writing anything. A trace of each response's `stop_reason` (observability, added for diagnosis) showed the cause. With thinking on, a 4,096-token output cap was not enough to think *and* write a file. On the third attempt, a response hit `max_tokens` partway through a tool request, and the harness crashed with `KeyError: 'cmd'`. That is exactly the incomplete-request case from Lesson 2 ("when not to run"). The fix was a setting of the request, `max_tokens` raised to 16,384 across the course. Making output refuse to run an incomplete request is one of the things the resilience layer adds.

**The agent killed itself: output, guardrails and sandboxing.** To test crash recovery in the resilience lesson, quark killed its test agent with `pkill -9 -f 08-resilience/quark.py`. Its own command line contained that path, so it killed itself too. Its Docker container outlived it, which is the leftover the sandboxing lesson had warned about for a harness killed hard. The fix was a rule given in the prompt: stop processes by PID, never by name pattern. A guardrail could enforce that rule as policy. The operator then made the same mistake with its own shell command, which suggests the hazard belongs to how the action is written, not to any one agent.

**Confident fabrication from memory: context, caught by evaluation.** The slides were written from semantic memory, and memory is a summary. On review, the primitive decks needed 22 slides tightened but contained nothing invented. The production decks needed 47 slides corrected and 5 removed. Writing from memory, quark had filled gaps with runs that never happened, cache numbers no run produced, and a reversed account of which model was benched. Others simplified the code until it was misstated, or put a mechanism under the wrong primitive. This is a context failure: what the request held was a lossy summary, and the model could not tell it apart from fact. It was caught only by a review step, checking each slide against the source, which is evaluation done by hand.

**What the case study shows.** The 48-line harness did real work over many sessions: it read, wrote, ran and debugged code and documents. Every failure that came up could be placed under one of the five primitives or one of the six layers. The failures were also the ones the course had already described, so the taxonomy was useful for diagnosis and not only for description. This is one case, with the agent and its author both inside the system being studied, so it shows the framework in use and does not stand as independent evidence.

---

## 9. Discussion

### 9.1 What would refute this

The claim is falsifiable on purpose. It fails if someone finds a part of a working harness that:

1. fits none of the five definitions;
2. can't be described as hardening inside one or more of them;
3. isn't a nesting of harnesses (§4, multiple agents).

The course ends with that invitation: *if you find something that genuinely fits none of the five, I'd like to hear about it.* Candidates worth testing include:

- learned components inside the harness (a trained router, a reward model guiding search);
- speculative or tree-search decoding loops;
- harnesses whose control flow is itself generated by a model at run time.

On the current reading, these are respectively control flow plus a model interface, control flow, and control flow. But they are the places the boundary is most likely to be tested.

### 9.2 Limitations

- **Pedagogical, not statistical.** The evidence is constructive (a harness built from the primitives), closure-by-cases (six layers placed one by one) and one case study. It is not a measured survey of many systems. A systematic decomposition of open-source harnesses against the five primitives is the obvious next study.
- **One worked example.** quark is one way to build each primitive, not the only way. The course says so throughout, and gives a second, fuller implementation of every primitive and layer for that reason.
- **Some boundaries are judgment calls.** The routing vs. backup and streaming vs. printing splits follow from the definitions, but they had to be stated. Someone with other definitions could draw them elsewhere. The value of the definitions is that they make every such choice explicit.
- **The model is held fixed.** The two-part split deliberately sets aside model development. Fine-tuning a model on a harness's traces shifts work from one part to the other, and this paper doesn't analyze that trade.

### 9.3 Implications

- **Shared vocabulary.** "Our agent uses memory" becomes a claim about context: which components, assembled how, and fitted how. "Our agent is reliable" becomes claims about resilience in the model interface and output, and about evaluation outside them.
- **Reporting.** Calls to disclose the harness when comparing agents [11] need a schema for *what* to disclose. The five primitives, plus the six layers, are a candidate.
- **Buying vs. building.** Every product in §7 replaces one primitive or layer. Choosing one is choosing which part of your harness you can no longer see.

---

## 10. Related work

**Cognitive architectures.** *Cognitive Architectures for Language Agents* (CoALA) [1] organizes language agents into memory modules, an action space (internal and external), and a decision-making cycle, drawing on cognitive science and symbolic AI. It is the closest prior attempt to say what agents are made of. The two accounts differ in their source and their level. CoALA's categories come from cognition; these come from what harness code does to a request and a response. CoALA's memory modules, and the retrieval and learning actions that read and write them, correspond here to context; its reasoning actions are calls through the model interface. Its external actions correspond to output, with input bringing their results back. Its decision cycle corresponds to control flow. The model interface, and the production layers as a category, have no direct counterpart in CoALA.

**Agent primitives in multi-agent systems.** *Agent Primitives* [2] breaks multi-agent systems into recurring computation patterns (review, voting and selection, planning and execution) and implements them as reusable blocks that communicate through the KV cache. Its primitives are patterns *of* model calls. In this paper's terms they are shapes of control flow, together with a choice about how calls pass state to each other (as KV cache rather than text), which sits at the boundary of context and the model interface. The two approaches are complementary.

**Workflows and agents.** Anthropic's *Building effective agents* [3] distinguishes workflows from agents by who decides the path, and names five common workflow patterns (prompt chaining, routing, parallelization, orchestrator–workers, evaluator–optimizer) built on an "augmented LLM". This paper adopts the workflow/agent distinction as a property of control flow and splits the augmented LLM into context, output and the model interface (§4).

**Harness engineering.** A growing body of 2026 work studies the harness directly. It covers empirical studies of harness design for coding agents [12], deterministic execution constraints [13], contract-based harnesses for auditable enterprise agents [10], reusable tool primitives within a harness [14], and code as an agent harness [15]. A position paper argues that agents should not be compared without disclosing the harness [11]. These works treat the harness as the object of study. This paper supplies a definition of what that object contains.

---

## 11. Conclusion

An agent is a model wrapped in a harness, and a harness is five things: input, context, the model interface and output, with control flow sequencing them and deciding when to stop.

Built one at a time, outward from a single API call, the five make a working agent in 48 lines, and nothing else is needed. Hardened for production with observability, guardrails, sandboxing, resilience, performance and evaluation, the same harness grows to 196 lines and still has the same five parts. Each layer lives inside the primitives it hardens, and evaluation is the same five primitives turned around to measure the first harness from outside. Products in the field turn out to be single primitives sold separately.

The point is not that every harness should look like quark. It's that every harness, however large, can be read with five questions, and that each design choice belongs to exactly one of them. Five primitives are all you need to build an agent harness, and all you need to take one apart.

---

## Acknowledgments and disclosure of AI use

The course this paper draws on was built with two AI agents, and the paper says so because the case study depends on it.

- **Claude Code** (Anthropic) worked with the author on the course's README and primitive lessons, operated quark, reviewed its output, and helped draft this paper from the course's content.
- **quark**, the agent built in the course and running on Anthropic's Claude models, wrote the six production lessons and the slide decks, which were then reviewed and corrected as described in §8.

The thesis, the primitives, their definitions, and the method of the course are the author's. Every run quoted in this paper is reproduced in full, with transcripts, in the companion repository.

---

## References

[1] T. R. Sumers, S. Yao, K. Narasimhan, T. L. Griffiths. *Cognitive Architectures for Language Agents.* Transactions on Machine Learning Research, 2024. arXiv:2309.02427.

[2] H. Jin, P. Kuang, Y. Yu, X. Yuan, H. Wang. *Agent Primitives: Reusable Latent Building Blocks for Multi-Agent Systems.* ICML 2026. arXiv:2602.03695.

[3] E. Schluntz, B. Zhang. *Building effective agents.* Anthropic Engineering, 2024. https://www.anthropic.com/engineering/building-effective-agents

[4] LiteLLM. https://github.com/BerriAI/litellm

[5] OpenRouter. https://openrouter.ai

[6] Mem0. https://github.com/mem0ai/mem0

[7] LangGraph. https://github.com/langchain-ai/langgraph

[8] Langfuse. https://github.com/langfuse/langfuse

[9] Open Policy Agent. https://github.com/open-policy-agent/opa

[10] *From Prompts to Contracts: Harness Engineering for Auditable Enterprise LLM Agents.* arXiv:2607.08028, 2026.

[11] *Stop Comparing LLM Agents Without Disclosing the Harness.* arXiv:2605.23950, 2026.

[12] *An Empirical Study of Harness Design for Coding Agents.* arXiv:2609.20804, 2026.

[13] *Harness Engineering for Predictable Agentic Systems: An Empirical Study of Deterministic Execution Constraints.* arXiv:2608.26197, 2026.

[14] *Harness Engineering in LLM Tool Use via Agent-Native Reusable Tool Primitives.* arXiv:2609.01736, 2026.

[15] *Code as Agent Harness.* arXiv:2605.18747, 2026.

[16] Model Context Protocol. https://modelcontextprotocol.io

---

## Appendix A. The finished harness

The complete 48-line harness from §5, with the system prompt shortened to `...` (the full prompt is one line in [`lessons/04-context/quark.py`](../lessons/04-context/quark.py)). Comments mark which primitive each part belongs to; they are not in the original file.

```python
import subprocess, sys, os, datetime
from anthropic import Anthropic, BadRequestError

client = Anthropic()                                                    # model interface
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]  # output
def mechanics(): return "\n".join('def system(): return "<system prompt redacted so you can see your self mechanics in harness>"' if l.startswith("def system():") else l for l in open(__file__).read().split("\n"))  # context: self-knowledge
def system(): return [{"type": "text", "text": f"# Self Model\n\n**Identity:** You are quark ... **Where:** {os.getcwd()}\n**When:** {datetime.date.today()} ... ```python\n{mechanics()}\n```", "cache_control": {"type": "ephemeral"}}]  # context: instructions

def compact(working_memory, drop):                                      # context: compaction
    turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
    if drop > len(turns): sys.exit("[working memory can't be summarized small enough]")
    keep = working_memory[turns[drop]:] if drop < len(turns) else [working_memory[turns[-1]]]
    summary = client.messages.create(model="claude-sonnet-5-5", max_tokens=2048, system=system(), messages=keep + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}])
    gist = next((b.text for b in summary.content if b.type == "text"), "")
    return [{"role": "user", "content": f"[your prior working memory, summarized] {gist}"}]


task = " ".join(sys.argv[1:]) or input("> ")                            # input: from a person
chat = len(sys.argv) < 2
working_memory, drop = [{"role": "user", "content": task}], 0           # context: working memory

while True:                                                             # control flow
    try:
        if drop:
            working_memory, drop = compact(working_memory, drop), 0
        reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, system=system(), tools=tools, messages=working_memory)  # model interface
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
        continue

    results = []
    for block in reply.content:                                         # output
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})  # input: from the world

    working_memory.append({"role": "assistant", "content": reply.content})
    if results:                                                         # control flow: go again
        working_memory.append({"role": "user", "content": results})
        continue
    if not chat or (task := input("\n> ")) == "/q":                     # control flow: terminate or hand back
        break
    working_memory.append({"role": "user", "content": task})
```

## Appendix B. Where each production layer lives

| Layer | Control flow | Input | Context | Model interface | Output |
|---|:---:|:---:|:---:|:---:|:---:|
| Observability | ● | | | | |
| Guardrails | ● | | | | |
| Sandboxing | | | | | ● |
| Resilience | | | | ● | ● |
| Performance | (routing, in the fuller example only) | | ● | ● | ● |
| Evaluation | outside the harness; built from control flow, input, model interface and output | | | | |

---

© 2026 Chase Dovey, Average Joes Lab. This paper is licensed under [CC BY-NC-SA 4.0](../LICENSE-CONTENT). Code listings are MIT-licensed; see [LICENSE](../LICENSE).
