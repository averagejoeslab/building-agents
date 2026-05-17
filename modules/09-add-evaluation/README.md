# Add evaluation

> **Harness component: the test harness for the harness.** How you measure whether the harness you've built actually produces a good agent — repeatably, regressably, with a judging signal you can trust.

> [!NOTE]
> **Coming soon.** This module is stubbed.

Up to this point, "does the agent work?" has been a vibe check. To change a prompt, swap a model, or refactor a tool with confidence, the agent needs an eval suite — a set of tasks with judging criteria, run repeatably, scored automatically.

## What this module will cover

- **Eval foundations.** Why agents are hard to evaluate (non-deterministic, multi-step, no single right answer) and what changes vs. classic ML eval.
- **Task-completion suites.** YAML cases that describe an environment, a prompt, and a success criterion.
- **LLM-as-judge.** When the criterion isn't exact-match, a model judges the result. The pitfalls and the prompt patterns that work.
- **Trajectory analysis.** Using the JSONL traces from Module 8, judge not just the final answer but *how* the agent got there — extra tool calls, dead ends, wasted tokens.
- **Regression testing.** Running the suite before and after a change; surfacing what got better or worse.

## Reference: evals/

The end state already lives at [`evals/`](../../evals/) at the repo root — it tests *any* of the scripts in `examples/`. It's structured as a runner (`run.py`), a per-case YAML format under `evals/cases/`, and a diff tool (`diff.py`) for comparing two runs.

```bash
uv run --project examples evals/run.py
# or against a specific agent script:
uv run --project examples evals/run.py examples/production_agent.py
```

---

**Next:** [Module 10: Add performance](../10-add-performance/)
