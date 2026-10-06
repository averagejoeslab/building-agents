# Five Primitives Are All You Need: Building an Agent Harness

**Chase Dovey**
Average Joes Lab

October 2026 · Preprint draft

Companion artifact (an open course with runnable code): [harness-engineering](https://github.com/averagejoeslab/building-agents) · Decomposition study: [supplement](./decomposition-study.md)

---

## Abstract

The software that surrounds a large language model (LLM) in an agent is described in the literature and in practice under many names: framework, scaffold, runtime, orchestration layer, harness. Recent work shows that this layer accounts for a substantial share of agent performance and that comparisons which omit it are misleading. It has not, however, been characterized in terms of its constituent parts. This paper provides such a characterization.

We separate an agent into two components. The **model** is treated as a fixed function, *TokensOut = Model(TokensIn)*. The **harness** comprises everything else, so that **Agent = Harness(Model)**. We argue that every harness is composed of **five mechanistic primitives**:

- **control flow**, which sequences the other four and determines termination;
- **input**, which gathers what is sent to the model, from a person or from the environment;
- **context**, which determines what the request contains and fits it to the model's context window;
- **the model interface**, which sends the request and receives the response;
- **output**, which handles the response, either by presenting it to a person or by executing it as a tool call.

Each primitive is defined both positively, by what it does, and negatively, by what it never does, so that the five are mutually exclusive.

The central argument is constructive. Starting from a single API call and adding one primitive at a time, we show that the deficiency at each step is precisely the next primitive. The result is a working agent of 48 lines of Python containing nothing outside the five.

Two results follow.

1. **Production concerns reduce to the primitives.** Observability, guardrails, sandboxing, resilience, performance and evaluation are shown to be hardening within the primitives they touch, not additional primitives.
2. **The decomposition holds on production systems.** We decompose three production coding agents (Claude Code, OpenAI Codex CLI and opencode) and find no component that requires a sixth primitive. The study also identifies where the original boundary rules were underspecified, and we refine them accordingly.

A case study, in which the constructed agent produced much of its own teaching material, illustrates the use of the decomposition for failure diagnosis.

---

## 1. Introduction

Descriptions of LLM agents use inconsistent terminology for the software around the model: *framework*, *scaffold*, *runtime*, *orchestration layer* and *harness* are all in common use. When the underlying systems are examined, however, they share a common mechanism:

1. a model is called;
2. some component determines what the call contains;
3. some component acts on what the call returns;
4. some component decides whether to call again.

The terminology varies; the mechanism does not.

The absence of a shared decomposition has practical costs.

- **Diagnosis.** Without names for an agent's parts, a failure cannot be attributed to a part.
- **Comparison.** Systems described in different terms cannot be compared directly.
- **The product landscape.** The same few ideas recur as separate products: memory layers, model gateways, tool protocols, tracing platforms, sandboxes and evaluation suites. Without a map, it is unclear which of them are new and which are existing ideas under new names.

Recent work establishes that this layer matters. Zhang et al. [4] argue that, among comparable frontier models, harness configuration can account for more of the variance in performance than the choice of model, and that agents should therefore not be compared without disclosing their harnesses. Fan et al. [5] hold a coding harness's loop fixed and vary three of its parts (planning, the action space and context management), finding that each alters agent behavior. Both treat the harness as a primary determinant of agent behavior. Fan et al. select parts of a harness to vary; the present work asks what the complete set of parts is.

Our approach is **reductive**: we decompose an agent until its parts are no longer shared across systems. It is also **mechanistic**: each part is defined by its function on the path from request to response, not by its name or by the product that provides it.

**Contributions.** Contributions 1–3 constitute the core of the paper; contributions 4–6 follow from them.

1. **A two-component view of agents,** Agent = Harness(Model), in which the model is a fixed function and all else is harness (§2).
2. **Five primitives of a harness,** each with a positive and a negative definition, together with rules for resolving cases at their boundaries (§3–4).
3. **A constructive argument for sufficiency:** a working agent built one primitive at a time, in which each step's deficiency is the next primitive (§5).
4. **A reduction of production concerns** to hardening within the primitives (§6).
5. **A decomposition of three production harnesses,** Claude Code, Codex and opencode, which finds no need for a sixth primitive and refines the boundary rules (§7).
6. **A case study** in which the constructed agent produced much of its own teaching material (§8).

The paper is accompanied by a companion artifact, *harness-engineering* [25], an open course with runnable code. The artifact builds the harness of §5 and the production layers of §6 incrementally and retains full transcripts of every run. The paper is self-contained: every listing and run on which the argument depends is reproduced in Appendices A–D.

---

## 2. Two components: the model and the harness

### 2.1 The model

The model predicts. Given a sequence of tokens, it produces a distribution over the next token:

> **TokensOut = Model(TokensIn)**

Viewed from outside, the model is a function. It retains no state between calls, cannot read from or act on its environment, and cannot initiate a further call. Everything it knows about the present moment is contained in its input. The model is the product of *model development* (training data, compute, and methods for training and evaluation), a separate discipline whose output we treat as fixed.

### 2.2 The harness

The harness comprises everything else. It determines how inputs are gathered, how they are presented to the model, how the model is called, how its outputs are handled, and how information flows among these steps:

> **Agent = Harness(Model)**

*Harness engineering* is the construction of this second component.

The division is deliberately coarse. Anything that is not the model's weights is harness: a system prompt, a tool, a retry policy, a memory store. Two agents built on the same model differ only in their harnesses; a comparison that omits the harness therefore omits the variable under study.

### 2.3 Method

The decomposition proceeds by repeated application of a single question:

> *What is it, and by what mechanistic primitives does it work?*

Applied to an agent, the question yields a model and a harness. Applied to a harness, it yields five primitives (§3). Applied once more, to a primitive, it yields answers that are no longer shared across systems: one harness's input reads a terminal, another's a chat channel, a third's a webhook. We take this as the stopping criterion. A primitive is the deepest level at which every harness still has the same parts.

Each primitive is given two definitions:

- a **positive** definition, stating what it does;
- a **negative** definition, stating what it never does and naming the primitive responsible for that function instead.

The negative definitions carry most of the analytical weight. They make the primitives mutually exclusive, so that each piece of harness code has exactly one home. A piece is assigned by **its function, not by its location in the code** or by its name (§4).

### 2.4 Scope

The primitives describe what happens on the path of a request at run time. Some software that ships with a harness never acts on that path, and we exclude it, as we exclude model development:

- **transport and hosting:** client/server splits, remote workspaces, the process serving a user interface;
- **persistence:** databases;
- **event wiring:** internal event buses;
- **configuration and packaging:** settings loaders, plugin installers.

These components carry, store or configure the primitives without constituting a step in a pass. Where such a component does act on the path, for example a saved transcript that the harness replays, that action is assigned like any other.

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

Input gathers what is to be sent. Context assembles it into a request and fits it to the model's window. The model interface sends the request and receives the response. Output handles the response, either presenting it to a person or executing a tool; a tool's result re-enters as input. Control flow determines what happens at the end of the path: another iteration, a turn for a person, or termination.

### 3.1 Model interface

**Does:** sends tokens to the model as a request and receives tokens as a response.

**Never does:** decide when to call (control flow), gather what is sent (input), determine how it is presented (context), or act on what is returned (output).

The model interface is the thinnest primitive, as a consequence of its position. The other four operate on the harness side; the model interface is the boundary itself, the parentheses in *Agent = Harness(Model)*. Its minimal form is a single SDK call. Richer implementations vary along several dimensions: the destination of the request (a hosted API, a local model, a gateway); its transport (an SDK, raw HTTP, a cross-provider translation layer); which model responds (a single model, or a backup when the first is unavailable); how the response arrives (whole or streamed); how many requests are sent (singly or in batches); failure handling (retries, backoff, timeouts); and request settings (output limits, reasoning effort, thinking summaries). All of these concern the delivery of one request and the receipt of one response.

### 3.2 Input

**Does:** gathers what is sent to the model, from a **person** (a task, a question, a message) or from **the environment** (the result of a tool execution: its output, its exit status, whether it failed).

**Never does:** determine how what it gathers is laid out in the request (context), send it (model interface), or decide whether to iterate (control flow).

Input is the harness's afferent pathway. Its sources include command-line arguments, prompts, pipes, chat applications, webhooks and schedules; its content may be text, images or files. Whatever the source, its function is to bring something from outside the harness to the edge of the request.

### 3.3 Output

**Does:** handles the model's response, either by **presenting** it to a person or by **executing** it as a tool call.

**Never does:** decide whether a tool's result is returned to the model (control flow), or determine what the next request contains (context).

Output is the efferent pathway. The model cannot act, but it can request an action: its response may contain a tool call, consisting of a name and arguments in a schema the harness has described to it. Output executes the call, and the result returns as input. The model requests; the harness acts. The design choices within output include which tools exist (one general tool or many specific ones); where they execute (locally, in a container, on a remote host, or at the provider); whether multiple calls execute sequentially or concurrently; when not to execute (a call truncated mid-generation is incomplete, and executing a partial command is worse than executing none); and how failures and hangs are handled.

Input and output are constructed independently but form two ends of a single exchange, which meets at the tool: output executes the call and input returns its result.

### 3.4 Control flow

**Does:** **sequences** the other four primitives, passing each one's product to the next, and **terminates**, deciding when to stop or return control to a person.

**Never does:** send the request (model interface), gather (input), present (context), or handle the response (output).

Control flow is the only primitive that contains the others. Its arrangement of them determines the kind of system that results.

| Shape | Arrangement | Who determines the next step |
|---|---|---|
| Single call | input → call → output, then stop | no one; it is fixed |
| Chat loop | call, present, return to the person, repeat | the person |
| Workflow | the harness code fixes the sequence of calls (e.g., draft, evaluate, revise) | the harness code |
| Agent loop | call; while the model requests tools, execute them, return the results, call again | the model |

The distinction between a *workflow* and an *agent* [3] is thus a property of control flow: which party determines the next step. Termination is an equal half of the definition. A loop without a defined termination condition has no bound on its cost. The minimal agent loop terminates when the model stops requesting tools; richer implementations also terminate on step limits, spending limits, refusals, or a person's instruction.

### 3.5 Context

**Does:** before every call, **assembles** what the request contains and **fits** it to the model's context window.

**Never does:** gather inputs (input), send the request (model interface), or decide when to call (control flow).

Each call begins without state. The model has no knowledge of its environment, the date, its own identity, its previous actions, or earlier instructions unless the harness includes them in the request. For this reason, a large share of what is built into harnesses is context. The following components are all means of determining what the model sees:

- **instructions:** the system prompt;
- **working memory:** the current session;
- **episodic memory:** prior sessions;
- **semantic memory:** durable facts;
- **procedural memory:** skills, recipes and playbooks;
- **retrieval:** search results inserted into the request;
- **compaction:** a summary substituted for history that no longer fits;
- **self-knowledge:** the agent's own description or source.

Input and context are distinct. Input brings an item to the edge of the request; context determines whether it is included, where, in what form, and what is removed to accommodate it.

### 3.6 Summary

| Primitive | Does | Never does |
|---|---|---|
| Model interface | sends the request, receives the response | decide when, gather, present, act |
| Input | gathers from a person or the environment | present, send, decide to iterate |
| Output | presents the response or executes a tool | decide whether results return, shape the next request |
| Control flow | sequences and terminates | send, gather, present, handle |
| Context | assembles and fits the request | gather, send, decide when |

---

## 4. Boundary rules

A taxonomy is only as useful as its treatment of difficult cases. The following rules resolve the cases encountered in this work. Each follows from the negative definitions of §3. Several were made explicit by the decomposition study of §7; these are marked.

**Assignment by function, not location.** Code that determines what the model sees is context, even when it resides inside a tool. For example, opencode attaches nested AGENTS.md files to the Read tool's result, and Claude Code's WebFetch tool condenses a page with a separate model call before the model sees it. Conversely, an approval decision is control flow even when it executes within a tool's runtime, as in Codex. *(Refined in §7.)*

**The tool channel.** In all three production harnesses studied, the model drives other primitives through tool calls: spawning a subagent, entering a planning mode, writing a task list, searching for tools, scheduling a wake-up, requesting a fresh context window. The tool call itself is output; its effect is assigned to the primitive it changes (control flow, context or input). *(From §7.)*

**Backup versus routing.** A change of model is classified by its trigger.

- If the change occurs because **the request could not be served** by the first model (it was unavailable, overloaded, or refused the request), it belongs to the **model interface**: it alters only how a single request obtains a response.
- If the change is **keyed to the work** (the task is simple; the current phase is planning), it is **routing**, a decision about the work, and belongs to **control flow**.

A fixed model for one class of request, such as compaction summaries, is a request setting and belongs to the model interface. Claude Code's `opusplan` setting, which uses one model for planning and another for execution, is keyed to the phase and is therefore control flow. A content-classifier fallback that retries a flagged request on another model is model interface; retaining the second model for the remainder of the session is a separate, control-flow decision. *(Refined in §7.)*

**Streaming.** *Receiving* a response as a stream is the model interface; *rendering* each fragment as it arrives is output.

**Parallelism.** Executing several *tool calls* from one response concurrently is output, since it concerns how those calls are executed. Issuing several *model calls* concurrently, whether to divide a task or to vote, arranges the work and is control flow.

**The reader of an artifact.** A record kept **for the model**, such as a searchable episode log, is **context**. A record kept **for the operator**, such as a trace of every call, is **observability** (§6). An artifact produced **for the user**, such as a per-turn diff of changed files, is **output**. A single file may serve several readers; Claude Code's session transcript is read by the operator and replayed by the harness on resumption. Each use is then assigned separately. *(Refined in §7.)*

**The consumer of a person's answer.** When the **harness** consumes the answer, as with an approval prompt, the answer is a **control-flow** decision, not new input. When the **model** consumes it, as when the model poses a question and receives the answer as a tool result, it is **input** from a person. *(From §7: Codex's `request_user_input`, opencode's question tool, Claude Code's AskUserQuestion.)*

