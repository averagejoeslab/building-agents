# CrewAI (one Agent executing a Task with tools)

**Source:** https://github.com/crewAIInc/crewAI · **Version:** commit 6115839576d68d2e83b9f7f31e6c55d471e1fc64 (2026-10-15) · **Language:** Python
**Path conventions:** `c/` = `lib/crewai/src/crewai/`; `t/` = `lib/crewai/tests/`. All paths relative to the repo root.
**What it is:** CrewAI (crewAI Inc.) is a multi-agent orchestration framework in which a `Crew` runs `Task`s through role-playing `Agent`s. Each task execution hands a prompt to an `AgentExecutor`, a state-machine `Flow` that loops a ReAct-style LLM call and tool execution until a final answer. The model is reached through the `LLM` class, which routes to native provider clients (OpenAI, Anthropic, Azure, Gemini, Bedrock) or falls back to `litellm.completion`.

## Control flow
- **Crew task sequencing:** `kickoff` prepares inputs then dispatches to `_run_sequential_process` or `_run_hierarchical_process` (which first creates a manager agent); both call `_execute_tasks`, a `for` loop over tasks that runs each synchronously via `task.execute_sync` or asynchronously via a future, feeding prior outputs forward. `c/crew.py:L1053–L1069`, `c/crew.py:L1522–L1529`, `c/crew.py:L1595–L1635`
- **Agent step loop as a Flow:** `AgentExecutor` is a `Flow`; `check_max_iterations` routes to `continue_reasoning` (text ReAct) or `continue_reasoning_native` (API tool calls), tool routers return to `initialized`, and `finalize` ends when `current_answer` is an `AgentFinish`. `c/agents/agent_executor.py:L2404–L2422`, `c/agents/agent_executor.py:L1828–L1909`, `c/agents/agent_executor.py:L2544–L2624`
- **Iteration budget:** `max_iter` (default 25) is checked by `has_reached_max_iterations`; on exhaustion `ensure_force_final_answer` appends a "give your final answer" instruction and makes one more LLM call. `c/agents/agent_builder/base_agent.py:L285–L287`, `c/utilities/agent_utils.py:L364–L375`, `c/agents/agent_executor.py:L1600–L1621`, `c/utilities/agent_utils.py:L377–L432`
- **Task-level retries, timeouts and guardrails:** `Agent.execute_task` re-enters itself on exception up to `max_retry_limit`, optionally under a thread-pool `max_execution_time`; `Task._execute_core` then runs guardrails up to `guardrail_max_retries` times, re-executing the agent when one fails. `c/agent/core.py:L862–L908`, `c/agent/core.py:L1029–L1068`, `c/task.py:L893–L910`, `c/task.py:L1327–L1395`
- **Human-in-the-loop gate:** when `human_input` is set, `invoke` calls `_handle_human_feedback`, whose sync provider loops `input()` -> append feedback message -> re-run the flow until an empty reply. `c/task.py:L233`, `c/agents/agent_executor.py:L3079–L3098`, `c/core/providers/human_input.py:L255–L265`, `c/core/providers/human_input.py:L319–L364`

## Input
- **Crew inputs:** `kickoff(inputs)` normalizes a dict, runs `before_kickoff` callbacks, interpolates it into task and agent templates, and optionally runs crew-level planning. `c/crews/utils.py:L243–L379`
- **Tool results re-enter as text:** in text mode the observation is appended to the action text and pushed as an assistant message; in native mode each result becomes a `role: "tool"` message; tool errors are injected as "Observation: Error executing tool". `c/agents/agent_executor.py:L1845–L1871`, `c/agents/agent_executor.py:L2014–L2046`
- **Human feedback:** the feedback string is formatted with the `human_feedback` slice and appended to the executor's messages before re-running. `c/core/providers/human_input.py:L230–L235`, `c/agents/agent_executor.py:L3537–L3549`

