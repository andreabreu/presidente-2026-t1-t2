from __future__ import annotations

MODULE_NAME = "swing"
SCRIPT_NAME = "python -m tse.swing"

CARGO_PRESIDENTE = 1
CARGO_GOVERNADOR = 3
SCOPE_PRESIDENTE = "BR"

NM_VOTAVEL_BRANCO = "BRANCO"
NM_VOTAVEL_NULO = "NULO"

LEVEL_MUNICIPIO = "municipio"
LEVEL_ZONA = "zona"
LEVEL_SECAO = "secao"

KEY_COLUMNS = {
    LEVEL_MUNICIPIO: ["uf", "cd_municipio"],
    LEVEL_ZONA: ["uf", "cd_municipio", "nr_zona"],
    LEVEL_SECAO: ["uf", "cd_municipio", "nr_zona", "nr_secao"],
}

ROW_FINALIST_PREFIX = "t1_"
ORIGEM_OUTROS_ELIMINADOS = "outros_eliminados_t1"
ORIGEM_BRANCOS_NULOS = "brancos_nulos_t1"
ORIGEM_ABSTENCAO = "abstencao_t1"
DESTINO_BRANCOS_NULOS = "brancos_nulos_t2"
DESTINO_ABSTENCAO = "abstencao_t2"

MIN_SHARE_INDIVIDUAL_CANDIDATE = 0.01

PORTE_BINS = {
    LEVEL_MUNICIPIO: [0, 5_000, 10_000, 20_000, 50_000, 200_000, float("inf")],
    LEVEL_ZONA: [0, 5_000, 10_000, 20_000, 50_000, 200_000, float("inf")],
    LEVEL_SECAO: [0, 100, 200, 300, 400, float("inf")],
}
PORTE_LABELS = {
    LEVEL_MUNICIPIO: ["<5k", "5k-10k", "10k-20k", "20k-50k", "50k-200k", ">200k"],
    LEVEL_ZONA: ["<5k", "5k-10k", "10k-20k", "20k-50k", "50k-200k", ">200k"],
    LEVEL_SECAO: ["<100", "100-200", "200-300", "300-400", ">400"],
}

MIN_STRATUM_SIZE = 30
MAD_TO_SIGMA = 1.4826

BOOTSTRAP_REPLICATES = 400
CI_LOWER_PCT = 2.5
CI_UPPER_PCT = 97.5

METHOD_BOUNDS_DUNCAN_DAVIS = "duncan_davis"
METHOD_BOUNDS_RETENCAO_TOTAL = "duncan_davis_retencao_total"
METHOD_GOODMAN_WLS = "goodman_wls"
METHOD_GOODMAN_RESTRITO = "goodman_restrito_0_1"
METHOD_GOODMAN_SIMPLEX = "goodman_simplex"
METHOD_BASELINE_PROPORCIONAL = "baseline_proporcional"

TOP_FLAGGED_ROWS = 500
TOP_SECAO_CSV_ROWS = 1_000

NATIONAL_LABEL = "BR"

ECOLOGICAL_CAVEAT_PT = (
    "Inferência ecológica: todas as estimativas de transferência são AGREGADAS (município/zona/seção) "
    "e não descrevem o comportamento de eleitores individuais. Dizer que 'eleitores de X votaram em Y' "
    "a partir destas tabelas é falácia ecológica. Intervalos refletem incerteza amostral do modelo, não "
    "a indeterminação fundamental do problema (ver bounds determinísticos)."
)
