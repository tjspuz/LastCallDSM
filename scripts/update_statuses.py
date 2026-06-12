#!/usr/bin/env python3
"""Status lifecycle engine for the published timeline.

Venues are living records: a `lastcall` becomes `closed` once its final day
passes, a `closed` venue can reopen, and an `opened` venue can quietly shut
down. This script applies the transitions that are safe to automate and
reports the ones that need a second signal before publishing.

Rules:
  1. lastcall -> closed: applied automatically once closedDate is in the past.
  2. Google Places drift (from data/reports/places-status.json):
     - status closed/lastcall but Places says OPERATIONAL  -> possible reopening
     - status opened but Places says CLOSED_PERMANENTLY    -> possible closure
     A drift observation is only acted on after it has been seen on
     STREAK_THRESHOLD consecutive runs (tracked in places-status-history.json),
     which filters out one-off Places mismatches (wrong location match, etc.).
     Even then, curated records are never flipped automatically; they are
     written to data/reports/status-changes.json for review. Catalog records
     (id prefix "osm-", verificationLevel "review") ARE flipped automatically
     because they were machine-generated to begin with.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENUES_PATH = ROOT / "data" / "venues.json"
PLACES_REPORT_PATH = ROOT / "data" / "reports" / "places-status.json"
PLACES_HISTORY_PATH = ROOT / "data" / "reports" / "places-status-history.json"
CHANGES_REPORT_PATH = ROOT / "data" / "reports" / "status-changes.json"

STREAK_THRESHOLD = 2


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def format_label(value: str, precision: str) -> str:
    parsed = datetime.strptime(value[:10], "%Y-%m-%d")
    if precision == "day":
        return parsed.strftime("%b %-d, %Y")
    if precision == "month":
        return parsed.strftime("%b %Y")
    return parsed.strftime("%Y")


def promote_expired_lastcalls(items: list[dict], today: date, changes: list[dict]) -> None:
    for item in items:
        if item.get("status") != "lastcall":
            continue
        closed_date = item.get("closedDate")
        if not closed_date:
            continue
        if datetime.strptime(closed_date[:10], "%Y-%m-%d").date() >= today:
            continue
        item["status"] = "closed"
        item["eventDate"] = closed_date
        item["sortDate"] = closed_date
        precision = item.get("closedDatePrecision", item.get("datePrecision", "day"))
        item["datePrecision"] = precision
        item["dateLabel"] = format_label(closed_date, precision)
        changes.append(
            {
                "id": item["id"],
                "name": item["name"],
                "transition": "lastcall->closed",
                "reason": f"closedDate {closed_date} has passed",
                "applied": True,
            }
        )


def is_catalog_record(item: dict) -> bool:
    return item.get("id", "").startswith("osm-") and item.get("verificationLevel") == "review"


def detect_places_drift(items: list[dict], changes: list[dict], apply_catalog: bool, today: date) -> None:
    places_rows = load_json(PLACES_REPORT_PATH, default=[])
    if not places_rows:
        return

    history = load_json(PLACES_HISTORY_PATH, default={})
    by_id = {item["id"]: item for item in items}

    for row in places_rows:
        item = by_id.get(row.get("id"))
        business_status = row.get("businessStatus")
        if not item or not business_status:
            continue
        # Places text search can match a same-name location in another state
        # (e.g. Louie's Wine Dive in Overland Park, KS); only trust Iowa hits.
        address = row.get("formattedAddress") or ""
        if address and ", IA" not in address:
            continue

        drift = None
        if item["status"] in {"closed", "lastcall"} and business_status == "OPERATIONAL":
            drift = "possible-reopening"
        elif item["status"] == "opened" and business_status == "CLOSED_PERMANENTLY":
            drift = "possible-closure"

        entry = history.get(item["id"], {"drift": None, "streak": 0})
        if drift is None:
            history[item["id"]] = {"drift": None, "streak": 0, "lastSeen": now_iso()}
            continue

        streak = entry["streak"] + 1 if entry.get("drift") == drift else 1
        history[item["id"]] = {
            "drift": drift,
            "streak": streak,
            "businessStatus": business_status,
            "lastSeen": now_iso(),
        }
        if streak < STREAK_THRESHOLD:
            continue

        applied = False
        if drift == "possible-closure" and apply_catalog and is_catalog_record(item):
            item["status"] = "closed"
            item["closedDate"] = today.isoformat()
            item["closedDatePrecision"] = "month"
            item["eventDate"] = today.isoformat()
            item["sortDate"] = today.isoformat()
            item["datePrecision"] = "month"
            item["dateLabel"] = format_label(today.isoformat(), "month")
            item["story"] = (
                f"{item['name']} appears to have closed; Google Places now reports it permanently closed."
            )
            item["publicDescription"] = item["story"]
            applied = True

        changes.append(
            {
                "id": item["id"],
                "name": item["name"],
                "transition": drift,
                "reason": f"Google Places businessStatus={business_status} for {streak} consecutive runs",
                "applied": applied,
            }
        )

    save_json(PLACES_HISTORY_PATH, history)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply venue status lifecycle transitions.")
    parser.add_argument(
        "--no-apply-catalog",
        action="store_true",
        help="Report Places drift for catalog records instead of auto-closing them.",
    )
    args = parser.parse_args()

    payload = load_json(VENUES_PATH)
    items = payload["items"]
    today = date.today()
    changes: list[dict] = []

    promote_expired_lastcalls(items, today, changes)
    detect_places_drift(items, changes, apply_catalog=not args.no_apply_catalog, today=today)

    items.sort(key=lambda item: item["sortDate"], reverse=True)
    payload["updatedAt"] = now_iso()
    save_json(VENUES_PATH, payload)
    save_json(
        CHANGES_REPORT_PATH,
        {"generatedAt": now_iso(), "changes": changes},
    )

    applied = [c for c in changes if c["applied"]]
    flagged = [c for c in changes if not c["applied"]]
    print(f"Applied {len(applied)} transition(s), flagged {len(flagged)} for review.")
    for change in changes:
        marker = "applied" if change["applied"] else "review"
        print(f"- [{marker}] {change['name']}: {change['transition']} ({change['reason']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
