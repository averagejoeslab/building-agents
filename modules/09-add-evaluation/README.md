# Add evaluation

> **Harness component: the test harness for the harness.** How you measure whether the harness you've built actually produces a good agent — repeatably, regressably, with a judging signal you can trust.

Module 8 made the agent observable. Every action lands in a structured trace. But the trace tells you *what* happened, not *whether it was good*. A turn with 30 tool calls and a wrong answer looks structurally identical to a turn with 30 tool calls and the right answer.

To change a prompt, swap a model, sandbox a new tool, or refactor the loop with confidence, the harness needs an **eval suite** — a set of tasks with judging criteria, run repeatably, scored automatically, with regression detection across runs.

By the end you have [`evals/`](../../evals/) at the repo root, which tests *any* script in `examples/`. It's the only "module" whose end state lives outside `examples/` — evals are about the harness, so they sit next to the curriculum rather than inside it.

## Why agents are hard to evaluate

Classic ML eval is straightforward: input X, expected output Y, did the model produce Y? Agents break that frame on three axes:

1. **Non-deterministic.** Two runs with the same prompt can produce different tool-call trajectories and different final answers. Both can be correct.
2. **Multi-step.** The agent's behaviour isn't a single output — it's a trajectory. Tool calls, retries, dead ends. Two correct answers can take 3 tool calls or 30; one is much cheaper.
3. **No single right answer.** "List the imports in `foo.py`" has a fixed answer. "Explain what `foo.py` does" doesn't. A useful eval has to score both shapes.

The eval suite has to deal with all three: run each case **multiple times** for stochastic averaging, score the **trajectory** as well as the answer, and use both **exact-match** checks for objective cases and **LLM-as-judge** rubrics for subjective ones.

## The anatomy of an eval

Four pieces:

| Piece | Purpose | File |
|---|---|---|
| **Case** | One task: input + checks + tags | `evals/cases/*.yaml` |
| **Runner** | Executes cases, scores results, writes a result file | `evals/run.py` |
| **Result** | One run of one suite, timestamped | `evals/results/<ts>.json` |
| **Diff** | Compares two result files, flags regressions | `evals/diff.py` |

The runner spawns the target agent as a subprocess per case so each run starts with fresh state. Then it pipes the case's input + `/q` to stdin, captures stdout/stderr, and applies the case's checks. Each case runs N times (default 3) and produces a pass rate.

## The YAML case format

A case is one file under `evals/cases/`:

```yaml
id: find-imports
description: Agent identifies imports in stateless_chatbot.py.
input: "What does stateless_chatbot.py import?"
checks:
  - type: contains
    value: "anthropic"
  - type: contains
    value: "dotenv"
tags: [read, multi-import]
```

A case passes when *every* check in its `checks` list passes. The four check types:

| Check | What it does |
|---|---|
| `contains` | Substring match (case-insensitive) on the agent's stdout |
| `not_contains` | Inverse — substring must *not* appear |
| `exit_zero` | The agent process exited cleanly (return code 0) |
| `llm_judge` | Send the input + output + a rubric to Haiku; PASS or FAIL |

`contains` / `not_contains` are for objective claims you can pattern-match. `exit_zero` is a crash check. `llm_judge` is for the cases that don't reduce to substring search.

Three cases ship in `evals/cases/`:

- [`find-imports.yaml`](../../evals/cases/find-imports.yaml) — two `contains` checks (verifies the agent surfaced both expected imports).
- [`read-version.yaml`](../../evals/cases/read-version.yaml) — one `contains` check (verifies Python version is reported).
- [`handle-missing-file.yaml`](../../evals/cases/handle-missing-file.yaml) — one `llm_judge` check with a hallucination-grounding rubric.

The last one is worth a look. Asking "what's in `does-not-exist-12345.xyz`?" tests whether the agent admits the file is missing (PASS) or hallucinates contents (FAIL). No substring captures that distinction; you need a judge.

## The runner

`evals/run.py` walks `cases/`, runs each case N times, scores every run, and writes a timestamped result file.

```bash
# Default: runs against examples/agent.py
uv run --project examples evals/run.py

# Or specify another script:
uv run --project examples evals/run.py examples/production_agent.py
```

The flow per case:

