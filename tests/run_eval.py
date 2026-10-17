"""Evaluation harness to run test_questions.json against OrgMindAgent."""

import json
import os
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.agent import OrgMindAgent


def run_evaluation(test_file: str = "tests/test_questions.json"):
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        sys.exit(1)

    with open(test_file, "r", encoding="utf-8") as f:
        tests = json.load(f)

    agent = OrgMindAgent()
    passed = 0

    print(f"\n=== Running OrgMind Evaluation Suite ({len(tests)} test cases) ===\n", flush=True)

    for t in tests:
        q_id = t["id"]
        q = t["question"]
        print(f"[{q_id}] Running: '{q}'", flush=True)
        res = agent.run(q)
        answer = res.get("answer", "")
        print(f"     Answer: {answer[:120]}...", flush=True)

        # Check required substrings
        must_contain = t.get("must_contain", [])
        mismatches = [sub for sub in must_contain if sub.lower() not in answer.lower()]

        if not mismatches:
            print(f"     Result: [PASS]", flush=True)
            passed += 1
        else:
            print(f"     Result: [FAIL] - Missing expected keywords: {mismatches}", flush=True)

    print(f"\n==========================================", flush=True)
    print(f"Score: {passed}/{len(tests)} tests passed ({passed/len(tests)*100:.1f}%)", flush=True)
    print(f"==========================================\n", flush=True)


if __name__ == "__main__":
    run_evaluation()
