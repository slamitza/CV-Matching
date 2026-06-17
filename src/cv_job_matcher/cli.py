from __future__ import annotations

from pathlib import Path
import argparse
import csv
import sys
from html import escape

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
    jobs_parser.add_argument(
        "--scored-only",
        action="store_true",
        help="Filter by match score. Scoring is opt-in via score_jobs = true.",
    )
    jobs_parser.add_argument("--status", default=None)
    jobs_parser.add_argument("--source", default=None)
    jobs_parser.add_argument("--limit", type=int, default=25)
    jobs_parser.set_defaults(func=cmd_jobs)

    new_jobs_parser = subparsers.add_parser(
        "new-jobs",
        help="List non-duplicate jobs first seen in the latest successful scan.",
    )
    new_jobs_parser.add_argument("--source", default=None)
    new_jobs_parser.add_argument("--limit", type=int, default=100)
    new_jobs_parser.set_defaults(func=cmd_new_jobs)

    export_parser = subparsers.add_parser("export-jobs", help="Export saved jobs to CSV.")
    export_parser.add_argument("--source", default=None)
    export_parser.add_argument("--out", required=True)
    export_parser.add_argument("--limit", type=int, default=10000)
    export_parser.set_defaults(func=cmd_export_jobs)

    export_html_parser = subparsers.add_parser(
        "export-jobs-html",
        help="Export saved jobs to an HTML report with latest new jobs highlighted.",
    )
    export_html_parser.add_argument("--source", default=None)
    export_html_parser.add_argument("--out", required=True)
    export_html_parser.add_argument("--limit", type=int, default=10000)
    export_html_parser.set_defaults(func=cmd_export_jobs_html)

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
    scored_only = bool(args.scored_only or args.min_score is not None)
    rows = database.list_jobs(
        min_score=min_score,
        status=args.status,
        source=args.source,
        limit=args.limit,
        scored_only=scored_only,
    )
    print_table(
        rows,
        [
            ("id", "ID"),
            ("website", "Website"),
            ("source_id", "Posting"),
            ("company", "Company"),
            ("title", "Title"),
            ("location", "Location"),
            ("source", "Source"),
            ("posted_at", "Posted"),
            ("seen_count", "Seen"),
            ("last_seen_at", "Last Seen"),
            ("status", "Status"),
            ("url", "URL"),
        ],
    )
    return 0


def cmd_new_jobs(args: argparse.Namespace) -> int:
    settings = load_settings(resolve_config_path(args.config))
    database = Database(settings.database_path)
    database.init()
    rows = database.list_new_jobs_from_latest_scan(source=args.source, limit=args.limit)
    print_table(
        rows,
        [
            ("website", "Website"),
            ("source_id", "JobID"),
            ("title", "Job title"),
            ("company", "Company"),
            ("url", "URL"),
        ],
    )
    return 0


def cmd_export_jobs(args: argparse.Namespace) -> int:
    settings = load_settings(resolve_config_path(args.config))
    database = Database(settings.database_path)
    database.init()
    rows = database.list_jobs(source=args.source, limit=args.limit)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        ("website", "Website"),
        ("source_id", "JobID"),
        ("title", "Job title"),
        ("company", "Company"),
        ("url", "URL"),
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([label for _key, label in columns])
        for row in rows:
            writer.writerow([row[key] if row[key] is not None else "" for key, _label in columns])

    print(f"Exported {len(rows)} jobs to {output_path}")
    return 0


def cmd_export_jobs_html(args: argparse.Namespace) -> int:
    settings = load_settings(resolve_config_path(args.config))
    database = Database(settings.database_path)
    database.init()
    rows = database.list_jobs(source=args.source, limit=args.limit)
    new_rows = database.list_new_jobs_from_latest_scan(source=args.source, limit=args.limit)
    new_source_ids = {str(row["source_id"]) for row in new_rows}
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(render_jobs_html(rows, new_source_ids), encoding="utf-8")
    print(f"Exported {len(rows)} jobs to {output_path}")
    return 0


