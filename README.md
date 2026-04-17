# Last Call DSM

`Last Call DSM` is a static, history-first tracker for Des Moines area restaurant and bar openings, closures, relocations, and reopenings.

It is intentionally split into two parts:

1. A public-facing static site that shows only curated venue records.
2. A Python lead collector that gathers raw signals from Google News RSS queries, `r/desmoines`, and optional Google Places verification without auto-publishing rumors.

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
- `data/venues.json`: curated venue history shown on the site
- `config/watchlists.json`: Google News and Reddit watch queries
- `scripts/collect.py`: lead collector and optional Google Places verifier
- `docs/data-strategy.md`: source evaluation and backfill strategy
- `docs/backfill-2020-2022.md`: notes from the deeper pandemic and post-pandemic history pass
- `.github/workflows/collect.yml`: scheduled collection workflow

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
2. Open `review.html` and review `latest-candidates.json`.
3. Confirm each event with an official venue post, Google Places status, or at least two independent sources.
4. Add only curated records to `data/venues.json`.
5. Keep uncertain historical entries with `verificationLevel: "review"` and a clear note.

The review queue stores decisions in browser `localStorage` and lets you export those decisions as JSON, which is useful before a future server-backed admin panel exists.

## Best next steps

- Add a submission form so locals can report openings and closures.
- Add Iowa licensing and city-agenda sources as manual verification references.
- Backfill 2021-2024 using year-bucketed Google News searches and local year-end closure roundups.
- Once the dataset grows, move curated records from JSON into SQLite or Supabase and keep the same front-end design.
