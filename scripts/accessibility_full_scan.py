import csv
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from axe_playwright_python.sync_playwright import Axe


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "technical_inventory_full_test.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "accessibility_full_test.csv"
)


CHECKPOINT_EVERY = 25

PAGE_TIMEOUT_MS = 30000

DELAY_SECONDS = 0.5


def load_eligible_pages():
    pages = []

    with INPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        for row in reader:
            status = str(
                row.get(
                    "status_code",
                    "",
                )
            ).strip()

            content_type = (
                row.get(
                    "raw_content_type",
                    "",
                )
                .lower()
            )

            redirects = int(
                row.get(
                    "redirects",
                    0,
                )
                or 0
            )

            if status != "200":
                continue

            if "text/html" not in content_type:
                continue

            if redirects > 0:
                continue

            url = (
                row.get(
                    "url",
                    "",
                )
                .strip()
            )

            path = (
                row.get(
                    "path",
                    "",
                )
                .strip()
            )

            if not url or not path:
                continue

            pages.append(
                {
                    "url": url,
                    "path": path,
                }
            )

    return pages


def load_existing_results():
    results = {}

    if not OUTPUT_FILE.exists():
        return results

    with OUTPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        for row in reader:
            path = (
                row.get(
                    "path",
                    "",
                )
                .strip()
            )

            if path:
                results[path] = row

    return results


def count_impacts(violations):
    counts = {
        "critical": 0,
        "serious": 0,
        "moderate": 0,
        "minor": 0,
        "unknown": 0,
    }

    for violation in violations:
        impact = (
            violation.get(
                "impact"
            )
            or "unknown"
        )

        if impact not in counts:
            impact = "unknown"

        counts[impact] += 1

    return counts


def build_summary(
    violation_count,
    impacts,
    rule_ids,
):
    if violation_count == 0:
        return (
            "[A11y automated] "
            "0 violation rules detected"
        )

    pieces = [
        (
            f"[A11y automated] "
            f"{violation_count} "
            "violation rules"
        )
    ]

    impact_parts = []

    for impact in [
        "critical",
        "serious",
        "moderate",
        "minor",
    ]:
        count = impacts.get(
            impact,
            0,
        )

        if count:
            impact_parts.append(
                f"{impact}={count}"
            )

    if impact_parts:
        pieces.append(
            ", ".join(
                impact_parts
            )
        )

    if rule_ids:
        pieces.append(
            "top: "
            + ", ".join(
                rule_ids[:5]
            )
        )

    return "; ".join(pieces)


def save_results(results):
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows = list(
        results.values()
    )

    fieldnames = [
        "path",
        "url",
        "scan_status",
        "violation_rules",
        "critical",
        "serious",
        "moderate",
        "minor",
        "unknown",
        "rule_ids",
        "accessibility_flag",
        "error",
    ]

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def main():
    pages = load_eligible_pages()

    results = load_existing_results()

    already_done = {
        path
        for path, row in results.items()
        if row.get(
            "scan_status"
        ) == "COMPLETE"
    }

    print("=" * 70)
    print("FULL ACCESSIBILITY SCAN")
    print("=" * 70)

    print(
        f"Eligible pages:     "
        f"{len(pages)}"
    )

    print(
        f"Already completed:  "
        f"{len(already_done)}"
    )

    print()

    axe = Axe()

    scanned_this_run = 0
    errors_this_run = 0

    with sync_playwright() as playwright:
        browser = (
            playwright
            .chromium
            .launch(
                headless=True
            )
        )

        context = browser.new_context(
            bypass_csp=True
        )

        page = context.new_page()

        for index, item in enumerate(
            pages,
            start=1,
        ):
            path = item["path"]
            url = item["url"]

            if path in already_done:
                continue

            scanned_this_run += 1

            print(
                f"[{index}/{len(pages)}] "
                f"{url}"
            )

            try:
                page.goto(
                    url,
                    wait_until=(
                        "domcontentloaded"
                    ),
                    timeout=(
                        PAGE_TIMEOUT_MS
                    ),
                )

                axe_results = axe.run(
                    page
                )

                response = (
                    axe_results.response
                )

                violations = (
                    response.get(
                        "violations",
                        [],
                    )
                )

                impacts = (
                    count_impacts(
                        violations
                    )
                )

                rule_ids = [
                    violation.get(
                        "id",
                        "",
                    )
                    for violation
                    in violations
                    if violation.get(
                        "id"
                    )
                ]

                violation_count = len(
                    violations
                )

                flag = build_summary(
                    violation_count,
                    impacts,
                    rule_ids,
                )

                results[path] = {
                    "path": path,
                    "url": url,
                    "scan_status": (
                        "COMPLETE"
                    ),
                    "violation_rules": (
                        violation_count
                    ),
                    "critical": (
                        impacts[
                            "critical"
                        ]
                    ),
                    "serious": (
                        impacts[
                            "serious"
                        ]
                    ),
                    "moderate": (
                        impacts[
                            "moderate"
                        ]
                    ),
                    "minor": (
                        impacts[
                            "minor"
                        ]
                    ),
                    "unknown": (
                        impacts[
                            "unknown"
                        ]
                    ),
                    "rule_ids": (
                        " | ".join(
                            rule_ids
                        )
                    ),
                    "accessibility_flag": (
                        flag
                    ),
                    "error": "",
                }

                print(
                    f"  Rules: "
                    f"{violation_count}"
                )

            except Exception as error:
                errors_this_run += 1

                print(
                    f"  ERROR: {error}"
                )

                results[path] = {
                    "path": path,
                    "url": url,
                    "scan_status": (
                        "ERROR"
                    ),
                    "violation_rules": "",
                    "critical": "",
                    "serious": "",
                    "moderate": "",
                    "minor": "",
                    "unknown": "",
                    "rule_ids": "",
                    "accessibility_flag": "",
                    "error": str(
                        error
                    )[:500],
                }

            if (
                CHECKPOINT_EVERY
                and scanned_this_run
                % CHECKPOINT_EVERY
                == 0
            ):
                save_results(
                    results
                )

                print()
                print(
                    "=" * 70
                )

                print(
                    "CHECKPOINT: "
                    f"{scanned_this_run} "
                    "pages scanned "
                    "this run"
                )

                print(
                    f"Results saved: "
                    f"{len(results)}"
                )

                print(
                    "=" * 70
                )

                print()

            time.sleep(
                DELAY_SECONDS
            )

        browser.close()

    save_results(
        results
    )

    completed = sum(
        1
        for row in results.values()
        if row.get(
            "scan_status"
        )
        == "COMPLETE"
    )

    errors = sum(
        1
        for row in results.values()
        if row.get(
            "scan_status"
        )
        == "ERROR"
    )

    print()
    print("=" * 70)
    print(
        "FULL ACCESSIBILITY "
        "SCAN COMPLETE"
    )
    print("=" * 70)

    print(
        f"Eligible pages:       "
        f"{len(pages)}"
    )

    print(
        f"Completed scans:      "
        f"{completed}"
    )

    print(
        f"Errors:               "
        f"{errors}"
    )

    print(
        f"Scanned this run:     "
        f"{scanned_this_run}"
    )

    print()
    print(
        f"Report: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()