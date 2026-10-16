# smolagents (CodeAgent and ToolCallingAgent)

**Source:** https://github.com/huggingface/smolagents · **Version:** commit 96f33faaf028479119ec8d34507b47694cf14e34 (2026-10-06) · **Language:** Python
**Path conventions:** `s/` = `src/smolagents/`; `t/` = `tests/`; `ex/` = `examples/`. All paths relative to the repo root.
**What it is:** smolagents is Hugging Face's small agent library built around one ReAct loop (`MultiStepAgent`) with two concrete agents: `CodeAgent`, whose model writes a Python snippet per step that a sandboxed interpreter runs, and `ToolCallingAgent`, whose model emits JSON tool calls. The model is reached through a `Model` adapter (OpenAI-compatible, LiteLLM, HF Inference, Bedrock, local transformers/vLLM/MLX) that normalizes messages and returns a `ChatMessage`.

## Control flow
- **Step loop:** `_run_stream` runs `while not returned_final_answer and self.step_number <= max_steps`, building one `ActionStep` per iteration and calling `_step_stream`, which makes exactly one model call and executes its action. `s/agents.py:L540–L611`
- **Stop rule:** the loop ends when a step yields an `ActionOutput` with `is_final_answer` (the `final_answer` tool was called); optional `final_answer_checks` run first and an `AgentError` from them keeps the loop going. `s/agents.py:L577–L592`, `s/agents.py:L613–L618`
- **Step budget and forced answer:** `max_steps` (default 20) caps iterations; on exhaustion `_handle_max_steps_reached` makes one extra model call (`provide_final_answer`) and records an `AgentMaxStepsError` step. `s/agents.py:L294–L303`, `s/agents.py:L606–L608`, `s/agents.py:L625–L637`
- **Error policy inside the loop:** `AgentGenerationError` (model call failed) is re-raised and ends the run; any other `AgentError` (parse, tool, execution) is stored on the step and the loop continues; `interrupt()` sets a switch checked at each iteration. `s/agents.py:L594–L604`, `s/agents.py:L546–L547`, `s/agents.py:L754–L756`
- **Planning cadence and managed agents:** `planning_interval` schedules an extra planning model call at step 1 and every N steps; `managed_agents` are sub-agents exposed to the model as tools, each running its own `run()` loop (depth 1 per level) and returning a templated report string. `s/agents.py:L548–L566`, `s/agents.py:L369–L387`, `s/agents.py:L868–L890`

## Input
- **Task entry:** `run(task, images, additional_args)` stores the task, appends a sentence listing `additional_args` keys, resets memory unless `reset=False`, and appends a `TaskStep`; the CLI's `run_smolagent` is a thin wrapper over `agent.run(prompt)`. `s/agents.py:L470–L491`, `s/cli.py:L219–L259`
- **Tool results re-enter as observations:** `ToolCallingAgent.process_tool_calls` joins each tool's stringified result into `memory_step.observations`; `CodeAgent` stores "Execution logs" plus the truncated last expression value. `s/agents.py:L1430–L1442`, `s/agents.py:L1753–L1755`
- **Errors re-enter as tool responses:** `ActionStep.to_messages` renders a stored error as a `TOOL_RESPONSE` message beginning "Error:" with a retry instruction. `s/memory.py:L138–L150`
- **Human input:** no mid-run prompt in the loop; the only channel is the optional `UserInputTool`, whose result the model consumes via `input()`. `s/default_tools.py:L93–L103`