**Direct actions by a person.** A shell command executed directly by the person (the `!cmd` syntax in Codex, Claude Code and opencode) brings environment state into the conversation and is input, although it reuses output's executor. *(From §7.)*

**Model-authored programs.** A program written by the model at run time is control flow if it sequences *model calls*; Claude Code's workflow scripts are an example. If it sequences only *tools*, it is output. The code-execution modes of Codex and opencode run model-written JavaScript that calls tools without calling the model, and are therefore output. *(From §7.)*

**Bundles.** A *mode*, a *skill*, a *hook system* or an *agent profile* is packaging that bundles settings across several primitives. Decomposed, each element has a single home. A planning mode, for instance, combines a context template, removed tools and an approval gate; a skill combines procedural memory, model-executable scripts and a tool allow-list; a hook system is a dispatcher (control flow) whose events each affect one primitive. *(From §7.)*

**The "augmented LLM".** The building block of a model augmented with retrieval, tools and memory [3] is not a primitive. It decomposes into context (retrieval, memory) and output (tools) around a model interface.

**Tool protocols.** The Model Context Protocol (MCP) [10] primarily provides pluggable output: tools built by third parties behind a common protocol. Its other features are assigned elsewhere: resources and prompts determine what the model sees and are **context**; *sampling* borrows the client's **model interface**; *elicitation* queries the person and is **input**. *(Refined in §7.)*

