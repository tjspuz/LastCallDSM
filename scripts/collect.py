#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "watchlists.json"
VENUES_PATH = ROOT / "data" / "venues.json"
CACHE_DIR = ROOT / "data" / "cache"
REPORTS_DIR = ROOT / "data" / "reports"

USER_AGENT = "LastCallDSM/0.1 (+https://github.com/tjspuz/LastCallDSM)"

OPENING_TERMS = {
    "opened": 3,
    "opening": 2,
    "opening soon": 3,
    "soft opening": 4,
    "grand opening": 4,
    "reopen": 2,
    "reopened": 3,
    "first bite": 2,
    "new restaurant": 3,
}

CLOSURE_TERMS = {
    "closed": 3,
    "closing": 3,
    "closure": 3,
    "last day": 4,
    "shuttered": 4,
    "shut down": 4,
    "bankruptcy": 4,
    "bankrupt": 4,
    "eviction": 4,
    "auction": 3,
    "for lease": 2,
    "liquor license": 2,
    "permanently closed": 5,
}

MOVE_TERMS = {
    "moving": 2,
    "moved": 2,
    "relocating": 2,
    "relocation": 2,
    "relocated": 2,
}

NEGATIVE_TERMS = {
    "best of",
    "recipe",
    "review",
    "top stories",
    "favorite",
    "weekend plans",
    "valentine",
    "best thing",
}

AREA_HINTS = (
    "Downtown",
    "East Village",
    "West Des Moines",
    "Waukee",
    "Ankeny",
    "Ingersoll",
    "Beaverdale",
    "Court Avenue",
    "Highland Park",
    "Urbandale",
    "Johnston",
)

NAME_PATTERNS = (
    re.compile(
        r'(?P<name>[A-Z][A-Za-z0-9&\'\-.\/ ]{2,48})\s+(opens?|opened|closing|closes|closed|reopens?|shuttered|moving|moved|relocating)\b'
    ),
    re.compile(r"First bite:\s*(?P<name>[A-Z][A-Za-z0-9&'\-.\/ ]{2,48})"),
    re.compile(r"(?P<name>[A-Z][A-Za-z0-9&'\-.\/ ]{2,48})\s+opening\b"),
)