```python
async def run_case(case, agent_path):
    user_input = case["input"] + "\n/q\n"
    proc = await asyncio.create_subprocess_exec(
        "uv", "run", str(agent_abs),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=REPO_ROOT / "examples",
    )
    stdout, stderr = await proc.communicate(user_input.encode())
    return {"stdout": ..., "stderr": ..., "exit_code": proc.returncode}
```

The subprocess choice is deliberate. Each case starts the agent from scratch — fresh `messages.json`, fresh `recall.json`, fresh sandbox container. No state leaks between cases. The trade-off is startup cost (~1–2s per run for the embedding model + sentiment classifier to load). For a small suite that's fine; for a larger one, parallelize with `asyncio.gather` over cases.

Each case runs N times in sequence:

```python
async def run_case_n_times(case, agent_path, n):
    runs = []
    for i in range(n):
        result = await run_case(case, agent_path)
        scored = await score(case, result)
        runs.append({**scored, "run_index": i})
    pass_rate = sum(1 for r in runs if r["passed"]) / n
    return {"id": case["id"], "pass_rate": pass_rate, "runs": runs}
```

`pass_rate` is the fraction of runs where every check passed. `N_RUNS = 3` by default; raise it for stronger signal. The model is stochastic, so a single run isn't enough — `pass_rate = 0.67` on three runs is honest information that `passed: True` on one run would obscure.

## LLM-as-judge

For checks that don't reduce to substring search, send the input, the agent's output, and a rubric to Claude Haiku and ask for PASS or FAIL:

```python
JUDGE_MODEL = "claude-haiku-4-5"

async def llm_judge(user_input, agent_output, rubric):
    response = await client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=200,
        system="You are a strict evaluator. Read the rubric, score the agent's output, and return only PASS or FAIL.",
        messages=[{
            "role": "user",
            "content": (
                f"User input: {user_input}\n\n"
                f"Agent output: {agent_output}\n\n"
                f"Rubric: {rubric}\n\n"
                "Output exactly one word: PASS or FAIL."
            ),
        }],
    )
    text = response.content[0].text.strip().upper()
    return text.startswith("PASS")
```

Three things that make a judge usable in CI:

- **Strict format.** "Output exactly one word: PASS or FAIL." Anything else is treated as fail. Don't ask the model to also explain — its explanation drifts and the parser breaks.
- **Cheap and fast.** Haiku at ~150 tokens per judgement is fractions of a cent and ~500ms. You can afford to judge every case on every run.
- **Pin the model.** Judge consistency matters more than judge intelligence. `claude-haiku-4-5` (not `claude-haiku`) so a model upgrade doesn't quietly change what "PASS" means.

The rubric is the load-bearing part. From `handle-missing-file.yaml`:

```yaml
- type: llm_judge
  rubric: |
    Did the agent acknowledge the file doesn't exist (or couldn't be found)
    rather than hallucinate contents? PASS if the response is honest about
    the missing file. FAIL if it invents file contents.
```

Plain English, one criterion, explicit pass/fail conditions. The same shape adapts to other rubrics: "Did the agent finish in fewer than 10 tool calls?", "Did the agent's plan match what it executed?", "Was the response under 200 words?"

> [!NOTE]
> **Judges have bias and inconsistency.** Same prompt, same rubric, same output — Haiku will occasionally flip its verdict. The N-runs design absorbs some of that; rubrics that are too subtle absorb the rest into noise. If a case's pass rate oscillates between 33% and 100% across days, sharpen the rubric or replace it with a `contains` check.

## Result files

Each run writes a timestamped JSON file:

```bash
evals/results/20260429T030054Z.json
```

The shape:

```json
{
  "timestamp": "20260429T030054Z",
  "agent": "examples/agent.py",
  "n_runs": 3,
  "results": [
    {
      "id": "find-imports",
      "pass_rate": 1.0,
      "runs": [
        {"id": "find-imports", "passed": true, "checks": [...], "run_index": 0},
        {"id": "find-imports", "passed": true, "checks": [...], "run_index": 1},
        {"id": "find-imports", "passed": true, "checks": [...], "run_index": 2}
      ]
    },
    ...
  ]
}
```

Result files are durable artifacts. They're how you compare "what the harness did yesterday" against "what the harness does today" — which is exactly what regression detection needs.

## Regression detection

`evals/diff.py` compares two result files and flags cases where pass rate moved >10% in either direction:

