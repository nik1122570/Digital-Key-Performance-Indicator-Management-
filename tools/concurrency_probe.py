"""Exercise two simultaneous authenticated HTTP writes on an isolated test site.

Required env: KPI_TEST_SITE (base URL), KPI_TEST_TOKEN (API key:secret for a
scoped KPI Manager). No credential is written or printed. See docs/UAT.md.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from threading import Barrier
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


def request(base, token, method, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = Request(
        base + path,
        data=body,
        method=method,
        headers={"Authorization": "token " + token, "Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=90) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        try:
            payload = json.load(error)
        except Exception:
            payload = {}
        return error.code, payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-isolated-test-site", action="store_true", required=True
    )
    sub = parser.add_subparsers(dest="case", required=True)
    generation = sub.add_parser("duplicate-review")
    generation.add_argument("--assignment", required=True)
    generation.add_argument("--start", required=True)
    generation.add_argument("--end", required=True)
    overlap = sub.add_parser("assignment-overlap")
    overlap.add_argument("--drafts", nargs=2, required=True)
    args = parser.parse_args()
    base = os.environ["KPI_TEST_SITE"].rstrip("/")
    token = os.environ["KPI_TEST_TOKEN"]
    if not base.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        raise SystemExit("Use HTTPS or a local test server.")
    if args.case == "duplicate-review":
        payload = {
            "assignment": args.assignment,
            "period_start": args.start,
            "period_end": args.end,
        }
        tasks = [("/api/method/kpi_management.api.recover_period", payload)] * 2
    else:
        tasks = []
        for name in args.drafts:
            status, payload = request(
                base,
                token,
                "GET",
                "/api/resource/KPI%20Structure%20Assignment/" + quote(name, safe=""),
            )
            if status != 200 or payload.get("data", {}).get("docstatus") != 0:
                raise SystemExit("Both named assignments must be accessible Drafts.")
            tasks.append(
                (
                    "/api/method/frappe.client.submit",
                    {"doc": json.dumps(payload["data"])},
                )
            )
    barrier = Barrier(2)

    def run(task):
        barrier.wait()
        return request(base, token, "POST", *task)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, tasks))
    for i, (status, payload) in enumerate(results, 1):
        print(
            json.dumps(
                {
                    "request": i,
                    "http_status": status,
                    "exception": payload.get("exc_type"),
                    "document": (payload.get("message") or {}).get("name")
                    if isinstance(payload.get("message"), dict)
                    else None,
                }
            )
        )
    successes = sum(200 <= status < 300 for status, _ in results)
    if successes != 1:
        raise SystemExit(
            "FAIL: expected exactly one successful mutation. Inspect test site and errors."
        )
    if not any(
        payload.get("exc_type")
        in ("ValidationError", "DuplicateEntryError", "TimestampMismatchError")
        for status, payload in results
        if status >= 400
    ):
        raise SystemExit(
            "FAIL: losing request failed for an unexpected reason; inspect logs."
        )
    print(
        "PASS: exactly one succeeded; loser was rejected by a business/concurrency guard. Verify the database record count in UAT."
    )


if __name__ == "__main__":
    main()

