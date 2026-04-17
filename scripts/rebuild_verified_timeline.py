#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
VENUES_PATH = ROOT / "data" / "venues.json"
CANDIDATES_PATH = ROOT / "data" / "reports" / "latest-candidates.json"
VERIFIED_REPORT_PATH = ROOT / "data" / "reports" / "latest-verified-candidates.json"
REJECTED_REPORT_PATH = ROOT / "data" / "reports" / "rejected-reviewed-candidates.json"
SUMMARY_PATH = ROOT / "data" / "reports" / "latest-verification-summary.json"

USER_AGENT = "LastCallDSM/0.2 (+https://github.com/tjspuz/LastCallDSM)"
AUTOMATED_STORY_PREFIXES = (
    "Imported from the reviewed lead queue.",
    "Automatically verified from the lead pipeline.",
)

LOCAL_AREAS = {
    "Des Moines Metro",
    "Des Moines",
    "Downtown",
    "West Des Moines",
    "Waukee",
    "Clive",
    "Urbandale",
    "Johnston",
    "Ankeny",
    "Altoona",
    "Pleasant Hill",
    "Windsor Heights",
    "Beaverdale",
    "East Village",
    "Ingersoll",
    "Merle Hay",
    "Sherman Hill",
    "South Side",
    "Drake",
    "Court Avenue",
    "Highland Park",
    "Western Gateway",
    "Gray's Station",
    "Franklin Avenue",
    "Botanical Garden",
    "Market District",
}

AREA_ALIASES = {
    "des moines": "Des Moines",
    "des moines metro": "Des Moines Metro",
    "downtown": "Downtown",
    "downtown des moines": "Downtown",
    "east village": "East Village",
    "west des moines": "West Des Moines",
    "waukee": "Waukee",
    "clive": "Clive",
    "urbandale": "Urbandale",
    "johnston": "Johnston",
    "ankeny": "Ankeny",
    "altoona": "Altoona",
    "pleasant hill": "Pleasant Hill",
    "windsor heights": "Windsor Heights",
    "beaverdale": "Beaverdale",
    "ingersoll": "Ingersoll",
    "merle hay": "Merle Hay",
    "sherman hill": "Sherman Hill",
    "south side": "South Side",
    "drake": "Drake",
    "court avenue": "Court Avenue",
    "highland park": "Highland Park",
    "western gateway": "Western Gateway",
    "gray's station": "Gray's Station",
    "franklin avenue": "Franklin Avenue",
    "botanical garden": "Botanical Garden",
    "market district": "Market District",
}

GENERIC_PREFIXES = (
    "why ",
    "what ",
    "look back",
    "new ",
    "popular ",
    "award-winning ",
    "restaurant with ",
    "des moines restaurants",
    "des moines metro restaurants",
    "bar owners",
    "the community",
    "the hottest",
    "the 12 hottest",
    "the 15 most-anticipated",
    "the most exciting",
    "try these",
    "meet the new",
    "new restaurants",
    "pizza locations",
    "one vegan",
    "long awaited reopening",
    "7 new restaurants",
    "10 exciting restaurant",
    "13 new restaurants",
    "17 new restaurants",
    "historic ",
    "one of the",
    "west des moines burger joint",
)

GENERIC_CONTAINS = (
    "plans for comeback",
    "files for chapter 11",
    "bankruptcy means for diners",
    "restaurant scene has openings",
    "opening in ankeny's former",
    "celebrate the re-opening",
    "look back at",
    "faces closure amid",
    "food court disappears",
    "that recently opened",
    "opening this fall",
    "restaurants are",
    "restaurants now",
    "must-try new restaurants",
    "most-anticipated restaurant openings",
    "things to know",
    "where to go",
    "you should try right now",
    "offer turkish delight",
    "this summer",
    "new bars that",
)