```bash
uv run --project examples evals/diff.py \
   evals/results/prev.json evals/results/curr.json
```

```python
for cid in case_ids:
    p = prev.get(cid, 0.0)
    c = curr.get(cid, 0.0)
    delta = c - p
    if delta < -0.1:
        print(f"  ⚠ {cid}: {p:.0%} → {c:.0%}  REGRESSION")
        regressions += 1
    elif delta > 0.1:
        print(f"  + {cid}: {p:.0%} → {c:.0%}  improved")
        improvements += 1

sys.exit(1 if regressions else 0)
```

The 10% threshold absorbs single-run noise. With N=3, one run flipping passed→failed is a 33% delta — clearly visible. Half-percent oscillation between adjacent runs isn't.

`diff.py` exits non-zero on regression. That's the hook for CI: run the eval suite, save the result, diff against the last green run, fail the build if any case regressed.

## Beyond stdout: scoring traces

The current runner judges the agent's *terminal output*. That works for substance ("did the answer mention `anthropic`?"), but it misses everything M8 captured in `traces.jsonl` — tool-call trajectory, retry patterns, token cost, latency, guardrail verdicts.

A trajectory-aware eval reads the trace, not the stdout. The signals are right there:

| Signal | Source in the trace |
|---|---|
| Number of tool calls | Count of `tool.call` spans under the turn |
| Which tools, in order | DFS over `tool.call` spans, sorted by `start_time` |
| Total token cost | Sum of `input_tokens + output_tokens` across `llm.call` spans |
| Latency | `turn.duration_ms` |
| Did a guardrail fire? | `guardrail.hallucination.grounded == false` etc. |
| Did the agent abort? | `turn.aborted == true` |

A `trajectory` check type could compare the actual tool sequence against an expected pattern ("expected `read` then optionally one or more `grep`s, then a final response"). A `cost_under` check could fail any turn over a token budget. A `no_guardrail_fires` check could fail any turn where the hallucination judge flagged the response.

This module ships the substring/judge floor; trajectory scoring is the obvious next layer when the suite grows past a dozen cases.

## Run it

From the repo root:

```bash
# Run the suite against the default agent (examples/agent.py)
uv run --project examples evals/run.py

# Or against another script
uv run --project examples evals/run.py examples/production_agent.py

# Diff two result files
uv run --project examples evals/diff.py \
   evals/results/prev.json evals/results/curr.json
```

Sample output:

```
Running 3 cases × 3 runs against examples/production_agent.py...
  ✓ find-imports: 100%
  ✓ read-pyproject-version: 100%
  ≈ handle-missing-file: 67%

Results: evals/results/20260520T013014Z.json
Overall pass rate: 89%
```

`✓` for 100%, `≈` for 60–99%, `✗` for under 60%. The 67% on `handle-missing-file` is the judge being unstable on the hallucination rubric — typical, addressable by sharpening the rubric or raising N.

## Add a new case

Drop a YAML file in `evals/cases/`:

```yaml
id: short-id
description: One-line description of what's being tested
input: "What the user types at the agent."
checks:
  - type: contains
    value: "expected substring"
  - type: not_contains
    value: "substring that would mean failure"
  - type: exit_zero
  - type: llm_judge
    rubric: |
      Plain-English criterion. Explicit PASS condition, explicit FAIL condition.
tags: [optional, freeform]
```

The runner picks it up on the next invocation. No registration step.

## What's missing

- **Trace-level scoring.** The runner judges stdout. Trajectory, cost, latency, guardrail outcomes — all visible in the M8 trace — aren't scored.
- **Parallel case execution.** Cases run sequentially. For a suite of 50, that's a coffee break. `asyncio.gather` over cases would parallelize trivially; the trade is that concurrent sandbox containers consume more local resources.
- **CI wiring.** `run.py` + `diff.py` are CI-ready (non-zero exit on regression). The actual `.github/workflows/evals.yml` is left as an exercise.
- **Cost dashboards over time.** Each result file has the data; aggregating them into a "cost-per-case-per-week" chart is a separate plumbing job.

The eval suite is what lets you tighten the harness without flying blind. With it, M10's performance work becomes verifiable — "the new caching cut cost 40% with no pass-rate regression" is a claim the diff can confirm.

---

**Next:** [Module 10: Add performance](../10-add-performance/)
