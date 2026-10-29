from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear, minimize

from .constants import (
    BOOTSTRAP_REPLICATES,
    CI_LOWER_PCT,
    CI_UPPER_PCT,
    METHOD_BASELINE_PROPORCIONAL,
    METHOD_GOODMAN_RESTRITO,
    METHOD_GOODMAN_SIMPLEX,
    METHOD_GOODMAN_WLS,
)
from .data import VOTE_T1_PREFIX, VOTE_T2_PREFIX, Contest

PERCENT = 100.0


@dataclass
class GoodmanResult:
    estimate: np.ndarray
    ci_low: np.ndarray
    ci_high: np.ndarray
    origins: list[str]
    destinations: list[str]
    method: str
    n_units: int
    bootstrap_replicates: int

    def to_frame(self) -> pd.DataFrame:
        records = []
        row_sums = self.estimate.sum(axis=1)
        for i, origin in enumerate(self.origins):
            for j, destination in enumerate(self.destinations):
                records.append(
                    {
                        "origem": origin,
                        "destino": destination,
                        "estimativa": self.estimate[i, j],
                        "ci_low": self.ci_low[i, j],
                        "ci_high": self.ci_high[i, j],
                        "soma_linha_origem": row_sums[i],
                        "metodo": self.method,
                        "n_unidades": self.n_units,
                        "n_bootstrap": self.bootstrap_replicates,
                    }
                )
        return pd.DataFrame(records)