@dataclass
class Lead:
    fingerprint: str
    source_id: str
    source_label: str
    source_type: str
    title: str
    summary: str
    url: str
    published_at: str
    status_guess: str
    score: int
    venue_guess: str
    area_guess: str
    matched_terms: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,application/rss+xml,application/xml,text/xml,text/plain,*/*",
        },
    )
    with urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str) -> Any:
    return json.loads(fetch_text(url))


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    items: list[dict[str, str]] = []

    for node in root.findall(".//item"):
        items.append(
            {
                "title": clean_html(node.findtext("title", default="")),
                "link": clean_html(node.findtext("link", default="")),
                "summary": clean_html(node.findtext("description", default="")),
                "published_at": clean_html(node.findtext("pubDate", default="")),
            }
        )

    if items:
        return items

    atom_namespace = {"atom": "http://www.w3.org/2005/Atom"}
    for node in root.findall(".//atom:entry", atom_namespace):
        link = ""
        link_node = node.find("atom:link", atom_namespace)
        if link_node is not None:
            link = clean_html(link_node.attrib.get("href", ""))
        items.append(
            {
                "title": clean_html(node.findtext("atom:title", default="", namespaces=atom_namespace)),
                "link": link,
                "summary": clean_html(node.findtext("atom:summary", default="", namespaces=atom_namespace)),
                "published_at": clean_html(
                    node.findtext("atom:updated", default="", namespaces=atom_namespace)
                ),
            }
        )
    return items


def build_google_news_url(query: str) -> str:
    encoded = quote_plus(query)
    return (
        "https://news.google.com/rss/search?"
        f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
    )


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def guess_name(title: str) -> str:
    for pattern in NAME_PATTERNS:
        match = pattern.search(title)
        if match:
            return match.group("name").strip(" .:-")
    return title.split(":")[-1].strip()


def guess_area(text: str) -> str:
    for area in AREA_HINTS:
        if area.lower() in text.lower():
            return area
    return "Des Moines Metro"


def score_text(title: str, summary: str) -> tuple[str, int, list[str]]:
    combined = f"{title} {summary}".lower()
    matched_terms: list[str] = []
    score = 0

    if any(term in combined for term in NEGATIVE_TERMS):
        score -= 2

    status = "review"
    opening_score = 0
    closing_score = 0
    move_score = 0

    for term, weight in OPENING_TERMS.items():
        if term in combined:
            opening_score += weight
            matched_terms.append(term)

    for term, weight in CLOSURE_TERMS.items():
        if term in combined:
            closing_score += weight
            matched_terms.append(term)

    for term, weight in MOVE_TERMS.items():
        if term in combined:
            move_score += weight
            matched_terms.append(term)

    if "restaurant" in combined or "bar" in combined or "brewery" in combined or "cafe" in combined:
        score += 2

    score += max(opening_score, closing_score, move_score)

    if closing_score > opening_score and closing_score >= 3:
        status = "closed"
    elif opening_score > closing_score and opening_score >= 3:
        status = "opened"
    elif move_score >= 2:
        status = "moved"

    return status, score, sorted(set(matched_terms))


def lead_fingerprint(*parts: str) -> str:
    digest = hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()
    return digest[:14]


def collect_google_news(sources: Iterable[dict[str, str]]) -> list[Lead]:
    leads: list[Lead] = []
    for source in sources:
        xml_text = fetch_text(build_google_news_url(source["query"]))
        rss_items = parse_rss_items(xml_text)
        for item in rss_items:
            status_guess, score, matched_terms = score_text(item["title"], item["summary"])
            if score < 3:
                continue
            venue_guess = guess_name(item["title"])
            area_guess = guess_area(f'{item["title"]} {item["summary"]}')
            leads.append(
                Lead(
                    fingerprint=lead_fingerprint(
                        source["id"], item["title"], item["link"], status_guess
                    ),
                    source_id=source["id"],
                    source_label=source["label"],
                    source_type="google_news",
                    title=item["title"],
                    summary=item["summary"],
                    url=item["link"],
                    published_at=item["published_at"],
                    status_guess=status_guess,
                    score=score,
                    venue_guess=venue_guess,
                    area_guess=area_guess,
                    matched_terms=matched_terms,
                )
            )
    return leads


def collect_reddit(sources: Iterable[dict[str, str]]) -> list[Lead]:
    leads: list[Lead] = []
    for source in sources:
        params = urlencode(
            {
                "restrict_sr": "1",
                "sort": "new",
                "limit": "100",
                "q": source["query"],
            }
        )
        payload = fetch_json(f"https://www.reddit.com/r/desmoines/search.json?{params}")
        posts = payload.get("data", {}).get("children", [])
        for node in posts:
            data = node.get("data", {})
            title = clean_html(data.get("title", ""))
            summary = clean_html(data.get("selftext", ""))
            url = data.get("url_overridden_by_dest") or f"https://www.reddit.com{data.get('permalink', '')}"
            status_guess, score, matched_terms = score_text(title, summary)
            if score < 3:
                continue
            leads.append(
                Lead(
                    fingerprint=lead_fingerprint(source["id"], title, url, status_guess),
                    source_id=source["id"],
                    source_label=source["label"],
                    source_type="reddit",
                    title=title,
                    summary=summary,
                    url=url,
                    published_at=datetime.fromtimestamp(
                        data.get("created_utc", 0), tz=timezone.utc
                    ).isoformat(),
                    status_guess=status_guess,
                    score=score,
                    venue_guess=guess_name(title),
                    area_guess=guess_area(f"{title} {summary}"),
                    matched_terms=matched_terms,
                )
            )
    return leads


def dedupe_leads(leads: Iterable[Lead]) -> list[Lead]:
    best_by_key: dict[str, Lead] = {}
    for lead in leads:
        key = normalize_text(f"{lead.venue_guess} {lead.status_guess} {lead.area_guess}")
        incumbent = best_by_key.get(key)
        if incumbent is None or lead.score > incumbent.score:
            best_by_key[key] = lead
    return sorted(best_by_key.values(), key=lambda lead: (lead.published_at, lead.score), reverse=True)


def verify_places() -> list[dict[str, Any]]:
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return []

    venues = load_json(VENUES_PATH)["items"]
    results: list[dict[str, Any]] = []
    for venue in venues:
        query = f'{venue["name"]} {venue["neighborhood"]} Iowa'
        request_body = json.dumps({"textQuery": query}).encode("utf-8")
        request = Request(
            "https://places.googleapis.com/v1/places:searchText",
            data=request_body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.businessStatus",
            },
        )
        with urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))

        place = payload.get("places", [{}])[0]
        results.append(
            {
                "id": venue["id"],
                "name": venue["name"],
                "query": query,
                "businessStatus": place.get("businessStatus"),
                "formattedAddress": place.get("formattedAddress"),
            }
        )
    return results


def build_summary(leads: list[Lead]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for lead in leads:
        status_counts[lead.status_guess] = status_counts.get(lead.status_guess, 0) + 1

    return {
        "generatedAt": now_iso(),
        "leadCount": len(leads),
        "statusCounts": status_counts,
        "topLeads": [asdict(lead) for lead in leads[:15]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Des Moines restaurant leads.")
    parser.add_argument(
        "--verify-places",
        action="store_true",
        help="Also hit Google Places API (New) for business status checks on curated venues.",
    )
    args = parser.parse_args()

    ensure_dirs()
    config = load_json(CONFIG_PATH)

    raw_google_news = collect_google_news(config["googleNews"])
    raw_reddit = collect_reddit(config["redditSearches"])
    leads = dedupe_leads([*raw_google_news, *raw_reddit])

    save_json(CACHE_DIR / "google-news.json", [asdict(lead) for lead in raw_google_news])
    save_json(CACHE_DIR / "reddit.json", [asdict(lead) for lead in raw_reddit])
    save_json(REPORTS_DIR / "latest-candidates.json", [asdict(lead) for lead in leads])
    save_json(REPORTS_DIR / "latest-summary.json", build_summary(leads))

    if args.verify_places:
        save_json(REPORTS_DIR / "places-status.json", verify_places())

    print(
        json.dumps(
            {
                "generatedAt": now_iso(),
                "candidateCount": len(leads),
                "googleNewsCount": len(raw_google_news),
                "redditCount": len(raw_reddit),
                "placesVerified": bool(args.verify_places),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
