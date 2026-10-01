# evals

The Module 9 artifact. An evaluation harness that runs YAML test cases against any script in `examples/`, scores outputs (with code checks and LLM-as-judge), aggregates pass rates over multiple runs, and tracks regressions across timestamped result files.

## Run the suite

From the repo root (the `--project examples` flag points uv at the shared dependency set):

```bash
# Default: runs against examples/agent.py
uv run --project examples evals/run.py

# Or specify another script:
uv run --project examples evals/run.py examples/production_agent.py
```

Each case runs N times (default 3) for stochastic averaging. Results land in `evals/results/<timestamp>.json`.

## Detect regressions

```bash
uv run --project examples evals/diff.py evals/results/prev.json evals/results/curr.json
```

Reports cases where pass rate dropped >10% (regression) or improved >10% (improvement). Exits non-zero on regression — useful in CI.

## Add a new case

Drop a YAML file in `evals/cases/`. Schema:

```yaml
id: short-id
description: One-line description
input: "What the user types at the agent."
checks:
  - type: contains       # substring in stdout (case-insensitive)
    value: "..."
  - type: not_contains   # substring NOT in stdout
    value: "..."
  - type: exit_zero      # agent exited cleanly
  - type: llm_judge      # LLM-as-judge with a rubric
    rubric: |
      Plain-English criterion. PASS or FAIL.
tags: [optional]
```

A case passes if every check in its `checks` list passes.

## Files

- `run.py` — the runner (subprocess + score + per-case stochastic averaging + result file)
- `diff.py` — regression diff between two result files
- `cases/*.yaml` — test cases
- `results/*.json` — timestamped run outputs (gitignored)

## Trade-offs

The runner spawns the agent as a subprocess with a throwaway `HOME`, so every run starts with empty state (no `messages.json` or `recall.json` carried over between cases or runs). That adds several seconds of startup per run while the agent loads its models. For larger eval suites, parallelize with `asyncio.gather` over cases — sequential is fine for the sample set here.

The LLM judge uses Claude Haiku 4.5 (fast and cheap). For cases where judge consistency matters, pin a specific model snapshot.