def weighted_design(X: np.ndarray, Y: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    root = np.sqrt(weights)[:, None]
    return X * root, Y * root


def goodman_wls(X: np.ndarray, Y: np.ndarray, weights: np.ndarray) -> np.ndarray:
    Xw, Yw = weighted_design(X, Y, weights)
    coefficients, *_ = np.linalg.lstsq(Xw, Yw, rcond=None)
    return coefficients


def goodman_bounded(X: np.ndarray, Y: np.ndarray, weights: np.ndarray) -> np.ndarray:
    Xw, Yw = weighted_design(X, Y, weights)
    columns = [lsq_linear(Xw, Yw[:, j], bounds=(0.0, 1.0), method="bvls").x for j in range(Yw.shape[1])]
    return np.column_stack(columns)


def goodman_simplex(X: np.ndarray, Y: np.ndarray, weights: np.ndarray) -> np.ndarray:
    Xw, Yw = weighted_design(X, Y, weights)
    scale = weights.sum()
    gram = Xw.T @ Xw / scale
    cross = Xw.T @ Yw / scale
    n_origins, n_destinations = cross.shape
    initial = project_rows_to_simplex(goodman_wls(X, Y, weights))

    def objective(flat: np.ndarray) -> float:
        beta = flat.reshape(n_origins, n_destinations)
        return float(np.einsum("ij,ik,kj->", beta, gram, beta) - 2 * np.einsum("ij,ij->", beta, cross))

    def gradient(flat: np.ndarray) -> np.ndarray:
        beta = flat.reshape(n_origins, n_destinations)
        return (2 * gram @ beta - 2 * cross).ravel()

    row_sum_jacobian = np.kron(np.eye(n_origins), np.ones((1, n_destinations)))
    row_sum_constraint = {
        "type": "eq",
        "fun": lambda flat: flat.reshape(n_origins, n_destinations).sum(axis=1) - 1.0,
        "jac": lambda flat: row_sum_jacobian,
    }
    solution = minimize(
        objective, initial.ravel(), jac=gradient, method="SLSQP",
        bounds=[(0.0, 1.0)] * (n_origins * n_destinations), constraints=[row_sum_constraint],
        options={"maxiter": 1000, "ftol": 1e-14},
    )
    return solution.x.reshape(n_origins, n_destinations)


def project_rows_to_simplex(matrix: np.ndarray) -> np.ndarray:
    clipped = np.clip(matrix, 0.0, 1.0)
    row_sums = clipped.sum(axis=1, keepdims=True)
    uniform = np.full_like(clipped, 1.0 / clipped.shape[1])
    return np.where(row_sums > 0, clipped / np.where(row_sums > 0, row_sums, 1.0), uniform)


FITTERS = {METHOD_GOODMAN_WLS: goodman_wls, METHOD_GOODMAN_RESTRITO: goodman_bounded, METHOD_GOODMAN_SIMPLEX: goodman_simplex}


def bootstrap_goodman(
    X: np.ndarray,
    Y: np.ndarray,
    weights: np.ndarray,
    method: str,
    rng: np.random.Generator,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    fit = FITTERS[method]
    point = fit(X, Y, weights)
    n = X.shape[0]
    draws = np.empty((replicates,) + point.shape)
    for r in range(replicates):
        idx = rng.integers(0, n, n)
        draws[r] = fit(X[idx], Y[idx], weights[idx])
    return point, np.percentile(draws, CI_LOWER_PCT, axis=0), np.percentile(draws, CI_UPPER_PCT, axis=0)


def shares(counts: pd.DataFrame, denominator: np.ndarray) -> np.ndarray:
    safe = np.where(denominator > 0, denominator, np.nan)
    return counts.to_numpy(dtype=float) / safe[:, None]


def fit_goodman(
    origin_counts: pd.DataFrame,
    destination_counts: pd.DataFrame,
    total: np.ndarray,
    weights: np.ndarray,
    method: str,
    rng: np.random.Generator,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> GoodmanResult:
    X = shares(origin_counts, total)
    Y = shares(destination_counts, total)
    keep = np.isfinite(X).all(axis=1) & np.isfinite(Y).all(axis=1) & (weights > 0)
    point, low, high = bootstrap_goodman(X[keep], Y[keep], weights[keep], method, rng, replicates)
    return GoodmanResult(
        point, low, high, list(origin_counts.columns), list(destination_counts.columns), method, int(keep.sum()), replicates
    )


def proportional_baseline_by_group(wide: pd.DataFrame, contest: Contest, groups: pd.Series) -> pd.DataFrame:
    a, b = contest.finalist_a, contest.finalist_b
    a1 = wide[f"{VOTE_T1_PREFIX}{a}"]
    b1 = wide[f"{VOTE_T1_PREFIX}{b}"]
    a2 = wide[f"{VOTE_T2_PREFIX}{a}"]
    b2 = wide[f"{VOTE_T2_PREFIX}{b}"]
    pair_share_a = a1.div((a1 + b1).where((a1 + b1) > 0, np.nan))
    baseline_a2 = pair_share_a * (a2 + b2)
    frame = pd.DataFrame(
        {
            "grupo": groups.values,
            "votos_t1_a": a1,
            "votos_t1_b": b1,
            "votos_t2_a": a2,
            "votos_t2_b": b2,
            "baseline_t2_a": baseline_a2,
            "baseline_t2_b": (a2 + b2) - baseline_a2,
        }
    )
    agg = frame.groupby("grupo").sum(numeric_only=True).reset_index()
    agg["share_a_t1_dupla"] = agg["votos_t1_a"] / (agg["votos_t1_a"] + agg["votos_t1_b"])
    agg["share_a_t2_observada"] = agg["votos_t2_a"] / (agg["votos_t2_a"] + agg["votos_t2_b"])
    agg["share_a_t2_baseline"] = agg["baseline_t2_a"] / (agg["votos_t2_a"] + agg["votos_t2_b"])
    agg["excesso_a_votos"] = agg["votos_t2_a"] - agg["baseline_t2_a"]
    agg["excesso_a_pp"] = (agg["share_a_t2_observada"] - agg["share_a_t2_baseline"]) * PERCENT
    agg["metodo"] = METHOD_BASELINE_PROPORCIONAL
    agg["finalista_a"] = a
    agg["finalista_b"] = b
    return agg


def baseline_flow_rows(agg_row: pd.Series, contest: Contest, origins: list[str]) -> list[dict]:
    share_a = agg_row["share_a_t1_dupla"]
    dest_a = contest.destination_label(contest.finalist_a)
    dest_b = contest.destination_label(contest.finalist_b)
    rows = []
    for origin in origins:
        if origin == contest.origin_label(contest.finalist_a):
            allocation = {dest_a: 1.0, dest_b: 0.0}
        elif origin == contest.origin_label(contest.finalist_b):
            allocation = {dest_a: 0.0, dest_b: 1.0}
        else:
            allocation = {dest_a: share_a, dest_b: 1.0 - share_a}
        for destination, value in allocation.items():
            rows.append({"origem": origin, "destino": destination, "estimativa": value, "metodo": METHOD_BASELINE_PROPORCIONAL})
    return rows
