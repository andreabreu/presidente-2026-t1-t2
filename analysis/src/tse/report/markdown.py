from __future__ import annotations

import html
import re

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![*\w])\*(?!\*)(.+?)\*(?!\*)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
ORDERED_ITEM = re.compile(r"^\s*\d+\.\s+(.*)$")
UNORDERED_ITEM = re.compile(r"^\s*[-*]\s+(.*)$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}")


def inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = INLINE_CODE.sub(r"<code>\1</code>", escaped)
    escaped = BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = ITALIC.sub(r"<em>\1</em>", escaped)
    return LINK.sub(r'<a href="\2">\1</a>', escaped)


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def parse_pipe_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    header = _split_table_row(lines[0])
    body = [_split_table_row(line) for line in lines[2:] if line.strip()]
    return header, body


def _render_table(lines: list[str]) -> str:
    header, body = parse_pipe_table(lines)
    head = "".join(f"<th>{inline(cell)}</th>" for cell in header)
    rows = "".join("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>" for row in body)
    return f'<table class="md-table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'


def markdown_to_html(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    list_tag: str | None = None
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            output.append(f"</{list_tag}>")
            list_tag = None

    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            flush_paragraph()
            close_list()
            block: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                block.append(lines[index])
                index += 1
            output.append(f"<pre><code>{html.escape(chr(10).join(block))}</code></pre>")
            index += 1
            continue
        if line.strip().startswith("|") and index + 1 < len(lines) and TABLE_SEPARATOR.match(lines[index + 1]):
            flush_paragraph()
            close_list()
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            output.append(_render_table(table_lines))
            continue
        heading = HEADING.match(line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            output.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            index += 1
            continue
        item = ORDERED_ITEM.match(line) or UNORDERED_ITEM.match(line)
        if item:
            flush_paragraph()
            tag = "ol" if ORDERED_ITEM.match(line) else "ul"
            if list_tag != tag:
                close_list()
                output.append(f"<{tag}>")
                list_tag = tag
            output.append(f"<li>{inline(item.group(1))}</li>")
            index += 1
            continue
        if not line.strip():
            flush_paragraph()
            close_list()
            index += 1
            continue
        if list_tag and line.startswith("  "):
            output[-1] = output[-1][: -len("</li>")] + " " + inline(line.strip()) + "</li>"
            index += 1
            continue
        close_list()
        paragraph.append(line.strip())
        index += 1
    flush_paragraph()
    close_list()
    return "\n".join(output)


def extract_section(text: str, heading_prefix: str) -> str:
    lines = text.splitlines()
    collected: list[str] = []
    inside = False
    for line in lines:
        if line.startswith(heading_prefix):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            collected.append(line)
    return "\n".join(collected).strip()
