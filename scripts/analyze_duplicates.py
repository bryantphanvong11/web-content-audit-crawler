import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "output"
)

GROUPS_FILE = (
    OUTPUT_DIR
    / "exact_title_groups_full_test.csv"
)

TECHNICAL_FILE = (
    OUTPUT_DIR
    / "technical_inventory_full_test.csv"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "duplicate_review_full_test.csv"
)


DELAY_SECONDS = 0.5
CHECKPOINT_EVERY = 25


HEADERS = {
    "User-Agent": (
        "Washington AGO Content Inventory Project "
        "(duplicate review crawler)"
    )
}


LANGUAGE_PATH_WORDS = {
    "arabic",
    "chinese",
    "japanese",
    "khmer",
    "korean",
    "lao",
    "russian",
    "ukrainian",
    "spanish",
    "vietnamese",
    "tagalog",
    "punjabi",
    "somali",
}


def clean(value):
    return " ".join(
        (value or "")
        .strip()
        .split()
    )


def normalize_text(value):
    value = (
        value or ""
    ).lower()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def build_full_url(path):
    if path.startswith(
        ("http://", "https://")
    ):
        return path

    return urljoin(
        "https://www.atg.wa.gov",
        path,
    )


def load_technical_inventory():
    inventory = {}

    with TECHNICAL_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            path = clean(
                row.get("path")
            )

            if not path:
                continue

            inventory[path] = row

    return inventory


def load_duplicate_groups():
    groups = []

    with GROUPS_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        for group_number, row in enumerate(
            reader,
            start=1,
        ):
            paths = [
                clean(path)
                for path in (
                    row.get("paths")
                    or ""
                ).split(" | ")
                if clean(path)
            ]

            if len(paths) < 2:
                continue

            groups.append(
                {
                    "group_id": (
                        f"DUP-{group_number:03d}"
                    ),
                    "normalized_title": clean(
                        row.get(
                            "normalized_title"
                        )
                    ),
                    "display_titles": clean(
                        row.get(
                            "display_titles"
                        )
                    ),
                    "paths": paths,
                }
            )

    return groups


def extract_page_details(
    session,
    url,
):
    response = session.get(
        url,
        timeout=30,
        allow_redirects=True,
    )

    soup = BeautifulSoup(
        response.text,
        "lxml",
    )

    html_tag = soup.find("html")

    language = ""

    if html_tag:
        language = clean(
            html_tag.get("lang")
        ).lower()

    canonical_url = ""

    canonical = soup.find(
        "link",
        rel=lambda value: (
            value
            and "canonical"
            in (
                value
                if isinstance(
                    value,
                    list,
                )
                else [value]
            )
        ),
    )

    if canonical:
        canonical_url = clean(
            canonical.get("href")
        )

        if canonical_url:
            canonical_url = urljoin(
                response.url,
                canonical_url,
            )

    description = ""

    meta_description = soup.find(
        "meta",
        attrs={
            "name": re.compile(
                r"^description$",
                re.I,
            )
        },
    )

    if meta_description:
        description = clean(
            meta_description.get(
                "content"
            )
        )

    h1 = soup.find("h1")

    h1_text = (
        clean(
            h1.get_text(
                " ",
                strip=True,
            )
        )
        if h1
        else ""
    )

    main = soup.find("main")

    if main is None:
        main = soup.find(
            attrs={
                "role": "main"
            }
        )

    if main is None:
        main = soup.body

    if main is None:
        body_text = ""

    else:
        # Work on a separate parsed fragment so
        # removing elements does not affect soup.
        fragment = BeautifulSoup(
            str(main),
            "lxml",
        )

        for tag in fragment.find_all(
            [
                "script",
                "style",
                "noscript",
                "nav",
                "header",
                "footer",
            ]
        ):
            tag.decompose()

        body_text = clean(
            fragment.get_text(
                " ",
                strip=True,
            )
        )

    word_count = len(
        body_text.split()
    )

    return {
        "language": language,
        "canonical_url": canonical_url,
        "meta_description": (
            description
        ),
        "h1": h1_text,
        "body_text": body_text,
        "word_count": word_count,
    }


def translation_signal(
    path,
    language,
):
    language = (
        language or ""
    ).lower()

    # Explicit non-English HTML language.
    if language and not language.startswith(
        "en"
    ):
        return True

    path_lower = (
        path or ""
    ).lower()

    for word in LANGUAGE_PATH_WORDS:
        if word in path_lower:
            return True

    return False


def archive_signal(path):
    path_lower = (
        path or ""
    ).lower()

    patterns = [
        r"/ago-opinions/year/",
        r"/orig-op-page-",
        r"/ago-opinion/topic-",
    ]

    return any(
        re.search(
            pattern,
            path_lower,
        )
        for pattern in patterns
    )


