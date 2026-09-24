import csv
from collections import Counter
from pathlib import Path


INPUT_FILE = Path(
    "data/output/technical_inventory_full_test.csv"
)


def main():
    if not INPUT_FILE.exists():
        print(f"ERROR: Could not find {INPUT_FILE}")
        return

    rows = []

    with INPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    print("=" * 70)
    print("FULL CRAWL AUDIT")
    print("=" * 70)
    print()

    print(f"Total rows: {len(rows)}")

    paths = [
        row.get("path", "").strip()
        for row in rows
        if row.get("path", "").strip()
    ]

    unique_paths = set(paths)

    print(f"Unique paths: {len(unique_paths)}")
    print(
        f"Duplicate path rows: "
        f"{len(paths) - len(unique_paths)}"
    )

    print()
    print("=" * 70)
    print("STATUS CODES")
    print("=" * 70)

    statuses = Counter(
        row.get("status_code", "").strip()
        for row in rows
    )

    for status, count in statuses.most_common():
        print(f"{status or '[blank]':>10}: {count}")

    print()
    print("=" * 70)
    print("CONTENT TYPES")
    print("=" * 70)

    content_types = Counter()

    for row in rows:
        raw_type = (
            row.get("raw_content_type", "")
            .split(";")[0]
            .strip()
            .lower()
        )

        content_types[
            raw_type or "[blank]"
        ] += 1

    for content_type, count in content_types.most_common(15):
        print(
            f"{content_type:<35} {count}"
        )

    print()
    print("=" * 70)
    print("REDIRECTS")
    print("=" * 70)

    redirected = [
        row
        for row in rows
        if int(row.get("redirects") or 0) > 0
    ]

    print(
        f"Pages with redirects: {len(redirected)}"
    )

    multi_hop = [
        row
        for row in redirected
        if int(row.get("redirects") or 0) > 1
    ]

    print(
        f"Multi-hop redirects:  {len(multi_hop)}"
    )

    print()
    print("=" * 70)
    print("CONTENT QUALITY CHECKS")
    print("=" * 70)

    html_rows = [
        row
        for row in rows
        if "text/html"
        in row.get(
            "raw_content_type",
            "",
        ).lower()
    ]

    missing_titles = [
        row
        for row in html_rows
        if not row.get(
            "title",
            "",
        ).strip()
    ]

    not_displayed = [
        row
        for row in html_rows
        if row.get(
            "last_modified",
            "",
        ).strip()
        == "Not Displayed"
    ]

    print(
        f"HTML pages:             {len(html_rows)}"
    )

    print(
        f"HTML pages no title:    {len(missing_titles)}"
    )

    print(
        "HTML pages with "
        f"'Not Displayed': {len(not_displayed)}"
    )

    print()
    print("=" * 70)
    print("POSSIBLE WARNING SIGNS")
    print("=" * 70)

    error_rows = [
        row
        for row in rows
        if str(
            row.get(
                "status_code",
                "",
            )
        ).startswith(
            ("4", "5")
        )
    ]

    print(
        f"4xx/5xx responses: {len(error_rows)}"
    )

    if error_rows:
        print()
        print("First 15 error URLs:")

        for row in error_rows[:15]:
            print(
                f"  {row.get('status_code')} "
                f"{row.get('path')}"
            )

    print()
    print("=" * 70)
    print("LAST 20 CRAWLED PATHS")
    print("=" * 70)

    for row in rows[-20:]:
        print(
            row.get("path", "")
        )

    print()
    print("=" * 70)
    print("AUDIT COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()