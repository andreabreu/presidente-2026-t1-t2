from __future__ import annotations

import numpy as np
import pandas as pd

from tse.anomalies.stats import benjamini_hochberg, last_digit_chi_square

GROUP_KEYS = ["SG_UF", "NR_TURNO", "NR_VOTAVEL"]


def last_digit_by_group(votes: pd.DataFrame, min_observations: int, cargo: int) -> pd.DataFrame:
    rows = []
    for (uf, turno, votavel), group in votes.groupby(GROUP_KEYS, observed=True):
        counts = group["QT_VOTOS"].to_numpy()
        if len(counts) < min_observations:
            continue
        statistic, p_value, n = last_digit_chi_square(counts)
        digits = np.bincount(counts % 10, minlength=10) / n
        rows.append(
            {
                "SG_UF": uf,
                "NR_TURNO": turno,
                "CD_CARGO": cargo,
                "NR_VOTAVEL": votavel,
                "NM_VOTAVEL": group["NM_VOTAVEL"].iloc[0],
                "n_secoes": n,
                "chi2": statistic,
                "p_valor": p_value,
                "max_desvio_digito": float(np.abs(digits - 0.1).max()),
                "digito_mais_frequente": int(digits.argmax()),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["q_fdr"] = np.nan
    for _, index in frame.groupby("NR_TURNO").groups.items():
        frame.loc[index, "q_fdr"] = benjamini_hochberg(frame.loc[index, "p_valor"].to_numpy())
    return frame