## Context
- **System and user prompt assembly:** `Prompts.task_execution` concatenates i18n slices (`role_playing`, `tools` or `no_tools`, a skill block, a date block) into a system prompt and a `task` slice into the user prompt, substituting `{role}`, `{goal}`, `{backstory}`. `c/utilities/prompts.py:L93–L142`, `c/utilities/prompts.py:L211–L260`, `c/translations/en.json:L8–L19`
- **Task prompt enrichment:** `_prepare_task_execution` takes `task.prompt()`, adds an output schema and the prior tasks' context, then appends up to five recalled memories under a "Memories from past conversations" header; knowledge retrieval and training data are added next. `c/agent/core.py:L678–L705`, `c/agent/core.py:L757–L823`, `c/agent/core.py:L957–L993`
- **Message list per call:** `_setup_messages` builds system + history + user (+ trailing) messages with cache breakpoints; the executor's `state.messages` grows with every assistant and tool message within the task. `c/agents/agent_executor.py:L510–L543`, `c/agents/agent_executor.py:L3274–L3283`
- **Window fitting by summarization:** before each call `_proactively_summarize_context` asks the LLM whether the request exceeds 85% of the window and, if so, chunks and LLM-summarizes the history in place; a provider context-length error routes to `recover_from_context_length`, which summarizes when `respect_context_window` is set and otherwise exits. `c/utilities/agent_utils.py:L632–L663`, `c/llms/base_llm.py:L427–L450`, `c/utilities/agent_utils.py:L942–L981`, `c/utilities/agent_utils.py:L1019–L1100`
- **Cross-task memory store:** `Memory` is a pluggable store (LanceDB default) written after each task via `remember_many` and read by `recall`. `c/memory/unified_memory.py:L76–L92`, `c/memory/unified_memory.py:L237–L248`, `c/agent/core.py:L1968`

## Model interface
- **`LLM.call`:** emits a start event, runs before-call hooks, builds completion params, then dispatches to streaming or non-streaming handlers that call `litellm.completion`; native providers are substituted by `_get_native_provider` for OpenAI, Anthropic, Azure, Gemini and others. `c/llm.py:L1846–L1960`, `c/llm.py:L1238–L1304`, `c/llm.py:L640–L692`
- **Retries:** `BaseLLM` wraps every subclass `call` in `run_with_rate_limit_retry`: 3 attempts on throttling errors with exponential backoff (1 s to 8 s, 20% jitter), honoring a provider `Retry-After`. `c/llms/base_llm.py:L185–L206`, `c/llms/retry.py:L35–L38`, `c/llms/retry.py:L100–L143`
- **Streaming:** `_handle_streaming_response` iterates `litellm.completion(stream=True)` chunks, accumulating text and tool-call arguments and emitting chunk events. `c/llm.py:L815–L858`, `c/llm.py:L1146–L1194`
- **Action format:** with native tool calling the response's tool calls are returned as objects; otherwise the text is parsed for `Action:`/`Action Input:` or `Final Answer:` by `parser.parse`, raising `OutputParserError` on malformed output; an unsupported-tools error downgrades to text mode. `c/agents/agent_executor.py:L1726–L1747`, `c/agents/parser.py:L62–L126`, `c/agents/agent_executor.py:L1784–L1788`

## Output
- **Tool execution (text mode):** `execute_tool_and_check_finality` drives `ToolUsage._use`, which rejects a repeated identical call, consults the cache, invokes the structured tool, and periodically re-appends the tool-format instructions to the result. `c/agents/agent_executor.py:L1845–L1860`, `c/tools/tool_usage.py:L503–L521`, `c/tools/tool_usage.py:L558–L569`, `c/tools/tool_usage.py:L622–L631`, `c/tools/tool_usage.py:L760–L777`
- **Tool execution (native mode):** `execute_native_tool` runs the pending calls in a `ThreadPoolExecutor` when `_should_parallelize_native_tool_calls` allows, else sequentially so a `result_as_answer` tool can short-circuit to `AgentFinish`. `c/agents/agent_executor.py:L1966–L1985`, `c/agents/agent_executor.py:L2080–L2111`, `c/agents/agent_executor.py:L2014–L2046`
- **Tool set and schema:** tools are `BaseTool`s parsed to `CrewStructuredTool`; delegation and ask-question tools are added for other agents; native mode converts them to OpenAI function schemas. `c/utilities/agent_utils.py:L173–L236`, `c/agent/core.py:L1355`, `c/utilities/agent_utils.py:L238–L306`
- **No sandbox:** tools run in-process in the executor thread; a per-tool `max_usage_count` and `tool_failure_policy` are the only limits found. `c/tools/tool_usage.py:L684–L690`, `c/agents/agent_builder/base_agent.py:L288–L290`
- **Result presentation:** `finalize` logs the final answer through `_show_logs`; `Task._execute_core` wraps it in a `TaskOutput` (raw, pydantic, json) and fires task callbacks; the crew returns a `CrewOutput`. `c/agents/agent_executor.py:L2622–L2624`, `c/task.py:L853–L890`, `c/task.py:L925–L937`