## Context
- **System prompt assembly:** `initialize_system_prompt` renders a Jinja template with the tool and managed-agent descriptions, authorized imports, custom `instructions`, and code-block tags; the template is `code_agent.yaml` (or `toolcalling_agent.yaml`). `s/agents.py:L1620–L1636`, `s/agents.py:L1265–L1274`, `s/prompts/code_agent.yaml:L1–L174`
- **History is the full memory:** `write_memory_to_messages` emits the system prompt plus every step's `to_messages` (assistant output, "Calling tools:" message, observation images, observation text, error); no window fitting, compaction or summarization exists. `s/agents.py:L758–L770`, `s/memory.py:L92–L151`
- **Role normalization and merging:** `get_clean_message_list` maps `TOOL_CALL` to assistant and `TOOL_RESPONSE` to user, merges consecutive same-role messages, and can flatten to text for models without multimodal input. `s/models.py:L282–L285`, `s/models.py:L332–L399`
- **Size limits by truncation only:** observations are head/tail truncated at 20,000 chars and executor print logs at 50,000 chars. `s/utils.py:L254–L267`, `s/local_python_executor.py:L57`, `s/local_python_executor.py:L1643–L1646`
- **Planning and summary variants:** planning calls wrap the memory in pre/post templates that include `remaining_steps`; `summary_mode` drops the system prompt and model outputs when a managed agent reports its work. `s/agents.py:L696–L713`, `s/memory.py:L92–L94`, `s/memory.py:L200–L206`

## Model interface
- **`Model` adapter:** `_prepare_completion_kwargs` builds the wire request (normalized messages, stop sequences, `response_format`, tool JSON schemas with `tool_choice="required"`); subclasses implement `generate`/`generate_stream` over their SDK, for example `OpenAIModel.generate` calling `client.chat.completions.create` and returning a `ChatMessage` with `TokenUsage`. `s/models.py:L502–L551`, `s/models.py:L1761–L1796`
- **Retries and rate limiting:** `ApiModel` wraps every call in a `Retrying` helper (3 attempts, exponential wait with jitter) whose predicate matches only rate-limit errors, and throttles with a `RateLimiter`; `LiteLLMRouterModel` delegates fallback routing to a litellm Router. `s/models.py:L39`, `s/models.py:L1174–L1182`, `s/models.py:L1194–L1202`, `s/models.py:L1363`
- **Streaming:** `generate_stream` yields `ChatMessageStreamDelta`s with `include_usage`; the agent aggregates them with `agglomerate_stream_deltas` and re-renders a rich `Live` panel per delta. `s/models.py:L1707–L1730`, `s/agents.py:L1660–L1672`
- **Action format:** `ToolCallingAgent` uses native tool calls and falls back to `parse_tool_calls` on text; `CodeAgent` extracts a code blob between `<code>`/`</code>` tags (or a JSON `{"code":...}` structured output) and appends the closing tag to history to nudge early stopping. `s/models.py:L583–L595`, `s/agents.py:L1326–L1333`, `s/agents.py:L1686–L1708`

## Output
- **Tool execution (`ToolCallingAgent`):** `execute_tool_call` checks the name against tools plus managed agents, substitutes state variables, validates arguments, and calls the tool with `sanitize_inputs_outputs=True`; multiple calls in one response run concurrently in a `ThreadPoolExecutor`. `s/agents.py:L1453–L1502`, `s/agents.py:L1412–L1428`
- **Code execution (`CodeAgent`):** the parsed snippet becomes a synthetic `python_interpreter` tool call and runs through `self.python_executor`; `executor_type` selects `local` or a remote sandbox. `s/agents.py:L1710–L1737`, `s/agents.py:L1598–L1618`
- **Local sandbox:** `LocalPythonExecutor` is an AST interpreter (`evaluate_python_code`) with an authorized-import allowlist, `DANGEROUS_MODULES`/`DANGEROUS_FUNCTIONS` denylists, a 10,000,000 operation cap, a 1,000,000 while-iteration cap and a 30 s timeout; `final_answer` is patched to raise `FinalAnswerException`. `s/local_python_executor.py:L57–L60`, `s/local_python_executor.py:L130–L154`, `s/local_python_executor.py:L1444–L1448`, `s/local_python_executor.py:L1583–L1668`
- **Remote sandboxes:** `E2BExecutor`, `DockerExecutor` (a Jupyter kernel-gateway container reached over WebSocket), `ModalExecutor` and `BlaxelExecutor` run the snippet elsewhere and return the final answer as a prefixed payload, with pickle deserialization refused unless `allow_pickle=True`. `s/remote_executors.py:L53–L96`, `s/remote_executors.py:L307–L332`, `s/remote_executors.py:L551–L677`
- **Result presentation:** the rich `AgentLogger` prints the code, execution logs and `Out:` value per step; final values pass through `handle_agent_output_types` (text, image, audio wrappers). `s/agents.py:L1738–L1762`, `s/monitoring.py:L130–L230`, `s/tools.py:L231–L249`

