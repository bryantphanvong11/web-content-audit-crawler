import csv
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

MAX_PAGES = 5


def eligible_pages():
    pages = []

    with INPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        for row in reader:
            status = str(
                row.get("status_code", "")
            ).strip()

            content_type = (
                row.get(
                    "raw_content_type",
                    ""
                )
                .lower()
            )

            redirects = int(
                row.get("redirects", 0)
                or 0
            )

            if status != "200":
                continue

            if "text/html" not in content_type:
                continue

            if redirects > 0:
                continue

            url = row.get(
                "url",
                "",
            ).strip()

            if not url:
                continue

            pages.append(url)

            if len(pages) >= MAX_PAGES:
                break

    return pages


def summarize_violations(response):
    violations = response.get(
        "violations",
        []
    )

    impacts = {}

    for violation in violations:
        impact = (
            violation.get("impact")
            or "unknown"
        )

        impacts[impact] = (
            impacts.get(impact, 0)
            + 1
        )

    top_rules = [
        violation.get("id", "")
        for violation in violations[:5]
    ]

    return impacts, top_rules


def main():
    pages = eligible_pages()

    print("=" * 70)
    print("ACCESSIBILITY TEST")
    print("=" * 70)

    print(
        f"Pages selected: {len(pages)}"
    )

    axe = Axe()

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

        for number, url in enumerate(
            pages,
            start=1,
        ):
            print()
            print("-" * 70)
            print(
                f"[{number}/{len(pages)}] "
                f"{url}"
            )

            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                results = axe.run(page)

                response = results.response

                impacts, top_rules = (
                    summarize_violations(
                        response
                    )
                )

                print(
                    "Violation rules: "
                    f"{results.violations_count}"
                )

                print(
                    f"Impact counts: "
                    f"{impacts}"
                )

                print(
                    "Top rules: "
                    + (
                        ", ".join(top_rules)
                        if top_rules
                        else "[none]"
                    )
                )

            except Exception as error:
                print(
                    f"ERROR: {error}"
                )

        browser.close()

    print()
    print("=" * 70)
    print("ACCESSIBILITY TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()