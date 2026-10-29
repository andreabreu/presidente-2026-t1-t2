from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .constants import (
    FORBIDDEN_WORD_PATTERNS,
    HEADING_PATTERN,
    MANDATORY_PHRASES_WITH_RESTRICTED_WORDS,
    PROSE_ALLOWED_PATTERNS,
    PROSE_EXEMPT_ATTRIBUTE,
    PROSE_EXEMPT_BLOCK_TAGS,
    SOURCED_SPAN_PATTERN,
    YEAR_PATTERN,
)

CONTEXT_CHARS = 40
TAG_PATTERN = re.compile(r"<[^>]+>")
DIGIT_RUN_PATTERN = re.compile(r"\d+([.,]\d+)*")
WHITESPACE_PATTERN = re.compile(r"\s+")


class ReportLintError(ValueError):
    pass


@dataclass(frozen=True)
class LintViolation:
    fragment: str
    context: str

    def __str__(self) -> str:
        return f"'{self.fragment}' em: …{self.context}…"


def _remove_block(html_text: str, tag: str) -> str:
    pattern = re.compile(rf"<{tag}\b[^>]*>.*?</{tag}>", re.DOTALL | re.IGNORECASE)
    return pattern.sub(" ", html_text)


def _remove_exempt_elements(html_text: str) -> str:
    pattern = re.compile(
        rf"<(section|div|article|aside)\b[^>]*{re.escape(PROSE_EXEMPT_ATTRIBUTE)}[^>]*>.*?</\1>",
        re.DOTALL | re.IGNORECASE,
    )
    previous = None
    while previous != html_text:
        previous = html_text
        html_text = pattern.sub(" ", html_text)
    return html_text


def _strip_years_from_headings(html_text: str) -> str:
    return HEADING_PATTERN.sub(lambda match: YEAR_PATTERN.sub(" ", match.group(0)), html_text)


def prose_text(html_text: str) -> str:
    text = _remove_exempt_elements(html_text)
    for tag in PROSE_EXEMPT_BLOCK_TAGS:
        text = _remove_block(text, tag)
    text = SOURCED_SPAN_PATTERN.sub(" ", text)
    text = _strip_years_from_headings(text)
    text = TAG_PATTERN.sub(" ", text)
    text = html.unescape(text)
    for pattern in PROSE_ALLOWED_PATTERNS:
        text = re.sub(pattern, " ", text)
    return WHITESPACE_PATTERN.sub(" ", text)


def digit_lint(html_text: str) -> list[LintViolation]:
    text = prose_text(html_text)
    violations = []
    for match in DIGIT_RUN_PATTERN.finditer(text):
        start = max(0, match.start() - CONTEXT_CHARS)
        end = min(len(text), match.end() + CONTEXT_CHARS)
        violations.append(LintViolation(match.group(0), text[start:end]))
    return violations


def visible_text(html_text: str) -> str:
    text = _remove_block(html_text, "script")
    text = _remove_block(text, "style")
    text = TAG_PATTERN.sub(" ", text)
    return WHITESPACE_PATTERN.sub(" ", html.unescape(text))


def forbidden_words_lint(
    text: str,
    allowed_phrases: tuple[str, ...] = MANDATORY_PHRASES_WITH_RESTRICTED_WORDS,
) -> list[LintViolation]:
    lowered = text.lower()
    for phrase in allowed_phrases:
        lowered = lowered.replace(phrase.lower(), " ")
    violations = []
    for pattern in FORBIDDEN_WORD_PATTERNS:
        for match in re.finditer(pattern, lowered, re.IGNORECASE):
            start = max(0, match.start() - CONTEXT_CHARS)
            end = min(len(lowered), match.end() + CONTEXT_CHARS)
            violations.append(LintViolation(match.group(0), lowered[start:end]))
    return violations


def assert_clean(html_text: str) -> None:
    problems = [f"dígito fora de span data-source: {v}" for v in digit_lint(html_text)]
    problems += [f"palavra proibida: {v}" for v in forbidden_words_lint(visible_text(html_text))]
    if problems:
        raise ReportLintError("\n".join(problems))
