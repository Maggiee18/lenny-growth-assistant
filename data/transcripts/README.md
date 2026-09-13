# Transcript data

The assistant ingests whatever files sit in this directory (recursively) at
ingestion time. Two sources are wired up:

## 1. Real data: Lenny's Podcast (recommended, requires network access once)

The official ["Lenny's Newsletter" data repo](https://github.com/LennysNewsletter/lennys-newsletterpodcastdata)
publishes a free "starter pack" of 50 real podcast transcripts specifically
for building AI tools on top of. Its license permits personal, non-commercial
use, including "publishing projects built with it" -- but **not**
redistributing the raw dataset files. So this repository does not commit
those files; instead, run:

```bash
python scripts/fetch_lennys_transcripts.py --limit 20
```

This downloads 20 real episode transcripts (title/guest/date/source URL
metadata included) into `data/transcripts/lennys_podcast/`, which is
git-ignored (see `.gitignore`). Pass `--limit 50` for the full starter pack.
Re-running ingestion afterwards (`POST /api/ingestion/run` or
`python scripts/ingest.py`) will pick these up automatically -- content-hash
deduping means re-running the fetch + ingest is always safe.

Attribution: transcripts remain (c) Lenny Rachitsky. Source metadata
(`source_url`) is preserved on every ingested chunk so every grounded answer
can link back to the original episode page.

## 2. Fallback: synthetic sample dataset (bundled, works offline)

`data/transcripts/sample_synthetic/` contains 5 short, **entirely fictional**
podcast-style transcripts ("Growth Signals" hosted by a fictional persona,
with fictional guests) covering activation, pricing, retention loops,
positioning, and PMF signals. These are committed to the repo so the app has
something to answer questions about out of the box, with no network access
and no license constraints -- they're original content written for this
project, not derived from any real podcast.

They are **not** real Lenny's Podcast content and are labeled as such in
their `source_url` fields (`example.com/growth-signals/...`). If both the
real and synthetic directories are present, both get ingested; the synthetic
set is small enough that it won't meaningfully dilute retrieval once real
transcripts are added.

## Supported file formats

See `backend/app/ingestion/loader.py` for the authoritative parsing logic.

| Format | Used for |
|---|---|
| `.md` with YAML frontmatter (`title`, `date`, `guest`, `post_url`, `description`) | Official Lenny's data repo format |
| `.json` (`title`, `episode`, `source_url`, `published_at`, `transcript`) | Synthetic samples, or any manually authored transcript |
| `.txt` (optional `Title:`/`Episode:`/`Source:`/`Published:` header lines) | Plain-text transcripts |
| `.vtt` | WebVTT caption exports |

No metadata is ever invented: a field missing from the source file is stored
as `null`, never guessed.
