from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .constants import METHOD_BOUNDS_DUNCAN_DAVIS, METHOD_BOUNDS_RETENCAO_TOTAL


@dataclass
class BoundSet:
    low: np.ndarray
    high: np.ndarray
    feasible: np.ndarray
    origins: list[str]
    destinations: list[str]
    method: str


def duncan_davis_bounds(origins: np.ndarray, destinations: np.ndarray, total: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rows = origins[:, :, None]
    cols = destinations[:, None, :]
    low = np.maximum(0.0, rows + cols - total[:, None, None])
    high = np.minimum(rows, cols)
    return low, high


def full_retention_bounds(
    origins: np.ndarray,
    destinations: np.ndarray,
    total: np.ndarray,
    finalist_origin_index: tuple[int, int],
    finalist_destination_index: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    low, high = duncan_davis_bounds(origins, destinations, total)
    n_units, n_origins, _ = low.shape
    non_finalist = np.array([i not in finalist_origin_index for i in range(n_origins)])
    pool_total = origins[:, non_finalist].sum(axis=1)
    feasible = np.ones(n_units, dtype=bool)
    for origin_idx, dest_idx in zip(finalist_origin_index, finalist_destination_index):
        inflow = destinations[:, dest_idx] - origins[:, origin_idx]
        feasible &= inflow >= 0
        inflow = np.maximum(inflow, 0.0)
        for other_origin in finalist_origin_index:
            retained = origins[:, origin_idx] if other_origin == origin_idx else 0.0
            low[:, other_origin, dest_idx] = retained
            high[:, other_origin, dest_idx] = retained
        for k in np.flatnonzero(non_finalist):
            others = pool_total - origins[:, k]
            low[:, k, dest_idx] = np.maximum(0.0, inflow - others)
            high[:, k, dest_idx] = np.minimum(origins[:, k], inflow)
    return low, high, feasible


def compute_bound_sets(
    origin_frame: pd.DataFrame,
    destination_frame: pd.DataFrame,
    total: np.ndarray,
    finalist_origin_labels: tuple[str, str],
    finalist_destination_labels: tuple[str, str],
) -> list[BoundSet]:
    origins = origin_frame.to_numpy(dtype=float)
    destinations = destination_frame.to_numpy(dtype=float)
    origin_labels = list(origin_frame.columns)
    destination_labels = list(destination_frame.columns)
    low, high = duncan_davis_bounds(origins, destinations, total)
    plain = BoundSet(low, high, np.ones(len(total), dtype=bool), origin_labels, destination_labels, METHOD_BOUNDS_DUNCAN_DAVIS)
    origin_idx = tuple(origin_labels.index(label) for label in finalist_origin_labels)
    dest_idx = tuple(destination_labels.index(label) for label in finalist_destination_labels)
    low_r, high_r, feasible = full_retention_bounds(origins, destinations, total, origin_idx, dest_idx)
    retention = BoundSet(low_r, high_r, feasible, origin_labels, destination_labels, METHOD_BOUNDS_RETENCAO_TOTAL)
    return [plain, retention]


def aggregate_bound_shares(bound_set: BoundSet, origins: np.ndarray, groups: pd.Series) -> pd.DataFrame:
    records = []
    for group_value, index in groups.groupby(groups).indices.items():
        mask = index[bound_set.feasible[index]]
        row_totals = origins[mask].sum(axis=0)
        low = bound_set.low[mask].sum(axis=0)
        high = bound_set.high[mask].sum(axis=0)
        for i, origin in enumerate(bound_set.origins):
            for j, destination in enumerate(bound_set.destinations):
                denominator = row_totals[i] if row_totals[i] > 0 else np.nan
                records.append(
                    {
                        "grupo": group_value,
                        "origem": origin,
                        "destino": destination,
                        "bound_low": low[i, j] / denominator,
                        "bound_high": high[i, j] / denominator,
                        "votos_origem": row_totals[i],
                        "n_unidades": len(index),
                        "n_unidades_viaveis": len(mask),
                        "metodo": bound_set.method,
                    }
                )
    return pd.DataFrame(records)


def unit_bounds_long(bound_set: BoundSet, keys: pd.DataFrame, origins: np.ndarray) -> pd.DataFrame:
    n_units, n_origins, n_dest = bound_set.low.shape
    unit_index = np.repeat(np.arange(n_units), n_origins * n_dest)
    origin_index = np.tile(np.repeat(np.arange(n_origins), n_dest), n_units)
    dest_index = np.tile(np.arange(n_dest), n_units * n_origins)
    frame = keys.iloc[unit_index].reset_index(drop=True)
    frame["origem"] = np.array(bound_set.origins)[origin_index]
    frame["destino"] = np.array(bound_set.destinations)[dest_index]
    frame["votos_origem"] = origins[unit_index, origin_index]
    frame["bound_low_votos"] = bound_set.low.reshape(-1)
    frame["bound_high_votos"] = bound_set.high.reshape(-1)
    denominator = np.where(frame["votos_origem"] > 0, frame["votos_origem"], np.nan)
    frame["bound_low"] = frame["bound_low_votos"] / denominator
    frame["bound_high"] = frame["bound_high_votos"] / denominator
    frame["viavel"] = bound_set.feasible[unit_index]
    frame["metodo"] = bound_set.method
    return frame