**Multiple agents.** Delegation from one agent to another is a shape of control flow, in which an outer harness sequences an inner one. It introduces no new primitive; it nests harnesses. The same rule covers model-backed components *within* a harness, such as an approval reviewer, a termination judge or a memory extractor: each is control flow combined with a model-interface call.

---

## 5. Constructive argument: the five primitives are sufficient

A taxonomy may be complete on paper yet incomplete in practice. The constructive test is to build an agent from the five primitives alone and determine whether anything further is required.

The construction proceeds outward from the model, in a different order from §3: the model interface first, since nothing reaches the model without it, and thereafter the primitive whose absence limits the preceding step. The worked example is quark, the author's agent. Each step's `quark.py` is the preceding step's file plus one primitive. All four files appear in Appendix A, and the runs quoted below appear in Appendix B. The implementation is one instantiation of each primitive among many.

### 5.1 Step 1: the model interface alone (9 lines)

The first harness consists of a single call. It sends a fixed question, *"What's in this directory?"*, and prints the full response. Three fields of the response are relevant: `content` (the output tokens, as blocks), `stop_reason` (why generation stopped) and `usage` (input and output token counts).

The model replies that it cannot see the directory and suggests running `ls`. It identifies the correct next action but cannot take it. Both ends of the path are stubs: the input is a fixed string, and the output is an unprocessed dump of the response.

### 5.2 Step 2: input and output (21 lines)

Input and output are constructed separately and then combined.

- **Input** takes a task from the command line and describes one tool, `bash`, in the request. Given *"how many lines are in README.md?"*, the model responds with a single `tool_use` block requesting `wc -l README.md`, with `stop_reason: tool_use`. With output still a stub, the request is not executed.
- **Output** processes each block of the response: text is printed and a tool call is executed with `subprocess`.
- **Combined,** the two require one further element: the command's result, wrapped as a `tool_result`, which constitutes input from the environment.

The combined harness executes `wc -l` and prints `71 README.md`. The model never observes this result; it is held in a list and not sent. The path terminates at output.

### 5.3 Step 3: control flow (30 lines)

The step-2 harness is placed inside a loop. The response and the tool results are appended to `messages`; if the model requested a tool, the loop calls the model again. When the model stops requesting tools, the run ends or, in interactive mode, returns control to the person.

Asked which step's `quark.py` is longest, the agent executed one `find … | wc -l` command and answered from its output. The run required two calls, and the second was possible only because the first call's result was returned.

The system is now an agent: the model determines the next step. The same four components arranged differently yield a single call, a chatbot or a workflow (§3.4); the artifact's second example for this step is an evaluator–optimizer workflow in which code determines the order of calls.

The agent, however, has no knowledge of its location, the date, its identity, or prior instructions, and `messages` grows without bound, so a sufficiently long session exceeds the model's context window. A component that determines what the model sees is required.

### 5.4 Step 4: context (48 lines)

The final primitive adds five context components:

- **working memory:** the step-3 `messages` list, renamed to reflect its role;
- **instructions:** a system prompt structured as models of the agent's self, its world, other agents and its body (its tool), regenerated on every call so that the working directory and date are current;
- **self-knowledge:** the agent's own source file, embedded in the system prompt so that the model can inspect the harness in which it runs;
- **semantic memory:** a file the agent reads and writes with its existing tool, requiring no dedicated memory code;
- **reactive compaction:** when the API rejects a request as too long, the oldest turns are dropped and the remainder summarized.

Three runs demonstrate the result. Asked what it is, the agent describes its name, its tool, its loop and its memory file, all of which are present in its context. Instructed to remember that the user prefers short answers, it writes an entry to its memory file. In a new session with empty working memory, asked what it knows about the user, it reads the file and answers accordingly. Working memory did not persist between runs; semantic memory did.

### 5.5 Summary of the construction

| Step | Adds | `quark.py` | Remaining deficiency |
|---|---|---|---|
| 1 | Model interface | 9 lines | Both ends are stubs; the model identifies `ls` as the next action and cannot execute it. |
| 2 | Input and output | 21 lines | A tool executes, but its result never reaches the model. |
| 3 | Control flow | 30 lines | The result is returned, but the agent has no knowledge of itself, its environment or its history, and its history is unbounded. |
| 4 | Context | 48 lines | None: the agent operates, retains knowledge across sessions, describes itself, and compacts when its window is full. |

At each step the remaining deficiency is the next primitive, and no step requires a component outside the five. The finished harness appears, annotated by primitive, in Appendix A.4.

The artifact also provides a second, fuller implementation of each primitive, to show that each is a space of design choices rather than a single design. These comprise a model interface with timeouts, retries, a backup model, streaming and adjustable reasoning settings; input and output through a Telegram chat, with two tools executed concurrently, timeouts, and suppression of truncated tool calls; control flow with a step limit, refusal handling, and the evaluator–optimizer workflow; and context with an episode log, skill files, token counting before each call, and truncation of long tool results. None required a sixth primitive.

---

## 6. Production concerns reduce to the primitives

A working harness is not yet suitable for unattended operation. Production agents add tracing, approvals, sandboxes, retries, caching and evaluation, each with its own products and literature, and it is natural to regard each as a new building block. The decomposition implies otherwise.

> **Corollary.** Production concerns contribute *hardening*, not new primitives. Each element of a production layer resides within a primitive, at a point where that primitive already acts.

The second part of the artifact tests this corollary one layer at a time. Each layer's `quark.py` is the preceding file plus that layer, and each layer is documented with the primitives on which it is built and those it leaves unchanged. The code each layer adds appears in Appendix C. The layers are summarized below.

| Layer | Resides in | Rationale | Mechanism | Lines added (`quark.py`) |
|----|----|------|------------|----|
| Observability | control flow | the only primitive with visibility of the whole sequence | reads the clock, `usage` and exit codes already present; appends one JSON record per event | +12 (59) |
| Guardrails | control flow (primarily) | control flow already decides whether a request becomes a command and whether to iterate | allow, ask or deny before each tool; refusals returned as readable tool results; step, token, cost and repetition limits; interruption | +26 (83) |
| Sandboxing | output | where a tool executes was always output's decision | commands executed via `docker exec` in a container with no network, capped resources, a read-only root and only the working directory mounted, so that the kernel, not a textual check, enforces the limits | +13 (94) |
| Resilience | model interface, output, context | where the environment can fail, and what must be replayed | retries with backoff, a backup model and clean termination; an answer for every tool call, including malformed ones; per-step persistence and resumption, marking interrupted commands as *may or may not have run* | +53 (135) |
| Performance | context, model interface, output | where tokens and latency are incurred | cache markers and trimming (context); streaming and a fixed small model for summaries (model interface); concurrent tool execution (output) | +47 (159) |
| Evaluation | outside the harness | it treats the agent as a black box | an outer loop that prepares a case, runs the real agent, grades the resulting state, and compares with the previous run | +38 (196) |

Several entries require qualification.

**Some layers span several primitives without adding one.** For resilience, a retry occurs within a single call (model interface), answering a malformed tool call is output, and resumption replays saved working memory (context); Codex performs the equivalent at request assembly, synthesizing "aborted" results for unfinished tool calls. For performance, concurrent execution of the model's tool calls is output, and a cache marker is a decision about request layout and therefore context. The artifact's fuller performance example also routes each task to a model tier; that element is control flow under the routing rule of §4.

