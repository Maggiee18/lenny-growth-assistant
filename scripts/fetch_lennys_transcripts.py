#!/usr/bin/env python3
"""Download the official Lenny's Newsletter "starter pack" podcast transcripts.

Source: https://github.com/LennysNewsletter/lennys-newsletterpodcastdata
License (see that repo's LICENSE.md): the starter dataset may be used for
personal, non-commercial work -- including "publishing projects built with
it" -- but the RAW dataset files may not be redistributed. That's why this
script downloads transcripts straight into a git-ignored directory
(data/transcripts/lennys_podcast/) at setup time instead of this repository
committing them itself. Each evaluator who runs this script is exercising
their own personal, non-commercial use of the dataset.

Usage:
    python scripts/fetch_lennys_transcripts.py            # fetch 20 episodes
    python scripts/fetch_lennys_transcripts.py --limit 50  # fetch all 50 (full starter pack)
    python scripts/fetch_lennys_transcripts.py --limit 5   # quick smoke test
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAW_BASE = "https://raw.githubusercontent.com/LennysNewsletter/lennys-newsletterpodcastdata/main"
DEST_DIR = Path(__file__).resolve().parents[1] / "data" / "transcripts" / "lennys_podcast"


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "lenny-growth-assistant-ingestion/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return resp.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=20, help="Number of podcast episodes to fetch (max 50, default 20).")
    parser.add_argument("--dest", type=Path, default=DEST_DIR, help="Destination directory for downloaded .md files.")
    args = parser.parse_args()

    print(f"Fetching index from {RAW_BASE}/index.json ...")
    try:
        index = json.loads(_fetch(f"{RAW_BASE}/index.json"))
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"ERROR: could not reach GitHub ({exc}).", file=sys.stderr)
        print(
            "No network access? Use the bundled synthetic sample dataset instead: "
            "data/transcripts/sample_synthetic/ is already ingestion-ready.",
            file=sys.stderr,
        )
        return 1

    episodes = index.get("podcasts", [])[: max(0, min(args.limit, 50))]
    if not episodes:
        print("No episodes found in index.json.", file=sys.stderr)
        return 1

    args.dest.mkdir(parents=True, exist_ok=True)
    ok, failed = 0, 0
    for ep in episodes:
        filename = ep["filename"]  # e.g. "podcasts/adam-mosseri.md"
        local_name = Path(filename).name
        dest_path = args.dest / local_name
        try:
            content = _fetch(f"{RAW_BASE}/{filename}")
            dest_path.write_bytes(content)
            ok += 1
            print(f"  + {local_name}")
        except (urllib.error.URLError, TimeoutError) as exc:
            failed += 1
            print(f"  ! failed {filename}: {exc}", file=sys.stderr)

    print(f"\nDownloaded {ok} transcript(s) to {args.dest} ({failed} failed).")
    print("These files are git-ignored per the source dataset's license -- do not commit them.")
    print("Next: run the ingestion endpoint/CLI to embed and index them.")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
