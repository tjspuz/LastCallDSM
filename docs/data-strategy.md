# Data Strategy

## Source tiers

### Tier 1: Verification and operational truth

- Google Places API (New)
  - Use `businessStatus` to confirm `OPERATIONAL`, `CLOSED_TEMPORARILY`, or `CLOSED_PERMANENTLY`.
  - Use Text Search (New) to find the place, then Place Details if you need deeper confirmation.
- Venue-owned websites and social posts
  - Best proof for openings, last-day announcements, relocations, and reopenings.
- Iowa Secretary of State business search
  - Useful for entity changes, dissolutions, and business identity cleanup.
- Iowa alcohol licensing and local city agenda materials
  - Useful for bar, brewery, and restaurant application or renewal changes.

### Tier 2: High-signal editorial coverage

- Google News RSS queries aimed at Des Moines metro restaurant and bar terms.
- Axios Des Moines.
- Des Moines Register.
- Business Record.
- KCCI, WHO 13, and similar local TV newsroom sites.

### Tier 3: Community signal

- `r/desmoines` JSON search.
- Community tips submitted through a form.
- Local newsletters and neighborhood groups reviewed manually.

### Tier 4: Restricted or brittle sources

- Facebook groups and pages.
  - Do not build your pipeline around scraping them.
  - Use them as manual discovery only, then verify elsewhere.

## Improvements over the original plan

### 1. Use Google News RSS as the main news ingestion layer

This is more durable than maintaining separate scrapers for each local site on day one.

Recommended query families:

- Opening terms:
  - `opened`
  - `opening`
  - `soft opening`
  - `grand opening`
  - `reopening`
- Closure terms:
  - `closed`
  - `closing`
  - `closure`
  - `last day`
  - `shuttered`
  - `permanently closed`
- Distress terms:
  - `bankruptcy`
  - `bankrupt`
  - `eviction`
  - `auction`
  - `for lease`
  - `sold`
  - `liquor license`
- Move and rebrand terms:
  - `moving`
  - `relocating`
  - `moved`
  - `rebrand`
  - `reopening`

### 2. Treat Reddit as a discovery source, not final proof

Reddit is excellent for catching rumors, neighborhood chatter, and early sightings. It is not enough by itself to mark a venue `verified`.

### 3. Do not depend on Facebook scraping

Meta actively fights scraping, and the long-term maintenance cost is not worth it. The safer play is:

- Follow key groups manually.
- Let the community submit tips.
- Verify tips through a second source before publication.

### 4. Add verification states

Every venue event should carry:

- `verified`
- `review`

Suggested rules:

- `closed` becomes `verified` if any of these are true:
  - Google Places returns `CLOSED_PERMANENTLY`.
  - The venue posts an official closure notice.
  - Two independent local sources report the closure.
- `opened` becomes `verified` if any of these are true:
  - The venue has an active official site or social announcement.
  - Google Places returns `OPERATIONAL` for the new location.
  - One local news source plus one venue-controlled source confirm it.

### 5. Separate leads from curated history

Raw pipeline output should never go straight onto the public timeline. Keep:

- `data/reports/latest-candidates.json` for review
- `data/venues.json` for published records

## Historical backfill plan

For a 3-5 year history project, the backfill work matters more than the scheduler.

### Best backfill sequence

1. Run year-bucketed Google News searches for 2021, 2022, 2023, 2024, and 2025.
2. Use local year-end roundup stories to seed known closures and openings quickly.
3. Search `r/desmoines` with the same year buckets and distress keywords.
4. Add iconic legacy closures first so the timeline feels historically credible.
5. Mark uncertain dates with year-only or month-only precision instead of inventing exact dates.

## Review workflow

Use the static `review.html` page as a holding area between collection and publication.

- `Accept`: likely ready for curation into `data/venues.json`
- `Hold`: needs a second source, official post, or date cleanup
- `Reject`: false positive, duplicate article, or irrelevant venue

Because the site is static right now, those review decisions are saved in browser storage and can be exported. That keeps the public timeline clean without waiting on a backend admin system.

### Good seed targets

- Long-running icons and cult favorites.
- Downtown anchor restaurants.
- East Village and Ingersoll corridor openings and losses.
- First-Iowa chain openings that got heavy coverage.

## Notes on AI extraction

AI can help extract name, status, and neighborhood from messy snippets, but it should be optional. A more bulletproof first version is:

- deterministic keyword scoring
- manual review queue
- Google Places or source verification

That keeps the project usable even if no model API key is configured.

## Primary references

- Reddit API docs: https://www.reddit.com/dev/api/
- Reddit Data API Terms: https://redditinc.com/policies/data-api-terms
- Google Places API overview: https://developers.google.com/maps/documentation/places/web-service
- Google Places Text Search (New): https://developers.google.com/maps/documentation/places/web-service/text-search
- Google Places Place Details (New): https://developers.google.com/maps/documentation/places/web-service/place-details
- Google Places `businessStatus` reference: https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places
- Facebook help on scraping: https://www.facebook.com/help/463983701520800
