#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "venues.json"

REQUIRED_FIELDS = {
    "id",
    "name",
    "status",
    "eventDate",
    "sortDate",
    "dateLabel",
    "datePrecision",
    "venueType",
    "venueTypeLabel",
    "neighborhood",
    "story",
    "verificationLevel",
    "sources",
}

VALID_STATUS = {"opened", "closed", "lastcall"}
VALID_PRECISION = {"day", "month", "year"}
VALID_VERIFICATION = {"verified", "review"}
PLANNED_TERMS = ("planned", "plan is", "expected to open", "set to open", "about to open")


def main() -> int:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    items = payload.get("items", [])

    errors: list[str] = []
    warnings: list[str] = []

    ids = Counter(item.get("id") for item in items)
    for entry_id, count in ids.items():
        if count > 1:
            errors.append(f"Duplicate id: {entry_id} ({count})")

    prev_sort = None
    for index, item in enumerate(items):
        missing = sorted(REQUIRED_FIELDS - item.keys())
        if missing:
            errors.append(f"{item.get('id', '<missing-id>')}: missing fields {missing}")
            continue

        if item["status"] not in VALID_STATUS:
            errors.append(f"{item['id']}: invalid status {item['status']}")

        if item["datePrecision"] not in VALID_PRECISION:
            errors.append(f"{item['id']}: invalid datePrecision {item['datePrecision']}")

        if item["verificationLevel"] not in VALID_VERIFICATION:
            errors.append(
                f"{item['id']}: invalid verificationLevel {item['verificationLevel']}"
            )

        if not item["sources"]:
            errors.append(f"{item['id']}: no sources")

        for source in item["sources"]:
            url = source.get("url", "")
            if url and not (url.startswith("http://") or url.startswith("https://")):
                errors.append(f"{item['id']}: invalid source url {url}")

        if prev_sort and prev_sort < item["sortDate"]:
            errors.append(
                f"{item['id']}: out of descending sort order ({prev_sort} before {item['sortDate']})"
            )
        prev_sort = item["sortDate"]

        if item["datePrecision"] == "year" and item["dateLabel"] != item["eventDate"][:4]:
            warnings.append(f"{item['id']}: year precision but dateLabel is {item['dateLabel']}")

        story_lower = item["story"].lower()
        if item["status"] == "opened" and any(term in story_lower for term in PLANNED_TERMS):
            warnings.append(
                f"{item['id']}: opening story still reads like a plan, verify before publishing"
            )

        if item["status"] == "lastcall":
            closed_date = item.get("closedDate")
            closed_precision = item.get("closedDatePrecision")
            if not closed_date:
                errors.append(f"{item['id']}: lastcall record missing closedDate")
            if closed_precision and closed_precision != "day":
                warnings.append(
                    f"{item['id']}: lastcall record should ideally have day precision, found {closed_precision}"
                )

    print(f"Audited {len(items)} records from {DATA_PATH}")
    if warnings:
      print("\nWarnings:")
      for warning in warnings:
          print(f"- {warning}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("\nNo blocking data issues found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
