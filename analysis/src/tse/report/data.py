from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from tse.config import ANALYSIS_ROOT, load_config
from tse.tables import tables_dir

SECTION_UNIT_MARKERS = ("secao", "seção")
TABLES_RELATIVE_DIR = "outputs/tables"


@dataclass(frozen=True)
class TableSpec:
    columns: tuple[str, ...] | None = None
    sort_by: str | None = None
    ascending: bool = False
    sort_abs: bool = False
    row_limit: int | None = None


@dataclass
class EmbeddedTable:
    source_id: str
    columns: list[str]
    rows: list[list[Any]]
    n_total: int
    n_shown: int
    truncated: bool
    sort_note: str


@dataclass
class TableStore:
    directory: Path = field(default_factory=tables_dir)
    config: dict = field(default_factory=load_config)
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    metas: dict[str, dict] = field(default_factory=dict)
    specs: dict[str, TableSpec] = field(default_factory=dict)

    def exists(self, source_id: str) -> bool:
        return (self.directory / f"{source_id}.parquet").exists() or (self.directory / f"{source_id}.csv").exists()

    def available_ids(self) -> list[str]:
        return sorted(path.stem.replace(".meta", "") for path in self.directory.glob("*.meta.json"))

    def meta(self, source_id: str) -> dict:
        if source_id not in self.metas:
            path = self.directory / f"{source_id}.meta.json"
            self.metas[source_id] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
                "source_id": source_id,
                "title_pt": source_id,
                "columns": {},
                "method": "",
                "caveats_pt": [],
                "n_rows": None,
            }
        return self.metas[source_id]

    def frame(self, source_id: str) -> pd.DataFrame:
        if source_id not in self.frames:
            parquet = self.directory / f"{source_id}.parquet"
            csv = self.directory / f"{source_id}.csv"
            self.frames[source_id] = pd.read_parquet(parquet) if parquet.exists() else pd.read_csv(csv)
        return self.frames[source_id]

    def csv_relative_path(self, source_id: str) -> str:
        return f"{TABLES_RELATIVE_DIR}/{source_id}.csv"

    def register(self, source_id: str, spec: TableSpec | None = None) -> None:
        self.specs.setdefault(source_id, spec or TableSpec())
        if spec is not None:
            self.specs[source_id] = spec

    def _row_limit_for(self, source_id: str, spec: TableSpec) -> int:
        report_config = self.config.get("report", {})
        if spec.row_limit is not None:
            return spec.row_limit
        explicit = report_config.get("row_limits", {}).get(source_id)
        if explicit is not None:
            return int(explicit)
        unit = str(self.meta(source_id).get("unit", "")).lower()
        if any(marker in unit for marker in SECTION_UNIT_MARKERS):
            return int(report_config.get("max_rows_secao", 2000))
        return int(report_config.get("max_rows_default", 20000))

    def embedded(self, source_id: str) -> EmbeddedTable:
        spec = self.specs.get(source_id, TableSpec())
        frame = self.frame(source_id)
        if spec.columns:
            frame = frame[[column for column in spec.columns if column in frame.columns]]
        sort_note = ""
        if spec.sort_by and spec.sort_by in frame.columns:
            key = frame[spec.sort_by].abs() if spec.sort_abs else frame[spec.sort_by]
            frame = frame.loc[key.sort_values(ascending=spec.ascending, na_position="last").index]
            direction = "crescente" if spec.ascending else "decrescente"
            sort_note = f"ordenada por {'|' + spec.sort_by + '|' if spec.sort_abs else spec.sort_by} ({direction})"
        limit = self._row_limit_for(source_id, spec)
        n_total = int(len(self.frame(source_id)))
        truncated = n_total > limit
        shown = frame.head(limit) if truncated else frame
        return EmbeddedTable(
            source_id=source_id,
            columns=[str(column) for column in shown.columns],
            rows=[[_json_safe(value) for value in row] for row in shown.itertuples(index=False, name=None)],
            n_total=n_total,
            n_shown=int(len(shown)),
            truncated=truncated,
            sort_note=sort_note,
        )


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (bool, int, str)):
        return value
    if hasattr(value, "item"):
        scalar = value.item()
        if isinstance(scalar, float) and (math.isnan(scalar) or math.isinf(scalar)):
            return None
        return scalar
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def relative_to_analysis(path: Path) -> str:
    return str(path.resolve().relative_to(ANALYSIS_ROOT))