def legacy_signals(path):
    signals = []

    path_lower = (
        path or ""
    ).lower()

    if ".aspx" in path_lower:
        signals.append(
            "legacy .aspx URL"
        )

    if re.search(
        r"-\d+$",
        path_lower,
    ):
        signals.append(
            "numbered URL suffix"
        )

    if re.search(
        r"-\d+-\d+$",
        path_lower,
    ):
        signals.append(
            "multiple numbered suffixes"
        )

    if "/orig-op-page-" in path_lower:
        signals.append(
            "legacy/archive-style path"
        )

    return signals


def canonical_matches_self(
    canonical_url,
    path,
):
    if not canonical_url:
        return False

    try:
        canonical_path = (
            urlsplit(
                canonical_url
            ).path
            or "/"
        )
    except Exception:
        return False

    return (
        canonical_path.rstrip("/")
        == path.rstrip("/")
    )


def primary_score(page):
    score = 0

    if page["status_code"] == "200":
        score += 100

    if page["redirects"] == 0:
        score += 40

    if page[
        "canonical_matches_self"
    ]:
        score += 20

    if not page["legacy_signals"]:
        score += 20

    if page["is_translation"]:
        # Translation variants should not usually
        # become the English group's primary URL.
        score -= 10

    if page["word_count"] > 0:
        score += min(
            page["word_count"] / 100,
            10,
        )

    # Prefer cleaner/shorter paths when all
    # other signals are comparable.
    score -= (
        len(page["path"])
        / 100
    )

    return score


def similarity(
    text_a,
    text_b,
):
    if not text_a or not text_b:
        return None

    # Limit exceptionally long pages while
    # retaining enough body content for
    # meaningful comparisons.
    a = normalize_text(
        text_a
    )[:30000]

    b = normalize_text(
        text_b
    )[:30000]

    return round(
        fuzz.ratio(
            a,
            b,
        ),
        1,
    )


def recommend(
    page,
    primary,
    similarity_score,
):
    status = page["status_code"]

    if status == "404":
        return (
            "No",
            "High",
            (
                "Page returns HTTP 404 "
                "and does not provide "
                "usable current content."
            ),
        )

    if status == "403":
        return (
            "Somewhat",
            "Low",
            (
                "Page returned HTTP 403. "
                "Content could not be fully "
                "evaluated automatically."
            ),
        )

    if status.startswith("5"):
        return (
            "Somewhat",
            "Low",
            (
                f"Page returned HTTP {status}; "
                "manual review recommended."
            ),
        )

    if page["redirects"] > 0:
        destination = (
            page["final_url"]
            or "[unknown destination]"
        )

        return (
            "No",
            "High",
            (
                "Obsolete redirect source. "
                f"Current destination: "
                f"{destination}"
            ),
        )

    if page["is_translation"]:
        return (
            "Keep",
            "High",
            (
                "Translation/language variant "
                "serves a distinct audience."
            ),
        )

    if page["path"] == primary["path"]:
        return (
            "Keep",
            "High",
            (
                "Best current candidate in "
                "this duplicate group based "
                "on status, URL quality, "
                "canonical signals and content."
            ),
        )

    if page["is_archive"]:
        if (
            similarity_score
            is not None
            and similarity_score < 85
        ):
            return (
                "Keep",
                "Medium",
                (
                    "Archive/year page shares "
                    "a title but contains "
                    "meaningfully different "
                    "body content."
                ),
            )

        return (
            "Somewhat",
            "Medium",
            (
                "Archive/pagination page may "
                "contain distinct records, "
                "but appears highly similar "
                "to another page in the group."
            ),
        )

    legacy = bool(
        page["legacy_signals"]
    )

    if similarity_score is None:
        return (
            "Somewhat",
            "Low",
            (
                "Same-title candidate but "
                "body similarity could not "
                "be calculated reliably."
            ),
        )

    if similarity_score >= 95:
        if legacy:
            return (
                "No",
                "High",
                (
                    f"Body is {similarity_score}% "
                    "similar to the primary page "
                    "and the URL has legacy/"
                    "duplicate characteristics."
                ),
            )

        return (
            "No",
            "Medium",
            (
                f"Body is {similarity_score}% "
                "similar to the primary page "
                "with little evidence of a "
                "distinct purpose."
            ),
        )

    if similarity_score >= 85:
        return (
            "Somewhat",
            "Medium",
            (
                f"Body is {similarity_score}% "
                "similar to the primary page, "
                "but differences may be "
                "meaningful."
            ),
        )

    return (
        "Keep",
        "Medium",
        (
            f"Same title but body similarity "
            f"is only {similarity_score}%, "
            "suggesting distinct content "
            "or purpose."
        ),
    )


