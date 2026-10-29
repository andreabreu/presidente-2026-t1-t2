from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .constants import Z_95


@dataclass(frozen=True)
class WithinEstimate:
    beta: float
    se_cluster: float
    n_obs: int
    n_groups: int
    n_treated: int

    @property
    def ci_low(self) -> float:
        return self.beta - Z_95 * self.se_cluster

    @property
    def ci_high(self) -> float:
        return self.beta + Z_95 * self.se_cluster


def _demean_within(values: np.ndarray, group_codes: np.ndarray, weights: np.ndarray) -> np.ndarray:
    weighted_sum = np.bincount(group_codes, weights=values * weights)
    weight_sum = np.bincount(group_codes, weights=weights)
    return values - (weighted_sum / weight_sum)[group_codes]


def within_estimator(outcome: pd.Series, treatment: pd.Series, group: pd.Series, weights: pd.Series) -> WithinEstimate:
    """Weighted OLS of outcome on treatment with group fixed effects; SE clustered by group."""
    frame = pd.DataFrame({"y": outcome, "x": treatment.astype(float), "g": group, "w": weights}).dropna()
    frame = frame[frame["w"] > 0]
    codes = pd.factorize(frame["g"])[0]
    w = frame["w"].to_numpy(dtype=float)
    y = _demean_within(frame["y"].to_numpy(dtype=float), codes, w)
    x = _demean_within(frame["x"].to_numpy(dtype=float), codes, w)
    sxx = float(np.sum(w * x * x))
    if sxx == 0.0:
        return WithinEstimate(float("nan"), float("nan"), len(frame), int(codes.max() + 1), int(frame["x"].sum()))
    beta = float(np.sum(w * x * y) / sxx)
    residual = y - beta * x
    cluster_scores = np.bincount(codes, weights=w * x * residual)
    se_cluster = float(np.sqrt(np.sum(cluster_scores ** 2)) / sxx)
    return WithinEstimate(beta, se_cluster, len(frame), int(codes.max() + 1), int(frame["x"].sum()))


def margin(votes_leader: int, votes_runner_up: int) -> int:
    return int(votes_leader) - int(votes_runner_up)


def votes_to_flip(votes_leader: int, votes_runner_up: int) -> dict[str, int]:
    difference = margin(votes_leader, votes_runner_up)
    return {
        "margem": difference,
        "votos_trocados_para_inverter": difference // 2 + 1,
        "votos_adicionais_segundo_para_inverter": difference + 1,
    }


def scenario_totals(frame: pd.DataFrame, exclude: pd.Series, leader_col: str, runner_col: str) -> dict[str, float]:
    kept = frame.loc[~exclude]
    leader = int(kept[leader_col].sum())
    runner = int(kept[runner_col].sum())
    return {
        "n_secoes_excluidas": int(exclude.sum()),
        "votos_lider_cenario": leader,
        "votos_segundo_cenario": runner,
        "margem_cenario": margin(leader, runner),
        "share_lider_cenario": leader / (leader + runner) if leader + runner else float("nan"),
    }
