#!/usr/bin/env python3
"""Enrich venue descriptions with real-world context.

Catalog records arrive with templated one-liners ("X is a restaurant operating
in Y."). This script upgrades them in three layers:

  1. Venue website metadata — fetch each venue's site and pull the
     og:description / meta description, which is usually the venue's own
     one-sentence pitch.
  2. Deterministic composition — clean the snippet, blend in cuisine and
     neighborhood, clamp to the UI's 175-char clip.
  3. Optional Claude polish — when ANTHROPIC_API_KEY is set (and the
     `anthropic` package is installed), batches of venues are rewritten into
     consistent, editorial one-liners. Without a key, layer 2 ships as-is, so
     the pipeline never depends on the API.

Results are cached in data/cache/enrichment.json keyed by record id, so reruns
only work on new or still-templated records. The 6-hour collect workflow calls
this with --limit so the catalog enriches itself gradually.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
VENUES_PATH = ROOT / "data" / "venues.json"
CATALOG_CACHE_PATH = ROOT / "data" / "cache" / "osm-catalog.json"
ENRICHMENT_CACHE_PATH = ROOT / "data" / "cache" / "enrichment.json"

USER_AGENT = "LastCallDSM/0.2 (+https://github.com/tjspuz/LastCallDSM)"
MAX_DESCRIPTION_LENGTH = 170  # the UI clips tile descriptions at 175 chars
TEMPLATE_PATTERN = re.compile(r" is an? .* operating in ")

META_DESCRIPTION_PATTERNS = (
    re.compile(
        r'<meta[^>]+property=(["\'])og:description\1[^>]+content=(["\'])(?P<text>[^<>]{20,500}?)\2',
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r'<meta[^>]+content=(["\'])(?P<text>[^<>]{20,500}?)\1[^>]+property=(["\'])og:description\3',
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r'<meta[^>]+name=(["\'])description\1[^>]+content=(["\'])(?P<text>[^<>]{20,500}?)\2',
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r'<meta[^>]+content=(["\'])(?P<text>[^<>]{20,500}?)\1[^>]+name=(["\'])description\3',
        re.IGNORECASE | re.DOTALL,
    ),
)

# Social profiles aren't venue websites — their meta descriptions are
# platform boilerplate (follower counts, login prompts).
SOCIAL_HOSTS = ("instagram.com", "facebook.com", "twitter.com", "x.com", "tiktok.com")

BOILERPLATE_SNIPPETS = (
    "order online",
    "official website",
    "just a moment",
    "enable javascript",
    "javascript is required",
    "this site uses cookies",
    "powered by",
    "coming soon",
    "under construction",
    "404",
    "followers",
    "log in",
    "sign up",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def clamp(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= MAX_DESCRIPTION_LENGTH:
        return text
    clipped = text[: MAX_DESCRIPTION_LENGTH - 3]
    return f"{clipped[: clipped.rfind(' ')]}..."


def fetch_site_description(url: str) -> str | None:
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    if any(host in url.lower() for host in SOCIAL_HOSTS):
        return None
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with urlopen(request, timeout=12) as response:
            html = response.read(400_000).decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return None

    for pattern in META_DESCRIPTION_PATTERNS:
        match = pattern.search(html)
        if not match:
            continue
        text = unescape(match.group("text")).strip()
        lowered = text.lower()
        if len(text) < 25 or any(snippet in lowered for snippet in BOILERPLATE_SNIPPETS):
            continue
        if '="' in text or "='" in text or "/>" in text:
            continue
        return text
    return None


def needs_enrichment(item: dict) -> bool:
    if item.get("descriptionSource") == "enriched":
        return False
    description = item.get("publicDescription") or item.get("story") or ""
    return not description or bool(TEMPLATE_PATTERN.search(description))


def compose_description(item: dict, snippet: str | None) -> str | None:
    if not snippet:
        return None
    text = snippet
    if item["name"].lower() not in text.lower():
        text = f"{item['name']}: {text}"
    return clamp(text)


def polish_with_claude(records: list[dict]) -> dict[str, str]:
    """Rewrite gathered snippets into consistent one-liners. Returns {} when
    the API is unavailable so the deterministic layer ships instead."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {}
    try:
        from anthropic import Anthropic
    except ImportError:
        print("anthropic package not installed; skipping LLM polish.")
        return {}

    client = Anthropic()
    polished: dict[str, str] = {}
    batch_size = 20

    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        venue_lines = [
            {
                "id": record["id"],
                "name": record["name"],
                "type": record.get("cuisine") or record.get("venueTypeLabel"),
                "area": record.get("neighborhood"),
                "snippet": record.get("snippet") or "",
            }
            for record in batch
        ]
        schema = {
            "type": "object",
            "properties": {
                "descriptions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["id", "description"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["descriptions"],
            "additionalProperties": False,
        }
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=4000,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            system=(
                "You write one-line descriptions for a Des Moines restaurant/bar tracker. "
                "For each venue, write one factual sentence (max 160 characters) describing "
                "what it is and what it's known for, in a warm local-paper tone. Use only "
                "the provided snippet and metadata; never invent specifics like dates, "
                "awards, or menu items not present in the input. If the snippet is empty, "
                "describe it plainly from its type and area."
            ),
            messages=[{"role": "user", "content": json.dumps({"venues": venue_lines})}],
        )
        if response.stop_reason == "refusal" or not response.content:
            continue
        payload = json.loads(response.content[0].text)
        for entry in payload.get("descriptions", []):
            polished[entry["id"]] = clamp(entry["description"])
        time.sleep(1)

    return polished


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich venue descriptions.")
    parser.add_argument("--limit", type=int, default=40, help="Max venues to process this run.")
    parser.add_argument("--no-llm", action="store_true", help="Skip the Claude polish layer.")
    args = parser.parse_args()

    payload = load_json(VENUES_PATH)
    items = payload["items"]
    cache = load_json(ENRICHMENT_CACHE_PATH, default={})
    catalog = load_json(CATALOG_CACHE_PATH, default={}) or {}
    websites = {
        f"osm-{entry['osmId'].replace('/', '-')}": entry.get("website")
        for entry in catalog.get("entries", [])
    }

    pending = [item for item in items if needs_enrichment(item) and item["id"] not in cache]
    batch = pending[: args.limit]

    gathered: list[dict] = []
    for item in batch:
        website = item.get("website") or websites.get(item["id"])
        snippet = fetch_site_description(website) if website else None
        gathered.append({**item, "snippet": snippet})
        time.sleep(0.5)

    polished = {} if args.no_llm else polish_with_claude(gathered)

    updated = 0
    for record in gathered:
        description = polished.get(record["id"]) or compose_description(record, record["snippet"])
        cache[record["id"]] = {
            "description": description,
            "snippet": record["snippet"],
            "source": "claude" if record["id"] in polished else ("website" if description else "none"),
            "fetchedAt": now_iso(),
        }
        if not description:
            continue
        for item in items:
            if item["id"] == record["id"]:
                item["story"] = description
                item["publicDescription"] = description
                item["descriptionSource"] = "enriched"
                updated += 1
                break

    save_json(ENRICHMENT_CACHE_PATH, cache)
    if updated:
        payload["updatedAt"] = now_iso()
        save_json(VENUES_PATH, payload)

    print(
        json.dumps(
            {
                "pending": len(pending),
                "processed": len(batch),
                "updated": updated,
                "llmPolished": len(polished),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
