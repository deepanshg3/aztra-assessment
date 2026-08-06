"""Independent black-box evaluation runner for the Retail Sales Analytics API.

Sends every question from ``questions.TEST_QUESTIONS`` to the running FastAPI
endpoint via HTTP, measures latency, saves all results to a timestamped JSON
file under ``evaluation_results/``, and prints progress to the console.

This module is completely independent of the production pipeline — it never
imports the orchestrator, LLM client, schemas, or any internal business logic.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from src.evaluation.questions import TEST_QUESTIONS

_EVALUATION_DIR: Path = Path("evaluation_results")
_ENDPOINT: str = "http://127.0.0.1:8000/ask"
_TIMEOUT_S: float = 120.0


def _format_timestamp(dt: datetime | None = None) -> str:
    """Return a compact ISO-like timestamp string, e.g. ``2026-08-06_17-30-42``.

    Args:
        dt: A datetime object. Defaults to the current UTC time.

    Returns:
        A string suitable for use in filenames.
    """
    target = dt or datetime.now(timezone.utc)
    return target.strftime("%Y-%m-%d_%H-%M-%S")


def _send_question(question: str) -> dict[str, Any]:
    """Send a single question to the API and return the result envelope.

    Args:
        question: The question text to send.

    Returns:
        A dict with keys ``question``, ``latency_ms``, and either
        ``response`` (on success) or ``status_code`` and ``error``
        (on failure).
    """
    start = time.perf_counter()

    try:
        resp = requests.post(
            _ENDPOINT,
            json={"question": question},
            timeout=_TIMEOUT_S,
        )
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        resp.raise_for_status()

        return {
            "question": question,
            "latency_ms": elapsed_ms,
            "response": resp.json(),
        }

    except requests.exceptions.Timeout:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        return {
            "question": question,
            "latency_ms": elapsed_ms,
            "status_code": 0,
            "error": "Request timed out",
        }

    except requests.exceptions.ConnectionError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        return {
            "question": question,
            "latency_ms": elapsed_ms,
            "status_code": 0,
            "error": f"Connection refused: {exc}",
        }

    except requests.exceptions.RequestException as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        status = resp.status_code if "resp" in dir() else 0
        return {
            "question": question,
            "latency_ms": elapsed_ms,
            "status_code": status,
            "error": str(exc),
        }

    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        return {
            "question": question,
            "latency_ms": elapsed_ms,
            "status_code": 0,
            "error": f"Unexpected error: {exc}",
        }


def run() -> Path:
    """Execute the full evaluation and save results to a timestamped JSON file.

    Returns:
        The path to the saved results file.
    """
    _EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

    total = len(TEST_QUESTIONS)
    results: list[dict[str, Any]] = []
    successful = 0
    failed = 0
    latencies: list[float] = []

    print(f"Evaluation started — {total} questions\n")

    for idx, (question, expected_intent) in enumerate(TEST_QUESTIONS, start=1):
        result = _send_question(question)
        result["expected_intent"] = expected_intent
        results.append(result)
        latencies.append(result["latency_ms"])

        if "response" in result:
            successful += 1
            status = result.get("status", "OK")
            intent = result["response"].get("intent", "?")
            print(
                f"[{idx}/{total}] PASS "
                f"({result['latency_ms']}ms) "
                f"intent={intent}"
            )
        else:
            failed += 1
            code = result.get("status_code", "?")
            print(
                f"[{idx}/{total}] FAIL "
                f"({result['latency_ms']}ms) "
                f"status={code}"
            )

    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": _ENDPOINT,
        "total_questions": total,
        "summary": {
            "successful": successful,
            "failed": failed,
            "average_latency_ms": avg_latency,
        },
        "results": results,
    }

    filename = f"evaluation_{_format_timestamp()}.json"
    output_path = _EVALUATION_DIR / filename

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 50}")
    print("Evaluation completed.")
    print(f"Questions executed: {total}")
    print(f"Average latency:    {avg_latency} ms")
    print(f"Successful requests: {successful}")
    print(f"Failed requests:    {failed}")
    print(f"Results written to: {output_path}")

    return output_path


def main() -> None:
    """Entry point for ``python -m src.evaluation.runner``."""
    run()


if __name__ == "__main__":
    main()