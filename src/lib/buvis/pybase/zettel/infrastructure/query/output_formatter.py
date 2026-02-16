from __future__ import annotations

import csv
import html
import io
import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def _cell(value: Any) -> str | Text:
    if isinstance(value, Text):
        return value
    if value is None:
        return ""
    return str(value)


def format_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    table = Table(show_header=True, header_style="bold")
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*(_cell(row.get(col)) for col in columns))
    Console().print(table)


def format_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(col, "") for col in columns])
    return buf.getvalue()


def format_markdown(rows: list[dict[str, Any]], columns: list[str]) -> str:
    lines = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        cells = [str(row.get(col, "")).replace("|", "\\|") for col in columns]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _filter_columns(rows: list[dict[str, Any]], columns: list[str]) -> list[dict[str, Any]]:
    return [{col: row.get(col, "") for col in columns} for row in rows]


def format_json(rows: list[dict[str, Any]], columns: list[str]) -> str:
    return json.dumps(_filter_columns(rows, columns), indent=2, default=str)


def format_jsonl(rows: list[dict[str, Any]], columns: list[str]) -> str:
    return "\n".join(json.dumps(r, default=str) for r in _filter_columns(rows, columns)) + "\n"


def format_html(rows: list[dict[str, Any]], columns: list[str]) -> str:
    h = html.escape
    header = "".join(f"<th>{h(col)}</th>" for col in columns)
    body = ""
    for row in rows:
        cells = "".join(f"<td>{h(str(row.get(col, '')))}</td>" for col in columns)
        body += f"<tr>{cells}</tr>\n"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Query Results</title>
<style>
  body {{ background: #1e1e2e; color: #cdd6f4; font-family: monospace; margin: 2em; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #45475a; padding: 6px 10px; text-align: left; }}
  th {{ background: #313244; }}
  tr:nth-child(even) {{ background: #181825; }}
</style>
</head><body>
<table><thead><tr>{header}</tr></thead>
<tbody>
{body}</tbody></table>
</body></html>
"""


def format_kanban(rows: list[dict[str, Any]], columns: list[str], group_by: str) -> None:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get(group_by) or "Ungrouped") or "Ungrouped"
        groups.setdefault(key, []).append(row)

    show_cols = [c for c in columns if c not in ("file_path", group_by)]
    con = Console()
    for group_name, group_rows in groups.items():
        lines = []
        for row in group_rows:
            parts = [str(row.get(c, "")) for c in show_cols if row.get(c)]
            lines.append(f"  \u2022 {' | '.join(parts)}")
        body = "\n".join(lines) or "  (empty)"
        title = f"[bold]{group_name}[/bold] ({len(group_rows)})"
        con.print(Panel(body, title=title, expand=True))
    con.print("[dim]Tip: add --tui for interactive kanban[/dim]")


def format_pdf(rows: list[dict[str, Any]], columns: list[str]) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=8)

    col_w = (pdf.w - 20) / max(len(columns), 1)
    pdf.set_font("Helvetica", "B", 9)
    for col in columns:
        pdf.cell(col_w, 8, col[:30], border=1)
    pdf.ln()

    pdf.set_font("Helvetica", size=8)
    for row in rows:
        for col in columns:
            text = str(row.get(col, ""))[:50]
            pdf.cell(col_w, 7, text, border=1)
        pdf.ln()

    return bytes(pdf.output())
