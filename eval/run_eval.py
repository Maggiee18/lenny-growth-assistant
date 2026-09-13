#!/usr/bin/env python3
"""Evaluation harness for The Lenny Growth Assistant.

Runs eval/questions.json against a LIVE backend (real Postgres + Ollama, via
`docker compose up` or a local `uvicorn` + Ollama setup) and reports:

  - retrieval hit rate            (fraction of grounded questions that got >=1 source)
  - source citation presence      (fraction of non-abstained answers with sources)
  - abstention behavior           (did q6 abstain? did q1/q2/q4 NOT abstain?)
  - session continuity            (did the follow-up question run in the same session?)
  - provider routing              (which provider/model answered, from /api/config)
  - artifact generation success   (did ship30/markdown/html requests produce an artifact?)

This is intentionally a straightforward HTTP-driven script, not a scored
benchmark -- it exists to demonstrate the engineering discipline of having a
repeatable check, not to claim a rigorous accuracy number. See PRD.md
"Success metrics" for the distinction between target and measured metrics.

Usage:
    python eval/run_eval.py --base-url http://localhost:8000
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

QUESTIONS_PATH = Path(__file__).parent / "questions.json"


def word_count(markdown_text: str) -> int:
    stripped = re.sub(r"[#*_`>-]", " ", markdown_text)
    return len(stripped.split())


def run(base_url: str) -> dict[str, Any]:
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    client = httpx.Client(base_url=base_url, timeout=120.0)

    config = client.get("/api/config").json()
    print(f"Provider: {config['provider']} | Model: {config['model']}")

    sessions: dict[str, str] = {}  # question id -> session_id, for follow-up chaining
    results = []

    for q in questions:
        session_id = None
        if q.get("requires_prior"):
            session_id = sessions.get(q["requires_prior"])
        if session_id is None:
            session_id = client.post("/api/sessions", json={"title": q["id"]}).json()["id"]
        sessions[q["id"]] = session_id

        start = time.perf_counter()
        resp = client.post(f"/api/sessions/{session_id}/messages", json={"content": q["prompt"]})
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        record: dict[str, Any] = {"id": q["id"], "category": q["category"], "latency_ms": elapsed_ms}

        if resp.status_code != 200:
            record["error"] = f"HTTP {resp.status_code}: {resp.text[:300]}"
            results.append(record)
            continue

        body = resp.json()
        record["abstained"] = body["abstained"]
        record["source_count"] = len(body["sources"])
        record["has_artifact"] = body["artifact_id"] is not None

        if q.get("expect_abstain") is not None:
            record["abstain_check"] = "pass" if body["abstained"] == q["expect_abstain"] else "FAIL"
        if q.get("expect_sources") is True:
            record["sources_check"] = "pass" if len(body["sources"]) > 0 else "FAIL"
        if q.get("expect_min_sources"):
            distinct_docs = len({s["document_id"] for s in body["sources"]})
            record["distinct_sources"] = distinct_docs
            record["min_sources_check"] = "pass" if distinct_docs >= q["expect_min_sources"] else "FAIL"

        if q.get("expect_artifact_type"):
            if not body["artifact_id"]:
                record["artifact_check"] = "FAIL (no artifact created)"
            else:
                artifact = client.get(f"/api/artifacts/{body['artifact_id']}").json()
                record["artifact_type"] = artifact["artifact_type"]
                record["artifact_check"] = (
                    "pass" if artifact["artifact_type"] == q["expect_artifact_type"] else "FAIL"
                )
                if q.get("expect_word_count_band"):
                    wc = word_count(artifact["content"])
                    lo, hi = q["expect_word_count_band"]
                    record["word_count"] = wc
                    record["word_count_check"] = "pass" if lo <= wc <= hi else f"FAIL ({wc} not in [{lo},{hi}])"

        results.append(record)
        print(f"  [{q['id']}] {q['category']} -> {json.dumps({k: v for k, v in record.items() if k not in ('id', 'category')})}")

    summary = _summarize(results, config)
    return {"config": config, "results": results, "summary": summary}


def _summarize(results: list[dict], config: dict) -> dict:
    non_errored = [r for r in results if "error" not in r]
    grounded = [r for r in non_errored if r.get("abstained") is False]
    total_checks = 0
    passed_checks = 0
    for r in non_errored:
        for key, value in r.items():
            if key.endswith("_check"):
                total_checks += 1
                if value == "pass":
                    passed_checks += 1

    return {
        "provider": config["provider"],
        "model": config["model"],
        "questions_run": len(results),
        "questions_errored": len(results) - len(non_errored),
        "retrieval_hit_rate": round(sum(1 for r in grounded if r.get("source_count", 0) > 0) / max(len(grounded), 1), 2),
        "artifact_generation_success_rate": round(
            sum(1 for r in non_errored if r.get("has_artifact")) / max(sum(1 for r in results if "expect_artifact_type" in str(r)), 1), 2
        )
        if any("artifact_type" in r for r in non_errored)
        else None,
        "assertion_pass_rate": round(passed_checks / max(total_checks, 1), 2),
        "assertion_checks_total": total_checks,
        "assertion_checks_passed": passed_checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "results.json")
    args = parser.parse_args()

    try:
        report = run(args.base_url)
    except httpx.ConnectError as exc:
        print(f"ERROR: could not reach backend at {args.base_url}: {exc}", file=sys.stderr)
        print("Make sure `docker compose up` (or your local backend) is running first.", file=sys.stderr)
        return 1

    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n=== Summary ===")
    print(json.dumps(report["summary"], indent=2))
    print(f"\nFull report written to {args.out}")

    return 0 if report["summary"]["assertion_pass_rate"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