ROUNDUP_PATTERNS = (
    re.compile(r"^\d+\s+(new|exciting|must-try|hot|restaurant)"),
    re.compile(r"look back at \d+", re.IGNORECASE),
    re.compile(r"restaurants? that", re.IGNORECASE),
    re.compile(r"bars? that", re.IGNORECASE),
    re.compile(r"hottest new restaurants?", re.IGNORECASE),
    re.compile(r"most-anticipated restaurant openings?", re.IGNORECASE),
)

PUBLICATION_TOKENS = (
    "axios",
    "register",
    "journal",
    "business",
    "record",
    "who13",
    "kcci",
    "weareiowa",
    "cityview",
    ".com",
    "patch",
    "eater",
    "willamette",
    "concrete playground",
    "aol",
    "yahoo",
)

TRUSTED_PUBLICATIONS = (
    "des moines register",
    "axios",
    "who13",
    "kcci",
    "weareiowa",
    "cityview",
    "business record",
    "business journals",
    "restaurant business",
)

NONLOCAL_PUBLICATIONS = (
    "eater austin",
    "providence journal",
    "daily advertiser",
    "news & observer",
    "willamette week",
    "concrete playground",
    "hot 107.9",
    "kansas city pitch",
    "arizona foothills",
    "coloradoan",
    "patch",
    "men's journal",
    "the-sun.com",
    "willamette",
)

CHAIN_NAMES = {
    "pizza hut",
    "arbys",
    "arby's",
    "bar louie",
    "happy joe's",
    "hardee's",
    "wingstop",
    "pita pit",
    "steak n shake",
    "steak 'n shake",
}

STATUS_TERMS = {
    "closed": ("closed", "closing", "closure", "shuttered", "bankruptcy", "auction"),
    "opened": ("opened", "opening", "reopened", "reopening", "grand opening"),
}

TEMPORARY_CLOSURE_TERMS = (
    "temporarily closed",
    "temporary closure",
    "temporarily",
    "closed its taproom until",
    "until may",
    "when will",
    "return",
    "renovated lunch spot",
)

NON_EVENT_TERMS = (
    "dies at age",
    "opened restaurant in 1952",
    "franchisee filed for bankruptcy",
    "locations in iowa",
    "means for diners",
    "reopened illegally",
)

GENERIC_NAME_TOKENS = {
    "a",
    "after",
    "ankeny",
    "bar",
    "bakery",
    "bbq",
    "beer",
    "brewery",
    "cafe",
    "café",
    "car",
    "center",
    "chicken",
    "city",
    "clive",
    "closed",
    "closing",
    "club",
    "cocktail",
    "coffee",
    "county",
    "court",
    "des",
    "dining",
    "district",
    "downtown",
    "drake",
    "east",
    "eggroll",
    "enters",
    "faces",
    "food",
    "foreclosure",
    "for",
    "franklin",
    "gateway",
    "good",
    "grill",
    "has",
    "highland",
    "historic",
    "house",
    "ingersoll",
    "is",
    "italian",
    "joint",
    "johnston",
    "korean",
    "la",
    "live",
    "longtime",
    "lounge",
    "market",
    "merle",
    "metro",
    "mexican",
    "moines",
    "music",
    "nc",
    "old",
    "park",
    "permanently",
    "pizza",
    "place",
    "popular",
    "proceedings",
    "pub",
    "restaurant",
    "reopening",
    "return",
    "rice",
    "roof",
    "rooftop",
    "side",
    "soon",
    "south",
    "sports",
    "spot",
    "station",
    "steak",
    "street",
    "sushi",
    "taproom",
    "tavern",
    "tequila",
    "thai",
    "underground",
    "urbandale",
    "village",
    "waukee",
    "west",
    "western",
    "whiskey",
    "wine",
}

