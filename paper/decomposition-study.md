# Supplement: decomposing three production harnesses

This supplement belongs to *[Agent = Harness(Model): Five Mechanistic Primitives of LLM Agent Harnesses](./agent-harness-primitives.md)*, §7. It gives the evidence behind each assignment, so a reader can check any line against its source.

| Harness | Source read | Version |
|---|---|---|
| OpenAI Codex CLI | source, [github.com/openai/codex](https://github.com/openai/codex) | commit `7ac954ea24116700632906d89715f7755cd3523e` (2026-10-06) |
| opencode | source, [github.com/anomalyco/opencode](https://github.com/anomalyco/opencode) (formerly `sst/opencode`) | commit `652c090dc119b5f3dc1e5e0bf1c4b40d9721f0ef`, v1.18.34 (2026-10-06) |
| Claude Code | public documentation only; the source is not published | code.claude.com/docs as of 2026-10-06 (CLI v2.1.288) |

**Path conventions:**
- Codex paths are relative to `codex-rs/`.
- In opencode paths, `oc/` = `packages/opencode/src/` and `core/` = `packages/core/src/`.
- In Claude Code links, `cc/X` = `https://code.claude.com/docs/en/X`.

**Method:** each part is assigned to one primitive, or to a production layer with the primitive it folds into. Each assignment gives evidence and a reason from the paper's definitions (§3–4). Line numbers are for the commits above.

---

## 1. OpenAI Codex CLI

### Control flow
- **Submission loop:** routes each operation (a turn's input, approvals, interrupts) to a task.
  `core/src/session/handlers.rs:423`
- **Turn loop:** `run_turn`. The loop continues on:
  - a tool call;
  - the server's `end_turn == false`;
  - pending user input.
  
  `core/src/session/turn.rs:164`, `:427–845`, `:577`
- **Stops:**
  - no follow-up (`turn.rs:661`);
  - a Stop hook (`:708`);
  - an error (`:838`);
  - an interrupt;
  - the session token budget (`core/src/agent/control/budget.rs:12–16`).
  
  There is no step or turn cap on the loop.
- **Nested harnesses:**
  - review mode (`core/src/tasks/review.rs:99–140`);
  - sub-agents (`core/src/agent/control/spawn.rs:281, 670`);
  - the guardian approval reviewer (`core/src/guardian/`).

### Input
- **From a person:** `Op::TurnInput` with text, image, audio, skill and mention (`protocol/src/protocol.rs:565`, `protocol/src/user_input.rs`).
- **Mid-turn:** steering and the inter-agent mailbox (`core/src/session/input_queue.rs:125–229`).
- **From the world:** tool results (`core/src/tools/parallel.rs:125–296`).
- **A person's `!cmd`:** recorded into history (`core/src/tasks/user_shell.rs:438–449`). This is input by the rule on direct actions by a person (§4).

### Context
- **Request assembly:** `build_prompt` (`turn.rs:1572–1601`).
- **Instructions:** base instructions (`models-manager/src/model_info.rs:16`) and AGENTS.md, root to cwd (`core/src/agents_md.rs`).
- **World state:** an environment block, re-injected only when it changes (`core/src/session/mod.rs:3600–3630`; `core/src/context/world_state/`).
- **Working memory:** history, with truncated tool outputs (`core/src/context_manager/history.rs:504–600`).
- **Compaction:**
  - local (`core/src/compact.rs:113`);
  - server-side (`core/src/compact_remote_v2.rs:79`);
  - triggered before, during and after a turn (`turn.rs:184, 612–659, 724–760`).
- **Memories and skills:** `memories/`, `skills/`.
- **Deferred tool loading:** `core/src/tools/handlers/tool_search.rs`.

### Model interface
- **Client:** Responses API only, over WebSocket with an HTTP/SSE fallback, always streamed (`core/src/client.rs:2237–2290`; `model-provider-info/src/lib.rs:100–111`).
- **Providers:** OpenAI, Bedrock, Ollama, LM Studio (`model-provider-info/src/lib.rs:660–695`).
- **Retries:** backoff with jitter, honoring `retry-after` (`core/src/responses_retry.rs:57–170`; `codex-client/src/retry.rs:43–51`).

### Output
- **Response handling:** `core/src/stream_events_utils.rs:315–358`.
- **Tool set:** `core/src/tools/spec_plan.rs`.
- **Unified exec:** `core/src/unified_exec/`.
- **Patches:** `apply-patch/`.
- **MCP:** `core/src/mcp_tool_call.rs`.
- **Code mode:** `core/src/tools/code_mode/`.
- **Execution:** tools start as each request finishes streaming (`turn.rs:2789`). Results are collected in order (`:3171`). A read/write lock lets parallel-safe tools run together (`tools/parallel.rs:205–209`).

### Production layers

| Layer | Where |
|---|---|
| Observability → control flow | `otel/`, `rollout-trace/`, tracing spans (`turn.rs:2553`), `core/src/tools/call_trace.rs` |
| Guardrails → control flow | approval requirement (`core/src/tools/sandboxing.rs:195`); orchestrator (`core/src/tools/orchestrator.rs`); command rules (`execpolicy/`, `core/src/exec_policy.rs`); guardian (`core/src/guardian/`); hooks; token budget |
| Sandboxing → output | Seatbelt (`sandboxing/src/seatbelt.rs`), bubblewrap + seccomp + Landlock (`linux-sandbox/`), Windows (`windows-sandbox-rs/`), network proxy (`network-proxy/`); selected in `sandboxing/src/manager.rs:310` |
| Resilience → model interface, output, context | retries and transport fallback (`client.rs:2271`); aborted-tool answers (`tools/parallel.rs:330–347`); synthetic outputs for unfinished calls at assembly time (`core/src/context_manager/normalize.rs:21`); JSONL rollout, resume and fork (`rollout/src/recorder.rs`; `core/src/thread_manager.rs:1267, 1477`) |
| Performance → context, model interface, output | environment diffs; trimming "to preserve cache" (`compact.rs:338–346`); incremental WebSocket requests and `prompt_cache_key` (`client.rs:357–391`); parallel tools |
| Evaluation | absent. `core/tests/suite/` tests the harness against a mocked Responses server |

### Hard cases
- **Approval and sandbox are coupled.**
  - The approval requirement depends on the sandbox policy (`core/src/tools/sandboxing.rs:199–206`).
  - An approval changes how the command runs, and a sandbox denial triggers a new approval (`core/src/tools/orchestrator.rs:228–560`).
  - Each piece has one home; the layers read each other. The paper's §6 changed because of this.
- **Guardian:** an LLM reviewer for approvals, so control flow plus a model-interface call, a nested harness.
- **`request_user_input`:** the answer is returned to the model, so it is input. Approvals are consumed by the harness, so they are control flow.
- **Code mode:** model-written JavaScript that calls tools without calling the model, so output, by §4's rule on programs the model writes.
- **Plan mode:** a template (context), a disabled tool (output), and a blocking question (control flow). It is a bundle, not a part.
- **Turn diffs:** shown to the user, never sent to the model (`core/src/turn_diff_tracker.rs`; `rollout/src/policy.rs:203`), so output.
- **`update_plan`:** shows the plan to a person and returns a constant (`core/src/tools/handlers/plan.rs:94–98`), so output.
- **A provider-side model reroute** happens beyond the boundary. The harness only shows a warning (`core/src/session/mod.rs:3930–3960`).

---

## 2. opencode

### Control flow
- **Loop:** `runLoop` (`oc/session/prompt.ts:1081–1341`). Each turn's outcome is compact, stop or continue (`oc/session/processor.ts:693–695`).
- **Stops:**
  - natural finish (`prompt.ts:1111–1130`);
  - structured output (`:1288–1293`);
  - content filter (`:1301–1308`);
  - a denied permission or question (`processor.ts:200–201`);
  - cancel (`prompt.ts:152–155`).
- **Soft step limit:** on the last step, a "tools are disabled" message is appended (`prompt.ts:1178–1179, 1281`), but the tools are still resolved and sent (`:1226–1241`). The decision is control flow; the enforcement goes through context.
- **Doom-loop check:** three identical calls in a row ask for permission (`processor.ts:353–380`).
- **Subagents:** the `task` tool recurses into a child session (`oc/tool/task.ts:198–221`), with a depth limit (`:107–118`).
- **Routing:** per-agent and per-command models (`oc/agent/agent.ts:281`; `prompt.ts:267`).

### Input
- **From clients:** one HTTP API (`POST /session/:id/message`) fed by the TUI, the CLI, ACP editors, web and desktop apps, a GitHub Action and Slack.
- **Building the user message:** `createUserMessage` (`prompt.ts:635`). It handles @files, images, MCP resources, slash commands and `!` shell (`:451`).
- **From the world:** tool results (`processor.ts:383–419`), and language-server diagnostics appended to edit results (`oc/tool/edit.ts:197–201`).

### Context
- **System prompt per model family:** `oc/session/system.ts:28–51`.
- **Environment block:** `:69–105`.
- **Skills:** `:107–119`.
- **AGENTS.md and CLAUDE.md:** `oc/session/instruction.ts`.
- **Reminders:** `oc/session/reminders.ts`.
- **Compaction and pruning:** `oc/session/compaction.ts:273–557`, `overflow.ts`.
- **Truncation that spills to a file:** `oc/tool/truncate.ts`.
- **Cache marks:** `oc/provider/transform.ts:358`.
- **Denied tools removed from the request:** `oc/session/llm/request.ts:210–216`. This is the guardrail slice that lands in context.

### Model interface
- **Client:** AI SDK `streamText` (`oc/session/llm.ts:280–353`), with about 20 bundled providers (`oc/provider/provider.ts:148–172`).
- **Retries:** backoff with jitter, honoring `retry-after` (`oc/session/retry.ts:26–36`).
- **Small model for titles:** `provider.ts:1961`.
- **Backup model:** none.

### Output
- **Tool registry:** `oc/tool/registry.ts:207–251`.
- **Tool wrapper:** `oc/tool/tool.ts:99–148`.
- **Shell:** spawn, timeout and kill (`oc/tool/shell.ts:293–309, 540–565`).
- **Execution:** tools run concurrently by the AI SDK (`oc/session/tools.ts:99–133`).
- **Display:** over the event stream to the TUI.

### Production layers

| Layer | Where |
|---|---|
| Observability | structured logs; OpenTelemetry (`core/observability.ts`; `llm.ts:208–222`); tool spans (`tool/tool.ts:145`); per-step tokens and cost (`processor.ts:452–469`) |
| Guardrails | allow/ask/deny rules (`oc/permission/index.ts`); per-agent rulesets (`agent.ts:119–264`); doom loop; subagent depth; denied tools hidden |
| Sandboxing | absent in the paper's sense. Commands run as plain child processes (`shell.ts:293–309`) |
| Resilience | retries; interrupted tools still answered (`processor.ts:585–607`); parts saved as they stream; snapshots and revert (`oc/snapshot/`, `oc/session/revert.ts`) |
| Performance | cache marks; pruning and truncation; small model for titles; concurrent tools |
| Evaluation | absent. Engineering tests use recorded model responses (`packages/http-recorder`) |

### Hard cases
- **Client/server:** transport and hosting, out of scope by §2.4. What crosses it is input or output.
- **Revert:** restoring files at a person's request is the weakest fit. It is assigned as resilience over output, and discussed in the paper's §9.2.
- **GitLab Duo Workflow as a "model":** a remote agent loop behind the model interface (`llm.ts:119–206`). Read as a nested harness.
- **A retry that spans tools:** tools run inside the streamed call, so retrying the stream may re-send a request after some tools already ran (`processor.ts:674–688`). This is a design hazard, not a new primitive.
- **Plugins and hooks:** each hook lands on one primitive. The loader and installer are packaging, out of scope.

---

## 3. Claude Code (documentation)

### Control flow
- **Agent loop** until no tool calls (`cc/agent-sdk/agent-loop`).
- **Stops:**
  - `maxTurns`;
  - `maxBudgetUsd`;
  - a refusal;
  - a Stop-hook veto, capped at 8 continuations (`cc/hooks`).
- **Interrupt and queued messages:** `cc/how-claude-code-works`, `cc/interactive-mode`.
- **Nested shapes:**
  - subagents, up to 3 layers deep and 20 at once (`cc/sub-agents`);
  - agent teams (`cc/agent-teams`);
  - workflow scripts the model writes (`cc/workflows`);
  - `/goal`, a model-judged stop hook (`cc/goal`);
  - schedules (`cc/scheduled-tasks`).
- **Plan mode:** an approval gate (`cc/permission-modes`).

### Input
- **From a person:**
  - terminal, IDE, web, Slack;
  - `-p` and stdin (`cc/headless`);
  - the SDK's streamed messages.
- **From the world:**
  - tool results;
  - Monitor event streams (`cc/tools-reference`);
  - channels (`cc/channels`).
- **Answers to the model's questions:** AskUserQuestion.

### Context
- **Instructions:**
  - system prompt presets (`cc/agent-sdk/modifying-system-prompts`);
  - output styles (`cc/output-styles`).
- **Memory:**
  - the CLAUDE.md hierarchy (`cc/memory`);
  - auto memory (`cc/memory#auto-memory`);
  - skills (`cc/skills`).
- **Fitting:**
  - compaction: clear old tool outputs, then summarize, then re-inject (`cc/context-window`);
  - tool search (`cc/mcp`);
  - in-tool truncation (`cc/tools-reference`).
- **Layout:** cache-ordered (`cc/prompt-caching`).

### Model interface
- **Providers:** Anthropic API, Bedrock, Google, Foundry, or a gateway (`cc/llm-gateway`).
- **Fallback:** a chain for outages (`cc/model-config#fallback-model-chains`).
- **Retries and timeout:** `cc/errors`.
- **Streaming:** yes.
- **Settings:** effort, thinking, fast mode (`cc/fast-mode`).

### Output
- **Tools:** Read, Edit, Write, Bash, Glob, Grep, WebFetch, WebSearch, LSP and more (`cc/tools-reference`).
- **Execution:** read-only tools in parallel, writes in sequence (`cc/agent-sdk/agent-loop`).
- **MCP:** `cc/mcp`.
- **Display:** terminal or JSON (`cc/headless`).

### Production layers

| Layer | Where |
|---|---|
| Observability | OpenTelemetry metrics, events and traces (`cc/monitoring-usage`); transcripts; cost |
| Guardrails | permission modes (`cc/permission-modes`); rules (`cc/permissions`); hooks; auto-mode classifier ([Anthropic, *Claude Code auto mode*](https://www.anthropic.com/engineering/claude-code-auto-mode)); caps |
| Sandboxing | Seatbelt or bubblewrap with a network proxy, off by default (`cc/sandboxing`; [Anthropic, *Claude Code sandboxing*](https://www.anthropic.com/engineering/claude-code-sandboxing)) |
| Resilience | retries; fallback chain; checkpoints (`cc/checkpointing`); resume and fork |
| Performance | prompt caching (`cc/prompt-caching`); tool search; streaming; parallel reads; `opusplan` routing (control flow) |
| Evaluation | `claude plugin eval` (`cc/plugin-evals`), outside the agent, for plugins and skills |

### Hard cases
- **Hooks:** a dispatcher (control flow) whose events land on different primitives:
  - permission decisions: control flow;
  - added context: context;
  - display rewrites: output.

  One judgment call remains. `updatedInput` rewrites the model's tool arguments, so it is assigned to output, although it is used as a guardrail.
- **Permissions and the sandbox read each other:**
  - the sandbox can stand in for a prompt;
  - the model can ask to leave the sandbox;
  - rules are merged into the sandbox configuration.

  See `cc/sandboxing`, `cc/permissions`.
- **Content-classifier fallback** (`cc/model-config#automatic-model-fallback`): model interface for the retried request, then control flow for staying on the second model.
- **Restore code** (`cc/checkpointing`): placed as resilience over output, the same weak fit as opencode's revert.
- **Server-side review** (`cc/permission-modes`): harness parts on the provider's side of the boundary.

**Limitation:** this decomposition rests on what the docs say. Undocumented behavior cannot be verified, and the "never does" half of each definition is weaker without the code.

---

## Notes on the method

The decompositions were done with AI assistance: an agent read the code or docs with the paper's definitions in hand and recorded each assignment with its evidence. Line numbers and URLs are given so each assignment can be checked independently. A second, independent decomposition would strengthen the result.
