#!/usr/bin/env python3
"""
Automatic test runner for AI Lead Classifier.
Runs all cases from test_cases.json, validates results, produces report.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.schemas import ClassifyRequest, LeadCard
from app.services.classifier import classify_lead

TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"
REPORTS_DIR = ROOT / "reports"


def load_cases() -> list[dict]:
    with TEST_CASES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def compare_field(actual: Any, expected: Any, field: str) -> tuple[bool, str | None]:
    if expected is None:
        return True, None
    if actual is None and expected is not None:
        return False, f"{field}: expected {expected!r}, got null"
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        # Allow small numeric tolerance
        if abs(actual - expected) > 1:
            return False, f"{field}: expected {expected}, got {actual}"
        return True, None
    if actual != expected:
        return False, f"{field}: expected {expected!r}, got {actual!r}"
    return True, None


async def run_single(case: dict) -> dict:
    start = time.perf_counter()
    settings = get_settings()

    payload = ClassifyRequest(**case["input"])
    result = await classify_lead(payload)
    elapsed_ms = (time.perf_counter() - start) * 1000

    record: dict[str, Any] = {
        "id": case["id"],
        "title": case["title"],
        "category": case.get("category"),
        "input": case["input"],
        "expected": case.get("expected", {}),
        "elapsed_ms": round(elapsed_ms, 1),
        "model": settings.MODEL_ID,
        "prompt_version": settings.PROMPT_VERSION,
        "success": False,
        "status": "fail",
        "actual": None,
        "diffs": [],
        "error": None,
    }

    if not result.success:
        record["error"] = result.error.model_dump() if hasattr(result, "error") else str(result)
        record["status"] = "fail"
        return record

    data = result.data
    record["actual"] = data.model_dump()
    record["success"] = True

    diffs = []
    expected = case.get("expected", {})
    for field, exp_val in expected.items():
        act_val = getattr(data, field, None)
        # Handle enums
        if hasattr(act_val, "value"):
            act_val = act_val.value
        ok, msg = compare_field(act_val, exp_val, field)
        if not ok and msg:
            diffs.append(msg)

    record["diffs"] = diffs
    record["status"] = "pass" if not diffs else "fail"
    return record


async def run_all() -> dict:
    cases = load_cases()
    results = []
    for case in cases:
        print(f"Running {case['id']}: {case['title']} ...", end=" ", flush=True)
        rec = await run_single(case)
        results.append(rec)
        print(rec["status"].upper())

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = total - passed

    # Metrics
    schema_valid = sum(1 for r in results if r["success"])
    service_ok = 0
    service_total = 0
    budget_ok = 0
    budget_total = 0
    deadline_ok = 0
    deadline_total = 0
    hallucination = 0

    for r in results:
        exp = r.get("expected", {})
        act = r.get("actual") or {}
        if "service" in exp:
            service_total += 1
            act_svc = act.get("service")
            if hasattr(act_svc, "value"):
                act_svc = act_svc.value
            if act_svc == exp["service"]:
                service_ok += 1
        if "budget_min_rub" in exp or "budget_max_rub" in exp:
            budget_total += 1
            ok = True
            if "budget_min_rub" in exp and act.get("budget_min_rub") != exp["budget_min_rub"]:
                # allow close values
                if not (isinstance(act.get("budget_min_rub"), (int, float)) and abs(act["budget_min_rub"] - exp["budget_min_rub"]) <= 1):
                    ok = False
            if "budget_max_rub" in exp and act.get("budget_max_rub") != exp["budget_max_rub"]:
                if not (isinstance(act.get("budget_max_rub"), (int, float)) and abs(act["budget_max_rub"] - exp["budget_max_rub"]) <= 1):
                    ok = False
            if ok:
                budget_ok += 1
        if "deadline_date" in exp:
            deadline_total += 1
            if act.get("deadline_date") == exp["deadline_date"]:
                deadline_ok += 1
        # Simple hallucination check: invented budget when not expected
        if act and exp.get("budget_min_rub") is None and act.get("budget_min_rub") is not None:
            hallucination += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "json_schema_valid_rate": round(schema_valid / total, 4) if total else 0,
        "service_accuracy": round(service_ok / service_total, 4) if service_total else None,
        "budget_accuracy": round(budget_ok / budget_total, 4) if budget_total else None,
        "deadline_accuracy": round(deadline_ok / deadline_total, 4) if deadline_total else None,
        "hallucination_errors": hallucination,
        "average_response_time_ms": round(sum(r["elapsed_ms"] for r in results) / total, 1) if total else 0,
        "results": results,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"TOTAL: {total}  PASSED: {passed}  FAILED: {failed}")
    print(f"JSON schema valid rate: {report['json_schema_valid_rate']}")
    print(f"Service accuracy: {report['service_accuracy']}")
    print(f"Budget accuracy: {report['budget_accuracy']}")
    print(f"Deadline accuracy: {report['deadline_accuracy']}")
    print(f"Hallucination errors: {report['hallucination_errors']}")
    print(f"Avg response time: {report['average_response_time_ms']} ms")
    print(f"Report saved to: {out_path}")
    print("=" * 60)

    return report


if __name__ == "__main__":
    asyncio.run(run_all())