def save_results(rows):
    fieldnames = [
        "duplicate_group",
        "group_title",
        "group_size",
        "path",
        "url",
        "status_code",
        "redirects",
        "final_url",
        "page_title",
        "h1",
        "language",
        "is_translation",
        "is_archive",
        "canonical_url",
        "canonical_matches_self",
        "meta_description",
        "word_count",
        "last_modified",
        "primary_path",
        "is_primary",
        "body_similarity_to_primary",
        "legacy_signals",
        "recommendation",
        "confidence",
        "recommendation_reason",
    ]

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def main():
    if not GROUPS_FILE.exists():
        raise SystemExit(
            f"ERROR: Missing {GROUPS_FILE}"
        )

    if not TECHNICAL_FILE.exists():
        raise SystemExit(
            f"ERROR: Missing {TECHNICAL_FILE}"
        )

    technical = (
        load_technical_inventory()
    )

    groups = (
        load_duplicate_groups()
    )

    total_candidates = sum(
        len(group["paths"])
        for group in groups
    )

    print("=" * 70)
    print("ENRICHED DUPLICATE ANALYSIS")
    print("=" * 70)

    print(
        f"Duplicate groups: "
        f"{len(groups)}"
    )

    print(
        f"Candidate pages:  "
        f"{total_candidates}"
    )

    print()

    session = requests.Session()
    session.headers.update(
        HEADERS
    )

    all_rows = []
    processed = 0

    for group in groups:
        group_pages = []

        print()
        print("=" * 70)
        print(
            f"{group['group_id']} "
            f"| {group['display_titles']}"
        )
        print("=" * 70)

        for path in group["paths"]:
            processed += 1

            technical_row = (
                technical.get(
                    path,
                    {},
                )
            )

            url = clean(
                technical_row.get(
                    "url"
                )
            ) or build_full_url(
                path
            )

            status = str(
                technical_row.get(
                    "status_code",
                    "",
                )
            ).strip()

            redirects = int(
                technical_row.get(
                    "redirects",
                    0,
                )
                or 0
            )

            page = {
                "duplicate_group": (
                    group["group_id"]
                ),
                "group_title": (
                    group["display_titles"]
                ),
                "group_size": len(
                    group["paths"]
                ),
                "path": path,
                "url": url,
                "status_code": status,
                "redirects": redirects,
                "final_url": clean(
                    technical_row.get(
                        "final_url"
                    )
                ),
                "page_title": clean(
                    technical_row.get(
                        "title"
                    )
                ),
                "last_modified": clean(
                    technical_row.get(
                        "last_modified"
                    )
                ),
                "language": "",
                "canonical_url": "",
                "canonical_matches_self": False,
                "meta_description": "",
                "h1": "",
                "body_text": "",
                "word_count": 0,
            }

            if (
                status == "200"
                and redirects == 0
            ):
                try:
                    details = (
                        extract_page_details(
                            session,
                            url,
                        )
                    )

                    page.update(
                        details
                    )

                except requests.RequestException as error:
                    print(
                        f"  FETCH ERROR: "
                        f"{path}: {error}"
                    )

            page[
                "is_translation"
            ] = translation_signal(
                path,
                page["language"],
            )

            page[
                "is_archive"
            ] = archive_signal(
                path
            )

            page[
                "legacy_signals"
            ] = legacy_signals(
                path
            )

            page[
                "canonical_matches_self"
            ] = canonical_matches_self(
                page["canonical_url"],
                path,
            )

            group_pages.append(
                page
            )

            print(
                f"[{processed}/"
                f"{total_candidates}] "
                f"{path}"
            )

            time.sleep(
                DELAY_SECONDS
            )

        primary = max(
            group_pages,
            key=primary_score,
        )

        for page in group_pages:
            if (
                page["path"]
                == primary["path"]
            ):
                similarity_score = 100.0

            else:
                similarity_score = similarity(
                    page["body_text"],
                    primary["body_text"],
                )

            (
                recommendation,
                confidence,
                reason,
            ) = recommend(
                page,
                primary,
                similarity_score,
            )

            output_row = {
                "duplicate_group": (
                    page[
                        "duplicate_group"
                    ]
                ),
                "group_title": (
                    page["group_title"]
                ),
                "group_size": (
                    page["group_size"]
                ),
                "path": page["path"],
                "url": page["url"],
                "status_code": (
                    page["status_code"]
                ),
                "redirects": (
                    page["redirects"]
                ),
                "final_url": (
                    page["final_url"]
                ),
                "page_title": (
                    page["page_title"]
                ),
                "h1": page["h1"],
                "language": (
                    page["language"]
                ),
                "is_translation": (
                    "YES"
                    if page[
                        "is_translation"
                    ]
                    else "NO"
                ),
                "is_archive": (
                    "YES"
                    if page[
                        "is_archive"
                    ]
                    else "NO"
                ),
                "canonical_url": (
                    page[
                        "canonical_url"
                    ]
                ),
                "canonical_matches_self": (
                    "YES"
                    if page[
                        "canonical_matches_self"
                    ]
                    else "NO"
                ),
                "meta_description": (
                    page[
                        "meta_description"
                    ]
                ),
                "word_count": (
                    page["word_count"]
                ),
                "last_modified": (
                    page[
                        "last_modified"
                    ]
                ),
                "primary_path": (
                    primary["path"]
                ),
                "is_primary": (
                    "YES"
                    if page["path"]
                    == primary["path"]
                    else "NO"
                ),
                "body_similarity_to_primary": (
                    similarity_score