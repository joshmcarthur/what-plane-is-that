#!/usr/bin/env python3
"""Build a compact hex -> description slice from the tar1090 aircraft database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from what_plane.aircraft_db import (
    DEFAULT_SOURCE_URL,
    fetch_slice,
    parse_registration_prefixes,
    write_slice_cache,
)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / ".cache" / "what-plane"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-url",
        default=DEFAULT_SOURCE_URL,
        help="tar1090 aircraft.csv.gz URL",
    )
    parser.add_argument(
        "--prefixes",
        default="ZK",
        help="Comma-separated registration prefixes (default: ZK)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for aircraft_db.json.gz and metadata",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prefixes = parse_registration_prefixes(args.prefixes)
    if not prefixes:
        print("At least one registration prefix is required", file=sys.stderr)
        return 1

    db = fetch_slice(args.source_url, prefixes)
    cache_path = args.output_dir / "aircraft_db.json.gz"
    meta_path = args.output_dir / "aircraft_db.meta.json"
    write_slice_cache(
        cache_path,
        meta_path,
        db,
        prefixes=prefixes,
        source_url=args.source_url,
    )

    print(
        f"Wrote {len(db)} entries to {cache_path} (prefixes={','.join(prefixes)})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
