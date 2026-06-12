# Last Call DSM

`Last Call DSM` is a static, history-first tracker for Des Moines area restaurant and bar openings, closures, relocations, and reopenings.

It is intentionally split into two parts:

1. A public-facing static site that shows curated venue records plus a metro-wide directory of every open restaurant, bar, and cafe.
2. An autonomous Python pipeline that gathers raw signals (Google News RSS, `r/desmoines`, OpenStreetMap, Google Places, venue websites), manages venue status lifecycles, and enriches descriptions — without auto-publishing rumors.

## Autonomous pipeline

The pipeline runs on GitHub Actions and has four stages:

1. **Discover** (`scripts/discover_open_venues.py`, weekly): queries the OpenStreetMap Overpass API for every named restaurant/bar/cafe/pub in the metro bounding box, dedupes against curated records, and merges open venues into `data/venues.json` as a directory (they sort below dated news events and display as "Open"). National chains are excluded by default (`--include-chains` to keep them). Venues that disappear from OSM are flagged in `data/reports/catalog-changes.json` as closure leads — never silently deleted.
2. **Collect** (`scripts/collect.py`, every 6 hours): Google News RSS + Reddit lead collection with keyword scoring, plus optional Google Places `businessStatus` verification of every published record.
3. **Lifecycle** (`scripts/update_statuses.py`, every run): auto-promotes `lastcall` records to `closed` once their final day passes; tracks Google Places drift (a closed venue reporting OPERATIONAL = possible reopening, an open one reporting CLOSED_PERMANENTLY = possible closure) across consecutive runs in `places-status-history.json`. Machine-generated catalog records are flipped automatically after two consistent observations; curated records are flagged for human review in `data/reports/status-changes.json`.
4. **Enrich** (`scripts/enrich_descriptions.py`, batched): pulls each venue's own website meta description, composes a clean one-liner (clamped to the UI's 175-char clip), and — when `ANTHROPIC_API_KEY` is set — polishes batches into consistent editorial blurbs with the Claude API. Fully functional without any key; results cached in `data/cache/enrichment.json`.

## Why this is stronger than the original outline

- Google News RSS queries are used as the first news layer instead of relying only on brittle per-site scraping. They let you watch many local outlets with one stable feed pattern and targeted keyword families.
- Reddit stays in the pipeline because it has excellent local signal, but it is treated as a lead source, not final proof.
- Facebook is not scraped. That route is fragile, likely to break, and likely to create policy headaches. The safer pattern is manual monitoring plus a community submission form.
- Google Places business status is built in as an optional verification layer for closures and moves.
- Official and quasi-official sources should be added to the editorial process: Iowa Secretary of State, Iowa alcohol licensing workflow, city agenda packets, and venue-owned sites.
- The site data model carries verification level and date precision, which matters for older venues where you may know the year before you know the exact last service date.

## Project layout

- `index.html`, `styles.css`, `app.js`: static site
- `review.html`, `review.css`, `review.js`: editorial review queue
- `data/venues.json`: curated venue history + open-venue directory shown on the site
- `config/watchlists.json`: Google News and Reddit watch queries
- `scripts/collect.py`: lead collector and optional Google Places verifier
- `scripts/discover_open_venues.py`: OpenStreetMap metro-wide open-venue discovery
- `scripts/update_statuses.py`: status lifecycle engine (lastcall→closed, reopen/closure drift)
- `scripts/enrich_descriptions.py`: description enrichment (website metadata + optional Claude polish)
- `docs/data-strategy.md`: source evaluation and backfill strategy
- `docs/backfill-2020-2022.md`: notes from the deeper pandemic and post-pandemic history pass
- `.github/workflows/collect.yml`: 6-hourly collection + lifecycle + enrichment workflow
- `.github/workflows/discover.yml`: weekly OSM catalog refresh workflow

## Local development

```bash
npm run dev
```

That serves the site at `http://localhost:4173`.

## Run the lead collector

```bash
npm run collect
```

Outputs:

- `data/cache/google-news.json`
- `data/cache/reddit.json`
- `data/reports/latest-candidates.json`
- `data/reports/latest-closure-candidates.json`
- `data/reports/latest-reddit-closures.json`
- `data/reports/latest-summary.json`

## Optional Google Places verification

Set a Google Places API (New) key:

```bash
export GOOGLE_PLACES_API_KEY=your_key_here
npm run verify:places
```

That writes `data/reports/places-status.json`.

## Audit the curated dataset

```bash
npm run audit:data
```

This checks sort order, required fields, source URLs, duplicate IDs, and a few common editorial mistakes like publishing a still-planned opening.

## Editorial workflow

1. Collect leads from Google News RSS and Reddit.
2. Open `review.html` and start with the closure queue from `latest-closure-candidates.json`.
3. Confirm each event with an official venue post, Google Places status, or at least two independent sources.
4. Add only curated records to `data/venues.json`.
5. Keep uncertain historical entries with `verificationLevel: "review"` and a clear note.

The review queue stores decisions in browser `localStorage` and lets you export those decisions as JSON, which is useful before a future server-backed admin panel exists.

## Best next steps

- Add a submission form so locals can report openings and closures.
- Add Iowa licensing and city-agenda sources as manual verification references.
- Backfill 2021-2024 using year-bucketed Google News searches and local year-end closure roundups.
- Once the dataset grows, move curated records from JSON into SQLite or Supabase and keep the same front-end design.