**Guardrails reside primarily, but not exclusively, in control flow.** In opencode and Claude Code, denied tools are also removed from the request, and that element is context. The decision retains a single home, while its enforcement may extend into another primitive.

**Layers are not mutually independent.** An earlier formulation of the corollary stated that each layer leaves the other primitives unchanged. The production harnesses show this to be too strong. In Codex, the approval policy and the sandbox policy are mutually dependent: (i) the approval requirement is computed from the sandbox setting; (ii) an approval alters how the command executes; and (iii) a sandbox denial triggers a further approval. Claude Code is similar: its sandbox can substitute for a permission prompt, and the model can request to leave the sandbox, which routes the request back through the guardrails. Each element still resides in one primitive. The primitives remain disjoint; the layers do not remain independent.

**Evaluation is the exception that confirms the rule.** It resides in none of the five because it is external to the agent, yet it is constructed from them: an outer **control-flow** loop, the task supplied as **input**, the check executed as **output**, and a model grader reached through the **model interface**. It is a second harness wrapped around the first. In the artifact it detected an apparently harmless change: reducing the step limit from 20 to 1 left three of four cases passing and flagged the fourth as `REGRESSED` (Appendix C.6). In the production harnesses, evaluation is likewise external: Codex and opencode ship only engineering tests against mocked or recorded model responses, and Claude Code's `claude plugin eval` grades plugins and skills by running the real agent.

The production harness of 196 lines can therefore be read under the same five headings as the 48-line harness. The layers strengthen the primitives without extending them. The corollary is supported by cases rather than proven; §9 states the conditions under which it would be refuted.

---

## 7. Decomposition of production harnesses

If the primitives are adequate, production harnesses, including large systems not designed for teaching, should decompose under them. We decomposed three production coding agents component by component, using the checklist with which the artifact concludes:

```
control flow          what kind of loop? who decides when to stop?
├── input             where do inputs come from: people, the world, both?
├── context           what does the request hold? which memories? how does it fit?
├── model interface   where does the request go, and how does the response come back?
└── output            where do outputs go? which tools, and how are they run?
```

### 7.1 Method

For each harness we (i) mapped the modules on the request path; (ii) assigned every substantive component to exactly one primitive, or to a production layer together with the primitive in which that layer resides, citing evidence and a justification from the definitions of §3; and (iii) recorded every component that was difficult to assign, testing each against the question of whether it fits none of the five.

