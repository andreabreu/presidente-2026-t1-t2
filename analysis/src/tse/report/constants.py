from __future__ import annotations

import re

PLOTLY_CDN_TEMPLATE = "https://cdn.plot.ly/plotly-{version}.min.js"

TAB_DASHBOARD = "dashboard"
TAB_EXECUTIVO = "executivo"
TAB_VALIDACAO = "validacao"
TAB_RESULTADOS = "resultados"
TAB_DEMOGRAFIA = "demografia"
TAB_VIRADAS = "viradas"
TAB_ANOMALIAS = "anomalias"
TAB_INVESTIGACAO = "investigacao"
TAB_METODOS = "metodos"
TAB_LIMITACOES = "limitacoes"
TAB_HIPOTESES = "hipoteses"
TAB_REVISAO = "revisao"
TAB_DADOS = "dados"

TAB_LABELS: dict[str, str] = {
    TAB_DASHBOARD: "Dashboard",
    TAB_EXECUTIVO: "Executivo",
    TAB_VALIDACAO: "Validação",
    TAB_RESULTADOS: "Resultados",
    TAB_DEMOGRAFIA: "Demografia",
    TAB_VIRADAS: "Viradas",
    TAB_ANOMALIAS: "Anomalias",
    TAB_INVESTIGACAO: "Investigação 25/10",
    TAB_METODOS: "Métodos",
    TAB_LIMITACOES: "Limitações",
    TAB_HIPOTESES: "Hipóteses",
    TAB_REVISAO: "Revisão",
    TAB_DADOS: "Dados brutos",
}

VERDICT_SUSTENTADO = "SUSTENTADO"
VERDICT_FRAGIL = "FRÁGIL"
VERDICT_REFUTADO = "REFUTADO"
VERDICT_INCONCLUSIVO = "INCONCLUSIVO"
EXECUTIVE_VERDICTS = frozenset({VERDICT_SUSTENTADO, VERDICT_FRAGIL})
REFUTATION_VERDICTS = frozenset({VERDICT_REFUTADO, VERDICT_INCONCLUSIVO})
REVIEWED_STATUSES = frozenset({"reviewed", "published"})
VERDICT_CSS_CLASS: dict[str, str] = {
    VERDICT_SUSTENTADO: "verdict-sustentado",
    VERDICT_FRAGIL: "verdict-fragil",
    VERDICT_REFUTADO: "verdict-refutado",
    VERDICT_INCONCLUSIVO: "verdict-inconclusivo",
}

CARGO_PRESIDENTE = 1
CARGO_GOVERNADOR = 3
CARGO_DEP_FEDERAL = 6
CARGO_LABELS: dict[int, str] = {
    1: "Presidente",
    3: "Governador",
    5: "Senador",
    6: "Deputado Federal",
    7: "Deputado Estadual",
    8: "Deputado Distrital",
}
TURNO_1 = 1
TURNO_2 = 2

RISK_SCORE_SENTENCE = (
    "O risk_score ordena unidades para eventual auditoria documental; "
    "não é probabilidade de fraude nem de erro."
)
ECOLOGICAL_FALLACY_BANNER = (
    "Falácia ecológica: todas as transferências abaixo são estimativas agregadas a partir de totais por unidade. "
    "Elas não observam nem permitem inferir o voto de qualquer eleitor individual. O que existe são intervalos "
    "determinísticos compatíveis com os totais e coeficientes de um modelo que assume homogeneidade entre unidades."
)
FORENSIC_CLASS_SENTENCE = (
    "Nenhuma afirmação de irregularidade material é possível com os arquivos atuais: "
    "faltam boletins de urna, logs e hashes. A classe forense permanece vazia."
)
PENDING_REVIEW_SENTENCE = "Sumário executivo aguardando revisão adversarial (Fase sete)."

MANDATORY_PHRASES_WITH_RESTRICTED_WORDS: tuple[str, ...] = (
    "não é probabilidade de fraude nem de erro",
    "não é probabilidade de fraude",
    "não mede chance de fraude",
    "anomalia ≠ fraude",
    "anomalia não é fraude",
)

FORBIDDEN_WORD_PATTERNS: tuple[str, ...] = (
    r"\bfraude[s]?\b",
    r"\bfraudulent[oa]s?\b",
    r"\bmanipula(ç|c)(ão|ões|ao|oes)\b",
    r"\bmanipulad[oa]s?\b",
    r"\badultera(ç|c)(ão|ões|ao|oes)\b",
    r"\badulterad[oa]s?\b",
    r"\burnas? viciadas?\b",
    r"\bvotos? roubados?\b",
    r"\bresultados? falsos?\b",
    r"\bsuspeit[oa]s?\b",
    r"\bsuspei(ç|c)(ão|ao)\b",
    r"\bcomprovad[oa]s?\b",
    r"\bevid(ê|e)ncias? de irregularidade",
    r"\bvotos? indevidos?\b",
    r"\bchance de irregularidade",
)

PROSE_EXEMPT_BLOCK_TAGS: tuple[str, ...] = ("script", "style", "table", "pre", "code", "svg", "textarea")
PROSE_EXEMPT_ATTRIBUTE = 'data-lint="exempt"'
HEADING_PATTERN = re.compile(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", re.DOTALL | re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
SOURCED_SPAN_PATTERN = re.compile(r"<span\b[^>]*\bdata-source=[^>]*>.*?</span>", re.DOTALL | re.IGNORECASE)

PROSE_ALLOWED_PATTERNS: tuple[str, ...] = (
    r"\d+\s?[ºª°]",
    r"\b[A-Z]{1,4}\d{2,3}\b",
    r"\bFase\s\d\b",
    r"§\s?\d+(\.\d+)?",
    r"\b(Censo|IBGE|TSE|Elei(ç|c)(õ|o)es|UE)\s(19|20)\d{2}\b",
    r"\b\d{2}/\d{2}(/\d{4})?\b",
)

NOTE_PHASE_ORDER: tuple[tuple[str, str], ...] = (
    ("validation", "Fase 1 — Validação matemática"),
    ("descriptive", "Fase 2 — Descritivo"),
    ("demography", "Fase 3 — Demografia"),
    ("swing", "Fase 4 — Virada 1º→2º turno"),
    ("anomalies", "Fase 5 — Anomalias e matriz de risco"),
)
LIMITATIONS_HEADING_PREFIX = "## Limitações"
ECOLOGICAL_HEADING_PREFIX = "## DECLARAÇÃO DE FALÁCIA ECOLÓGICA"

INVESTIGATION_TABLE_PREFIX = "inv_"
REVIEW_TABLE_ID = "rev_vereditos"
TIMELINE_PATH = "investigation/timeline/timeline.json"
FLOW_BU_PATH = "investigation/data/flow_bu.json"
EVIDENCE_MATRIX_PATH = "investigation/evidence_matrix.csv"
REVIEW_NOTES_DIR = "outputs/review"
ANOMALIES_EXPORT_CANDIDATES: tuple[str, ...] = ("outputs/anomalies_export.json", "outputs/tables/anom_export.json")

HYPOTHESES_SOURCE = "hypotheses.yaml"
CONFIG_SOURCE = "config.yaml"
MANIFEST_SOURCE = "outputs/run_manifest.json"
FORENSIC_CHECKLIST_PATH = "docs/FORENSIC_CHECKLIST.md"
FORENSIC_MATRIX_HEADING = "## 1. Matriz de auditabilidade"
