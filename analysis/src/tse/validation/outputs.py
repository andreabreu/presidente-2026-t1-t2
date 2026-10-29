from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..config import load_config

SCRIPT = "python -m tse.validation"
UNIT_BY_TABLE = {
    "val_balanco_secao": "seção × turno × cargo",
    "val_balanco_munzona": "município/zona × turno × cargo",
    "val_legenda_partido": "município/zona × turno × cargo × partido",
    "val_limites_fisicos": "seção (ou mun/zona) × turno × cargo",
    "val_agregacao_niveis": "nível de agregação × turno × cargo",
    "val_divergencia_fontes": "chave de agregação × turno × cargo",
    "val_br_vs_brasil": "linha × turno × cargo",
    "val_cobertura_cand": "candidato × turno × cargo",
    "val_timestamps": "linha × turno × cargo",
    "val_inconsistencias": "uma linha por inconsistência",
    "val_resumo": "uma linha por check",
    "val_timestamps_geracao": "dataset × escopo",
    "val_tamanho_secao": "UF × turno",
}

GROUP_COLUMN_DOCS = {
    "check_id": "identificador do check (ver val_resumo)",
    "hypothesis_id": "id em hypotheses.yaml",
    "source_table": "tabela de saída à qual o check pertence",
    "tipo": "descrição textual da identidade/comparação",
    "identidade_exata": "True se a identidade é esperada valer em 100% das linhas; False se é identidade candidata/informativa",
    "NR_TURNO": "turno",
    "CD_CARGO": "código do cargo (1 Presidente, 3 Governador, 5 Senador, 6 Dep. Federal, 7 Dep. Estadual, 8 Dep. Distrital)",
    "SG_UF": "UF (ZZ = exterior)",
    "n_rows_tested": "linhas testadas",
    "n_violations": "linhas que violam a identidade",
    "share_violations": "n_violations / n_rows_tested",
    "sum_abs_delta": "soma de |observado − esperado| nas violações",
    "max_abs_delta": "máximo de |observado − esperado| nas violações",
    "sum_expected": "soma do lado esperado (base para magnitude relativa)",
    "rel_magnitude": "sum_abs_delta / Σ|esperado|",
    "max_rel_delta": "máximo de |observado − esperado| / |esperado| nas violações",
}

VIOLATION_COLUMN_DOCS = {
    **{k: GROUP_COLUMN_DOCS[k] for k in ("check_id", "hypothesis_id", "source_table", "tipo", "identidade_exata")},
    "classe": "classe de achado (documental)",
    "SG_UF": "UF", "CD_MUNICIPIO": "código TSE do município", "NR_ZONA": "zona", "NR_SECAO": "seção",
    "NR_TURNO": "turno", "CD_CARGO": "cargo",
    "chave_extra": "chave adicional (SQ_CANDIDATO, NR_PARTIDO, métrica ou NR_VOTAVEL)",
    "expected": "valor do lado esquerdo/esperado", "observed": "valor do lado direito/observado",
    "delta_abs": "observed − expected", "delta_rel": "delta_abs / |expected|",
}


def tables_dir() -> Path:
    path = load_config()["outputs_dir"] / "tables"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_table(source_id: str, frame: pd.DataFrame, title_pt: str, description_pt: str, hypothesis_ids: list[str],
                columns: dict[str, str], method: str, caveats_pt: list[str]) -> None:
    directory = tables_dir()
    frame.to_csv(directory / f"{source_id}.csv", index=False)
    frame.to_parquet(directory / f"{source_id}.parquet", index=False)
    meta = {
        "source_id": source_id,
        "title_pt": title_pt,
        "description_pt": description_pt,
        "script": SCRIPT,
        "hypothesis_ids": hypothesis_ids,
        "unit": UNIT_BY_TABLE.get(source_id, ""),
        "n_rows": int(len(frame)),
        "columns": {name: columns.get(name, "") for name in frame.columns},
        "method": method,
        "caveats_pt": caveats_pt,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(directory / f"{source_id}.meta.json", "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