| Harness | Source | Version |
|---|---|---|
| **OpenAI Codex CLI** [22] | source code, [github.com/openai/codex](https://github.com/openai/codex) (Rust, `codex-rs/`) | commit `7ac954e`, 2026-10-06 |
| **opencode** [23] | source code, [github.com/anomalyco/opencode](https://github.com/anomalyco/opencode) (TypeScript; formerly `sst/opencode`) | commit `652c090`, v1.18.34, 2026-10-06 |
| **Claude Code** [24] | public documentation only (code.claude.com/docs and Anthropic engineering posts); the source is not published | documentation as of 2026-10-06 (CLI v2.1.288) |

The decomposition was performed with AI assistance. An agent read the source code or documentation with the definitions of this paper and recorded each assignment with file-and-line or URL evidence, so that every assignment can be verified against its source. The complete tables, with the evidence for each assignment, are provided in the [supplement](./decomposition-study.md).

### 7.2 Design choices within each primitive

| | Claude Code | Codex | opencode |
|---|---|---|---|
| **Control flow** | Agent loop that is also a chat loop: the user may interrupt, and messages entered mid-turn are queued into the same turn. Terminates on: no tool calls, `maxTurns`, `maxBudgetUsd`, a refusal, a Stop-hook veto. Nested: subagents (up to 3 levels, 20 concurrent), agent teams, model-written workflow scripts, a model-judged `/goal`, schedules. | Agent loop within a chat loop. Terminates on: no tool call, a Stop hook, an error, an interrupt, a session token budget. **No step limit.** Nested: review mode, sub-agents, an LLM approval reviewer ("guardian"). | Agent loop with user turns between runs. Terminates on: natural completion, structured output, a content filter, a denied permission, cancellation. The step limit is **soft**: the model is instructed to stop but tools are still provided. Nested: subagents via a `task` tool. |
| **Input** | Terminal, IDE, web, Slack, `-p`, stdin, the SDK stream; tool results; background-task and channel events; schedules; questions posed by the model to the user. | TUI, headless `exec`, a JSON-RPC app server, voice; text, images, audio, mentions; mid-turn steering and an inter-agent mailbox; tool results; `!cmd`. | A single HTTP server fed by the TUI, the CLI, editors (ACP), web and desktop applications, a GitHub Action and Slack; @files, images, MCP resources, slash commands, `!cmd`; tool results; language-server diagnostics after edits. |
| **Context** | System prompt and output style; a CLAUDE.md hierarchy (managed, user, project, local); a model-written memory file; skills loaded on demand; on-demand search instead of an index; reminders; clear-then-summarize compaction; tool search; truncation within tools; a cache-ordered layout. | Model-specific base instructions; AGENTS.md from root to working directory; an environment block re-sent only on change; working memory with truncated tool outputs; local or server-side compaction before, during and after a turn; cross-session memories; skills; deferred tool loading. | A system prompt per model family; an environment block; AGENTS.md and CLAUDE.md; skills; mode reminders; proactive and reactive compaction; pruning of old tool outputs; truncation that spills to a file; cache markers. |
| **Model interface** | Anthropic SDK over four providers or a gateway; streaming; retries with a timeout; a fallback chain for outages; a small model for background calls; effort, thinking and cache settings. | Responses API only; WebSocket with an HTTP fallback; always streamed; retries with backoff and jitter; OpenAI, Bedrock, Ollama and LM Studio; effort and service tier. No backup model for turns. | Vercel AI SDK over approximately 20 bundled providers; always streamed; retries with backoff; a small model for titles. No backup model. |
| **Output** | Many specific tools, with Bash as the general fallback; read-only tools in parallel, writes sequentially; background commands; MCP; server-side tools (web search); terminal, JSON or stream-JSON output. | Unified PTY execution, `apply_patch`, planning, image and MCP tools, hosted web search, a JavaScript code mode; each tool starts as soon as its call finishes streaming; a lock permits parallel execution of safe tools. | bash, read, edit, write, patch, grep, glob, task, web, todo, skill and question tools, plus MCP and plugins; executed concurrently by the SDK; a code mode; rendered through the server's event stream. |

The three harnesses make markedly different choices within each primitive: termination conditions, input sources, context fitting, and tool execution. Each of these choices, however, lies within a primitive.

### 7.3 Production layers

| Layer | Claude Code | Codex | opencode |
|---|---|---|---|
| Observability | ✔ OpenTelemetry metrics, events and traces; transcripts; cost | ✔ OpenTelemetry, tracing spans, a trace bundle | ✔ structured logs, OpenTelemetry spans, per-step tokens and cost |
| Guardrails | ✔ six permission modes, allow/ask/deny rules, hooks, a learned auto-approval classifier, turn and budget limits | ✔ approval policies, a rule language for commands, an LLM reviewer, hooks, a token budget | ✔ allow/ask/deny rules per agent, a repetition check (the same call three times), a subagent depth limit |
| Sandboxing | ✔ Seatbelt or bubblewrap with a network proxy (off by default); worktrees; cloud VMs | ✔ Seatbelt; bubblewrap, seccomp and Landlock; Windows restricted tokens; a network proxy | ✘ no kernel-enforced limits: permission prompts, worktrees, and a confined interpreter for code mode only |
| Resilience | ✔ retries, a fallback chain, snapshots before edits, resumption and forking | ✔ retries, a transport fallback, answers for aborted tools, resumption and forking from a saved log | ✔ retries, interrupted tools still answered, every part persisted as it streams, snapshots and revert |
| Performance | ✔ prompt caching, tool search, streaming, parallel reads | ✔ streaming, incremental WebSocket requests, a cache key, environment diffs, parallel tools | ✔ cache markers, pruning and truncation, concurrent tools |
| Evaluation | partial: `claude plugin eval`, external to the agent, for plugins and skills | ✘ engineering tests against a mocked model only | ✘ engineering tests with recorded model responses only |

Every layer of §6 appears in at least two of the three harnesses, and each resides where the corollary predicts. The one layer absent from all three cores, evaluation, is the layer the corollary places outside the harness.

### 7.4 Difficult cases

The purpose of the study was to find a component that does not fit. The following components exerted the most pressure on the decomposition, and their resolution is recorded here.

1. **Hook systems** (Claude Code, Codex, opencode plugins). A hook system can block a tool, add context, rewrite a tool's arguments, veto termination, or log. It is a bundle, not a part: the dispatcher is control flow, and each event's effect is assigned to one primitive. One effect remained a matter of judgment: Claude Code's `updatedInput`, which rewrites the model's tool arguments before execution. Because it handles the response, we assign it to output, although it is used as a guardrail.
2. **Coupling between guardrails and sandboxing** (Codex, Claude Code). These cases exerted the strongest pressure on §6 and motivated the revision of its claim. They do not add a primitive.
3. **Model-backed components within the harness:** Claude Code's auto-approval classifier and `/goal` judge, Codex's guardian reviewer, and Codex's memory extraction. Section 9.1 anticipated that learned components would test the boundary. All four resolve as the decomposition predicts: control flow combined with a model-interface call, that is, a nested harness.
4. **Model-authored programs.** Claude Code's workflow scripts sequence agents and are therefore control flow authored at run time. The code modes of Codex and opencode execute model-written JavaScript that calls tools without an intervening model call, and are therefore output. This was the case closest to a counterexample; it resolved once the rule of §4 was stated: a program is control flow when it sequences model calls.
5. **Undo.** Claude Code's "restore code" and opencode's revert roll back files at the person's request rather than the model's. Snapshotting before each edit is resilience within output, and deleting messages is context. The file restoration itself, however, does not handle a model response. We assign it as resilience over output's past actions. It is the weakest fit in the study and is discussed in §9.2.
6. **Server-side harness components.** Claude Code's server-side classifier review, Codex's server-side compaction, and provider-side rerouting of a request to a different model all execute on the provider's side of the boundary. Each is still assignable (respectively a guardrail, context, and a model-interface event presented to the person), but they show that the boundary denoted by the parentheses in *Agent = Harness(Model)* does not coincide with the client/server boundary.
7. **A remote agent behind the model interface.** opencode can treat GitLab's Duo Workflow service as a "language model"; the service runs its own agent loop and invokes opencode's tools. It resolves only as a nested harness whose interface is a remote agent rather than a model.
8. **Persistence that also serves as a trace.** Each harness's saved transcript is read by the operator (observability) and replayed on resumption (context). This is one artifact with two readers; each use is assigned separately.

**Result.** Every run-time component of the three harnesses either resides in one primitive, decomposes into elements that each reside in one, or nests a harness. No component requires a sixth primitive. The study did alter the paper: it made explicit five rules that had previously been applied implicitly (assignment by function, the tool channel, the reader of an artifact, the consumer of a person's answer, and model-authored programs), and it weakened one claim, the independence of layers.

### 7.5 Products

The same analysis applies to products. Each product is *centered on* a primitive or layer, and most extend into others.

| Product | Centered on | Also touches |
|-----|--------|--------|
| LiteLLM, OpenRouter (gateways) [6, 7] | the model interface: one API over many providers, load balancing, failover to backup models, retries, rate-limit handling | spending limits (guardrails), logging (observability), response caching (performance); OpenRouter's Auto Router selects a model per prompt, which is routing and therefore control flow |
| MCP [10] | pluggable output: tools behind a common protocol | resources and prompts (context), sampling (model interface), elicitation (input) |
| Mem0 [8] | context: stores what to remember, returns what is relevant per request | extraction is itself a model call |
| LangGraph [9] | control flow: steps and edges defined as a graph and executed | its checkpointer serves resilience, working memory (context) and approval pauses (guardrails) |
| Langfuse, LangSmith [11, 12] | observability, hence control flow | evaluation; versioned prompts served at run time (context) |
| Open Policy Agent [13] | the decision component of guardrails; the harness enforces it | none |
| NeMo Guardrails [14] | guardrails in control flow: allow or block around each call | input and retrieval rails that modify what the request contains (context) |
| E2B, Daytona, Modal Sandboxes [15–17] | sandboxing, hence output | snapshot and resume (resilience) |
| Temporal [18] | resilience: records, retries and replays each step | executes the user's workflow code and thus also hosts control flow |
| Braintrust, promptfoo, Inspect [19–21] | evaluation: executes and grades cases, retains history or logs | production tracing (Braintrust); Inspect also supplies the agent under test |

Products are thus composed of primitives as well: each is marketed as a single capability and constructed from several.

---

## 8. Case study: an agent that wrote its own lessons

The finished 48-line harness was used for substantive work on the companion artifact, the repository that teaches it. Claude Code operated it from a terminal, as a person would; quark had no knowledge of Claude Code. The supporting evidence appears in Appendix D. Over four runs, quark:

1. read the entire repository and recorded what it learned in its memory file, producing approximately 25 KB of notes, one entry per lesson;
2. in a new session with empty working memory, wrote slide decks for the four primitive lessons *from memory alone*, without opening any lesson file;
3. wrote the six production lessons, one session per lesson, each building its `quark.py` from the preceding one, executing its code, and including the actual output;
4. in a further new session, wrote slide decks for the six production lessons, again from memory.

The arrangement itself instantiates the decomposition. The script that ran one quark session per lesson, halting if a lesson produced no `quark.py`, is control flow at a higher level: a workflow around an agent.

The failures are the instructive part of the study, and each is attributable to a primitive.

**A silent stop followed by a crash: model interface and output.** The session writing the observability lesson stopped twice without producing any output. A trace of each response's `stop_reason`, added for diagnosis (an instance of observability), identified the cause: with extended thinking enabled, an output limit of 4,096 tokens was insufficient for reasoning followed by writing a file. On the third attempt, a response reached `max_tokens` partway through a tool call, and the harness failed with `KeyError: 'cmd'`. This is the truncated tool call that §3.3 lists among the cases in which output should not execute. The remedy was a request setting, raising `max_tokens` to 16,384 throughout the artifact; the guard against the same failure, refusing to execute an incomplete call, is part of what the resilience layer adds to output.

**Self-termination: output, guardrails and sandboxing.** To test crash recovery, quark terminated its test agent with `pkill -9 -f 08-resilience/quark.py`. Its own command line contained that path, so the command also terminated quark. Its Docker container outlived it, which is the residual state the sandboxing layer had warned of for a harness that is killed abruptly. The remedy was a rule in the prompt: terminate processes by PID, never by name. A guardrail could enforce the same rule as policy. Claude Code, operating quark, subsequently made the same error with its own shell command, indicating that the hazard lies in how the action is expressed rather than in a particular agent.

**Confabulation from memory: context, detected by evaluation.** The slide decks were written from memory, and memory is a summary. The four primitive decks required 22 slides to be tightened but contained no invented content. The six production decks required 47 slides to be corrected and 5 to be removed: writing from memory, quark had filled gaps with runs that never occurred, cache figures that no run produced, and a reversed account of which model was disabled. Other slides simplified the code to the point of misstatement or assigned a mechanism to the wrong primitive. This is a context failure: the request contained a lossy summary that the model could not distinguish from fact. Only review, checking each slide against its source, detected it; that review constitutes evaluation performed manually.

**Discussion.** The 48-line harness performed substantive work across many sessions: it read, wrote, executed and debugged code and documents. Every failure was attributable to a single primitive or layer, and each was a failure the artifact had already described in §3 and §6. The decomposition was therefore useful for diagnosis, not only for description. This is a single case in which both the agent and the author are participants; it illustrates the decomposition in use and does not constitute independent evidence.

---

## 9. Discussion

### 9.1 Falsifiability

The claim is formulated to be refutable. It fails if a component of a working harness is found that (i) satisfies none of the five definitions; (ii) cannot be understood as hardening within one or more of them; and (iii) is not a nested harness (§4). The artifact concludes with an explicit invitation to report such a component.

Prior to the study, three classes of system were identified as the most likely to violate the boundary:

- learned components within the harness;
- search or decoding loops;
- harnesses whose control flow is generated by a model at run time.

The production harnesses provided live instances of the first and third classes, and all were accommodated: Claude Code's approval classifier and `/goal` judge, Codex's guardian reviewer, Claude Code's workflow scripts, and the code modes of Codex and opencode. Search and decoding loops did not arise and remain untested.

### 9.2 Points of strain in the definitions

No component required a sixth primitive, but two definitions are under strain.

**Output and person-initiated actions.** Output is defined with respect to *the model's* response. When a person reverts the agent's file changes (Claude Code's restore, opencode's revert), the harness acts on the environment without a model response. We assign this as resilience over output's past actions. A cleaner resolution might broaden output to *the harness acting on a person or the environment, typically at the model's request*. We retain the narrower definition because it is the one the artifact teaches; this is the first candidate for refinement.

**Model changes with compound triggers.** The backup-versus-routing rule classifies a model change by its trigger. A change that begins as a failure response and then persists, such as Claude Code's content-classifier fallback, comprises two decisions: model interface, then control flow. This is consistent with the rules, but shows that a single feature can span a boundary.

### 9.3 Limitations

- **The core evidence is the author's own.** The construction, the production layers and the case study derive from the author's artifact and agent. Section 7 adds three external systems, but only three, all of them coding agents. Harnesses for other domains (voice, browsing, robotics) have not been examined.
- **Claude Code was analyzed from documentation only.** Only its documented behavior could be verified, which is weaker than source analysis, particularly for the negative half of each definition.
- **The decompositions were AI-assisted.** Each assignment cites its evidence and can be checked, but a second, independent decomposition with a measure of inter-rater agreement would strengthen the result.
- **Some boundaries are stipulated.** The rules for backup versus routing, receiving versus rendering, the reader of an artifact, and the consumer of an answer follow from the definitions but had to be stated explicitly; alternative definitions could place these boundaries elsewhere. Their value lies in making each such choice explicit.
- **The model is held fixed.** Model development is excluded. Fine-tuning a model on a harness's traces shifts work between the two components, a trade-off not analyzed here.

### 9.4 Implications

- **A shared vocabulary.** A claim that an agent "uses memory" becomes a claim about context: which components, how they are assembled, and how they are fitted. A claim that an agent is "reliable" becomes a set of claims about resilience in the model interface and output, and about evaluation outside them.
- **A disclosure schema.** Calls to disclose the harness when comparing agents [4] require a schema specifying what to disclose. The five primitives and the production layers provide one, and §7.2 shows such a disclosure for three agents.
- **Build-versus-buy decisions.** Each product in §7.5 replaces part of a primitive or a layer. Adopting a product is a decision about which part of the harness becomes opaque to its builder.

---

## 10. Related work

**Cognitive architectures.** CoALA [1] organizes language agents into memory modules, an action space of internal and external actions, and a decision-making cycle. Drawing on cognitive science and symbolic AI, it is the closest prior account of the composition of agents. Its categories derive from cognition, whereas ours derive from the operations harness code performs on a request and its response. The correspondence is as follows: CoALA's memory modules, together with the retrieval and learning actions that read and write them, correspond to context; its reasoning actions correspond to calls through the model interface; its external actions correspond to output, with input returning their results; and its decision cycle corresponds to control flow. The model interface as a primitive, and production layers as a category, have no direct counterpart in CoALA.

**Agent primitives for multi-agent systems.** The term "primitives" is used in a different sense by Jin et al. [2], and the distinction requires clarification. They decompose multi-agent systems into recurring latent patterns (review, voting and selection, planning and execution) that communicate through the KV cache rather than text, composed per query by an organizer. Their primitives are patterns *of* model calls; in our terms they are shapes of control flow, including the organizer. Passing state through the KV cache is a design choice at the boundary between context and the model interface. The two accounts are complementary.

**Workflows and agents.** Schluntz and Zhang [3] distinguish workflows from agents by which party determines the execution path, and describe five workflow patterns built on an "augmented LLM": prompt chaining, routing, parallelization, orchestrator–workers and evaluator–optimizer. We adopt their workflow/agent distinction as a property of control flow, and decompose the augmented LLM into context, output and the model interface (§4).

**Harness engineering.** Two works provide the premise of this paper, and one of them also provides an external check.

- **Zhang et al.** [4] argue that harness configuration can account for more performance variance than model choice, and propose a standard for disclosing the harness. Their argument motivates the present work: if the harness matters to this degree, it requires a vocabulary. Section 9.4 proposes the five primitives as the schema such a disclosure requires.
- **Fan et al.** [5] hold a coding harness's loop fixed and vary planning, the action space and context management across four models, finding that each choice affects trajectories differently. These three dimensions were chosen independently of our framework, and each falls within one of the five primitives: planning is control flow, the action space is output, and context management is context. This is an independent decomposition that falls within ours. Their findings also support the observation of §7.2 that harnesses differ in the choices made *within* each primitive.

---

## 11. Conclusion

An agent is a model wrapped in a harness, and a harness consists of five primitives: input, context, the model interface and output, sequenced and terminated by control flow.

Constructed one at a time, outward from a single API call, the five primitives yield a working agent of 48 lines, with no further component required. This is the paper's central claim. The concerns a production harness adds subsequently, from observability to evaluation, reduce to hardening within the same five. Three production coding agents, built by three independent teams, also decompose under them; the study refined the boundary rules and found no component requiring a sixth primitive.

The claim is not that every harness should resemble quark. It is that every harness, irrespective of scale, can be analyzed with five questions, and that each of its design decisions belongs to exactly one of them. Five primitives suffice to build an agent harness and to take one apart.

---

## Acknowledgments and disclosure of AI use

The companion artifact was developed with two AI agents, and we disclose this because the case study depends on it.

- **Claude Code** (Anthropic) assisted the author with the artifact's README and primitive lessons, operated quark and reviewed its output, conducted the decomposition study of §7 under the author's direction, and assisted in drafting this paper from the artifact's content.
- **quark**, the agent constructed in §5, running on Anthropic's Claude models, wrote the six production lessons and the slide decks, which were subsequently reviewed and corrected as described in §8.

The thesis, the five primitives, their definitions and the method are the author's, and the author is responsible for every claim in this paper. Every run quoted here is excerpted in the appendices and reproduced in full, with transcripts, in the artifact.

---

## References

[1] T. R. Sumers, S. Yao, K. Narasimhan, T. L. Griffiths. Cognitive Architectures for Language Agents. *Transactions on Machine Learning Research*, 2024. arXiv:2309.02427.

[2] H. Jin, P. Kuang, Y. Yu, X. Yuan, H. Wang. Agent Primitives: Reusable Latent Building Blocks for Multi-Agent Systems. *ICML*, 2026. arXiv:2602.03695.

[3] E. Schluntz, B. Zhang. Building Effective Agents. Anthropic Engineering, December 19, 2024. https://www.anthropic.com/engineering/building-effective-agents

[4] Y. Zhang, J. Wang, Y. Ge, W. Xu, J. Hamm, C. K. Reddy. Stop Comparing LLM Agents Without Disclosing the Harness. arXiv:2605.23950, 2026.

[5] R.-Z. Fan, Z. Zhang, S. Ma, Y. Hu, S. Wang, K. Song, F. Liu, H. Zamani, X. Wang. An Empirical Study of Harness Design for Coding Agents. arXiv:2609.20804, 2026.

[6] LiteLLM. Router: load balancing and fallbacks. https://docs.litellm.ai/docs/routing

[7] OpenRouter. Model fallbacks; Auto Router. https://openrouter.ai/docs/guides/routing/model-fallbacks

[8] Mem0. Memory operations. https://docs.mem0.ai/core-concepts/memory-operations/add

[9] LangGraph. Persistence. https://docs.langchain.com/oss/python/langgraph/persistence

[10] Model Context Protocol. Architecture overview. https://modelcontextprotocol.io/docs/learn/architecture

[11] Langfuse. https://github.com/langfuse/langfuse

[12] LangSmith. Observability. https://docs.langchain.com/langsmith/observability

[13] Open Policy Agent. Documentation. https://www.openpolicyagent.org/docs

[14] NVIDIA NeMo Guardrails. Guardrail types. https://docs.nvidia.com/nemo/guardrails/latest/about/rail-types.html

[15] E2B. Documentation. https://e2b.dev/docs

[16] Daytona. Sandboxes. https://www.daytona.io/docs/en/sandboxes/

[17] Modal. Sandboxes. https://modal.com/docs/guide/sandboxes

[18] Temporal. Event History. https://docs.temporal.io/encyclopedia/event-history

[19] Braintrust. Evaluate. https://www.braintrust.dev/docs/evaluate

[20] promptfoo. Introduction. https://www.promptfoo.dev/docs/intro/

[21] UK AI Security Institute. Inspect. https://inspect.aisi.org.uk/

[22] OpenAI. Codex CLI. https://github.com/openai/codex (commit 7ac954e).

[23] opencode. https://github.com/anomalyco/opencode (commit 652c090).

[24] Anthropic. Claude Code documentation. https://code.claude.com/docs (accessed 2026-10-06).

[25] C. Dovey. *harness-engineering*: an open course with runnable code (companion artifact). Average Joes Lab, 2026. https://github.com/averagejoeslab/building-agents

---

## Appendix A. The build, file by file

The four files of §5 are reproduced in full. Each extends the previous file by one primitive.

### A.1 The model interface alone (9 lines)

```python
from anthropic import Anthropic

client = Anthropic()
reply = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=16384,
    messages=[{"role": "user", "content": "What's in this directory?"}],
)
print(reply.model_dump_json(indent=2))
```

### A.2 Plus input and output (21 lines)

```python
import subprocess, sys
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
task = " ".join(sys.argv[1:]) or input("> ")
reply = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=16384,
    tools=tools,
    messages=[{"role": "user", "content": task}],
)
results = []
for block in reply.content:
    if block.type == "text":
        print(block.text)
    if block.type == "tool_use":
        print(f"$ {block.input['cmd']}")
        done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(done.stdout)
        results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})
```

### A.3 Plus control flow (30 lines)

```python
import subprocess, sys
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

task = " ".join(sys.argv[1:]) or input("> ")
chat = len(sys.argv) < 2
messages = [{"role": "user", "content": task}]

while True:
    reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)

    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})

    messages.append({"role": "assistant", "content": reply.content})
    if results:
        messages.append({"role": "user", "content": results})
        continue
    if not chat or (task := input("\n> ")) == "/q":
        break
    messages.append({"role": "user", "content": task})
```

### A.4 Plus context: the finished harness (48 lines)

This is the full 48-line harness from §5, with the system prompt shortened to `...`. The full prompt is one long line in the artifact's `lessons/04-context/quark.py`; it holds the self, world, other-selves and body models described in §5.4, and ends with the file's own source. The comments mark which primitive each part belongs to; they are not part of the original file.

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
    if not chat or (task := input("\n> ")) == "/q":                     # control flow: stop, or hand back
        break
    working_memory.append({"role": "user", "content": task})
```

## Appendix B. The runs quoted in §5

Each excerpt is taken from a single recorded run; the model's wording varies between runs.

**B.1 The model interface alone.** The response's `content` holds an empty `thinking` block and a `text` block. The text begins:

```
I can't see your file system, so I can't tell what's in your directory. No files or tools have been shared in this conversation. Here's how you can check yourself:

**macOS / Linux (Terminal)**
ls          # basic listing
```

`stop_reason` is `end_turn`, and `usage` shows 15 input tokens and 331 output tokens, 38 of them thinking.

**B.2 Input, with output still a stub.** Given *"how many lines are in README.md?"*, the whole `content` is one tool request:

```
{"id": "toolu_01UksmSeN8qGMiYrrgfvUDZC", "input": {"cmd": "wc -l README.md"}, "name": "bash", "type": "tool_use"}
"stop_reason": "tool_use"
```

**B.3 Input and output together.** The same task. The command runs, and its result never reaches the model:

```
$ wc -l README.md
71 README.md
```

**B.4 Control flow.** *"which quark.py in the lessons folder is the longest? answer in one sentence"*. Two calls: one command, then the answer from its result.

```
$ find . -path "*lessons*" -name "quark.py" -exec wc -l {} + 2>/dev/null | sort -n
   9 ./lessons/01-model-interface/quark.py
  21 ./lessons/02-input-and-output/quark.py
  30 ./lessons/03-control-flow/quark.py
  48 ./lessons/04-context/quark.py
 108 total

The longest is `./lessons/04-context/quark.py`, at 48 lines.
```

**B.5 Context.** Three separate runs.

*"what are you, and how do you work? three sentences"*:

```
I'm quark, an AI agent whose only way of acting and observing is a bash shell. [...] For long-term memory I keep timestamped notes in `.quark/memory/memory.md`, so what I learn can carry over between sessions.
```

*"remember that I prefer short answers"*: it appended an entry to its memory file and replied:

```
- User preference: prefers short answers (keep replies brief)

I saved that. I'll keep my answers short.
```

*"what do you know about me?"*, in a new session with empty working memory:

```
$ ... cat .quark/memory/memory.md
# Quark Memory

## 2026-10-05 21:56:11
- User preference: prefers short answers (keep replies brief)

Not much yet. My memory has one note about you: you prefer short answers.
```

## Appendix C. The code each production layer adds

Each layer's `quark.py` is the previous file plus the lines below, abbreviated where marked. Comments indicate the primitive in which each element resides.

**C.1 Observability (+12 lines), in control flow.** One function, called at each point the loop already passes: the start, after each model call, after each tool, on each compaction.

```python
def trace(**event):                                    # observability: append one JSON line per event
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "run": run, **event}) + "\n")
...
trace(event="model", seconds=round(time.time() - start, 2), stop_reason=reply.stop_reason, input_tokens=reply.usage.input_tokens, ...)
```

**C.2 Guardrails (+26 lines), in control flow.** A gate before each tool, and limits before each call.

```python
MAX_STEPS, MAX_TOKENS = 20, 200_000
SAFE = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "date", "echo", "du", "df", "stat", "file", "uniq"}
DENY = re.compile(r"\bsudo\b|rm\s+-\w*[rf]|mkfs|git\s+push|(curl|wget).*\|\s*(ba)?sh|\.env\b")
def guard(cmd):                                        # allow, deny or ask a person
    if DENY.search(cmd): return "blocked by policy"
    if not re.search(r"[;&<>$`\n(]", cmd) and all((p.split() or [""])[0] in SAFE for p in cmd.split("|")): return None
    try: answer = input(f"allow `{cmd}`? [y/N] ").strip()
    except EOFError: answer = ""
    return None if answer.lower() == "y" else f"the person said no: {answer or 'no'}"
