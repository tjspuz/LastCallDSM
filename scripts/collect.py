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
from urllib.parse import quote_plus, urlencode, urlparse
from urllib.error import HTTPError
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
        r"(?i)looks like\s+(?P<name>[A-Z0-9][A-Za-z0-9&'’\-.\/ ]{2,60}?)(?:\s+(?:on|in|at)\s+[A-Z0-9][A-Za-z0-9&'’\-.\/ ]+)?\s+is\s+(?:closing|closed|moving|relocating)\b"
    ),
    re.compile(
        r"(?P<name>[A-Z0-9][A-Za-z0-9&'’\-.\/ ]{2,60}?)\s+(?:closing|closes|closed|opens?|opened|reopens?|reopened|moving|moved|relocating|files? for bankruptcy|announces closure)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r'(?P<name>[A-Z][A-Za-z0-9&\'\-.\/ ]{2,48})\s+(opens?|opened|closing|closes|closed|reopens?|shuttered|moving|moved|relocating)\b'
    ),
    re.compile(r"First bite:\s*(?P<name>[A-Z][A-Za-z0-9&'\-.\/ ]{2,48})"),
    re.compile(r"(?P<name>[A-Z][A-Za-z0-9&'\-.\/ ]{2,48})\s+opening\b"),
)

COMMENT_SPLITTER = re.compile(r"\n+|(?<!/),|;|(?<=[.!?])\s+")
COMMENT_LEADIN = re.compile(
    r"^(from when i was a kid|for nostalgia|my picks?|i miss|mine is|for me|used to be|definitely|probably|maybe|honestly)\s*:\s*",
    re.IGNORECASE,
)
VENUE_CLEANUP_PATTERNS = (
    re.compile(r"(?i)^looks like\s+"),
    re.compile(r"(?i)\s+(?:on|in|at)\s+[A-Z0-9][A-Za-z0-9&'’\-.\/ ]+$"),
    re.compile(
        r"(?i)\s+(?:is|are)\s+(?:closing|closed|moving|relocating|gone|done)\b.*$"
    ),
    re.compile(r"(?i)\s+(?:was|were|has|had)\b.*$"),
    re.compile(
        r"(?i)\s+(?:closing|closed|opens?|opened|reopens?|reopened|moving|moved|relocating|files? for bankruptcy|announces closure)\b.*$"
    ),
    re.compile(r"(?i)\s+(?:restaurant|bar|brewery|cafe|taproom)\s*$"),
)
COMMENT_NOISE = {
    "i miss that place",
    "same",
    "yes",
    "yes.",
    "same here",
    "me too",
    "this",
    "absolutely",
    "for sure",
}
COMMENT_LEAD_WORDS = {
    "i",
    "it",
    "its",
    "my",
    "me",
    "we",
    "they",
    "this",
    "that",
    "but",
    "same",
    "yes",
    "no",
    "the",
    "a",
    "an",
}
VENUE_BLOCKLIST = {
    "dahl's",
    "old country buffet",
    "ryan's",
}
LIKELY_VENUE_WORDS = {
    "bar",
    "bbq",
    "brewery",
    "burger",
    "burgers",
    "cafe",
    "café",
    "chili",
    "chophouse",
    "coffee",
    "diner",
    "fresh",
    "grill",
    "house",
    "java",
    "joint",
    "kitchen",
    "mews",
    "palace",
    "pizza",
    "pub",
    "restaurant",
    "sushi",
    "taco",
    "tacopocalypse",
    "tavern",
    "wine",
}

DISH_TOKENS = {
    "enchilada",
    "salsa",
    "beignets",
    "tenderloin",
    "ribs",
}


@dataclass
class Lead:
    fingerprint: str
    source_id: str
    source_label: str
    source_type: str
    source_query: str
    source_sort: str
    source_timeframe: str
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


def fetch_reddit_search_json(params: dict[str, str]) -> Any:
    attempts = [
        ("https://www.reddit.com/r/desmoines/search.json", {**params, "raw_json": "1"}),
        ("https://old.reddit.com/r/desmoines/search.json", {**params, "raw_json": "1"}),
    ]

    last_error: Exception | None = None
    for base_url, query_params in attempts:
        try:
            return fetch_json(f"{base_url}?{urlencode(query_params)}")
        except HTTPError as error:
            last_error = error
            if error.code != 403:
                raise

    if last_error is not None:
        raise last_error

    raise RuntimeError("Reddit search fetch failed with no response.")


