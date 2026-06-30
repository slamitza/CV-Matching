#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import hashlib

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "config" / "settings.toml"
EXAMPLE_CONFIG = ROOT_DIR / "config" / "settings.example.toml"
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
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Settings TOML path.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Destination manual jobs CSV.")
    args = parser.parse_args()

    out_path = _resolve_path(args.out)
    settings = _load_toml(_resolve_config_path(args.config))
    excluded_companies = [
        str(company) for company in settings.get("excluded_companies", [])
    ]
    existing_rows, excluded = _filter_rows_by_company(
        _read_rows(out_path),
        excluded_companies,
    )
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
            if _company_is_excluded(normalized["company"], excluded_companies):
                excluded += 1
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
    if excluded:
        print(f"Excluded {excluded} rows by configured company filters")
    if skipped:
        print(f"Skipped {skipped} duplicate or incomplete rows")
    return 0


def _resolve_config_path(config: str) -> Path:
    path = _resolve_path(config)
    if path.exists():
        return path
    if path == DEFAULT_CONFIG and EXAMPLE_CONFIG.exists():
        return EXAMPLE_CONFIG
    raise SystemExit(f"Config not found: {path}")


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


def _load_toml(path: Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    normalized = {column: (row.get(column) or "").strip() for column in COLUMNS}
    if not normalized["source_id"]:
        source = normalized["url"] or "|".join(
            [normalized["title"], normalized["company"], normalized["location"]]
        )
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
        normalized["source_id"] = f"manual-{digest}"
    return normalized


def _filter_rows_by_company(
    rows: list[dict[str, str]],
    excluded_companies: list[str],
) -> tuple[list[dict[str, str]], int]:
    if not excluded_companies:
        return rows, 0
    kept_rows = []
    excluded = 0
    for row in rows:
        if _company_is_excluded(row.get("company"), excluded_companies):
            excluded += 1
            continue
        kept_rows.append(row)
    return kept_rows, excluded


def _company_is_excluded(company: str | None, excluded_companies: list[str]) -> bool:
    normalized_company = _normalize_company(company)
    if not normalized_company:
        return False
    return any(
        excluded_company in normalized_company
        for excluded_company in _normalized_company_filters(excluded_companies)
    )


def _normalized_company_filters(excluded_companies: list[str]) -> list[str]:
    return [
        normalized
        for company in excluded_companies
        if (normalized := _normalize_company(company))
    ]


def _normalize_company(company: str | None) -> str:
    return " ".join(str(company or "").casefold().split())


if __name__ == "__main__":
    raise SystemExit(main())
