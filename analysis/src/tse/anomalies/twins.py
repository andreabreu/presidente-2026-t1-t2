from __future__ import annotations

import numpy as np
import pandas as pd

from tse.anomalies.stats import (
    benjamini_hochberg,
    count_identical_row_pairs,
    permutation_p_value,
    permuted_identical_pairs,
)

PAIR_KEYS = ["CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]


def identical_pairs(vectors: pd.DataFrame) -> pd.DataFrame:
    duplicated = vectors[vectors.duplicated(["CD_MUNICIPIO", "NR_TURNO", "vetor"], keep=False)]
    rows = []
    for (municipio, turno, vector), group in duplicated.groupby(["CD_MUNICIPIO", "NR_TURNO", "vetor"], sort=False):
        records = group.sort_values(["NR_ZONA", "NR_SECAO"]).to_dict("records")
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                a, b = records[i], records[j]
                rows.append(
                    {
                        "SG_UF": a["SG_UF"],
                        "CD_MUNICIPIO": municipio,
                        "NM_MUNICIPIO": a["NM_MUNICIPIO"],
                        "NR_TURNO": turno,
                        "NR_ZONA_a": a["NR_ZONA"],
                        "NR_SECAO_a": a["NR_SECAO"],
                        "NR_ZONA_b": b["NR_ZONA"],
                        "NR_SECAO_b": b["NR_SECAO"],
                        "QT_COMPARECIMENTO": a["QT_COMPARECIMENTO"],
                        "vetor": vector,
                    }
                )
    return pd.DataFrame(rows)


def municipio_wide_matrices(long_votes: pd.DataFrame) -> dict[int, np.ndarray]:
    wide = long_votes.pivot_table(
        index=PAIR_KEYS, columns="NR_VOTAVEL", values="QT_VOTOS", aggfunc="sum", fill_value=0
    )
    matrices = {}
    for municipio, block in wide.groupby(level="CD_MUNICIPIO", sort=False):
        matrices[int(municipio)] = block.to_numpy(dtype=np.int32)
    return matrices


def permutation_null_by_municipio(
    matrices: dict[int, np.ndarray], n_permutations: int, seed: int
) -> pd.DataFrame:
    rows = []
    for municipio, matrix in matrices.items():
        if len(matrix) < 2:
            continue
        rng = np.random.default_rng([seed, municipio])
        observed = count_identical_row_pairs(matrix)
        null = permuted_identical_pairs(matrix, n_permutations, rng)
        rows.append(
            {
                "CD_MUNICIPIO": municipio,
                "n_secoes_elegiveis": len(matrix),
                "pares_identicos_observados": observed,
                "pares_identicos_nulo_media": float(null.mean()),
                "pares_identicos_nulo_p95": float(np.percentile(null, 95)),
                "p_permutacao": permutation_p_value(observed, null),
                "n_permutacoes": n_permutations,
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["q_fdr"] = benjamini_hochberg(frame["p_permutacao"].to_numpy())
    return frame