def fetch_reddit_search_rss(params: dict[str, str]) -> list[dict[str, str]]:
    attempts = [
        f"https://www.reddit.com/r/desmoines/search.rss?{urlencode(params)}",
        f"https://old.reddit.com/r/desmoines/search.rss?{urlencode(params)}",
    ]

    last_error: Exception | None = None
    for url in attempts:
        try:
            return parse_rss_items(fetch_text(url))
        except HTTPError as error:
            last_error = error
            if error.code != 403:
                raise

    if last_error is not None:
        raise last_error

    raise RuntimeError("Reddit RSS fetch failed with no response.")


def normalize_reddit_thread_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path.endswith(".json"):
        path = f"{path}.json"
    base = f"{parsed.scheme or 'https'}://{parsed.netloc or 'www.reddit.com'}{path}"
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}raw_json=1&limit=500&sort=top"


def fetch_reddit_thread_json(url: str) -> Any:
    parsed = urlparse(url)
    permalink = parsed.path.rstrip("/")
    attempts = []
    for domain in ("www.reddit.com", "old.reddit.com"):
        attempts.append(normalize_reddit_thread_url(f"https://{domain}{permalink}"))

    last_error: Exception | None = None
    for attempt in attempts:
        try:
            return fetch_json(attempt)
        except HTTPError as error:
            last_error = error
            if error.code != 403:
                raise

    if last_error is not None:
        raise last_error

    raise RuntimeError("Reddit thread fetch failed with no response.")


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


