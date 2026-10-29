from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def shares(votes: Sequence[float]) -> np.ndarray:
    values = np.asarray(votes, dtype=float)
    total = values.sum()
    if total <= 0:
        return np.zeros_like(values)
    return values / total


def hhi(votes: Sequence[float]) -> float:
    return float(np.square(shares(votes)).sum())


def effective_number(votes: Sequence[float]) -> float:
    concentration = hhi(votes)
    return float(1.0 / concentration) if concentration > 0 else 0.0


def margin_top1_top2(votes: Sequence[float]) -> float:
    ordered = np.sort(np.asarray(votes, dtype=float))[::-1]
    if ordered.size == 0:
        return 0.0
    runner_up = ordered[1] if ordered.size > 1 else 0.0
    return float(ordered[0] - runner_up)


def margin_share_pp(votes: Sequence[float]) -> float:
    ordered = np.sort(shares(votes))[::-1]
    if ordered.size == 0:
        return 0.0
    runner_up = ordered[1] if ordered.size > 1 else 0.0
    return float((ordered[0] - runner_up) * 100)


def concentration_by_group(frame: pd.DataFrame, group_columns: list[str], vote_column: str) -> pd.DataFrame:
    def summarize(group: pd.DataFrame) -> pd.Series:
        votes = group[vote_column].to_numpy()
        return pd.Series(
            {
                "votos_validos": float(votes.sum()),
                "n_candidatos": int((votes > 0).sum()),
                "hhi": hhi(votes),
                "n_efetivo_candidatos": effective_number(votes),
                "margem_votos": margin_top1_top2(votes),
                "margem_pp": margin_share_pp(votes),
            }
        )

    return frame.groupby(group_columns, sort=True).apply(summarize, include_groups=False).reset_index()