...
    if steps >= MAX_STEPS or spent >= MAX_TOKENS: ...   # top of the loop: stop before another call
...
            if (no := guard(block.input["cmd"])):       # the refusal goes back as the tool's result
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": no, "is_error": True})
                continue
```

**C.3 Sandboxing (+13 lines), in output.** A container started once before the loop, and the tool call aimed at it.

```python
up = subprocess.run(["docker", "run", "-d", "--rm", "--name", box, "--network", "none", "--memory", "512m", "--cpus", "1",
                     "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only",
                     "--tmpfs", "/tmp", "-e", "HOME=/tmp", "--user", f"{os.getuid()}:{os.getgid()}",
                     "-v", f"{where}:{where}", "-w", where, IMAGE, "sleep", "infinity"], ...)
...
done = subprocess.run(["docker", "exec", box, "timeout", "-s", "KILL", str(TIMEOUT), "sh", "-c", block.input["cmd"]], ...)
```

**C.4 Resilience (+53 lines), in the model interface, output and context.** SDK retries and a backup model; a saved session; interrupted requests answered on resume.

```python
client = Anthropic(timeout=300, max_retries=3)         # model interface: retries with backoff
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]
def ask(**request):                                    # model interface: backup model, then stop cleanly
    for model in MODELS:
        try: return client.messages.create(model=model, **request)
        except (APIConnectionError, APIStatusError) as e:
            if isinstance(e, APIStatusError) and e.status_code < 500 and e.status_code != 429: raise
            trace(event="model_failed", model=model, error=type(e).__name__)
    raise Down()
