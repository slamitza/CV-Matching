from __future__ import annotations

from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse
import json
import re

from .database import Database


JOB_STATUS_PATH_RE = re.compile(r"^/jobs/(\d+)/status$")
VALID_JOB_STATUSES = {"new", "applied", "discarded"}
STORED_VIEWS = {"applied", "discarded"}


def serve_jobs_dashboard(
    database: Database,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    limit: int = 10000,
) -> None:
    database.init()

    class JobsDashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib method name.
            path = urlparse(self.path).path
            if path == "/health":
                self._send_text("ok")
                return
            if path not in {"/", "/jobs"}:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            rows = database.list_jobs(limit=limit)
            self._send_html(render_dashboard(rows))

        def do_POST(self) -> None:  # noqa: N802 - stdlib method name.
            path = urlparse(self.path).path
            match = JOB_STATUS_PATH_RE.match(path)
            if not match:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            job_id = int(match.group(1))
            try:
                payload = self._read_payload()
                status = str(payload.get("status", "")).strip().lower()
                if status not in VALID_JOB_STATUSES:
                    raise ValueError("status must be 'new', 'applied', or 'discarded'")
                database.set_job_status(job_id, status=status)
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            self._send_json({"ok": True, "job_id": job_id, "status": status})

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_payload(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(content_length).decode("utf-8") if content_length else ""
            content_type = self.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return json.loads(body or "{}")
            parsed = parse_qs(body)
            return {key: values[-1] for key, values in parsed.items()}

        def _send_html(self, html: str) -> None:
            encoded = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_text(self, text: str) -> None:
            encoded = text.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer((host, port), JobsDashboardHandler)
    print(f"Jobs dashboard: http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping jobs dashboard.")
    finally:
        server.server_close()


def render_dashboard(rows: list[object]) -> str:
    open_rows = [row for row in rows if _status_view(_row_status(row)) == "open"]
    applied_rows = [row for row in rows if _row_status(row) == "applied"]
    discarded_rows = [row for row in rows if _row_status(row) == "discarded"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Jobs Database</title>
  <style>
    :root {{
      color-scheme: light;
      --border: #d0d7de;
      --muted: #57606a;
      --text: #1f2328;
      --surface: #ffffff;
      --surface-alt: #f6f8fa;
      --accent: #0969da;
      --applied: #dceeff;
      --success: #1f883d;
      --discarded: #fff1f1;
      --danger: #cf222e;
      --new: #dff7df;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      background: var(--surface);
    }}
    header {{
      align-items: center;
      border-bottom: 1px solid var(--border);
      display: flex;
      gap: 16px;
      justify-content: space-between;
      padding: 16px 20px;
      position: sticky;
      top: 0;
      background: var(--surface);
      z-index: 2;
    }}
    h1 {{
      font-size: 20px;
      margin: 0;
    }}
    .counts {{
      color: var(--muted);
      font-size: 14px;
    }}
    nav {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .tab-button {{
      align-items: center;
      background: var(--surface-alt);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      cursor: pointer;
      display: inline-flex;
      font: inherit;
      gap: 6px;
      padding: 8px 10px;
    }}
    .tab-button[aria-selected="true"] {{
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }}
    .applied-icon {{
      background: var(--success);
      border-radius: 999px;
      display: inline-block;
      height: 14px;
      position: relative;
      width: 14px;
    }}
    .applied-icon::after {{
      border-bottom: 2px solid white;
      border-left: 2px solid white;
      content: "";
      height: 4px;
      left: 3px;
      position: absolute;
      top: 4px;
      transform: rotate(-45deg);
      width: 7px;
    }}
    .discarded-icon {{
      background: var(--danger);
      border-radius: 999px;
      display: inline-block;
      height: 14px;
      position: relative;
      width: 14px;
    }}
    .discarded-icon::before,
    .discarded-icon::after {{
      background: white;
      border-radius: 1px;
      content: "";
      height: 2px;
      left: 3px;
      position: absolute;
      top: 6px;
      width: 8px;
    }}
    .discarded-icon::before {{
      transform: rotate(45deg);
    }}
    .discarded-icon::after {{
      transform: rotate(-45deg);
    }}
    main {{
      padding: 20px;
    }}
    section[hidden] {{
      display: none;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      font-size: 14px;
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--surface-alt);
      position: sticky;
      top: 66px;
      z-index: 1;
    }}
    tr.new-job {{
      background: var(--new);
    }}
    tr.applied-job {{
      background: var(--applied);
    }}
    tr.discarded-job {{
      background: var(--discarded);
    }}
    .action-cell {{
      width: 176px;
    }}
    .action-buttons {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .status-button {{
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
      font: inherit;
      padding: 6px 8px;
      white-space: nowrap;
    }}
    .apply-button {{
      background: #1f883d;
      border-color: #1f883d;
      color: white;
    }}
    .open-button {{
      background: var(--surface-alt);
      color: var(--text);
    }}
    .discard-button {{
      background: var(--danger);
      border-color: var(--danger);
      color: white;
    }}
    a {{
      color: var(--accent);
    }}
    .empty {{
      color: var(--muted);
      padding: 24px;
      text-align: center;
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Jobs Database</h1>
      <div class="counts">
        Open <span data-count="open">{len(open_rows)}</span> ·
        Applied <span data-count="applied">{len(applied_rows)}</span> ·
        Discarded <span data-count="discarded">{len(discarded_rows)}</span> ·
        Total <span data-count="total">{len(rows)}</span>
      </div>
    </div>
    <nav aria-label="Job status views">
      <button class="tab-button" data-tab-button="open" aria-selected="true">Open Jobs</button>
      <button class="tab-button" data-tab-button="applied" aria-selected="false">
        <span class="applied-icon" aria-hidden="true"></span>
        Applied
      </button>
      <button class="tab-button" data-tab-button="discarded" aria-selected="false">
        <span class="discarded-icon" aria-hidden="true"></span>
        Discarded
      </button>
    </nav>
  </header>
  <main>
    <section data-tab-panel="open">
      {render_table(open_rows, view="open")}
    </section>
    <section data-tab-panel="applied" hidden>
      {render_table(applied_rows, view="applied")}
    </section>
    <section data-tab-panel="discarded" hidden>
      {render_table(discarded_rows, view="discarded")}
    </section>
  </main>
  <script>
    (() => {{
      const panels = new Map(
        Array.from(document.querySelectorAll("[data-tab-panel]")).map((panel) => [
          panel.dataset.tabPanel,
          panel,
        ])
      );
      const buttons = new Map(
        Array.from(document.querySelectorAll("[data-tab-button]")).map((button) => [
          button.dataset.tabButton,
          button,
        ])
      );

      function showTab(name) {{
        panels.forEach((panel, key) => {{
          panel.hidden = key !== name;
        }});
        buttons.forEach((button, key) => {{
          button.setAttribute("aria-selected", String(key === name));
        }});
      }}

      function selectedTab() {{
        for (const [key, button] of buttons.entries()) {{
          if (button.getAttribute("aria-selected") === "true") {{
            return key;
          }}
        }}
        return "open";
      }}

      function syncEmptyRows() {{
        document.querySelectorAll("[data-table-body]").forEach((body) => {{
          const hasJobs = Boolean(body.querySelector("[data-job-row]"));
          const emptyRow = body.querySelector("[data-empty-row]");
          if (hasJobs && emptyRow) {{
            emptyRow.remove();
          }}
          if (!hasJobs && !emptyRow) {{
            const row = document.createElement("tr");
            row.dataset.emptyRow = "true";
            row.innerHTML = '<td colspan="9" class="empty">No jobs in this view.</td>';
            body.appendChild(row);
          }}
        }});
      }}

      function updateCounts() {{
        const rows = Array.from(document.querySelectorAll("[data-job-row]"));
        const openCount = rows.filter((row) => viewForStatus(row.dataset.status) === "open").length;
        const appliedCount = rows.filter((row) => row.dataset.status === "applied").length;
        const discardedCount = rows.filter((row) => row.dataset.status === "discarded").length;
        document.querySelector('[data-count="open"]').textContent = openCount;
        document.querySelector('[data-count="applied"]').textContent = appliedCount;
        document.querySelector('[data-count="discarded"]').textContent = discardedCount;
        document.querySelector('[data-count="total"]').textContent = rows.length;
      }}

      function viewForStatus(status) {{
        if (status === "applied" || status === "discarded") {{
          return status;
        }}
        return "open";
      }}

      function actionButtonsHtml(status) {{
        if (viewForStatus(status) === "open") {{
          return `
            <div class="action-buttons">
              <button class="status-button apply-button" data-status-button data-target-status="applied">Applied</button>
              <button class="status-button discard-button" data-status-button data-target-status="discarded">Discard</button>
            </div>
          `;
        }}
        return `
          <div class="action-buttons">
            <button class="status-button open-button" data-status-button data-target-status="new">Move back</button>
          </div>
        `;
      }}

      function configureRow(row, status) {{
        row.dataset.status = status;
        row.classList.toggle("applied-job", status === "applied");
        row.classList.toggle("discarded-job", status === "discarded");
        row.querySelector(".action-cell").innerHTML = actionButtonsHtml(status);
      }}

      function moveRow(row, status) {{
        const currentTab = selectedTab();
        configureRow(row, status);
        const targetView = viewForStatus(status);
        const targetBody = document.querySelector(`[data-table-body="${{targetView}}"]`);
        targetBody.appendChild(row);
        syncEmptyRows();
        updateCounts();
        showTab(currentTab);
      }}

      document.querySelectorAll("[data-tab-button]").forEach((button) => {{
        button.addEventListener("click", () => showTab(button.dataset.tabButton));
      }});

      document.addEventListener("click", async (event) => {{
        const button = event.target.closest("[data-status-button]");
        if (!button) {{
          return;
        }}
        const row = button.closest("[data-job-row]");
        const jobId = row.dataset.jobId;
        const status = button.dataset.targetStatus;
        const rowButtons = Array.from(row.querySelectorAll("[data-status-button]"));
        rowButtons.forEach((rowButton) => {{
          rowButton.disabled = true;
        }});
        try {{
          const response = await fetch(`/jobs/${{jobId}}/status`, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ status }}),
          }});
          const payload = await response.json();
          if (!response.ok || !payload.ok) {{
            throw new Error(payload.error || "Could not update job");
          }}
          moveRow(row, status);
        }} catch (error) {{
          alert(error.message);
        }} finally {{
          rowButtons.forEach((rowButton) => {{
            if (rowButton.isConnected) {{
              rowButton.disabled = false;
            }}
          }});
        }}
      }});
    }})();
  </script>
