from __future__ import annotations

import numpy as np
import pandas as pd

from tse.anomalies.stats import component_from_q, severity_from_rubric, weighted_risk_score

SECTION_KEYS = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO"]
CLASS_STATISTICAL = "estatistico"
CLASS_DOCUMENTAL = "documental"
FINDING_TURNOUT = "comparecimento_extremo"
FINDING_BLANK_NULL = "nulos_x_share"
FINDING_UNANIMITY = "unanimidade"
FINDING_TWIN = "secao_gemea"
FINDING_DIVERGENCE = "divergencia_fontes"
FINDING_SWING = "residuo_virada"
FINDING_DEMOGRAPHY = "demografia_impossivel"
COMPONENT_BY_FINDING = {
    FINDING_TURNOUT: "comparecimento_extremo",
    FINDING_BLANK_NULL: "nulos_x_share",
    FINDING_UNANIMITY: "unanimidade",
    FINDING_DIVERGENCE: "divergencia_fontes",
    FINDING_SWING: "residuo_virada",
}
WHAT_BU_RESOLVES = {
    FINDING_TURNOUT: "BU confirma comparecimento e aptos registrados pela urna; perfil do eleitorado da seção explica o extremo",
    FINDING_BLANK_NULL: "BU confirma brancos/nulos da urna; perfil do eleitorado (escolaridade) explica a taxa",
    FINDING_UNANIMITY: "BU confirma a contagem por candidato; correspondência efetivada identifica o local (aldeia/presídio)",
    FINDING_TWIN: "BU das duas seções mostra se os vetores idênticos existem na origem ou são duplicação na exportação",
    FINDING_DIVERGENCE: "BU é a fonte primária que arbitra entre os arquivos divergentes",
    FINDING_SWING: "BU dos dois turnos confirma os totais; perfil do eleitorado contextualiza a mudança",
}
SOURCE_QUERY_ID = "tse.anomalies.risk.build_risk_matrix"


def build_risk_matrix(
    base: pd.DataFrame,
    findings: pd.DataFrame,
    weights: dict[str, float],
    available_components: list[str],
    q_cutoff: float,
) -> pd.DataFrame:
    matrix = base[SECTION_KEYS + ["NM_MUNICIPIO", "QT_APTOS", "NM_LOCAL_VOTACAO", "flags_exclusao", "tem_flag_exclusao"]].copy()
    matrix = matrix.rename(columns={"QT_APTOS": "n_eleitores"})
    components = {name: np.zeros(len(matrix)) for name in weights}
    matrix = matrix.set_index(SECTION_KEYS)
    findings = findings.set_index(SECTION_KEYS)
    documental = pd.Series(False, index=matrix.index)
    for finding_type, group in findings.groupby("finding_type"):
        group = group[~group.index.duplicated()]
        aligned = group.reindex(matrix.index)
        component_name = COMPONENT_BY_FINDING.get(finding_type)
        if component_name in components:
            components[component_name] = np.nan_to_num(
                component_from_q(aligned["q_fdr"].to_numpy(), q_cutoff) * aligned["peso_componente"].fillna(1).to_numpy()
            )
        if finding_type == FINDING_DIVERGENCE:
            documental |= aligned["q_fdr"].notna()
    matrix = matrix.reset_index()
    summary = _summarise_findings(findings.reset_index(), q_cutoff)
    matrix = matrix.merge(summary, on=SECTION_KEYS, how="left")
    matrix["finding_types"] = matrix["finding_types"].apply(lambda value: value if isinstance(value, list) else [])
    matrix["n_findings_significativos"] = matrix["n_findings_significativos"].fillna(0).astype(int)
    for name, values in components.items():
        matrix[f"comp_{name}"] = values
    matrix["risk_score"] = weighted_risk_score(components, weights, available_components)
    matrix["classe"] = np.where(documental.to_numpy(), CLASS_DOCUMENTAL, CLASS_STATISTICAL)
    matrix["severity"] = [
        severity_from_rubric(q, n, flagged, n_findings, is_documental)
        for q, n, flagged, n_findings, is_documental in zip(
            matrix["q_fdr_min"].to_numpy(),
            matrix["n_eleitores"].to_numpy(),
            matrix["tem_flag_exclusao"].to_numpy(),
            matrix["n_findings_significativos"].to_numpy(),
            documental.to_numpy(),
        )
    ]
    matrix["what_bu_would_resolve"] = matrix["finding_types"].apply(
        lambda types: "; ".join(WHAT_BU_RESOLVES[t] for t in types if t in WHAT_BU_RESOLVES) or "sem achado; nada a resolver"
    )
    matrix["source_query_id"] = SOURCE_QUERY_ID
    matrix["componentes_disponiveis"] = ",".join(available_components)
    return matrix.sort_values(["risk_score", "severity"], ascending=False).reset_index(drop=True)


def _summarise_findings(findings: pd.DataFrame, q_cutoff: float) -> pd.DataFrame:
    significant = findings[findings["q_fdr"] < q_cutoff]
    grouped = findings.groupby(SECTION_KEYS)
    summary = grouped.agg(p_empirico_min=("p_empirico", "min"), q_fdr_min=("q_fdr", "min")).reset_index()
    types = (
        significant.groupby(SECTION_KEYS)["finding_type"]
        .agg(lambda values: sorted(set(values)))
        .rename("finding_types")
        .reset_index()
    )
    types["n_findings_significativos"] = types["finding_types"].map(len)
    return summary.merge(types, on=SECTION_KEYS, how="left")


def aggregate_to_municipio(matrix: pd.DataFrame) -> pd.DataFrame:
    grouped = matrix.groupby(["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_TURNO", "CD_CARGO"], observed=True)
    ranking = grouped.agg(
        n_secoes=("NR_SECAO", "size"),
        n_eleitores=("n_eleitores", "sum"),
        risk_score_medio=("risk_score", "mean"),
        risk_score_max=("risk_score", "max"),
        n_secoes_severity_ge2=("severity", lambda s: int((s >= 2).sum())),
        n_secoes_severity_ge3=("severity", lambda s: int((s >= 3).sum())),
        n_secoes_com_achado=("n_findings_significativos", lambda s: int((s > 0).sum())),
        q_fdr_min=("q_fdr_min", "min"),
    ).reset_index()
    ranking["share_secoes_com_achado"] = ranking["n_secoes_com_achado"] / ranking["n_secoes"]
    return ranking.sort_values(["risk_score_medio", "n_secoes_severity_ge2"], ascending=False).reset_index(drop=True)