def save(task, working_memory):                        # written atomically after each step
    ...
    os.replace(SESSION + ".tmp", SESSION)
def unfinished():                                      # context: replay working memory; answer what was lost
    ...
        working_memory.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b["id"], "content": "interrupted: the harness stopped before this finished, so it may or may not have run. Check before repeating it.", "is_error": True} for b in lost]})
```

**C.5 Performance (+47 lines), in context, the model interface and output.** A cache mark on the conversation, a cap on tool results, streaming, a small model for summaries, and tools run together.

```python
MODELS, FAST = ["claude-sonnet-5-5", "claude-opus-5-5"], ["claude-haiku-4-5"]   # FAST: compaction only
def ask(models=MODELS, live=False, **request):         # model interface: stream the reply
    ...
            with client.messages.stream(model=model, **request) as stream: ...
def trim(text):                                        # context: keep the start and end of a long result
    if len(text) <= MAX_RESULT: return text
    return text[:MAX_RESULT // 2] + f"\n[... {len(text) - MAX_RESULT} characters cut ...]\n" + text[-MAX_RESULT // 2:]
def cached(working_memory):                            # context: mark the end of the conversation for the cache
    last = working_memory[-1]
    blocks = [{"type": "text", "text": last["content"]}] if isinstance(last["content"], str) else list(last["content"])
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return working_memory[:-1] + [{"role": last["role"], "content": blocks}]
...
    with ThreadPoolExecutor() as pool:                 # output: run the approved commands at the same time
        outputs = dict(zip(pending, pool.map(execute, pending.values())))
```

**C.6 Evaluation (+38 lines), outside the harness.** Four cases. Each sets up a fresh folder, runs the real agent on its task, and checks what the agent left behind.

```python
def evaluate(names):
    ...
    for case in cases:
        where = tempfile.mkdtemp(prefix=f"eval-{case['name']}-")
        subprocess.run(case["setup"], shell=True, cwd=where)
        try: subprocess.run([sys.executable, os.path.abspath(__file__), case["task"]], cwd=where, input="y\n" * 50, ..., timeout=300)
        except subprocess.TimeoutExpired: pass
        passed = subprocess.run(case["check"], shell=True, cwd=where, ...).returncode == 0
        ...
    return 1 if failed else 0
```

The baseline, and the same cases after lowering `MAX_STEPS` from 20 to 1:

```
pass  count      2 steps    4.1s    13435 tokens
pass  fix        3 steps    5.2s    20262 tokens
pass  rename     2 steps    3.9s    13428 tokens
pass  remember   2 steps    4.3s    13582 tokens
4/4 passed

pass  count      1 steps    3.0s     6687 tokens
FAIL  fix        1 steps    2.6s     6644 tokens  kept /tmp/eval-fix-1pf3a9_w  REGRESSED: it passed last time
pass  rename     1 steps    2.9s     6674 tokens
pass  remember   1 steps    3.1s     6778 tokens
3/4 passed
```

## Appendix D. Case-study evidence

**D.1 The silent stop and the crash.** The response trace that diagnosed it, one line per model call, from the third attempt at the observability lesson. The last response hit the cap partway through a tool request:

```
[trace] stop_reason=tool_use blocks=['thinking', 'tool_use'] out=3642 thinking=2498
[trace] stop_reason=tool_use blocks=['text', 'tool_use'] out=228 thinking=0
[trace] stop_reason=tool_use blocks=['thinking', 'tool_use'] out=148 thinking=70
[trace] stop_reason=max_tokens blocks=['thinking', 'tool_use'] out=4096 thinking=2260
  File "lessons/04-context/quark.py", line 37, in <module>
    print(f"$ {block.input['cmd']}")
KeyError: 'cmd'
```

**D.2 The agent that killed itself.** The command quark ran to test crash recovery while writing the resilience lesson. Its own command line contained `08-resilience/quark.py`, so the pattern matched quark too:

```
(yes y | uv run --project $R $R/production/08-resilience/quark.py "Run 'sleep 20; echo first > first.txt' as one command, ..." > out1.txt 2>&1 &) ; ... ; pkill -9 -f 08-resilience/quark.py; ...
```

**D.3 Fabrication from memory.** The two decks written from memory were checked slide by slide against the lessons:

- **The four primitive decks:** 22 slides tightened, none invented.
- **The six production decks:** 47 slides corrected and 5 removed.

The removed slides described runs that never happened, quoted cache numbers no run produced, or reversed which model had been disabled. The artifact keeps quark's transcripts and its memory file as they were after the runs.

## Appendix E. Where each production layer lives

| Layer | Control flow | Input | Context | Model interface | Output |
|---|:---:|:---:|:---:|:---:|:---:|
| Observability | ● | | | | |
| Guardrails | ● | | ○ hiding denied tools | | |
| Sandboxing | | | | | ● |
| Resilience | | | ○ replaying saved memory | ● | ● |
| Performance | ○ routing, in the fuller example | | ● | ● | ● |
| Evaluation | outside the harness, built from control flow, input, model interface and output | | | | |

● where the layer lives · ○ a slice that lands in another primitive

---

© 2026 Chase Dovey, Average Joes Lab. This paper is licensed under [CC BY-NC-SA 4.0](../LICENSE-CONTENT). Code listings are MIT-licensed; see [LICENSE](../LICENSE).