</body>
</html>
"""


def render_table(rows: list[object], *, view: str) -> str:
    headers = [
        "Action",
        "ID",
        "Website",
        "Company",
        "Title",
        "Location",
        "URL",
        "Seen",
        "Last Seen",
    ]
    body = "\n".join(render_row(row) for row in rows)
    if not body:
        body = (
            f'<tr data-empty-row><td colspan="{len(headers)}" class="empty">'
            "No jobs in this view.</td></tr>"
        )
    return f"""
      <table>
        <thead><tr>{"".join(f"<th>{escape(header)}</th>" for header in headers)}</tr></thead>
        <tbody data-table-body="{escape(view, quote=True)}">
          {body}
        </tbody>
      </table>
    """


def render_row(row: object) -> str:
    job_id = str(_row_value(row, "id") or "")
    status = _row_status(row)
    url = str(_row_value(row, "url") or "")
    classes = []
    if status == "applied":
        classes.append("applied-job")
    if status == "discarded":
        classes.append("discarded-job")
    if int(_row_value(row, "seen_count") or 0) <= 1:
        classes.append("new-job")
    row_class = f' class="{" ".join(classes)}"' if classes else ""
    cells = [
        (
            '<td class="action-cell">'
            f"{render_action_buttons(status)}"
            "</td>"
        ),
        f"<td>{escape(job_id)}</td>",
        f"<td>{escape(str(_row_value(row, 'website') or ''))}</td>",
        f"<td>{escape(str(_row_value(row, 'company') or ''))}</td>",
        f"<td>{escape(str(_row_value(row, 'title') or ''))}</td>",
        f"<td>{escape(str(_row_value(row, 'location') or ''))}</td>",
        (
            f'<td><a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">'
            f"{escape(url)}</a></td>"
            if url
            else "<td></td>"
        ),
        f"<td>{escape(str(_row_value(row, 'seen_count') or ''))}</td>",
        f"<td>{escape(str(_row_value(row, 'last_seen_at') or ''))}</td>",
    ]
    return (
        f'<tr{row_class} data-job-row data-job-id="{escape(job_id, quote=True)}" '
        f'data-status="{escape(status, quote=True)}">{"".join(cells)}</tr>'
    )


def render_action_buttons(status: str) -> str:
    if _status_view(status) == "open":
        return (
            '<div class="action-buttons">'
            '<button class="status-button apply-button" data-status-button '
            'data-target-status="applied">Applied</button>'
            '<button class="status-button discard-button" data-status-button '
            'data-target-status="discarded">Discard</button>'
            "</div>"
        )
    return (
        '<div class="action-buttons">'
        '<button class="status-button open-button" data-status-button '
        'data-target-status="new">Move back</button>'
        "</div>"
    )


def _row_status(row: object) -> str:
    return str(_row_value(row, "status") or "new").strip().lower()


def _status_view(status: str) -> str:
    if status in STORED_VIEWS:
        return status
    return "open"


def _row_value(row: object, key: str) -> object | None:
    try:
        return row[key]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return None
