from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd

from .constants import (
    DEFAULT_UTC_OFFSET,
    MIN_GAP_SECONDS,
    NULL_MARKERS,
    RECEPTION_BANDS,
    TIMESTAMP_FORMAT,
    TIMEZONE_GROUP_LABELS,
    TOP_GAPS,
    UTC_OFFSET_BY_UF,
)


def parse_tse_timestamp(values: pd.Series) -> pd.Series:
    cleaned = values.where(~values.isin(NULL_MARKERS))
    return pd.to_datetime(cleaned, format=TIMESTAMP_FORMAT, errors="coerce")


def parse_summary(values: pd.Series, column: str) -> dict:
    parsed = parse_tse_timestamp(values)
    is_null_marker = values.isna() | values.isin(NULL_MARKERS)
    return {
        "column": column,
        "n_rows": int(len(values)),
        "n_null_marker": int(is_null_marker.sum()),
        "n_unparseable": int((parsed.isna() & ~is_null_marker).sum()),
        "share_parseable": float(parsed.notna().mean()) if len(values) else float("nan"),
        "n_distinct_second": int(parsed.dropna().nunique()),
        "min": parsed.min(),
        "max": parsed.max(),
        "length_values": ",".join(str(v) for v in sorted(values.dropna().str.len().unique())),
    }


def timezone_group(uf: pd.Series) -> pd.Series:
    offsets = uf.map(UTC_OFFSET_BY_UF).fillna(DEFAULT_UTC_OFFSET).astype(int)
    return offsets.map(TIMEZONE_GROUP_LABELS)


def reception_band(timestamps: pd.Series) -> pd.Series:
    clock = timestamps.dt.time
    labels = pd.Series(pd.NA, index=timestamps.index, dtype="object")
    for label, start, end in RECEPTION_BANDS:
        mask = clock.notna()
        if start is not None:
            mask &= clock >= start
        if end is not None:
            mask &= clock < end
        labels[mask & labels.isna()] = label
    return labels


def count_by_minute(timestamps: pd.Series, groups: pd.DataFrame | None = None) -> pd.DataFrame:
    minute = timestamps.dt.floor("min").rename("minuto")
    frame = pd.concat([groups, minute], axis=1) if groups is not None else minute.to_frame()
    keys = [*(groups.columns if groups is not None else []), "minuto"]
    return frame.dropna(subset=["minuto"]).groupby(keys, observed=True).size().rename("n_secoes").reset_index()


def find_gaps(timestamps: pd.Series, window_start: pd.Timestamp, window_end: pd.Timestamp,
              min_gap_seconds: int = MIN_GAP_SECONDS, top: int = TOP_GAPS) -> pd.DataFrame:
    inside = timestamps[(timestamps >= window_start) & (timestamps <= window_end)].dropna()
    ordered = np.sort(inside.unique())
    if len(ordered) < 2:
        return pd.DataFrame(columns=["gap_inicio", "gap_fim", "duracao_s", "n_antes_5min", "n_depois_5min"])
    starts, ends = ordered[:-1], ordered[1:]
    durations = (ends - starts) / np.timedelta64(1, "s")
    keep = durations >= min_gap_seconds
    gaps = pd.DataFrame({"gap_inicio": starts[keep], "gap_fim": ends[keep], "duracao_s": durations[keep]})
    gaps = gaps.sort_values("duracao_s", ascending=False).head(top).reset_index(drop=True)
    five_minutes = pd.Timedelta(minutes=5)
    gaps["n_antes_5min"] = [int(((inside >= s - five_minutes) & (inside <= s)).sum()) for s in gaps["gap_inicio"]]
    gaps["n_depois_5min"] = [int(((inside >= e) & (inside <= e + five_minutes)).sum()) for e in gaps["gap_fim"]]
    return gaps


def lag_seconds(reception: pd.Series, first_totalization: pd.Series) -> pd.Series:
    return (first_totalization - reception).dt.total_seconds()


def lag_quantiles(lags: pd.Series, quantiles: tuple[float, ...]) -> dict[str, float]:
    valid = lags.dropna()
    result = {f"q{q:g}".replace(".", "_"): float(valid.quantile(q)) if len(valid) else float("nan") for q in quantiles}
    result["media_s"] = float(valid.mean()) if len(valid) else float("nan")
    result["n"] = int(len(valid))
    return result


def after_clock(timestamps: pd.Series, clock: time) -> pd.Series:
    return timestamps.dt.time >= clock