NAME_EXTRACTION_PATTERNS = (
    re.compile(
        r"(?P<name>[A-Z0-9][A-Za-z0-9&'’.\- ]{2,60}?)\s+(?:closing|closed|reopening|reopens|opens|opened|auctioned|shuttered|faces closure|enters foreclosure|announces closure)\b"
    ),
    re.compile(
        r"(?P<name>[A-Z0-9][A-Za-z0-9&'’.\- ]{2,60}?)\s+in\s+(?:downtown\s+)?(?:Des Moines|West Des Moines|Waukee|Ankeny|Clive|Urbandale|Johnston)\b"
    ),
    re.compile(
        r"(?:Des Moines[’']s?|Waukee[’']s?|Ankeny[’']s?|Johnston[’']s?|West Des Moines[’']s?)\s+(?P<name>[A-Z0-9][A-Za-z0-9&'’.\- ]{2,50}?)\s+(?:bar|brewery|restaurant|cafe|taproom)\b"
    ),
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml,application/xml,text/xml,text/plain,*/*",
        },
    )
    with urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


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
    return items


def google_news_search(query: str) -> list[dict[str, str]]:
    encoded = quote_plus(query)
    xml_text = fetch_text(
        f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    )
    return parse_rss_items(xml_text)


def parse_date_to_iso(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    for parser in (
        lambda item: datetime.fromisoformat(item.replace("Z", "+00:00")),
        parsedate_to_datetime,
    ):
        try:
            parsed = parser(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError, IndexError):
            continue
    return None


def format_date_label(iso_date: str) -> str:
    parsed = datetime.strptime(iso_date, "%Y-%m-%d")
    return parsed.strftime("%b %Y")


def looks_like_publication_suffix(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in PUBLICATION_TOKENS)


def split_publication(text: str) -> tuple[str, str]:
    if " - " not in text:
        return text.strip(), ""
    head, tail = text.rsplit(" - ", 1)
    if looks_like_publication_suffix(tail):
        return head.strip(), tail.strip()
    return text.strip(), ""


def publication_from_url(url: str) -> str:
    hostname = urlparse(url).netloc.lower()
    hostname = hostname.removeprefix("www.")
    if not hostname:
        return ""
    if hostname.endswith("desmoinesregister.com"):
        return "Des Moines Register"
    if hostname.endswith("axios.com"):
        return "Axios"
    if hostname.endswith("who13.com"):
        return "WHO13"
    if hostname.endswith("kcci.com"):
        return "KCCI"
    if hostname.endswith("weareiowa.com"):
        return "We Are Iowa"
    if hostname.endswith("businessrecord.com"):
        return "Business Record"
    if hostname.endswith("dmcityview.com"):
        return "Cityview"
    if hostname.endswith("bizjournals.com"):
        return "Business Journals"
    return hostname


def canonical_area(value: str) -> str | None:
    lowered = normalize(value)
    if lowered in AREA_ALIASES:
        return AREA_ALIASES[lowered]
    for key, canonical in AREA_ALIASES.items():
        if key in lowered:
            return canonical
    return None


def extract_candidate_status(candidate: dict) -> str:
    return candidate.get("status") or candidate.get("status_guess") or "review"


def extract_candidate_area(candidate: dict) -> str:
    area = candidate.get("area") or candidate.get("area_guess") or "Des Moines Metro"
    canonical = canonical_area(area)
    return canonical or area.strip() or "Des Moines Metro"


def extract_candidate_name(candidate: dict) -> tuple[str, str]:
    raw = (
        candidate.get("venue")
        or candidate.get("venue_guess")
        or candidate.get("title")
        or ""
    ).strip()
    name, publication = split_publication(raw)
    if is_roundup_headline(name):
        name = infer_name_from_text(candidate.get("title") or raw)
    return cleanup_facility_name(name), publication


def cleanup_facility_name(name: str) -> str:
    value = name.strip()
    value = re.sub(
        r"\b(closing|closed|reopening|reopens|opens|opened|auctioned|items to be|faces closure|temporarily closed|announces closure|enters foreclosure proceedings|is now permanently)\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"^(?:Des Moines[’']s?|Waukee[’']s?|Ankeny[’']s?|Johnston[’']s?|West Des Moines[’']s?)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s+(?:in|on|at)\s+(?:downtown\s+)?(?:Des Moines|West Des Moines|Waukee|Ankeny|Clive|Urbandale|Johnston)$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b(location|store doors|restaurant|taproom)\b$", "", value, flags=re.IGNORECASE).strip(" .,-")
    value = re.sub(r"\s+", " ", value)
    return value


def infer_name_from_text(text: str) -> str:
    cleaned = split_publication(text)[0]
    for pattern in NAME_EXTRACTION_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            return match.group("name").strip(" .,-")
    return cleaned


def is_roundup_headline(text: str) -> bool:
    lowered = text.lower().strip()
    if any(lowered.startswith(prefix) for prefix in GENERIC_PREFIXES):
        return True
    if any(fragment in lowered for fragment in GENERIC_CONTAINS):
        return True
    return any(pattern.search(text) for pattern in ROUNDUP_PATTERNS)


def is_specific_name(name: str, area: str) -> bool:
    lowered = name.lower().strip()
    if not lowered or len(lowered) < 4:
        return False
    if is_roundup_headline(lowered):
        return False
    if any(term in lowered for term in NON_EVENT_TERMS):
        return False
    if lowered.endswith(" is") or lowered.endswith(" are") or lowered.endswith(" to"):
        return False
    if lowered.endswith(" has") or lowered.endswith(" ready for a full"):
        return False
    if "," in name and len(name.split()) > 6:
        return False
    if lowered in CHAIN_NAMES and area in {"Des Moines Metro", "Des Moines"}:
        return False
    if lowered.startswith("des moines ") and area in {"Des Moines Metro", "Des Moines"}:
        return False
    if len(name.split()) == 1 and area in {"Des Moines Metro", "Des Moines"} and lowered not in {"django", "americana", "zora"}:
        return False
    if not has_distinctive_token(name, area):
        return False
    return True


def has_distinctive_token(name: str, area: str) -> bool:
    area_tokens = set(normalize(area).split())
    tokens = [token for token in re.findall(r"[A-Za-z0-9']+", name.lower()) if len(token) > 1]
    distinctive = [
        token
        for token in tokens
        if token not in GENERIC_NAME_TOKENS and token not in area_tokens and not token.isdigit()
    ]
    return len(distinctive) >= 1


def distinctive_tokens(name: str, area: str) -> list[str]:
    area_tokens = set(normalize(area).split())
    tokens = [token for token in re.findall(r"[A-Za-z0-9']+", name.lower()) if len(token) > 1]
    return [
        token
        for token in tokens
        if token not in GENERIC_NAME_TOKENS and token not in area_tokens and not token.isdigit()
    ]


def fuzzy_candidate_key(name: str, area: str, status: str) -> tuple[str, str, str]:
    tokens = distinctive_tokens(name, area)
    root = " ".join(tokens[:3]) if tokens else normalize(name)
    return root, normalize(area), status


def trusted_publication_score(publication: str) -> int:
    lowered = publication.lower()
    if any(token in lowered for token in NONLOCAL_PUBLICATIONS):
        return -2
    if any(token in lowered for token in TRUSTED_PUBLICATIONS):
        return 2
    return 0


def infer_type(name: str) -> tuple[str, str]:
    text = name.lower()
    if any(token in text for token in ("cafe", "bakery", "coffee")):
        return "cafe", "Cafe"
    if any(token in text for token in ("brew", "brewery", "taproom", "bar", "pub", "patio", "chophouse", "live music")):
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
    if "bar louie" in text:
        return "Bar & Grill"
    return "Category Pending"


def candidate_key(name: str, area: str, status: str) -> tuple[str, str, str]:
    return normalize(name), normalize(area), status


def has_status_signal(text: str, status: str) -> bool:
    lowered = normalize(text)
    return any(normalize(term) in lowered for term in STATUS_TERMS.get(status, ()))


def matches_name(text: str, name: str) -> bool:
    haystack = normalize(text)
    tokens = [token for token in normalize(name).split() if len(token) > 2]
    if not tokens:
        return False
    if normalize(name) in haystack:
        return True
    return sum(token in haystack for token in tokens) >= min(len(tokens), 2)


def matches_area(text: str, area: str) -> bool:
    canonical = canonical_area(area) or area
    if canonical in {"Des Moines Metro", "Des Moines"}:
        return True
    return normalize(canonical) in normalize(text)


def build_confirmation_queries(name: str, area: str, status: str) -> list[str]:
    area_term = area if area not in {"Des Moines Metro", "Des Moines"} else "\"Des Moines\""
    status_terms = {
        "closed": "(closed OR closing OR closure OR shuttered OR bankruptcy OR auction)",
        "opened": "(opened OR opening OR reopening OR grand opening)",
    }[status]
    return [
        f"\"{name}\" {area_term} {status_terms}",
        f"\"{name}\" Iowa {status_terms}",
    ]


def evaluate_confirmation_item(item: dict[str, str], name: str, area: str, status: str) -> tuple[int, dict[str, str]] | None:
    text = f"{item['title']} {item['summary']}"
    if is_roundup_headline(item["title"]):
        return None
    if not matches_name(text, name):
        return None
    if not matches_area(text, area):
        return None
    if not has_status_signal(text, status):
        return None

    publication = publication_from_url(item["link"])
    score = 3
    if normalize(name) in normalize(item["title"]):
        score += 2
    if matches_area(item["title"], area):
        score += 1
    score += trusted_publication_score(publication)
    return score, {
        "title": item["title"],
        "link": item["link"],
        "published_at": item["published_at"],
        "publication": publication,
    }


def confirm_candidate(name: str, area: str, status: str) -> dict[str, str] | None:
    best: tuple[int, dict[str, str]] | None = None
    for query in build_confirmation_queries(name, area, status):
        try:
            items = google_news_search(query)
        except Exception:
            continue
        for item in items[:10]:
            evaluated = evaluate_confirmation_item(item, name, area, status)
            if evaluated is None:
                continue
            if best is None or evaluated[0] > best[0]:
                best = evaluated
    if best is None:
        return None
    return best[1]


def base_items(payload: dict) -> list[dict]:
    items = []
    for item in payload["items"]:
        story = item.get("story", "")
        if any(story.startswith(prefix) for prefix in AUTOMATED_STORY_PREFIXES):
            continue
        items.append(item)
    return items


def build_verified_record(candidate: dict, name: str, area: str, status: str, evidence: dict[str, str]) -> dict:
    evidence_name = cleanup_facility_name(infer_name_from_text(evidence.get("title", "")))
    if is_specific_name(evidence_name, area) and len(evidence_name) < len(name):
        name = evidence_name

    event_date = parse_date_to_iso(evidence.get("published_at", "")) or parse_date_to_iso(
        candidate.get("published_at", "")
    )
    if event_date is None:
        raise ValueError("No parseable event date")

    venue_type, venue_type_label = infer_type(name)
    evidence_publication = evidence.get("publication") or publication_from_url(evidence.get("link", ""))
    story_bits = [
        "Automatically verified from the lead pipeline.",
        f"Matched facility-specific coverage for {name} in {area}.",
    ]
    if evidence_publication:
        story_bits.append(f"Confirmation source: {evidence_publication}.")

    return {
        "id": f"{slugify(name)}-{slugify(area)}-{status}-{event_date}",
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
        "story": " ".join(story_bits),
        "verificationLevel": "verified",
        "sources": [
            {
                "label": candidate.get("source_label", "Lead pipeline"),
                "url": candidate.get("url", ""),
            },
            {
                "label": evidence_publication or "Google News confirmation",
                "url": evidence.get("link", ""),
            },
        ],
    }


def normalize_sources(sources: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        label = (source.get("label") or "Source").strip()
        url = (source.get("url") or "").strip()
        key = (label, url)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({"label": label, "url": url})
    return cleaned


def collapse_verified_records(records: list[dict]) -> list[dict]:
    collapsed: dict[tuple[str, str, str], dict] = {}
    for record in records:
        key = fuzzy_candidate_key(record["name"], record["neighborhood"], record["status"])
        incumbent = collapsed.get(key)
        if incumbent is None:
            collapsed[key] = record
            continue

        preferred = incumbent
        alternate = record
        if (
            len(record["name"]) > len(incumbent["name"])
            or record["sortDate"] > incumbent["sortDate"]
        ):
            preferred = record
            alternate = incumbent

        preferred["sources"] = normalize_sources(
            [*preferred.get("sources", []), *alternate.get("sources", [])]
        )
        collapsed[key] = preferred

    return list(collapsed.values())


def main() -> int:
    venues_payload = load_json(VENUES_PATH)
    candidates = load_json(CANDIDATES_PATH)

    curated_items = base_items(venues_payload)
    existing_keys = {
        candidate_key(item["name"], item["neighborhood"], item["status"]) for item in curated_items
    }

    verified_records: dict[tuple[str, str, str], dict] = {}
    rejected: list[dict] = []

    for candidate in candidates:
        status = extract_candidate_status(candidate)
        if status not in {"opened", "closed"}:
            rejected.append({**candidate, "reason": "status-not-publishable"})
            continue

        area = extract_candidate_area(candidate)
        if area not in LOCAL_AREAS:
            rejected.append({**candidate, "reason": "area-not-local"})
            continue

        name, inline_publication = extract_candidate_name(candidate)
        if not is_specific_name(name, area):
            rejected.append({**candidate, "reason": "not-facility-specific"})
            continue

        headline = candidate.get("title", "") or candidate.get("venue", "")
        if is_roundup_headline(headline):
            rejected.append({**candidate, "reason": "roundup-headline"})
            continue
        if status == "closed":
            combined_text = normalize(
                f"{headline} {candidate.get('summary', '')} {candidate.get('venue', '')}"
            )
            if any(normalize(term) in combined_text for term in TEMPORARY_CLOSURE_TERMS):
                rejected.append({**candidate, "reason": "temporary-closure"})
                continue
        if any(normalize(term) in normalize(headline) for term in NON_EVENT_TERMS):
            rejected.append({**candidate, "reason": "non-event-story"})
            continue

        publication = inline_publication or publication_from_url(candidate.get("url", ""))
        if trusted_publication_score(publication) < 0:
            rejected.append({**candidate, "reason": "nonlocal-publication"})
            continue

        key = candidate_key(name, area, status)
        if key in existing_keys:
            rejected.append({**candidate, "reason": "duplicate-of-curated"})
            continue

        evidence = confirm_candidate(name, area, status)
        if evidence is None:
            rejected.append({**candidate, "reason": "no-facility-confirmation"})
            continue

        try:
            record = build_verified_record(candidate, name, area, status, evidence)
        except ValueError:
            rejected.append({**candidate, "reason": "bad-date"})
            continue

        incumbent = verified_records.get(key)
        if incumbent is None or record["sortDate"] > incumbent["sortDate"]:
            verified_records[key] = record

    verified_items = collapse_verified_records(list(verified_records.values()))

    merged_items = sorted(
        [
            *curated_items,
            *(
                {**record, "sources": normalize_sources(record["sources"])}
                for record in verified_items
            ),
        ],
        key=lambda item: (item["sortDate"], item["name"].lower()),
        reverse=True,
    )

    venues_payload["items"] = merged_items
    venues_payload["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    save_json(VENUES_PATH, venues_payload)
    save_json(
        VERIFIED_REPORT_PATH,
        sorted(
            verified_items,
            key=lambda item: (item["sortDate"], item["name"].lower()),
            reverse=True,
        ),
    )
    save_json(REJECTED_REPORT_PATH, rejected)
    save_json(
        SUMMARY_PATH,
        {
            "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "curatedBaseCount": len(curated_items),
            "verifiedImportCount": len(verified_items),
            "rejectedCount": len(rejected),
            "publicTimelineCount": len(merged_items),
        },
    )

    print(
        json.dumps(
            {
                "curatedBaseCount": len(curated_items),
                "verifiedImportCount": len(verified_items),
                "rejectedCount": len(rejected),
                "publicTimelineCount": len(merged_items),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
