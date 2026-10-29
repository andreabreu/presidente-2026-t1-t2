from __future__ import annotations

from datetime import time

MODULE_NAME = "investigation"
SCRIPT = "python -m tse.investigation"
TABLE_PREFIX = "inv_"
HYPOTHESIS_IDS = ["H24", "H_INV1", "H_INV2", "H_INV3", "H_INV4", "H_INV5"]

TIMESTAMP_FORMAT = "%d/%m/%Y %H:%M:%S"
NULL_MARKERS = ("#NULO", "#NE", "", "-1", "-3")

SCOPE_PRESIDENTE = "BR"
SCOPE_NACIONAL = "BRASIL"
SCOPE_EXTERIOR = "ZZ"
CD_CARGO_PRESIDENTE = 1
TURNOS = (1, 2)
ELECTION_DATES = {1: "2026-10-04", 2: "2026-10-25"}

ORIGEM_URNA = "Urna Eletrônica"
ORIGEM_TOTALIZACAO = "Totalização"
SECAO_INSTALADA = "Sim"

UTC_OFFSET_BY_UF = {"AC": -5, "AM": -4, "RO": -4, "RR": -4, "MT": -4, "MS": -4}
DEFAULT_UTC_OFFSET = -3
TIMEZONE_GROUP_LABELS = {-5: "UTC-5 (AC)", -4: "UTC-4 (AM/RO/RR/MT/MS)", -3: "UTC-3 (demais)"}

OFFICIAL_CLOSING = time(17, 0)
EXTENDED_CLOSING = time(19, 0)
ANALYSIS_WINDOW_START = time(17, 0)
ANALYSIS_WINDOW_END = time(23, 59, 59)
RECEPTION_BANDS = [
    ("antes_17h", None, time(17, 0)),
    ("17h00_17h30", time(17, 0), time(17, 30)),
    ("17h30_18h00", time(17, 30), time(18, 0)),
    ("18h00_19h00", time(18, 0), time(19, 0)),
    ("19h00_20h00", time(19, 0), time(20, 0)),
    ("apos_20h", time(20, 0), None),
]
EXTENSION_CONSISTENT_RECEPTION = time(19, 10)
LAG_ALERT_SECONDS = 3600
LAG_QUANTILES = (0.0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999, 1.0)
MIN_GAP_SECONDS = 60
TOP_GAPS = 5
BOOTSTRAP_CONFIDENCE = 0.95
Z_95 = 1.959963984540054
