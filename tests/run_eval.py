"""OrgMind Model Evaluation Harness & Benchmark Runner.

Technical Terms:
- Model Harness: An automated testing framework that executes standardized benchmark
  questions against different LLM models and measures accuracy, tool routing, latency,
  and citation grounding.
- Grounding Accuracy: Verifying that cited sources exist in FalkorDB and actually substantiate the claim.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
core_pkg = os.path.join(project_root, "packages", "core")
if core_pkg not in sys.path:
    sys.path.insert(0, core_pkg)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from orgmind.agent import OrgMindAgent


def run_evaluation(
    model: str = None,
    test_file: str = "tests/test_questions.json",
    output_report: str = None,
    limit: int = None,
    verbose: bool = False,
) -> dict[str, Any]:
    if not os.path.exists(test_file):
        print(f"[Error] Test file not found: {test_file}")
        sys.exit(1)

    with open(test_file, encoding="utf-8") as f:
        tests = json.load(f)

    if limit and limit > 0:
        tests = tests[:limit]

    agent = OrgMindAgent(model=model)
    actual_model = agent.model

    print("=" * 70)
    print(f" [OrgMind Evaluation Harness] Benchmarking Model: {actual_model}")
    print(f" Total Benchmark Questions: {len(tests)}")
    print("=" * 70 + "\n", flush=True)

    results = []
    passed_count = 0
    total_latency = 0.0

    for idx, t in enumerate(tests, 1):
        q_id = t["id"]
        category = t.get("category", "general")
        q = t["question"]
        expected_tool = t.get("expected_tool")
        must_contain = t.get("must_contain", [])

        as_of = t.get("as_of")
        caller_role = t.get("caller_role", "Viewer")
        agent.caller_role = caller_role

        print(f'[{idx}/{len(tests)}] [{q_id}] ({category}) Q: "{q}"', flush=True)
        t_start = time.perf_counter()
        agent_res = agent.run(q, as_of=as_of)
        duration = round(time.perf_counter() - t_start, 2)
        total_latency += duration

        answer = agent_res.get("answer", "")
        tool_calls = agent_res.get("tool_calls", [])
        tools_used = [tc.get("tool") for tc in tool_calls]
        citations = agent_res.get("citations", {})
        valid_citations = citations.get("valid", [])
        invalid_citations = citations.get("invalid", [])
        is_grounded = agent_res.get("grounded", True)

        # 1. Check keyword presence (supports both exact strings and [A, B] OR choices)
        mismatches = []
        for sub in must_contain:
            if isinstance(sub, list):
                if not any(item.lower() in answer.lower() for item in sub):
                    mismatches.append(f"({' OR '.join(sub)})")
            else:
                if sub.lower() not in answer.lower():
                    mismatches.append(sub)

        # 2. Tool alignment check
        tool_match = (expected_tool in tools_used) if expected_tool else True

        # 3. Overall pass condition
        is_pass = (len(mismatches) == 0) and (len(invalid_citations) == 0)

        if is_pass:
            passed_count += 1
            status_tag = "[PASS]"
        else:
            status_tag = "[FAIL]"

        print(
            f"       -> {status_tag} in {duration}s | Tools: {tools_used} | Citations: {valid_citations}",
            flush=True,
        )
        if mismatches:
            print(f"          Missing expected keywords: {mismatches}", flush=True)
        if invalid_citations:
            print(f"          HALLUCINATED CITATIONS: {invalid_citations}", flush=True)
        if verbose:
            print(f"          Full Answer: {answer}\n", flush=True)

        results.append(
            {
                "id": q_id,
                "category": category,
                "question": q,
                "passed": is_pass,
                "duration_sec": duration,
                "expected_tool": expected_tool,
                "tools_used": tools_used,
                "tool_matched": tool_match,
                "missing_keywords": mismatches,
                "valid_citations": valid_citations,
                "invalid_citations": invalid_citations,
                "is_grounded": is_grounded,
                "answer_preview": answer[:250],
            }
        )

    # Summary Statistics
    total_tests = len(tests)
    pass_rate = round((passed_count / total_tests) * 100, 1) if total_tests else 0
    avg_latency = round(total_latency / total_tests, 2) if total_tests else 0.0

    print("\n" + "=" * 70)
    print(" [OrgMind Benchmark Report Summary]")
    print("=" * 70)
    print(f" Model Tested:          {actual_model}")
    print(f" Pass Rate:             {passed_count}/{total_tests} ({pass_rate}%)")
    print(f" Average Turn Latency:  {avg_latency}s")
    print(f" Total Evaluation Time: {round(total_latency, 2)}s")
    print("=" * 70 + "\n")

    report_payload = {
        "model": actual_model,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_tests": total_tests,
        "passed_tests": passed_count,
        "pass_rate_pct": pass_rate,
        "avg_latency_sec": avg_latency,
        "total_latency_sec": round(total_latency, 2),
        "results": results,
    }

    if not output_report:
        safe_model_name = actual_model.replace("/", "_").replace(":", "_")
        output_report = f"tests/eval_report_{safe_model_name}.json"

    with open(output_report, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    print(f"[Report] Detailed benchmark results saved to: {output_report}\n")
    return report_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OrgMind Model Evaluation Harness")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model identifier (e.g. ollama/qwen2.5-coder:14b, gpt-4o)",
    )
    parser.add_argument(
        "--test-file",
        type=str,
        default="tests/test_questions.json",
        help="Path to test questions JSON",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Path to write evaluation report JSON"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of test questions to run"
    )
    parser.add_argument("--verbose", action="store_true", help="Print verbose answers")

    args = parser.parse_args()
    report = run_evaluation(
        model=args.model,
        test_file=args.test_file,
        output_report=args.output,
        limit=args.limit,
        verbose=args.verbose,
    )

    # Exit 0 if all tests pass, else 1
    sys.exit(0 if report["passed_tests"] == report["total_tests"] else 1)
