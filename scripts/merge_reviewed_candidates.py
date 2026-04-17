#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENUES_PATH = ROOT / "data" / "venues.json"
CANDIDATES_PATH = ROOT / "data" / "reports" / "latest-candidates.json"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def infer_type(name: str) -> tuple[str, str]:
    text = name.lower()
    if any(token in text for token in ("cafe", "bakery", "coffee")):
        return "cafe", "Cafe"
    if any(token in text for token in ("brew", "brewery", "taproom", "bar", "pub", "patio", "chophouse")):
        return "bar", "Bar"
    return "restaurant", "Restaurant"


def infer_cuisine(name: str) -> str:
    text = name.lower()
    if "pizza" in text:
        return "Pizza"
    if "burger" in text:
        return "Burgers"
    if "thai" in text:
        return "Thai"
    if "bbq" in text or "barbecue" in text:
        return "Barbecue"
    if "brew" in text or "taproom" in text:
        return "Brewery"
    if "cafe" in text or "bakery" in text or "coffee" in text:
        return "Cafe / Bakery"
    if "sushi" in text:
        return "Sushi"
    if "steak" in text or "chophouse" in text:
        return "Steakhouse"
    return "Category Pending"


def format_date_label(iso_date: str) -> str:
    parsed = datetime.strptime(iso_date, "%Y-%m-%d")
    return parsed.strftime("%b %Y")


def main() -> None:
    venues_payload = json.loads(VENUES_PATH.read_text(encoding="utf-8"))
    candidates = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))

    items = venues_payload["items"]
    existing_keys = {
        (normalize(item["name"]), item["status"], item["eventDate"]): item for item in items
    }
    existing_ids = {item["id"] for item in items}

    added = 0
    skipped = 0

    for candidate in candidates:
        status = candidate.get("status")
        if status not in {"opened", "closed"}:
            continue

        name = candidate.get("venue", "").strip()
        if not name:
            skipped += 1
            continue

        event_date = candidate.get("published_at", "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", event_date):
            skipped += 1
            continue

        dedupe_key = (normalize(name), status, event_date)
        if dedupe_key in existing_keys:
            skipped += 1
            continue

        venue_type, venue_type_label = infer_type(name)
        entry_id = f"{slugify(name)}-{status}-{event_date}"
        if entry_id in existing_ids:
            suffix = 2
            while f"{entry_id}-{suffix}" in existing_ids:
                suffix += 1
            entry_id = f"{entry_id}-{suffix}"

        area = candidate.get("area", "Des Moines Metro").strip() or "Des Moines Metro"
        source_label = candidate.get("source_label", "Reviewed candidate")
        story = (
            f"Imported from the reviewed lead queue. Source label: {source_label}. "
            f"Headline cleanup and deeper sourcing can be refined later."
        )

        items.append(
            {
                "id": entry_id,
                "name": name,
                "status": status,
                "eventDate": event_date,
                "sortDate": event_date,
                "dateLabel": format_date_label(event_date),
                "datePrecision": "day",
                "venueType": venue_type,
                "venueTypeLabel": venue_type_label,
                "cuisine": infer_cuisine(name),
                "neighborhood": area,
                "story": story,
                "verificationLevel": "verified",
                "sources": [
                    {
                        "label": source_label,
                        "url": ""
                    }
                ]
            }
        )
        existing_keys[dedupe_key] = items[-1]
        existing_ids.add(entry_id)
        added += 1

    items.sort(key=lambda item: (item["sortDate"], item["name"].lower()), reverse=True)
    venues_payload["updatedAt"] = datetime.utcnow().strftime("%Y-%m-%d")
    VENUES_PATH.write_text(json.dumps(venues_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps({"added": added, "skipped": skipped, "total": len(items)}, indent=2))


if __name__ == "__main__":
    main()
