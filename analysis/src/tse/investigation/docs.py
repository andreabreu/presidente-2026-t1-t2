"""Gera timeline, matriz de evidências e notas jurídicas a partir das tabelas inv_*."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tse.config import ANALYSIS_ROOT
from tse.tables import get_logger, tables_dir

logger = get_logger("investigation")
ROOT = ANALYSIS_ROOT / "investigation"


def _read(source_id: str) -> pd.DataFrame | None:
    path = tables_dir() / f"{source_id}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    path = tables_dir() / f"{source_id}.csv"
    return pd.read_csv(path) if path.exists() else None


def write_timeline() -> Path:
    ROOT.joinpath("timeline").mkdir(parents=True, exist_ok=True)
    events = []
    janela = _read("inv_janela_suspensao")
    if janela is not None and len(janela):
        row = janela.iloc[0].to_dict()
        events.append(
            {
                "id": "janela_empirica_t2",
                "when": str(row.get("inicio") or row.get("t_inicio") or "2026-10-25"),
                "label": "Janela empírica de recepção BU (2º turno) observada nos CSVs",
                "status": "confirmado_nos_dados",
                "source_id": "inv_janela_suspensao",
                "payload": {k: (None if pd.isna(v) else v) for k, v in row.items()},
            }
        )
    pos19 = _read("inv_secoes_pos_19h_resumo")
    if pos19 is not None:
        events.append(
            {
                "id": "pos_19h_resumo",
                "when": "2026-10-25T19:00:00-03:00",
                "label": "Resumo de seções com timestamp após 19h (2º turno)",
                "status": "confirmado_nos_dados",
                "source_id": "inv_secoes_pos_19h_resumo",
                "n_rows": int(len(pos19)),
            }
        )
    flow_path = ROOT / "data" / "flow_bu.json"
    if flow_path.exists():
        flow = json.loads(flow_path.read_text(encoding="utf-8"))
        events.append(
            {
                "id": "flow_bu",
                "when": flow.get("generated_at"),
                "label": "Fluxograma documental do caminho do BU até a totalização",
                "status": "documental",
                "source": "investigation/data/flow_bu.json",
                "nodes": len(flow.get("nodes", [])),
            }
        )
    events.append(
        {
            "id": "limitacao_bu",
            "when": datetime.now(timezone.utc).isoformat(),
            "label": "BUs/logs/hashes não baixados — investigação temporal não é auditoria forense de urna",
            "status": "limitacao",
        }
    )
    path = ROOT / "timeline" / "timeline.json"
    path.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "events": events}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def write_evidence_matrix() -> Path:
    rows = [
        {"questao": "Identidades de balanço fecham?", "status": "sim_com_correcoes", "fonte": "val_resumo", "classe": "documental"},
        {"questao": "Placar Presidente munzona = seção?", "status": "a_verificar_no_review", "fonte": "desc_placar_presidente", "classe": "documental"},
        {"questao": "Há BU/hash/log locais?", "status": "nao", "fonte": "downloads/", "classe": "forense"},
        {"questao": "Timestamps de recepção disponíveis?", "status": "sim_parcial", "fonte": "detalhe_votacao_secao.DT_RECEBIMENTO_BU_HOR_TSE", "classe": "documental"},
        {"questao": "Janela pós-19h altera margem de forma material?", "status": "ver inv_impacto_margem", "fonte": "inv_impacto_margem", "classe": "estatistico"},
        {"questao": "Seções unânimes = irregularidade?", "status": "nao_inferivel", "fonte": "anom_secao_unanime", "classe": "estatistico"},
        {"questao": "Transferência A→B individual observável?", "status": "nao", "fonte": "swing_*", "classe": "estatistico"},
    ]
    path = ROOT / "evidence_matrix.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def write_legal_note() -> Path:
    ROOT.joinpath("legal").mkdir(parents=True, exist_ok=True)
    text = """# Nota jurídica / limites de interpretação (não é parecer advocatício)

## O que os dados abertos permitem
- Verificar consistência interna dos CSVs de totalização (identidades, agregações, BR vs BRASIL).
- Descrever placares, participação e padrões territoriais.
- Gerar **filas de auditoria documental** (risk_score), não juízos de ilicitude.

## O que não permitem
- Afirmar adulteração de urna, voto ou transmissão sem Boletim de Urna, log e cadeia de custódia.
- Inferir o voto de eleitor individual a partir de agregados (falácia ecológica).
- Transformar p-valor / q_fdr / risk_score em “probabilidade de fraude”.

## Referências de processo (contexto)
- Resolução TSE sobre totalização e disponibilização de BUs (ver checklist em `docs/FORENSIC_CHECKLIST.md`).
- Lei de Acesso à Informação / dados abertos: uso legítimo para auditoria cidadã estatística e documental.

## Linguagem recomendada
Usar: inconsistência documental, anomalia estatística, requer auditoria de BU.
Evitar: fraude, manipulação, urna viciada — salvo citação explícita de fonte forense independente.
"""
    path = ROOT / "legal" / "limites.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_sources_index() -> Path:
    ROOT.joinpath("sources").mkdir(parents=True, exist_ok=True)
    text = """# Fontes usadas na investigação 25/10

- CSVs TSE 2026 em `downloads/resultados-2026/` (detalhe_votacao_secao, votacao_secao_BR).
- Tabelas `outputs/tables/inv_*.csv`.
- `investigation/data/flow_bu.json` (fluxo documental + janela empírica).
- Portal de Dados Abertos do TSE e notícias públicas citadas no flow (quando status=confirmado).

Arquivos brutos auxiliares em `investigation/sources/raw/` (se houver).
"""
    path = ROOT / "sources" / "README.md"
    path.write_text(text, encoding="utf-8")
    return path


def generate_all() -> dict[str, str]:
    paths = {
        "timeline": str(write_timeline()),
        "evidence": str(write_evidence_matrix()),
        "legal": str(write_legal_note()),
        "sources": str(write_sources_index()),
    }
    logger.info("investigation docs: %s", paths)
    return paths