def render_jobs_html(rows: list[object], new_source_ids: set[str]) -> str:
    columns = [
        ("website", "Website"),
        ("source_id", "JobID"),
        ("title", "Job title"),
        ("company", "Company"),
        ("url", "URL"),
    ]
    rendered_rows = []
    for row in rows:
        source_id = str(_row_value(row, "source_id") or "")
        title = str(_row_value(row, "title") or "")
        status = str(_row_value(row, "status") or "").lower()
        is_new = source_id in new_source_ids
        is_applied = status == "applied"
        job_key = f"{_row_value(row, 'website') or ''}:{source_id}"
        checked = " checked" if is_applied else ""
        cells = [
            (
                '<td class="applied-cell">'
                f'<input type="checkbox" data-applied-checkbox aria-label="Applied: {escape(title, quote=True)}"{checked}>'
                "</td>"
            )
        ]
        for key, _label in columns:
            raw_value = _row_value(row, key)
            value = "" if raw_value is None else str(raw_value)
            if key == "url" and value:
                safe_url = escape(value, quote=True)
                cells.append(
                    f'<td><a href="{safe_url}" target="_blank" rel="noreferrer">{safe_url}</a></td>'
                )
            else:
                cells.append(f"<td>{escape(value)}</td>")
        classes = []
        if is_new:
            classes.append("new-job")
        if is_applied:
            classes.append("applied-job")
        row_class = f' class="{" ".join(classes)}"' if classes else ""
        rendered_rows.append(
            f'<tr{row_class} data-job-key="{escape(job_key, quote=True)}" '
            f'data-status="{escape(status, quote=True)}">{"".join(cells)}</tr>'
        )

    table_body = "\n".join(rendered_rows) or (
        f'<tr><td colspan="{len(columns) + 1}" class="empty">No jobs saved yet.</td></tr>'
    )
    headers = "<th>Applied</th>" + "".join(f"<th>{escape(label)}</th>" for _key, label in columns)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>LinkedIn Jobs</title>
  <style>
    body {{
      color: #1f2328;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 24px;
    }}
    h1 {{
      font-size: 22px;
      margin: 0 0 8px;
    }}
    .legend {{
      color: #57606a;
      margin: 0 0 18px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid #d0d7de;
      font-size: 14px;
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f6f8fa;
      position: sticky;
      top: 0;
    }}
    tr.new-job {{
      background: #dff7df;
    }}
    tr.applied-job {{
      background: #dceeff;
    }}
    .applied-cell {{
      text-align: center;
      width: 72px;
    }}
    input[type="checkbox"] {{
      height: 18px;
      width: 18px;
    }}
    a {{
      color: #0969da;
    }}
    .empty {{
      color: #57606a;
      text-align: center;
    }}
  </style>
</head>
<body>
  <h1>LinkedIn Jobs</h1>
  <p class="legend">Light green rows are new jobs from the latest successful scan. Light blue rows are checked as applied.</p>
  <table>
    <thead><tr>{headers}</tr></thead>
    <tbody>
{table_body}
    </tbody>
  </table>
  <script>
    (() => {{
      const storagePrefix = "cv-job-matcher:applied:";
      document.querySelectorAll("tr[data-job-key]").forEach((row) => {{
        const checkbox = row.querySelector("[data-applied-checkbox]");
        if (!checkbox) {{
          return;
        }}

        const storageKey = storagePrefix + row.dataset.jobKey;
        const storedValue = window.localStorage.getItem(storageKey);
        const databaseApplied = row.dataset.status === "applied";
        const applied = storedValue === null ? databaseApplied : storedValue === "true";

        checkbox.checked = applied;
        row.classList.toggle("applied-job", applied);
        checkbox.addEventListener("change", () => {{
          row.classList.toggle("applied-job", checkbox.checked);
          window.localStorage.setItem(storageKey, checkbox.checked ? "true" : "false");
        }});
      }});
    }})();
  </script>
</body>
</html>
"""


def _row_value(row: object, key: str) -> object | None:
    try:
        return row[key]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return None


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
