#!/usr/bin/env python3
"""
Honest automatic test runner for AI Lead Classifier.
- Produces standardized error format even without API key
- Compares only fields that are present in "expected"
- Detects hallucinations more carefully
- Supports repeatability check (3 runs) for selected cases
- Always writes a report to reports/
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.schemas import ClassifyRequest
from app.services.classifier import classify_lead

TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"
REPORTS_DIR = ROOT / "reports"

# Cases used for repeatability check (run 3 times)
REPEATABILITY_IDS = ["TC-001", "TC-002", "TC-010"]


def load_cases() -> list[dict]:
    with TEST_CASES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _normalize(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    return value


def compare_field(actual: Any, expected: Any, field: str) -> tuple[bool, str | None]:
    """Honest comparison. None in expected means 'do not check this field'."""
    if expected is None and field.startswith("budget"):
        # Explicitly expect null
        if actual is not None:
            return False, f"{field}: expected null, got {actual!r}"
        return True, None

    if expected is None:
        return True, None

    actual = _normalize(actual)

    if actual is None and expected is not None:
        return False, f"{field}: expected {expected!r}, got null"

    if isinstance(expected, bool):
        if bool(actual) != expected:
            return False, f"{field}: expected {expected}, got {actual}"
        return True, None

    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if abs(float(actual) - float(expected)) > 1:
            return False, f"{field}: expected {expected}, got {actual}"
        return True, None

    if str(actual) != str(expected):
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

    if not getattr(result, "success", False):
        # Standardized error format
        err = getattr(result, "error", None)
        if err is not None:
            record["error"] = err.model_dump() if hasattr(err, "model_dump") else dict(err)
        else:
            record["error"] = {"code": "INTERNAL_ERROR", "message": str(result)}
        record["status"] = "fail"
        return record

    data = result.data
    record["actual"] = data.model_dump()
    record["success"] = True

    diffs = []
    expected = case.get("expected", {})
    for field, exp_val in expected.items():
        act_val = getattr(data, field, None)
        ok, msg = compare_field(act_val, exp_val, field)
        if not ok and msg:
            diffs.append(msg)

    record["diffs"] = diffs
    record["status"] = "pass" if not diffs else "fail"
    return record


async def check_repeatability(cases_by_id: dict) -> dict:
    """Run selected cases 3 times and check that key fields stay stable."""
    results = {}
    for cid in REPEATABILITY_IDS:
        case = cases_by_id.get(cid)
        if not case:
            continue
        runs = []
        for _ in range(3):
            rec = await run_single(case)
            runs.append(rec)
        # Compare key fields across successful runs
        successful = [r for r in runs if r["success"] and r["actual"]]
        stable = True
        note = ""
        if len(successful) < 2:
            stable = False
            note = "not enough successful runs"
        else:
            keys = ["service", "lead_quality", "budget_min_rub", "budget_max_rub", "needs_human_review"]
            base = successful[0]["actual"]
            for other in successful[1:]:
                for k in keys:
                    if base.get(k) != other["actual"].get(k):
                        stable = False
                        note = f"field {k} changed between runs"
                        break
                if not stable:
                    break
        results[cid] = {
            "stable": stable,
            "note": note,
            "runs_status": [r["status"] for r in runs],
        }
    return results


async def run_all() -> dict:
    cases = load_cases()
    cases_by_id = {c["id"]: c for c in cases}
    results = []

    print("=" * 60)
    print("Running test suite (honest mode)")
    print("=" * 60)

    for case in cases:
        print(f"{case['id']}: {case['title'][:50]} ...", end=" ", flush=True)
        rec = await run_single(case)
        results.append(rec)
        print(rec["status"].upper())
        if rec["diffs"]:
            for d in rec["diffs"]:
                print(f"    → {d}")

    # Repeatability
    print("\nRepeatability check (3 runs)...")
    repeatability = await check_repeatability(cases_by_id)
    for cid, info in repeatability.items():
        status = "STABLE" if info["stable"] else "UNSTABLE"
        print(f"  {cid}: {status} {info.get('note', '')}")

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = total - passed
    schema_valid = sum(1 for r in results if r["success"])

    # Accurate metrics only on cases that have the field in expected
    service_ok = service_total = 0
    budget_ok = budget_total = 0
    deadline_ok = deadline_total = 0
    human_review_ok = human_review_total = 0

    for r in results:
        exp = r.get("expected", {})
        act = r.get("actual") or {}
        if "service" in exp:
            service_total += 1
            if _normalize(act.get("service")) == exp["service"]:
                service_ok += 1
        if "budget_min_rub" in exp or "budget_max_rub" in exp:
            budget_total += 1
            ok = True
            if "budget_min_rub" in exp:
                a, e = act.get("budget_min_rub"), exp["budget_min_rub"]
                if e is None:
                    if a is not None:
                        ok = False
                elif a is None or abs(float(a) - float(e)) > 1:
                    ok = False
            if "budget_max_rub" in exp:
                a, e = act.get("budget_max_rub"), exp["budget_max_rub"]
                if e is None:
                    if a is not None:
                        ok = False
                elif a is None or abs(float(a) - float(e)) > 1:
                    ok = False
            if ok:
                budget_ok += 1
        if "deadline_date" in exp:
            deadline_total += 1
            if act.get("deadline_date") == exp["deadline_date"]:
                deadline_ok += 1
        if "needs_human_review" in exp:
            human_review_total += 1
            if bool(act.get("needs_human_review")) == bool(exp["needs_human_review"]):
                human_review_ok += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "json_schema_valid_rate": round(schema_valid / total, 4) if total else 0,
        "service_accuracy": round(service_ok / service_total, 4) if service_total else None,
        "budget_accuracy": round(budget_ok / budget_total, 4) if budget_total else None,
        "deadline_accuracy": round(deadline_ok / deadline_total, 4) if deadline_total else None,
        "needs_human_review_accuracy": round(human_review_ok / human_review_total, 4) if human_review_total else None,
        "repeatability": repeatability,
        "average_response_time_ms": round(sum(r["elapsed_ms"] for r in results) / total, 1) if total else 0,
        "results": results,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Also write a stable name for the repository
    stable_path = REPORTS_DIR / "latest_report.json"
    with stable_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"TOTAL: {total}  PASSED: {passed}  FAILED: {failed}")
    print(f"JSON schema valid rate: {report['json_schema_valid_rate']}")
    print(f"Service accuracy:       {report['service_accuracy']}")
    print(f"Budget accuracy:        {report['budget_accuracy']}")
    print(f"Deadline accuracy:      {report['deadline_accuracy']}")
    print(f"needs_human_review:     {report['needs_human_review_accuracy']}")
    print(f"Avg response time:      {report['average_response_time_ms']} ms")
    print(f"Report saved to:        {out_path}")
    print(f"Also saved as:          {stable_path}")
    print("=" * 60)

    return report


if __name__ == "__main__":
    asyncio.run(run_all())
