from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import yaml

from .constants import CONFIG_SOURCE, HYPOTHESES_SOURCE
from .data import TableStore

AGG_FIRST = "first"
AGG_SUM = "sum"
AGG_COUNT = "count"
AGG_MEAN = "mean"
AGG_MAX = "max"
AGG_MIN = "min"
AGG_RATIO = "ratio"
AGG_NUNIQUE = "nunique"

FMT_INT = "int"
FMT_PCT1 = "pct1"
FMT_PCT2 = "pct2"
FMT_DEC2 = "dec2"
FMT_DEC3 = "dec3"
FMT_TEXT = "text"
FMT_SHARE_PCT1 = "share_pct1"
FMT_SHARE_PCT2 = "share_pct2"


class QueryError(ValueError):
    pass


def format_pt_br(value: Any, fmt: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if fmt == FMT_TEXT:
        return str(value)
    if fmt == FMT_INT:
        return f"{int(round(float(value))):,}".replace(",", ".")
    if fmt in (FMT_SHARE_PCT1, FMT_SHARE_PCT2):
        value = float(value) * 100
        fmt = FMT_PCT1 if fmt == FMT_SHARE_PCT1 else FMT_PCT2
    decimals = {FMT_PCT1: 1, FMT_PCT2: 2, FMT_DEC2: 2, FMT_DEC3: 3}[fmt]
    text = f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return text + ("%" if fmt in (FMT_PCT1, FMT_PCT2) else "")


def _apply_filter(frame: pd.DataFrame, where: dict[str, Any]) -> pd.DataFrame:
    for column, expected in where.items():
        if column not in frame.columns:
            raise QueryError(f"coluna de filtro inexistente: {column}")
        if isinstance(expected, (list, tuple, set)):
            frame = frame[frame[column].isin(list(expected))]
        elif isinstance(expected, str) and expected.startswith(("<", ">")):
            operator, threshold = expected[:2].strip(), float(expected.lstrip("<>=").strip())
            series = pd.to_numeric(frame[column], errors="coerce")
            comparisons = {"<": series < threshold, "<=": series <= threshold, ">": series > threshold, ">=": series >= threshold}
            frame = frame[comparisons[operator]]
        elif expected is None:
            frame = frame[frame[column].isna()]
        else:
            frame = frame[frame[column] == expected]
    return frame


def evaluate(frame: pd.DataFrame, column: str, where: dict[str, Any], aggregate: str) -> Any:
    subset = _apply_filter(frame, where)
    if aggregate == AGG_COUNT:
        return int(len(subset))
    if aggregate == AGG_RATIO:
        numerator, denominator = column.split("/")
        total = float(subset[denominator].sum())
        return float(subset[numerator].sum()) / total if total else None
    if column not in subset.columns:
        raise QueryError(f"coluna inexistente: {column}")
    series = subset[column]
    if aggregate == AGG_FIRST:
        if len(series) != 1:
            raise QueryError(f"consulta '{column}' com filtro {where} devolveu {len(series)} linhas (esperava uma)")
        return series.iloc[0]
    if aggregate == AGG_NUNIQUE:
        return int(series.nunique())
    return getattr(series, aggregate)()


@dataclass
class QueryRegistry:
    store: TableStore
    queries: dict[str, dict] = field(default_factory=dict)
    config_values: dict[str, Any] = field(default_factory=dict)
    hypotheses: list[dict] = field(default_factory=list)

    def _register(self, query_id: str, record: dict) -> None:
        if query_id in self.queries and self.queries[query_id] != record:
            raise QueryError(f"query_id duplicado com definição diferente: {query_id}")
        self.queries[query_id] = record

    def value(
        self,
        query_id: str,
        source_id: str,
        column: str,
        where: dict[str, Any] | None = None,
        aggregate: str = AGG_FIRST,
    ) -> Any:
        where = where or {}
        raw = evaluate(self.store.frame(source_id), column, where, aggregate)
        self._register(
            query_id,
            {
                "id": query_id,
                "source": self.store.csv_relative_path(source_id),
                "filter": {k: (list(v) if isinstance(v, (set, tuple)) else v) for k, v in where.items()},
                "aggregate": aggregate,
                "column": column,
                "value": _plain(raw),
            },
        )
        self.store.register(source_id)
        return raw

    def span(
        self,
        query_id: str,
        source_id: str,
        column: str,
        fmt: str = FMT_INT,
        where: dict[str, Any] | None = None,
        aggregate: str = AGG_FIRST,
    ) -> str:
        raw = self.value(query_id, source_id, column, where, aggregate)
        return _span(self.store.csv_relative_path(source_id), query_id, format_pt_br(_plain(raw), fmt))

    def config_span(self, query_id: str, dotted_key: str, fmt: str = FMT_DEC2) -> str:
        node: Any = self.store.config
        for part in dotted_key.split("."):
            node = node[part]
        self._register(query_id, {"id": query_id, "source": CONFIG_SOURCE, "filter": {}, "aggregate": "key", "column": dotted_key, "value": _plain(node)})
        return _span(CONFIG_SOURCE, query_id, format_pt_br(node, fmt))

    def hypotheses_count_span(self, query_id: str, where: dict[str, Any]) -> str:
        count = sum(1 for item in self.hypotheses if all(item.get(k) == v for k, v in where.items()))
        self._register(query_id, {"id": query_id, "source": HYPOTHESES_SOURCE, "filter": where, "aggregate": AGG_COUNT, "column": "id", "value": count})
        return _span(HYPOTHESES_SOURCE, query_id, format_pt_br(count, FMT_INT))

    def literal_span(self, query_id: str, source: str, label: str, value: Any, fmt: str = FMT_INT) -> str:
        self._register(query_id, {"id": query_id, "source": source, "filter": {}, "aggregate": "file", "column": label, "value": _plain(value)})
        return _span(source, query_id, format_pt_br(value, fmt))

    def dump_yaml(self) -> str:
        return yaml.safe_dump({"queries": list(self.queries.values())}, allow_unicode=True, sort_keys=False)


def _span(source: str, query_id: str, text: str) -> str:
    return f'<span class="num" data-source="{html.escape(source)}" data-query="{html.escape(query_id)}">{html.escape(text)}</span>'


def _plain(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value