## Production concerns
- **Persistence:** memory lives only in the process (`AgentMemory.steps`); `save`/`to_dict`/`push_to_hub` serialize the agent definition (tools, prompts, model config) but not run state, and `RunResult` returns steps and token usage to the caller. `s/memory.py:L214–L235`, `s/agents.py:L892–L1010`, `s/agents.py:L196–L265`
- **Safety & security:** code runs in the AST interpreter with import allowlist and denylists or in a remote sandbox; API keys are excluded from `to_dict`; tool inputs/outputs are type-sanitized; no approval gate or prompt-injection defense found. `s/local_python_executor.py:L130–L154`, `s/models.py:L618–L623`, `s/tools.py:L244–L248`
- **Observability:** `Monitor.update_metrics` is registered as a step callback and sums input/output tokens and step duration; each step keeps `model_input_messages`, `model_output_message`, `token_usage` and `timing`; OpenTelemetry tracing is external via the `openinference` instrumentor. `s/monitoring.py:L81–L118`, `s/agents.py:L416–L435`, `t/test_telemetry.py:L26–L35`
- **Resilience:** rate-limit retries at the model client, a per-snippet execution timeout, error steps fed back to the model, and a forced final answer at `max_steps`; no resume after crash found. `s/models.py:L1174–L1182`, `s/local_python_executor.py:L1663–L1668`, `s/agents.py:L625–L637`
- **Performance:** parallel tool calls via threads, token streaming, stop sequences to cut generation, head/tail truncation of observations, and a client-side `RateLimiter`. `s/agents.py:L1412–L1428`, `s/agents.py:L1645–L1650`, `s/utils.py:L257–L267`, `s/models.py:L1173`
- **Evaluation:** a pytest suite covers agents, executors, models and memory, and `examples/smolagents_benchmark` scores agents on benchmark tasks. `t/test_agents.py:L1–L40`, `t/test_local_python_executor.py:L1–L40`, `ex/smolagents_benchmark/run.py:L1–L40`

## Hard to place
- **`final_answer` tool:** it is a tool the model calls (output) whose execution raises `FinalAnswerException` inside the executor, and the loop reads `is_final_answer` to stop; the rules split it cleanly (output executes, control flow consumes the flag) but the stop signal is carried by an exception thrown inside the sandbox. `s/local_python_executor.py:L1629–L1635`, `s/agents.py:L577–L592`
- **Shared `state` dict:** tool results that are images or audio are stored under a name in `self.state` and the model is told only "Stored 'image.png' in memory"; the same dict is pushed into the executor namespace, so it is a record kept for the model (context) that lives in the execution environment (output). `s/agents.py:L1388–L1396`, `s/agents.py:L493–L495`, `s/agents.py:L1444–L1451`
- **`final_answer_checks`:** user-supplied validators the harness runs on the model's answer and that can force another iteration; a harness-consumed gate, so control flow, though they execute arbitrary code like a tool. `s/agents.py:L613–L618`

## Summary
| Primitive | Design decision |
|---|---|
| Input | Task string plus optional images and named args; tool results and errors re-enter as text observations |
| Context | Jinja system prompt plus full step memory replayed each call; truncation only, no compaction |
| Model interface | Pluggable Model adapters over provider SDKs; rate-limit retries; native tool calls or code blobs |
| Output | JSON tool calls run in threads, or Python snippets in an AST interpreter or remote sandbox |
| Control flow | ReAct while-loop to max_steps, stops on final_answer; optional periodic planning; managed agents as tools |
