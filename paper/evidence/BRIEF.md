# Deconstruction brief

You are gathering evidence for a paper that claims every LLM agent harness is built from five mechanistic primitives, and that everything else about a harness is either a design decision within a primitive or a production concern across them. Your job: deconstruct ONE harness, component by component, and record evidence a reader can check. Do not argue the thesis; record what is there. If something does not fit, say so: that is the most valuable finding.

## Definitions

An agent = Harness(Model). The model maps tokens to a next token and nothing more. The harness is everything else on the path of a request at run time.

The five primitives. Each has a positive definition (what it does) and a negative one (what it never does):

| Primitive | Does | Never does |
|---|---|---|
| **Input** | captures what comes in: a person's message, an event, a tool's result, a person's answer to a question the model asked | never decides what the model is shown (context), never runs anything (output) |
| **Context** | assembles what the model is shown on one call: instructions, tools' descriptions, the conversation, memories, retrieved material; fits it to the window (truncation, compaction, summaries) | never calls the model (model interface), never acts on the world (output) |
| **Model interface** | sends the request to the model and brings back the response: the client, the wire format, streaming, retries of a failed request, a backup model when the request could not be served | never decides what the request contains (context), never acts on the response (output) |
| **Output** | handles the response: shows words to a person, carries out tool calls and returns their results; the tool set, the executor, sandboxing of execution | never decides whether to go again (control flow), never assembles the next request (context) |
| **Control flow** | defines the shape of the loop: go again, hand back, or stop; step and token budgets; approval gates the harness consumes; sub-agent and multi-agent sequencing; routing to a model keyed to the work | never captures input, assembles context, calls the model or runs a tool itself |

Assignment rules:
- Assign by FUNCTION, not by file location or name. Code inside a "tool" that decides what the model sees is context.
- A tool call the model makes is output; its EFFECT is assigned to the primitive it changes (a "spawn sub-agent" tool is output, the spawning is control flow).
- A model change because the request could not be served (unavailable, overloaded) is model interface. A model change keyed to the work (planning vs. execution, cheap model for titles) is control flow.
- Receiving a stream is model interface; rendering fragments as they arrive is output.
- Several tool calls from one response run concurrently: output. Several model calls issued concurrently: control flow.
- A record kept for the model (searchable memory) is context. A record kept for the operator (traces, logs) is observability. An artifact for the user (a diff view) is output.
- A person's answer the HARNESS consumes (an approval) is control flow. A person's answer the MODEL consumes (an AskUser tool's result) is input.
- A program the model writes at run time that sequences model calls is control flow; one that sequences only tools is output.
- Modes, skills, hooks, agent profiles are BUNDLES: decompose each into its parts.
- Multi-agent: delegation is control flow of an outer harness; the inner agent is a harness of its own. Note depth and how results return.
- Out of scope (note but do not assign): hosting/transport, packaging, configuration loading, UI framework code, telemetry infrastructure itself (but WHAT is recorded is observability).

Six production concerns, each a question asked of the primitives: persistence (what outlasts the session), safety & security (what could do harm, who could make it: sandboxes, approvals, never-lists, secret handling, prompt-injection defenses), observability (what did it do: traces, logs, token accounting), resilience (what if something breaks: retries, timeouts, compaction on overflow, resume after crash), performance (slow or costly: caching, streaming, parallel tools, trimming), evaluation (how do we know it still works: test suites, evals of the agent).

## Output format

Write ONE Markdown file at the path you are given. Structure, exactly:

```
# <Harness name>

**Source:** <repo URL or docs URL> · **Version:** commit <full hash> (<date>) or "documentation as of <date>, CLI version X" · **Language:** …
**Path conventions:** <abbreviations you use>
**What it is:** two or three sentences: what the harness is for, who makes it, how the model is reached.

## Control flow
- **<component>:** <one sentence on the mechanism>. `path/file.ext:L123–L140`
...
## Input
## Context
## Model interface
## Output

## Production concerns
| Concern | Where it lives (primitive) | Mechanism | Evidence |
|---|---|---|---|
| Persistence | … | … | `path:line` |
| Safety & security | … | … | … |
| Observability | … | … | … |
| Resilience | … | … | … |
| Performance | … | … | … |
| Evaluation | … | … | … |

## Design decisions (one line each: the choice this harness made within a primitive)
- Input: …
- Context: …
- Model interface: …
- Output: …
- Control flow: …

## Hard cases
- **<component>:** why it was hard to place; which rule resolved it; or "DOES NOT FIT" with the reason.

## Summary row
| Input | Context | Model interface | Output | Control flow |
|---|---|---|---|---|
| ≤12 words | ≤12 words | ≤12 words | ≤12 words | ≤12 words |
```

Rules for evidence:
- Every bullet cites a file and line range at the pinned commit (run `git -C <repo> rev-parse HEAD` and record the full hash and `git log -1 --format=%ad --date=short`). Open the file and confirm the lines before citing. Line numbers must be exact.
- For a documentation-only harness, cite the page URL and the section heading, and the date you read it.
- Quote nothing longer than one line. Do not invent. If you cannot find a mechanism, write "not found" rather than guessing.
- Be concrete: name the function, the file, the loop, the stop condition, the compaction trigger, the sandbox technology, the retry policy.
- Aim for 40–80 evidence bullets in total. Prefer the request path (what happens from a user message to the next model call) over peripheral features.