def clean_venue_name(value: str) -> str:
    cleaned = value.strip(" .:-")
    cleaned = COMMENT_LEADIN.sub("", cleaned)
    for pattern in VENUE_CLEANUP_PATTERNS:
        cleaned = pattern.sub("", cleaned).strip(" .:-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" .:-")


def looks_like_venue_name(value: str) -> bool:
    cleaned = clean_venue_name(value)
    lowered = cleaned.lower()
    if not cleaned or len(cleaned) < 3:
        return False
    if lowered in COMMENT_NOISE or lowered in VENUE_BLOCKLIST:
        return False
    if lowered.startswith(("what ", "why ", "looks like ")) or lowered.endswith((" is", " are", " has")):
        return False
    raw_words = re.findall(r"[A-Za-z0-9'’/&.-]+", cleaned)
    words = re.findall(r"[A-Za-z0-9'’]+", cleaned)
    if len(words) > 7:
        return False
    if raw_words and raw_words[0].lower() in COMMENT_LEAD_WORDS:
        return False
    if raw_words and raw_words[0].lower() in DISH_TOKENS:
        return False
    capitalized = sum(word[:1].isupper() or word[:1].isdigit() for word in raw_words if word)
    has_venue_term = any(word.lower().strip(".") in LIKELY_VENUE_WORDS for word in raw_words)
    if len(words) == 1:
        token = words[0].lower()
        return len(token) >= 5 and (token[0].isalpha() or "'" in token)
    if capitalized < 2 and not has_venue_term:
        return False
    return True


def split_comment_mentions(text: str) -> list[str]:
    stripped = COMMENT_LEADIN.sub("", text.strip())
    stripped = re.sub(r"\s+", " ", stripped)
    if not stripped:
        return []

    segments: list[str] = []
    for chunk in COMMENT_SPLITTER.split(stripped):
        chunk = chunk.strip(" .:-")
        if not chunk:
            continue
        if " and " in chunk and chunk.count(" and ") <= 2:
            parts = [part.strip(" .:-") for part in re.split(r"\band\b", chunk, flags=re.IGNORECASE)]
            if all(looks_like_venue_name(part) for part in parts if part):
                segments.extend([part for part in parts if part])
                continue
        segments.append(chunk)
    return segments


def extract_comment_venues(text: str) -> list[str]:
    venues: list[str] = []
    for segment in split_comment_mentions(text):
        cleaned = clean_venue_name(segment)
        if not looks_like_venue_name(cleaned):
            continue
        normalized = normalize_text(cleaned)
        words = normalized.split()
        if len(words) == 1 and words[0] not in LIKELY_VENUE_WORDS and len(words[0]) < 5:
            continue
        venues.append(cleaned)
    deduped: list[str] = []
    seen: set[str] = set()
    for venue in venues:
        key = normalize_text(venue)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(venue)
    return deduped


def guess_name(title: str) -> str:
    for pattern in NAME_PATTERNS:
        match = pattern.search(title)
        if match:
            return clean_venue_name(match.group("name"))
    trailing = title.split(":")[-1].strip()
    cleaned = clean_venue_name(trailing)
    return cleaned or trailing


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
                    source_query=source["query"],
                    source_sort="relevance",
                    source_timeframe="all",
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


def collect_reddit(sources: Iterable[dict[str, str]]) -> tuple[list[Lead], list[str]]:
    leads: list[Lead] = []
    warnings: list[str] = []
    for source in sources:
        sort = source.get("sort", "new")
        timeframe = source.get("timeframe", "year")
        params = {
            "restrict_sr": "1",
            "sort": sort,
            "t": timeframe,
            "limit": str(source.get("limit", 100)),
            "q": source["query"],
        }
        try:
            payload = fetch_reddit_search_json(params)
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
                        source_query=source["query"],
                        source_sort=sort,
                        source_timeframe=timeframe,
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
        except HTTPError as error:
            if error.code != 403:
                raise
            try:
                rss_items = fetch_reddit_search_rss(params)
                for item in rss_items:
                    title = item["title"]
                    summary = item["summary"]
                    url = item["link"]
                    status_guess, score, matched_terms = score_text(title, summary)
                    if score < 3:
                        continue
                    leads.append(
                        Lead(
                            fingerprint=lead_fingerprint(source["id"], title, url, status_guess),
                            source_id=source["id"],
                            source_label=source["label"],
                            source_type="reddit",
                            source_query=source["query"],
                            source_sort=sort,
                            source_timeframe=timeframe,
                            title=title,
                            summary=summary,
                            url=url,
                            published_at=item["published_at"],
                            status_guess=status_guess,
                            score=score,
                            venue_guess=guess_name(title),
                            area_guess=guess_area(f"{title} {summary}"),
                            matched_terms=matched_terms,
                        )
                    )
            except HTTPError:
                warnings.append(
                    f"Reddit blocked source {source['id']} ({source['query']}); no JSON or RSS results returned."
                )
    return leads, warnings


def walk_reddit_comments(children: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for child in children:
        if child.get("kind") != "t1":
            continue
        data = child.get("data", {})
        yield data
        replies = data.get("replies")
        if isinstance(replies, dict):
            yield from walk_reddit_comments(replies.get("data", {}).get("children", []))


def collect_reddit_comment_threads(sources: Iterable[dict[str, Any]]) -> tuple[list[Lead], list[str]]:
    leads: list[Lead] = []
    warnings: list[str] = []
    for source in sources:
        try:
            payload = fetch_reddit_thread_json(source["url"])
        except HTTPError as error:
            warnings.append(
                f"Reddit blocked thread source {source['id']} ({source['url']}); comments were not mined."
            )
            continue

        if not isinstance(payload, list) or len(payload) < 2:
            warnings.append(f"Unexpected Reddit thread payload for {source['id']}.")
            continue

        post_data = (
            payload[0].get("data", {}).get("children", [{}])[0].get("data", {})
            if isinstance(payload[0], dict)
            else {}
        )
        thread_title = clean_html(post_data.get("title", ""))
        default_status = source.get("defaultStatus", "closed")
        default_area = source.get("defaultArea", "Des Moines Metro")

        comment_listing = payload[1].get("data", {}).get("children", []) if isinstance(payload[1], dict) else []
        for comment in walk_reddit_comments(comment_listing):
            body = clean_html(comment.get("body", ""))
            if not body or normalize_text(body) in COMMENT_NOISE:
                continue

            venues = extract_comment_venues(body)
            if not venues:
                continue

            published_at = datetime.fromtimestamp(
                comment.get("created_utc", 0), tz=timezone.utc
            ).isoformat()
            permalink = comment.get("permalink", "")
            url = (
                f"https://www.reddit.com{permalink}"
                if permalink
                else source["url"]
            )

            for venue in venues:
                leads.append(
                    Lead(
                        fingerprint=lead_fingerprint(source["id"], venue, url, published_at),
                        source_id=source["id"],
                        source_label=source["label"],
                        source_type="reddit_comment",
                        source_query=source["url"],
                        source_sort="top",
                        source_timeframe="all",
                        title=venue,
                        summary=body,
                        url=url,
                        published_at=published_at,
                        status_guess=default_status,
                        score=4,
                        venue_guess=venue,
                        area_guess=default_area,
                        matched_terms=["comment-mention"],
                    )
                )
    return leads, warnings


def dedupe_leads(leads: Iterable[Lead]) -> list[Lead]:
    best_by_key: dict[str, Lead] = {}
    for lead in leads:
        key = normalize_text(f"{lead.venue_guess} {lead.status_guess} {lead.area_guess}")
        incumbent = best_by_key.get(key)
        if incumbent is None or (lead.score, lead.published_at) > (
            incumbent.score,
            incumbent.published_at,
        ):
            best_by_key[key] = lead

    status_priority = {"closed": 0, "review": 1, "opened": 2, "moved": 3}
    return sorted(
        best_by_key.values(),
        key=lambda lead: (
            status_priority.get(lead.status_guess, 9),
            lead.published_at,
            lead.score,
        ),
        reverse=False,
    )


def sort_leads_for_report(leads: Iterable[Lead]) -> list[Lead]:
    status_priority = {"closed": 0, "review": 1, "opened": 2, "moved": 3}
    return sorted(
        leads,
        key=lambda lead: (
            status_priority.get(lead.status_guess, 9),
            -lead.score,
            lead.published_at,
        ),
    )


def build_closure_report(leads: Iterable[Lead]) -> list[Lead]:
    closure_like = [lead for lead in leads if lead.status_guess in {"closed", "review"}]
    return sort_leads_for_report(closure_like)


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


def build_summary(leads: list[Lead], warnings: list[str] | None = None) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    source_type_counts: dict[str, int] = {}
    for lead in leads:
        status_counts[lead.status_guess] = status_counts.get(lead.status_guess, 0) + 1
        source_type_counts[lead.source_type] = source_type_counts.get(lead.source_type, 0) + 1

    return {
        "generatedAt": now_iso(),
        "leadCount": len(leads),
        "statusCounts": status_counts,
        "sourceTypeCounts": source_type_counts,
        "warnings": warnings or [],
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
    raw_reddit, warnings = collect_reddit(config["redditSearches"])
    raw_reddit_comments, comment_warnings = collect_reddit_comment_threads(
        config.get("redditCommentThreads", [])
    )
    warnings.extend(comment_warnings)
    leads = dedupe_leads([*raw_google_news, *raw_reddit, *raw_reddit_comments])
    closure_report = build_closure_report(leads)
    reddit_closure_report = sort_leads_for_report(
        [
            lead
            for lead in [*raw_reddit, *raw_reddit_comments]
            if lead.status_guess in {"closed", "review"}
        ]
    )

    save_json(CACHE_DIR / "google-news.json", [asdict(lead) for lead in raw_google_news])
    save_json(CACHE_DIR / "reddit.json", [asdict(lead) for lead in raw_reddit])
    save_json(CACHE_DIR / "reddit-comments.json", [asdict(lead) for lead in raw_reddit_comments])
    save_json(REPORTS_DIR / "latest-candidates.json", [asdict(lead) for lead in sort_leads_for_report(leads)])
    save_json(
        REPORTS_DIR / "latest-closure-candidates.json",
        [asdict(lead) for lead in closure_report],
    )
    save_json(
        REPORTS_DIR / "latest-reddit-closures.json",
        [asdict(lead) for lead in reddit_closure_report],
    )
    save_json(REPORTS_DIR / "latest-summary.json", build_summary(leads, warnings))

    if args.verify_places:
        save_json(REPORTS_DIR / "places-status.json", verify_places())

    print(
        json.dumps(
            {
                "generatedAt": now_iso(),
                "candidateCount": len(leads),
                "closureCandidateCount": len(closure_report),
                "googleNewsCount": len(raw_google_news),
                "redditCount": len(raw_reddit),
                "redditCommentCount": len(raw_reddit_comments),
                "warnings": warnings,
                "placesVerified": bool(args.verify_places),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
