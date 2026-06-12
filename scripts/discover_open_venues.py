#!/usr/bin/env python3
"""Discover every open restaurant, bar, and cafe in the Des Moines metro.

Uses the OpenStreetMap Overpass API (free, keyless) to enumerate food and
drink venues inside the metro bounding box, then merges them into
data/venues.json as `opened` catalog records so the public site lists all
operating facilities, not just newsworthy ones.

Rules of the merge:
  - Curated records (anything without an "osm-" id) always win. A catalog
    entry whose name matches an existing record is skipped.
  - Catalog records are stable: the first run stamps `firstSeen`, later runs
    refresh tags (cuisine, website, address) without churning ids or dates.
  - National chains (OSM `brand` tag) are excluded by default so the list
    stays focused on local venues; pass --include-chains to keep them.
  - Venues that disappear from OSM are NOT silently deleted. They are listed
    in data/reports/catalog-changes.json because a disappearance is often a
    closure worth investigating, which is the whole point of this project.

The raw normalized catalog is also written to data/cache/osm-catalog.json so
other scripts (enrichment, verification) can use it without re-querying.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
VENUES_PATH = ROOT / "data" / "venues.json"
CATALOG_CACHE_PATH = ROOT / "data" / "cache" / "osm-catalog.json"
CHANGES_REPORT_PATH = ROOT / "data" / "reports" / "catalog-changes.json"

USER_AGENT = "LastCallDSM/0.2 (+https://github.com/tjspuz/LastCallDSM)"

# Covers Norwalk/Cumming up through Ankeny/Polk City, Waukee east to Altoona.
METRO_BBOX = "41.43,-93.98,41.80,-93.38"

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

OVERPASS_QUERY = f"""
[out:json][timeout:90];
(
  node["amenity"~"^(restaurant|bar|cafe|pub|biergarten|fast_food)$"]["name"]({METRO_BBOX});
  way["amenity"~"^(restaurant|bar|cafe|pub|biergarten|fast_food)$"]["name"]({METRO_BBOX});
  node["craft"="brewery"]["name"]({METRO_BBOX});
  way["craft"="brewery"]["name"]({METRO_BBOX});
);
out center tags;
"""

VENUE_TYPE_MAP = {
    "restaurant": ("restaurant", "Restaurant"),
    "fast_food": ("restaurant", "Restaurant"),
    "bar": ("bar", "Bar"),
    "pub": ("bar", "Bar"),
    "biergarten": ("bar", "Bar"),
    "cafe": ("cafe", "Cafe"),
    "brewery": ("bar", "Bar"),
}

CITY_FIXES = {
    "west des moins": "West Des Moines",
    "des moines": "Des Moines",
    "wdm": "West Des Moines",
}

CUISINE_LABELS = {
    "american": "American",
    "bbq": "Barbecue",
    "barbecue": "Barbecue",
    "burger": "Burgers",
    "chinese": "Chinese",
    "coffee_shop": "Coffee Shop",
    "ice_cream": "Ice Cream",
    "indian": "Indian",
    "italian": "Italian",
    "japanese": "Japanese",
    "korean": "Korean",
    "mexican": "Mexican",
    "pizza": "Pizza",
    "sandwich": "Sandwiches",
    "seafood": "Seafood",
    "steak_house": "Steakhouse",
    "sushi": "Sushi",
    "thai": "Thai",
    "vietnamese": "Vietnamese",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def normalize_name(value: str) -> str:
    # Curated records qualify multi-location names with a parenthetical
    # ("Bar Louie (Jordan Creek)") — match on the base name.
    value = re.sub(r"\([^)]*\)", " ", value).lower()
    value = re.sub(r"['’]", "", value)
    value = re.sub(r"\b(the|a|an)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def fetch_overpass() -> list[dict]:
    body = urlencode({"data": OVERPASS_QUERY}).encode("utf-8")
    last_error: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            request = Request(
                endpoint,
                data=body,
                headers={"User-Agent": USER_AGENT},
            )
            with urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get("elements", [])
        except Exception as error:  # noqa: BLE001 - try the mirror before failing
            last_error = error
            time.sleep(5)
    raise RuntimeError(f"All Overpass endpoints failed: {last_error}")


def cuisine_label(raw: str) -> str:
    first = raw.split(";")[0].strip()
    if first in CUISINE_LABELS:
        return CUISINE_LABELS[first]
    return first.replace("_", " ").title()


def clean_city(tags: dict) -> str:
    raw = (tags.get("addr:city") or "").strip()
    if not raw:
        return "Des Moines Metro"
    return CITY_FIXES.get(raw.lower(), raw)


def build_address(tags: dict) -> str:
    street = " ".join(
        part for part in (tags.get("addr:housenumber"), tags.get("addr:street")) if part
    )
    return ", ".join(part for part in (street, clean_city(tags), "IA", tags.get("addr:postcode")) if part)


def template_story(name: str, kind_label: str, cuisine: str | None, area: str) -> str:
    what = f"{cuisine.lower()} {kind_label.lower()}" if cuisine and cuisine.lower() not in kind_label.lower() else kind_label.lower()
    article = "an" if what[:1] in "aeiou" else "a"
    place = area if area != "Des Moines Metro" else "the Des Moines metro"
    return f"{name} is {article} {what} operating in {place}."


def normalize_element(element: dict) -> dict | None:
    tags = element.get("tags", {})
    name = (tags.get("name") or "").strip()
    if not name:
        return None

    kind = tags.get("amenity") or ("brewery" if tags.get("craft") == "brewery" else None)
    if kind not in VENUE_TYPE_MAP:
        return None
    venue_type, venue_type_label = VENUE_TYPE_MAP[kind]

    cuisine = cuisine_label(tags["cuisine"]) if tags.get("cuisine") else None
    area = clean_city(tags)
    center = element.get("center") or {}
    lat = element.get("lat", center.get("lat"))
    lon = element.get("lon", center.get("lon"))

    start_date = (tags.get("start_date") or "").strip()
    opened_date = None
    opened_precision = None
    if re.fullmatch(r"\d{4}", start_date):
        opened_date, opened_precision = f"{start_date}-01-01", "year"
    elif re.fullmatch(r"\d{4}-\d{2}", start_date):
        opened_date, opened_precision = f"{start_date}-01", "month"
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date):
        opened_date, opened_precision = start_date, "day"

    return {
        "osmId": f"{element['type']}/{element['id']}",
        "name": name,
        "venueType": venue_type,
        "venueTypeLabel": venue_type_label,
        "cuisine": cuisine,
        "neighborhood": area,
        "address": build_address(tags),
        "website": tags.get("website") or tags.get("contact:website"),
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "openingHours": tags.get("opening_hours"),
        "brand": tags.get("brand"),
        "lat": lat,
        "lon": lon,
        "openedDate": opened_date,
        "openedDatePrecision": opened_precision,
    }


# Catalog entries with no known opening date sort beneath every dated event,
# so the timeline reads news-first with the open-venue directory after it.
DIRECTORY_SORT_DATE = "1900-01-01"


def catalog_record(entry: dict, first_seen: str) -> dict:
    record = {
        "id": f"osm-{entry['osmId'].replace('/', '-')}",
        "name": entry["name"],
        "status": "opened",
        "eventDate": entry["openedDate"] or DIRECTORY_SORT_DATE,
        "sortDate": entry["openedDate"] or DIRECTORY_SORT_DATE,
        "dateLabel": "Open",
        "datePrecision": "day",
        "venueType": entry["venueType"],
        "venueTypeLabel": entry["venueTypeLabel"],
        "cuisine": entry["cuisine"] or "Category Pending",
        "neighborhood": entry["neighborhood"],
        "story": template_story(
            entry["name"], entry["venueTypeLabel"], entry["cuisine"], entry["neighborhood"]
        ),
        "verificationLevel": "review",
        "sources": [
            {
                "label": "OpenStreetMap",
                "url": f"https://www.openstreetmap.org/{entry['osmId']}",
            }
        ],
        "publicDescription": template_story(
            entry["name"], entry["venueTypeLabel"], entry["cuisine"], entry["neighborhood"]
        ),
        "firstSeen": first_seen,
    }
    if entry["openedDate"]:
        record["openedDate"] = entry["openedDate"]
        record["openedDatePrecision"] = entry["openedDatePrecision"]
    if entry["address"]:
        record["address"] = entry["address"]
    if entry["website"]:
        record["website"] = entry["website"]
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover open Des Moines metro venues from OSM.")
    parser.add_argument(
        "--include-chains",
        action="store_true",
        help="Keep venues that carry an OSM brand tag (national chains).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing venues.json.",
    )
    args = parser.parse_args()

    elements = fetch_overpass()
    entries = [entry for entry in (normalize_element(el) for el in elements) if entry]
    if not args.include_chains:
        entries = [entry for entry in entries if not entry["brand"]]

    # Dedupe same-name entries that sit within ~400m of each other (OSM often
    # has both a building outline and a point for one venue). Multi-location
    # locals at genuinely different addresses are kept.
    by_name: dict[str, list[dict]] = {}
    deduped_entries: list[dict] = []
    for entry in entries:
        kept = by_name.setdefault(normalize_name(entry["name"]), [])
        if any(
            entry["lat"] is not None
            and other["lat"] is not None
            and abs(entry["lat"] - other["lat"]) < 0.004
            and abs(entry["lon"] - other["lon"]) < 0.005
            for other in kept
        ):
            continue
        kept.append(entry)
        deduped_entries.append(entry)
    entries = deduped_entries

    save_json(
        CATALOG_CACHE_PATH,
        {"generatedAt": now_iso(), "bbox": METRO_BBOX, "count": len(entries), "entries": entries},
    )

    payload = load_json(VENUES_PATH)
    items = payload["items"]
    curated_names = {
        normalize_name(item["name"]) for item in items if not item["id"].startswith("osm-")
    }
    existing_catalog = {item["id"]: item for item in items if item["id"].startswith("osm-")}

    today = date.today().isoformat()
    added, refreshed, seen_ids = [], [], set()

    for entry in entries:
        if normalize_name(entry["name"]) in curated_names:
            continue
        record_id = f"osm-{entry['osmId'].replace('/', '-')}"
        seen_ids.add(record_id)
        existing = existing_catalog.get(record_id)
        if existing:
            stable = catalog_record(entry, existing.get("firstSeen", today))
            # Preserve fields the lifecycle/enrichment scripts may have set.
            if existing.get("status") != "opened":
                continue
            if existing.get("verificationLevel") == "verified":
                stable["verificationLevel"] = "verified"
            if existing.get("descriptionSource") == "enriched":
                stable["story"] = existing["story"]
                stable["publicDescription"] = existing["publicDescription"]
                stable["descriptionSource"] = "enriched"
            if stable != existing:
                existing.clear()
                existing.update(stable)
                refreshed.append(record_id)
        else:
            record = catalog_record(entry, today)
            items.append(record)
            added.append(record["name"])

    missing = [
        {"id": item["id"], "name": item["name"], "neighborhood": item["neighborhood"]}
        for item_id, item in existing_catalog.items()
        if item_id not in seen_ids and item.get("status") == "opened"
    ]

    # Descending by date, with same-day (directory) records alphabetical.
    items.sort(key=lambda item: item["name"].lower())
    items.sort(key=lambda item: item["sortDate"], reverse=True)
    payload["updatedAt"] = now_iso()

    if not args.dry_run:
        save_json(VENUES_PATH, payload)
    save_json(
        CHANGES_REPORT_PATH,
        {
            "generatedAt": now_iso(),
            "catalogSize": len(entries),
            "added": added,
            "refreshed": len(refreshed),
            "disappearedFromOSM": missing,
        },
    )

    print(
        json.dumps(
            {
                "catalogSize": len(entries),
                "added": len(added),
                "refreshed": len(refreshed),
                "disappearedFromOSM": len(missing),
                "dryRun": args.dry_run,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
