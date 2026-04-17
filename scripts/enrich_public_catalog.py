#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENUES_PATH = ROOT / "data" / "venues.json"
CANDIDATES_PATH = ROOT / "data" / "reports" / "latest-candidates.json"

TODAY = date(2026, 4, 17)

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "twentyone": 21,
    "twentytwo": 22,
    "twentythree": 23,
    "twentyfour": 24,
    "twentyfive": 25,
    "twentysix": 26,
    "twentyseven": 27,
    "twentyeight": 28,
    "twentynine": 29,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "fiftysix": 56,
}

MANUAL_OVERRIDES = {
    "louie-s-wine-dive-des-moines-metro-closed-2015-12-16": {
        "status": "lastcall",
        "neighborhood": "Drake",
        "venueType": "bar",
        "venueTypeLabel": "Bar",
        "cuisine": "Wine Bar",
        "openedDate": "2009-01-01",
        "openedDatePrecision": "year",
        "closedDate": "2026-05-31",
        "closedDatePrecision": "day",
        "story": (
            "Known for its wine list, brunch crowd, and polished neighborhood feel "
            "near Drake, Louie's Wine Dive announced it will pour its last glasses on May 31."
        ),
    },
    "801-chophouse-des-moines-metro-closed-2026-04-17": {
        "exclude": True,
    },
    "eddie-bauer-store-des-moines-metro-closed-2026-02-04": {
        "exclude": True,
    },
    "health-clinics-des-moines-metro-closed-2025-12-19": {
        "exclude": True,
    },
    "the-des-moines-register-ankeny-opened-2025-12-01": {
        "exclude": True,
    },
    "rhode-island-s-1st-ever-wingstop-throws-grand-opening-celebration-johnston-opened-2025-10-15": {
        "exclude": True,
    },
    "disney-store-des-moines-metro-closed-2021-04-30": {
        "exclude": True,
    },
    "store-badowers-des-moines-metro-closed-2021-02-26": {
        "exclude": True,
    },
    "video-warehouse-des-moines-metro-closed-2020-12-21": {
        "exclude": True,
    },
    "vaudeville-mews-des-moines-metro-closed-2020-10-09": {
        "exclude": True,
    },
    "mural-johnston-closed-2020-01-03": {
        "exclude": True,
    },
    "george-the-chili-king-closure": {
        "closedDate": "2020-01-01",
        "closedDatePrecision": "year",
        "story": (
            "Known for chili, loose-meat sandwiches, malt shakes, and its old-school diner feel, "
            "George the Chili King remains one of the metro's most mourned closures."
        ),
    },
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def year_from_item(item: dict) -> int:
    return int(item["eventDate"][:4])


def parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def format_date_label(value: str, precision: str | None) -> str:
    parsed = parse_iso(value)
    if not parsed:
        return value
    if precision == "day":
        return parsed.strftime("%b %-d, %Y")
    if precision == "month":
        return parsed.strftime("%b %Y")
    return parsed.strftime("%Y")


def humanize_story(text: str) -> str:
    story = re.sub(r"\s+", " ", text).strip()
    if story.startswith("Automatically verified from the lead pipeline."):
        story = story.replace("Automatically verified from the lead pipeline.", "").strip()
    story = story.replace("Matched facility-specific coverage for", "").strip()
    story = story.replace("Confirmation source: news.google.com.", "").strip()
    return story.strip(" .")


def is_generic_summary(text: str, item: dict) -> bool:
    summary = normalize(text)
    if not summary:
        return True

    exact = normalize(f"{item['name']} in {item['neighborhood']}")
    if summary == exact:
        return True

    if len(summary.split()) <= 6 and normalize(item["name"]) in summary:
        return True

    return False


def extract_year_phrase(text: str) -> int | None:
    direct_patterns = [
        re.compile(r"\bsince (\d{4})\b", re.I),
        re.compile(r"\bopened in (\d{4})\b", re.I),
        re.compile(r"\bfounded in (\d{4})\b", re.I),
        re.compile(r"\bestablished in (\d{4})\b", re.I),
        re.compile(r"\bopened in (\d{4})\b", re.I),
    ]
    for pattern in direct_patterns:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def extract_run_length_years(text: str) -> int | None:
    digit_match = (
        re.search(r"\bafter (?:about |more than |over |almost )?(\d{1,2})\+? years\b", text, re.I)
        or re.search(r"\bafter a (\d{1,2})-year run\b", text, re.I)
        or re.search(r"\bfor more than (\d{1,2}) years\b", text, re.I)
        or re.search(r"\bafter (\d{1,2}) years in business\b", text, re.I)
    )
    if digit_match:
        return int(digit_match.group(1))

    word_match = re.search(
        r"\bafter (?:about |more than |over |almost )?([a-z]+(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?) years\b",
        text,
        re.I,
    )
    if not word_match:
        return None

    token = word_match.group(1).replace(" ", "").replace("-", "").lower()
    return NUMBER_WORDS.get(token)


def extract_exact_date(text: str, default_year: int) -> tuple[str, str] | None:
    month_pattern = "|".join(MONTHS.keys())
    match = re.search(
        rf"\b({month_pattern})\.?\s+(\d{{1,2}})(?:,\s*(\d{{4}}))?",
        text,
        re.I,
    )
    if match:
        month = MONTHS[match.group(1).lower()]
        day = int(match.group(2))
        year = int(match.group(3) or default_year)
        return f"{year:04d}-{month:02d}-{day:02d}", "day"

    month_year = re.search(rf"\b({month_pattern})\.?\s+(\d{{4}})\b", text, re.I)
    if month_year:
        month = MONTHS[month_year.group(1).lower()]
        year = int(month_year.group(2))
        return f"{year:04d}-{month:02d}-01", "month"

    return None


def candidate_matches(item: dict, candidates: list[dict]) -> list[dict]:
    name_norm = normalize(item["name"])
    tokens = [token for token in name_norm.split() if len(token) > 2]
    matches = []
    for candidate in candidates:
        haystack = normalize(
            " ".join(
                [
                    candidate.get("title", ""),
                    candidate.get("summary", ""),
                    candidate.get("venue_guess", ""),
                ]
            )
        )
        if name_norm in haystack:
            matches.append(candidate)
            continue
        if tokens and sum(token in haystack for token in tokens) >= min(2, len(tokens)):
            matches.append(candidate)
    return matches


def derive_open_date(item: dict, matches: list[dict]) -> tuple[str | None, str | None]:
    if item["status"] == "opened":
        return item["eventDate"], item["datePrecision"]

    combined = " ".join([item.get("story", "")] + [match.get("summary", "") for match in matches])
    direct_year = extract_year_phrase(combined)
    if direct_year:
        return f"{direct_year:04d}-01-01", "year"

    run_years = extract_run_length_years(combined)
    if run_years:
        return f"{year_from_item(item) - run_years:04d}-01-01", "year"

    if "had opened only the year before" in combined.lower():
        return f"{year_from_item(item) - 1:04d}-01-01", "year"

    return None, None


def derive_close_date(item: dict, matches: list[dict]) -> tuple[str | None, str | None]:
    if item["status"] == "opened":
        return None, None

    texts = [item.get("story", "")] + [match.get("summary", "") for match in matches] + [match.get("title", "") for match in matches]
    for text in texts:
        extracted = extract_exact_date(text, year_from_item(item))
        if extracted:
            return extracted

    return item["eventDate"], item["datePrecision"]


def derive_public_description(item: dict, matches: list[dict]) -> str:
    override_story = humanize_story(item.get("story", ""))
    if override_story and not is_generic_summary(override_story, item):
        return override_story

    for match in matches:
        summary = re.sub(r"\s+", " ", match.get("summary", "")).strip()
        if not summary or is_generic_summary(summary, item):
            continue
        if len(summary) > 180:
            summary = summary[:177]
            summary = summary[: summary.rfind(" ")].rstrip(" ,.;:") + "..."
        return summary

    if item["status"] == "opened":
        return f"{item['name']} opened in {item['dateLabel']} as a {item['venueTypeLabel'].lower()} in {item['neighborhood']}."
    if item["status"] == "lastcall":
        return f"{item['name']} is in its final stretch in {item['neighborhood']} before a confirmed closing date."
    return f"{item['name']} closed in {item['dateLabel']} after a run in {item['neighborhood']}."


def main() -> None:
    payload = load_json(VENUES_PATH)
    candidates = load_json(CANDIDATES_PATH)

    updated_items = []
    for item in payload["items"]:
        override = MANUAL_OVERRIDES.get(item["id"], {})
        if override.get("exclude"):
            continue

        merged = {**item, **{k: v for k, v in override.items() if k != "exclude"}}
        matches = candidate_matches(merged, candidates)

        opened_date, opened_precision = derive_open_date(merged, matches)
        closed_date, closed_precision = derive_close_date(merged, matches)

        if override.get("openedDate"):
            opened_date = override["openedDate"]
            opened_precision = override.get("openedDatePrecision", "year")
        if override.get("closedDate"):
            closed_date = override["closedDate"]
            closed_precision = override.get("closedDatePrecision", "day")

        close_obj = parse_iso(closed_date)
        if close_obj and close_obj > TODAY:
            merged["status"] = "lastcall"
        elif merged["status"] != "opened":
            merged["status"] = "closed"

        merged["openedDate"] = opened_date
        merged["openedDatePrecision"] = opened_precision
        merged["closedDate"] = closed_date
        merged["closedDatePrecision"] = closed_precision
        merged["publicDescription"] = override.get(
            "story",
            derive_public_description(merged, matches),
        )

        if merged["status"] == "opened" and opened_date:
            merged["eventDate"] = opened_date
            merged["datePrecision"] = opened_precision or merged.get("datePrecision", "month")
            merged["dateLabel"] = format_date_label(
                opened_date,
                opened_precision or merged.get("datePrecision"),
            )
            merged["sortDate"] = opened_date
        elif merged["status"] in {"closed", "lastcall"} and closed_date:
            merged["eventDate"] = closed_date
            merged["datePrecision"] = closed_precision or merged.get("datePrecision", "month")
            merged["dateLabel"] = format_date_label(
                closed_date,
                closed_precision or merged.get("datePrecision"),
            )
            merged["sortDate"] = closed_date

        updated_items.append(merged)

    payload["items"] = sorted(updated_items, key=lambda item: item["sortDate"], reverse=True)
    save_json(VENUES_PATH, payload)


if __name__ == "__main__":
    main()
