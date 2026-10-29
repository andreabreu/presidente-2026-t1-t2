from __future__ import annotations

import html
import json
from typing import Any

from .data import TableStore

CHART_BAR = "bar"
CHART_HBAR = "hbar"
CHART_HIST = "hist"
CHART_SCATTER = "scatter"
CHART_FIGURE = "figure"
CHART_SANKEY = "sankey"


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def attrs(**values: Any) -> str:
    parts = []
    for key, value in values.items():
        if value is None or value is False:
            continue
        name = key.replace("_", "-")
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        parts.append(f'{name}="{esc(value)}"')
    return " ".join(parts)


def table(store: TableStore, source_id: str, columns: list[str] | None = None, title: str | None = None, page_size: int | None = None, filter: dict | None = None) -> str:
    store.register(source_id)
    meta = store.meta(source_id)
    heading = title or meta.get("title_pt", source_id)
    return (
        f'<div class="tbl" {attrs(data_table=source_id, data_cols=",".join(columns) if columns else None, data_page=page_size, data_filter=filter)}>'
        f'<div class="tbl-title">{esc(heading)} <code>{esc(source_id)}</code></div></div>'
    )


def chart(kind: str, source_id: str | None, title: str, **options: Any) -> str:
    return f'<div class="chart" {attrs(data_chart=kind, data_table=source_id, data_title=title, **options)}></div>'


def figure(figure_id: str, title: str) -> str:
    return chart(CHART_FIGURE, None, title, data_figure=figure_id)


def banner(text: str, level: str = "info") -> str:
    return f'<div class="banner banner-{level}">{text}</div>'


def placeholder(text: str) -> str:
    return f'<div class="placeholder">{esc(text)}</div>'


def section(title: str, body: str, anchor: str | None = None) -> str:
    anchor_attr = f' id="{esc(anchor)}"' if anchor else ""
    return f"<section{anchor_attr}><h2>{title}</h2>{body}</section>"


def paragraph(text: str) -> str:
    return f"<p>{text}</p>"


def bullet_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def static_table(headers: list[str], rows: list[list[str]], css_class: str = "md-table") -> str:
    head = "".join(f"<th>{header}</th>" for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<table class="{css_class}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def verbatim(body_html: str, note: str) -> str:
    return f'<div class="verbatim" data-lint="exempt"><div class="banner banner-info">{note}</div>{body_html}</div>'
