# examples

Runnable harness checkpoints for the [building-agents curriculum](../README.md). Each script is one stage in the construction of a coding-agent harness — the cumulative end state of one module. Read the module first, then run the script to see that stage's harness in action. The filename describes what the system has *become* at that point.

Each is one self-contained file with no imports between scripts. Code is duplicated across files on purpose: a reader can open any script and understand the entire harness at that level without jumping around.

## Setup (once)

```bash
cp .env.example .env          # paste your Anthropic API key
uv sync                        # install deps into ./.venv
```

The `uv sync` pulls in `sentence-transformers` (used by `stateful_chatbot.py` and later) which downloads ~2GB of PyTorch. The first run of any memory-using script also downloads the embedding model itself (~80MB).

## Run a script

```bash
uv run llm_call_async.py      # or any other script
```

Run from `examples/` — the `.env` and `.venv` are resolved relative to this directory.

## Checkpoints

[`test.py`](./test.py) is the Module 1 toy — the minimal "model + one tool + a loop" agent shown in the prose. It exists to make the very first concept concrete and isn't part of the strict-superset chain below (the chain starts at `llm_call_sync.py`, which deliberately drops the tool to focus on the model interface, and builds back up from there).

Each script in the table below is a strict superset of the previous one's capabilities.

| # | Script | Module | Harness component added |
|---|---|---|---|
| 0 | [`test.py`](./test.py) | [1](../modules/01-what-is-an-agent/) | *(toy)* minimal model + one tool + a TAO loop in ~50 lines |
| 1 | [`llm_call_sync.py`](./llm_call_sync.py) / [`llm_call_async.py`](./llm_call_async.py) | [2](../modules/02-an-llm-call/) | **Model interface** — sync `messages.create` and async streaming |
| 2 | [`stateless_chatbot.py`](./stateless_chatbot.py) | [3](../modules/03-add-a-loop/) | **Control flow** — a loop bound to the terminal |
| 3 | [`stateful_chatbot.py`](./stateful_chatbot.py) | [4](../modules/04-add-memory/) | **Memory + context management** — persistence, token budget eviction, semantic recall |
| 4 | [`agent.py`](./agent.py) | [5](../modules/05-add-tools/) | **Tool / action layer** — tools, TAO loop, async parallel dispatch |
| 5 | [`sandbox_agent.py`](./sandbox_agent.py) | [6](../modules/06-add-sandboxing/) | **Execution environment** — Docker-isolated `bash` |
| 6 | [`safe_agent.py`](./safe_agent.py) | [7](../modules/07-add-guardrails/) | **Safety constraints** — approval gates, loop bounds, retry/backoff |
| 7 | [`traced_agent.py`](./traced_agent.py) | [8](../modules/08-add-observability/) | **Structured tracing** — JSONL spans for every LLM and tool call |
| 8 | [`production_agent.py`](./production_agent.py) | [10](../modules/10-add-performance/) | **Production hardening** — prompt caching, tool caching, threading, structured prompts, `assemble()` |

(Module 9 — Evaluation — ships at [`evals/`](../evals/) at the repo root, since it tests the scripts here rather than being one.)

## Picking which one to run

- **Reading the curriculum?** Run each script as you finish its module.
- **Want a chat companion that remembers across sessions?** `stateful_chatbot.py`.
- **Want a coding agent?** `agent.py` minimum; `safe_agent.py` if you want sandboxing + approval gates.
- **Debugging a behavior issue?** `traced_agent.py`. Every action ends up in `~/.traced-agent/traces.jsonl`.
- **Want the full production-shaped artifact?** `production_agent.py`.

## Dockerfile

`Dockerfile.sandbox` lives here. The `sandbox_agent.py`, `safe_agent.py`, `traced_agent.py`, and `production_agent.py` scripts all build and use it on first run. Requires Docker to be running.

## State files

Stateful scripts persist to `~/.<name>/` directories:

- `~/.stateful-chatbot/` — `messages.json`, `recall.json`
- `~/.agent/` — same shape as stateful-chatbot
- `~/.sandbox-agent/` — same plus the sandbox container survives between runs
- `~/.safe-agent/` — adds approval/loop-bound state
- `~/.traced-agent/` — adds `traces.jsonl`
- `~/.production-agent/` — same shape as traced
