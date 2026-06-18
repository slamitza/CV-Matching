#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import hashlib


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT_DIR / "data" / "manual_jobs.csv"
COLUMNS = [
    "source_id",
    "title",
    "company",
    "location",
    "url",
    "description",
    "posted_at",
    "remote",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge one or more job CSV files into data/manual_jobs.csv."
    )
    parser.add_argument("csv", nargs="+", help="CSV file exported from the browser extractor.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Destination manual jobs CSV.")
    args = parser.parse_args()

    out_path = _resolve_path(args.out)
    existing_rows = _read_rows(out_path)
    seen_source_ids = {row["source_id"] for row in existing_rows if row.get("source_id")}
    seen_urls = {row["url"] for row in existing_rows if row.get("url")}

    imported = 0
    skipped = 0
    rows = list(existing_rows)

    for input_arg in args.csv:
        input_path = _resolve_path(input_arg)
        for row in _read_rows(input_path):
            normalized = _normalize_row(row)
            if not normalized["title"] or not normalized["company"]:
                skipped += 1
                continue
            source_id = normalized["source_id"]
            url = normalized["url"]
            if source_id in seen_source_ids or (url and url in seen_urls):
                skipped += 1
                continue
            rows.append(normalized)
            seen_source_ids.add(source_id)
            if url:
                seen_urls.add(url)
            imported += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Imported {imported} jobs into {out_path}")
    if skipped:
        print(f"Skipped {skipped} duplicate or incomplete rows")
    return 0


def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    normalized = {column: (row.get(column) or "").strip() for column in COLUMNS}
    if not normalized["source_id"]:
        source = normalized["url"] or "|".join(
            [normalized["title"], normalized["company"], normalized["location"]]
        )
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
        normalized["source_id"] = f"manual-{digest}"
    return normalized


if __name__ == "__main__":
    raise SystemExit(main())
