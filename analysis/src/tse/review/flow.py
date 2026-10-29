from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear, minimize

PERCENT = 100.0
CANDIDATE_T1_PATTERN = re.compile(r"^c\d+_t1$")
BOUNDS_UNIT = (0.0, 1.0)
SLSQP_OPTIONS = {"maxiter": 2000, "ftol": 1e-14}


def candidate_number(column: str) -> int:
    return int(column[1:].split("_")[0])


def finalists(candidates: pd.DataFrame) -> tuple[int, int]:
    second = candidates[candidates.NR_TURNO == 2].sort_values("votos", ascending=False)
    return int(second.NR_CANDIDATO.iloc[0]), int(second.NR_CANDIDATO.iloc[1])


def flow_frames(wide: pd.DataFrame, finalist_a: int, finalist_b: int, min_share: float = 0.01) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """Origens T1 e destinos T2 em contagens, com total = max(aptos_t1, aptos_t2) por unidade."""
    t1_columns = [c for c in wide.columns if CANDIDATE_T1_PATTERN.match(c)]
    totals_t1 = {c: wide[c].sum() for c in t1_columns}
    grand = sum(totals_t1.values())
    major = [c for c in t1_columns if totals_t1[c] / grand >= min_share and c not in (f"c{finalist_a}_t1", f"c{finalist_b}_t1")]
    minor = [c for c in t1_columns if c not in major and c not in (f"c{finalist_a}_t1", f"c{finalist_b}_t1")]
    total = np.maximum(wide.aptos_t1, wide.aptos_t2).to_numpy(float)
    origins = pd.DataFrame({"A_t1": wide[f"c{finalist_a}_t1"], "B_t1": wide[f"c{finalist_b}_t1"]})
    for column in major:
        origins[column] = wide[column]
    origins["outros_t1"] = wide[minor].sum(axis=1)
    origins["brancos_nulos_t1"] = wide.brancos_nulos_t1
    origins["abstencao_t1"] = total - wide.comp_t1
    destinations = pd.DataFrame(
        {
            "A_t2": wide[f"c{finalist_a}_t2"],
            "B_t2": wide[f"c{finalist_b}_t2"],
            "brancos_nulos_t2": wide.brancos_nulos_t2,
            "abstencao_t2": total - wide.comp_t2,
        }
    )
    return origins.astype(float), destinations.astype(float), total


def shares(counts: pd.DataFrame, total: np.ndarray) -> np.ndarray:
    return counts.to_numpy(float) / total[:, None]


def goodman_wls(X: np.ndarray, Y: np.ndarray, w: np.ndarray) -> np.ndarray:
    root = np.sqrt(w)[:, None]
    beta, *_ = np.linalg.lstsq(X * root, Y * root, rcond=None)
    return beta


def goodman_bounded(X: np.ndarray, Y: np.ndarray, w: np.ndarray) -> np.ndarray:
    root = np.sqrt(w)[:, None]
    return np.column_stack([lsq_linear(X * root, (Y * root)[:, j], bounds=BOUNDS_UNIT, method="bvls").x for j in range(Y.shape[1])])


def goodman_simplex(X: np.ndarray, Y: np.ndarray, w: np.ndarray) -> np.ndarray:
    root = np.sqrt(w)[:, None]
    Xw, Yw = X * root, Y * root
    gram, cross = Xw.T @ Xw / w.sum(), Xw.T @ Yw / w.sum()
    n_origins, n_destinations = cross.shape

    def objective(flat):
        beta = flat.reshape(n_origins, n_destinations)
        return float(np.trace(beta.T @ gram @ beta) - 2 * np.sum(beta * cross))

    def gradient(flat):
        beta = flat.reshape(n_origins, n_destinations)
        return (2 * gram @ beta - 2 * cross).ravel()

    start = np.full((n_origins, n_destinations), 1.0 / n_destinations)
    constraint = {"type": "eq", "fun": lambda flat: flat.reshape(n_origins, n_destinations).sum(axis=1) - 1.0}
    solution = minimize(objective, start.ravel(), jac=gradient, method="SLSQP", bounds=[BOUNDS_UNIT] * start.size, constraints=[constraint], options=SLSQP_OPTIONS)
    return solution.x.reshape(n_origins, n_destinations)


def transfer_table(beta: np.ndarray, origins: pd.DataFrame, destinations: pd.DataFrame, method: str) -> pd.DataFrame:
    rows = []
    for i, origin in enumerate(origins.columns):
        for j, destination in enumerate(destinations.columns):
            rows.append({"origem": origin, "destino": destination, "estimativa": float(beta[i, j]), "metodo": method})
    return pd.DataFrame(rows)


def duncan_davis_national(origins: pd.DataFrame, destinations: pd.DataFrame, total: np.ndarray) -> pd.DataFrame:
    o, d = origins.to_numpy(float), destinations.to_numpy(float)
    low = np.maximum(0.0, o[:, :, None] + d[:, None, :] - total[:, None, None]).sum(axis=0)
    high = np.minimum(o[:, :, None], d[:, None, :]).sum(axis=0)
    row_total = o.sum(axis=0)
    rows = []
    for i, origin in enumerate(origins.columns):
        for j, destination in enumerate(destinations.columns):
            rows.append({"origem": origin, "destino": destination, "bound_low": low[i, j] / row_total[i], "bound_high": high[i, j] / row_total[i]})
    return pd.DataFrame(rows)


def bootstrap_boundary_share(X: np.ndarray, Y: np.ndarray, w: np.ndarray, fit, cell: tuple[int, int], rng: np.random.Generator, replicates: int, tolerance: float = 1e-9) -> float:
    """Fração de réplicas bootstrap em que a célula fica colada no limite 1.0 (IC percentil degenerado)."""
    n = X.shape[0]
    at_boundary = 0
    for _ in range(replicates):
        idx = rng.integers(0, n, n)
        if fit(X[idx], Y[idx], w[idx])[cell] >= 1.0 - tolerance:
            at_boundary += 1
    return at_boundary / replicates


def proportional_baseline(wide: pd.DataFrame, finalist_a: int, finalist_b: int, groups: pd.Series | None = None) -> pd.DataFrame:
    """Baseline: finalistas retêm tudo e o restante se divide na proporção T1 da dupla, dentro de cada unidade de 'groups'."""
    a1, b1 = wide[f"c{finalist_a}_t1"], wide[f"c{finalist_b}_t1"]
    a2, b2 = wide[f"c{finalist_a}_t2"], wide[f"c{finalist_b}_t2"]
    group = groups if groups is not None else pd.Series("BR", index=wide.index)
    frame = pd.DataFrame({"g": group.values, "a1": a1.values, "b1": b1.values, "a2": a2.values, "b2": b2.values})
    agg = frame.groupby("g").sum()
    agg["share_t1"] = agg.a1 / (agg.a1 + agg.b1)
    agg["baseline_a2"] = agg.share_t1 * (agg.a2 + agg.b2)
    totals = agg[["a2", "b2", "baseline_a2"]].sum()
    observed = totals.a2 / (totals.a2 + totals.b2)
    baseline = totals.baseline_a2 / (totals.a2 + totals.b2)
    return pd.DataFrame([{"share_a_t2_observada": observed, "share_a_t2_baseline": baseline, "excesso_a_pp": (observed - baseline) * PERCENT, "n_grupos": len(agg)}])


def implied_national_shares(beta: np.ndarray, origins: pd.DataFrame) -> np.ndarray:
    return origins.to_numpy(float).sum(axis=0) @ beta
