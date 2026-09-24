import csv
import re
from pathlib import Path
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parent.parent

GA4_FILE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "ga4_sessions_export.csv"
)

INVENTORY_FILE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "technical_inventory_full_test.csv"
)

MATCH_FILE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "ga4_inventory_matches.csv"
)

GA4_UNMATCHED_FILE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "ga4_unmatched_paths.csv"
)

INVENTORY_UNMATCHED_FILE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "inventory_without_ga4_match.csv"
)


def normalize_path(value):
    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    # Handle full URLs.
    if value.startswith(
        ("http://", "https://")
    ):
        value = urlsplit(value).path

    # Remove query strings and fragments.
    value = value.split("?", 1)[0]
    value = value.split("#", 1)[0]

    # Make duplicate leading slashes consistent.
    value = re.sub(r"^/+", "/", value)

    if not value.startswith("/"):
        value = "/" + value

    # Remove trailing slash except homepage.
    if len(value) > 1:
        value = value.rstrip("/")

    return value


def load_ga4():
    sessions_by_path = {}
    raw_rows = 0
    report_period = None

    with open(
        GA4_FILE,
        newline="",
        encoding="utf-8-sig",
    ) as file:
        reader = csv.reader(file)

        for row in reader:
            if not row:
                continue

            first = row[0].strip()

            if first.startswith("#"):
                match = re.search(
                    r"(\d{8})-(\d{8})",
                    first,
                )

                if match:
                    report_period = (
                        f"{match.group(1)}-"
                        f"{match.group(2)}"
                    )

                continue

            if first == (
                "Page path and screen class"
            ):
                continue

            # Ignore the GA4 Grand total row.
            if not first:
                continue

            if len(row) < 2:
                continue

            sessions_text = row[1].strip()

            try:
                sessions = int(
                    float(sessions_text)
                )
            except ValueError:
                continue

            path = normalize_path(first)

            if not path:
                continue

            raw_rows += 1

            sessions_by_path[path] = (
                sessions_by_path.get(
                    path,
                    0,
                )
                + sessions
            )

    return (
        sessions_by_path,
        raw_rows,
        report_period,
    )


def find_inventory_column(headers):
    candidates = [
        "path",
        "url/path",
        "url",
        "requested_url",
        "requested url",
        "requested_url_normalized",
        "normalized_url",
        "normalized url",
    ]

    lookup = {
        header.strip().lower(): header
        for header in headers
    }

    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]

    return None


def load_inventory():
    paths = []

    with open(
        INVENTORY_FILE,
        newline="",
        encoding="utf-8-sig",
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise SystemExit(
                "ERROR: Inventory CSV "
                "has no headers."
            )

        path_column = find_inventory_column(
            reader.fieldnames
        )

        if not path_column:
            print(
                "Could not automatically "
                "find URL/path column."
            )

            print(
                "Available columns:"
            )

            for column in reader.fieldnames:
                print(f"  - {column}")

            raise SystemExit(
                "Update the candidate list "
                "with the correct column."
            )

        print(
            "Inventory path column:",
            path_column,
        )

        for row in reader:
            path = normalize_path(
                row.get(path_column)
            )

            if path:
                paths.append(path)

    return paths


def write_results(
    ga4_sessions,
    inventory_paths,
):
    inventory_set = set(inventory_paths)
    ga4_set = set(ga4_sessions)

    matched = sorted(
        inventory_set & ga4_set
    )

    ga4_unmatched = sorted(
        ga4_set - inventory_set
    )

    inventory_unmatched = sorted(
        inventory_set - ga4_set
    )

    with open(
        MATCH_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)

        writer.writerow(
            [
                "path",
                "sessions",
            ]
        )

        for path in matched:
            writer.writerow(
                [
                    path,
                    ga4_sessions[path],
                ]
            )

    with open(
        GA4_UNMATCHED_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)

        writer.writerow(
            [
                "ga4_path",
                "sessions",
            ]
        )

        for path in ga4_unmatched:
            writer.writerow(
                [
                    path,
                    ga4_sessions[path],
                ]
            )

    with open(
        INVENTORY_UNMATCHED_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)

        writer.writerow(
            ["inventory_path"]
        )

        for path in inventory_unmatched:
            writer.writerow([path])

    matched_sessions = sum(
        ga4_sessions[path]
        for path in matched
    )

    return (
        matched,
        ga4_unmatched,
        inventory_unmatched,
        matched_sessions,
    )


def main():
    if not GA4_FILE.exists():
        raise SystemExit(
            f"Missing GA4 file:\n{GA4_FILE}"
        )

    if not INVENTORY_FILE.exists():
        raise SystemExit(
            "Missing inventory file:\n"
            f"{INVENTORY_FILE}"
        )

    (
        ga4_sessions,
        ga4_raw_rows,
        report_period,
    ) = load_ga4()

    inventory_paths = load_inventory()

    (
        matched,
        ga4_unmatched,
        inventory_unmatched,
        matched_sessions,
    ) = write_results(
        ga4_sessions,
        inventory_paths,
    )

    print()
    print("=" * 60)
    print("GA4 / INVENTORY MATCH AUDIT")
    print("=" * 60)

    print(
        "GA4 report period:",
        report_period,
    )

    print(
        "GA4 raw page-path rows:",
        ga4_raw_rows,
    )

    print(
        "GA4 unique normalized paths:",
        len(ga4_sessions),
    )

    print(
        "Inventory rows:",
        len(inventory_paths),
    )

    print(
        "Inventory unique paths:",
        len(set(inventory_paths)),
    )

    print()
    print(
        "Matched inventory paths:",
        len(matched),
    )

    print(
        "Inventory paths without GA4 match:",
        len(inventory_unmatched),
    )

    print(
        "GA4 paths not in inventory:",
        len(ga4_unmatched),
    )

    print(
        "Sessions on matched paths:",
        matched_sessions,
    )

    print()
    print("Reports written:")
    print(MATCH_FILE)
    print(GA4_UNMATCHED_FILE)
    print(INVENTORY_UNMATCHED_FILE)


if __name__ == "__main__":
    main()