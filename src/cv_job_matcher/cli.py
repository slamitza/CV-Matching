from __future__ import annotations

from pathlib import Path
import argparse
import sys

from .config import load_settings
from .database import Database
from .scanner import scan


DEFAULT_CONFIG = Path("config/settings.toml")
EXAMPLE_CONFIG = Path("config/settings.example.toml")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args) or 0)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-matcher")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to settings TOML.")
    subparsers = parser.add_subparsers(required=True)

    init_parser = subparsers.add_parser("init-db", help="Create or migrate the SQLite database.")
    init_parser.set_defaults(func=cmd_init_db)

    scan_parser = subparsers.add_parser("scan", help="Scan configured job sources once.")
    scan_parser.add_argument("--source", action="append", help="Only scan a named source. Can be repeated.")
    scan_parser.add_argument("--dry-run", action="store_true", help="Fetch and score without writing.")
    scan_parser.set_defaults(func=cmd_scan)

    jobs_parser = subparsers.add_parser("jobs", help="List matched jobs.")
    jobs_parser.add_argument("--min-score", type=float, default=None)
    jobs_parser.add_argument("--status", default=None)
    jobs_parser.add_argument("--limit", type=int, default=25)
    jobs_parser.set_defaults(func=cmd_jobs)

    apply_parser = subparsers.add_parser("apply", help="Record or update an application for a job.")
    apply_parser.add_argument("job_id", type=int)
    apply_parser.add_argument("--status", default="applied")
    apply_parser.add_argument("--notes", default=None)
    apply_parser.set_defaults(func=cmd_apply)

    applications_parser = subparsers.add_parser("applications", help="List tracked applications.")
    applications_parser.add_argument("--limit", type=int, default=50)
    applications_parser.set_defaults(func=cmd_applications)

    return parser


def cmd_init_db(args: argparse.Namespace) -> int:
    settings = load_settings(resolve_config_path(args.config))
    database = Database(settings.database_path)
    database.init()
    print(f"Initialized database at {settings.database_path}")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    settings = load_settings(resolve_config_path(args.config))
    source_names = set(args.source) if args.source else None
    summaries = scan(settings, source_names=source_names, dry_run=args.dry_run)
    for summary in summaries:
        status = "ok" if summary.error is None else f"error: {summary.error}"
        print(
            f"{summary.source}: found={summary.found_count} "
            f"new={summary.new_count} updated={summary.updated_count} {status}"
        )
    return 1 if any(summary.error for summary in summaries) else 0


def cmd_jobs(args: argparse.Namespace) -> int:
    settings = load_settings(resolve_config_path(args.config))
    database = Database(settings.database_path)
    database.init()
    min_score = settings.minimum_score if args.min_score is None else args.min_score
    rows = database.list_jobs(min_score=min_score, status=args.status, limit=args.limit)
    print_table(
        rows,
        [
            ("id", "ID"),
            ("match_score", "Score"),
            ("company", "Company"),
            ("title", "Title"),
            ("location", "Location"),
            ("source", "Source"),
            ("status", "Status"),
            ("url", "URL"),
        ],
    )
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    settings = load_settings(resolve_config_path(args.config))
    database = Database(settings.database_path)
    database.init()
    database.record_application(args.job_id, status=args.status, notes=args.notes)
    print(f"Recorded job {args.job_id} as {args.status}")
    return 0


def cmd_applications(args: argparse.Namespace) -> int:
    settings = load_settings(resolve_config_path(args.config))
    database = Database(settings.database_path)
    database.init()
    rows = database.list_applications(limit=args.limit)
    print_table(
        rows,
        [
            ("id", "ID"),
            ("job_id", "Job"),
            ("company", "Company"),
            ("position", "Position"),
            ("status", "Status"),
            ("applied_at", "Applied At"),
            ("notes", "Notes"),
        ],
    )
    return 0


def resolve_config_path(value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path
    if path == DEFAULT_CONFIG and EXAMPLE_CONFIG.exists():
        print(
            "warning: config/settings.toml not found; using config/settings.example.toml",
            file=sys.stderr,
        )
        return EXAMPLE_CONFIG
    raise FileNotFoundError(f"Config file not found: {path}")


def print_table(rows: list[object], columns: list[tuple[str, str]]) -> None:
    if not rows:
        print("No rows.")
        return

    rendered_rows = [
        [truncate(str(row[key] if row[key] is not None else ""), 70) for key, _label in columns]
        for row in rows
    ]
    widths = [
        max(len(label), *(len(rendered[index]) for rendered in rendered_rows))
        for index, (_key, label) in enumerate(columns)
    ]
    header = "  ".join(label.ljust(widths[index]) for index, (_key, label) in enumerate(columns))
    print(header)
    print("  ".join("-" * width for width in widths))
    for rendered in rendered_rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(rendered)))


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