## Production concerns
- **Persistence:** the long-term memory store (LanceDB or Qdrant) and task execution logs outlast the run; `checkpoint` config lets `kickoff` resume a restored crew. `c/memory/unified_memory.py:L237–L248`, `c/crew.py:L1492–L1520`, `c/crew.py:L400–L406`, `c/crew.py:L1013`
- **Safety & security:** guardrails (callable or LLM-judged) validate task output; hooks can block an LLM or tool call or request human approval; no execution sandbox found. `c/task.py:L393–L406`, `c/hooks/llm_hooks.py:L137–L150`, `c/hooks/tool_hooks.py:L107–L121`
- **Observability:** every step emits typed events on `crewai_event_bus` (task, LLM call, tool usage, memory retrieval); `TokenCalcHandler` and `calculate_usage_metrics` aggregate token counts; `tracing` and `output_log_file` are crew options. `c/events/event_bus.py:L95–L110`, `c/events/event_bus.py:L572`, `c/agent/core.py:L1299`, `c/crew.py:L2273`, `c/crew.py:L343`, `c/crew.py:L412`
- **Resilience:** rate-limit retries at the client, agent re-execution to `max_retry_limit`, execution timeout, parser-error recovery that re-prompts, context-length recovery by summarization. `c/llms/retry.py:L124–L143`, `c/agent/core.py:L886–L888`, `c/agents/agent_executor.py:L2980–L3017`
- **Performance:** tool result cache, streaming, parallel native tool calls, proactive summarization, `max_rpm` throttling via `RPMController`, prompt cache breakpoints. `c/tools/tool_usage.py:L558–L569`, `c/agent/core.py:L1253–L1254`, `c/crew.py:L649`, `c/agents/agent_executor.py:L521–L525`
- **Evaluation:** a large pytest suite with recorded cassettes covers crews, agents, tasks, LLMs and memory; `utilities/evaluators` holds agent and task evaluators. `t/test_crew.py:L1–L40`, `t/cassettes`, `c/utilities/evaluators`

## Hard to place
- **`AgentExecutor` as a Flow:** the per-task loop is itself expressed in CrewAI's `Flow` state machine (routers and listeners), so the loop body mixes control flow (`check_max_iterations`, `route_by_answer_type`) with context (`_setup_messages`) and output (`execute_tool_action`) in one class; the rules split it by function but the file does not. `c/agents/agent_executor.py:L187`, `c/agents/agent_executor.py:L2410–L2422`
- **Planning as an in-loop sub-harness:** when `planning_enabled`, `generate_plan` makes its own model calls, creates todos, and the executor runs each todo as a nested reasoning loop with replanning; a program that sequences model calls, so control flow, though it lives inside the executor. `c/agents/agent_executor.py:L554–L598`, `c/agents/agent_executor.py:L1312–L1379`, `c/agents/agent_executor.py:L2752–L2803`
- **Proactive summarization triggered by the model client:** `is_context_window_overflowing_threshold` lives on `BaseLLM` yet decides what the model is shown; by function it is context. `c/llms/base_llm.py:L427–L450`, `c/utilities/agent_utils.py:L645`

## Summary
| Primitive | Design decision |
|---|---|
| Input | Crew inputs interpolated into templates; tool results and human feedback appended as messages |
| Context | Role/goal/backstory system prompt, task plus memory and knowledge; LLM summarization near window limit |
| Model interface | LLM class over native provider clients or litellm; rate-limit retries; streaming; native or ReAct text |
| Output | In-process BaseTool execution with cache and repeat check; parallel native calls; no sandbox |
| Control flow | Flow state machine per task to max_iter, task sequencing by crew, guardrail retries, human gate |
