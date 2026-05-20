"""Evaluation harness for building-agents.

Loads YAML test cases from evals/cases/, runs each against the target agent
N times via subprocess, scores outputs (contains/not_contains/exit_zero/
llm_judge), aggregates pass rates with stochastic averaging, and writes a
timestamped result file to evals/results/.
"""
import os
import sys
import asyncio
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / "examples" / ".env")

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

JUDGE_MODEL = "claude-haiku-4-5"

CASES_DIR = REPO_ROOT / "evals" / "cases"
RESULTS_DIR = REPO_ROOT / "evals" / "results"

DEFAULT_AGENT = "examples/agent.py"
N_RUNS = 3   # per case; raise for stronger signal


async def run_case(case: dict, agent_path: str) -> dict:
    """Run the agent once with the case's input. Return stdout/stderr."""
    user_input = case["input"] + "\n/q\n"
    agent_abs = (REPO_ROOT / agent_path).resolve() if not Path(agent_path).is_absolute() else Path(agent_path).resolve()
    proc = await asyncio.create_subprocess_exec(
        "uv", "run", str(agent_abs),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=REPO_ROOT / "examples",
    )
    stdout, stderr = await proc.communicate(user_input.encode())
    return {
        "stdout": stdout.decode(errors="replace"),
        "stderr": stderr.decode(errors="replace"),
        "exit_code": proc.returncode,
    }


async def llm_judge(user_input: str, agent_output: str, rubric: str) -> bool:
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


async def score(case: dict, result: dict) -> dict:
    """Apply each check; return per-check pass/fail and overall."""
    check_results = []
    for check in case.get("checks", []):
        ctype = check["type"]
        if ctype == "contains":
            passed = check["value"].lower() in result["stdout"].lower()
        elif ctype == "not_contains":
            passed = check["value"].lower() not in result["stdout"].lower()
        elif ctype == "exit_zero":
            passed = result["exit_code"] == 0
        elif ctype == "llm_judge":
            passed = await llm_judge(case["input"], result["stdout"], check["rubric"])
        else:
            print(f"warning: unknown check type {ctype!r}")
            passed = False
        check_results.append({"type": ctype, "passed": passed})

    overall = all(c["passed"] for c in check_results) if check_results else False
    return {"id": case["id"], "passed": overall, "checks": check_results}


async def run_case_n_times(case: dict, agent_path: str, n: int) -> dict:
    runs = []
    for i in range(n):
        result = await run_case(case, agent_path)
        scored = await score(case, result)
        runs.append({**scored, "run_index": i})
    pass_rate = sum(1 for r in runs if r["passed"]) / n
    return {"id": case["id"], "pass_rate": pass_rate, "runs": runs}


async def main():
    agent_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AGENT

    case_files = sorted(CASES_DIR.glob("*.yaml"))
    if not case_files:
        print(f"No case files found in {CASES_DIR}")
        sys.exit(1)
    cases = [yaml.safe_load(p.read_text()) for p in case_files]

    print(f"Running {len(cases)} cases × {N_RUNS} runs against {agent_path}...")
    results = []
    for case in cases:
        r = await run_case_n_times(case, agent_path, N_RUNS)
        results.append(r)
        marker = "✓" if r["pass_rate"] == 1.0 else ("≈" if r["pass_rate"] >= 0.6 else "✗")
        print(f"  {marker} {r['id']}: {r['pass_rate']:.0%}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_file = RESULTS_DIR / f"{timestamp}.json"
    out_file.write_text(json.dumps({
        "timestamp": timestamp,
        "agent": agent_path,
        "n_runs": N_RUNS,
        "results": results,
    }, indent=2))

    overall = sum(r["pass_rate"] for r in results) / len(results)
    print(f"\nResults: {out_file}")
    print(f"Overall pass rate: {overall:.1%}")


if __name__ == "__main__":
    asyncio.run(main())
