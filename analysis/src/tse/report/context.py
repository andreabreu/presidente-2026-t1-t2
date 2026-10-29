from __future__ import annotations

from dataclasses import dataclass, field

from tse.config import ANALYSIS_ROOT, load_config
from tse.hypotheses import load_hypotheses

from .constants import TURNO_1, TURNO_2
from .data import TableStore
from .prose import FMT_TEXT, QueryRegistry

PLACAR_TABLE = "desc_placar_presidente"
RANK_FIRST = 1
RANK_SECOND = 2


@dataclass(frozen=True)
class Candidate:
    number: int
    name: str
    party: str


@dataclass
class ReportContext:
    store: TableStore
    queries: QueryRegistry
    hypotheses: list[dict]
    config: dict
    finalists: dict[str, Candidate] = field(default_factory=dict)

    @classmethod
    def create(cls) -> "ReportContext":
        config = load_config()
        store = TableStore(config=config)
        hypotheses = load_hypotheses() if (ANALYSIS_ROOT / "hypotheses.yaml").exists() else []
        registry = QueryRegistry(store=store, hypotheses=hypotheses)
        context = cls(store=store, queries=registry, hypotheses=hypotheses, config=config)
        context.finalists = context._discover_finalists()
        return context

    def _discover_finalists(self) -> dict[str, Candidate]:
        frame = self.store.frame(PLACAR_TABLE)
        found: dict[str, Candidate] = {}
        for label, turno, rank in (("a", TURNO_2, RANK_FIRST), ("b", TURNO_2, RANK_SECOND), ("t1_first", TURNO_1, RANK_FIRST), ("t1_second", TURNO_1, RANK_SECOND)):
            row = frame[(frame["NR_TURNO"] == turno) & (frame["rank"] == rank)].iloc[0]
            found[label] = Candidate(int(row["NR_CANDIDATO"]), str(row["NM_URNA_CANDIDATO"]), str(row["SG_PARTIDO"]))
        return found

    def candidate_name_span(self, label: str) -> str:
        turno, rank = {"a": (TURNO_2, RANK_FIRST), "b": (TURNO_2, RANK_SECOND), "t1_first": (TURNO_1, RANK_FIRST), "t1_second": (TURNO_1, RANK_SECOND)}[label]
        return self.queries.span(
            f"Q_DESC_placar_t{turno}_rank{rank}_nome",
            PLACAR_TABLE,
            "NM_URNA_CANDIDATO",
            FMT_TEXT,
            where={"NR_TURNO": turno, "rank": rank},
        )

    def candidate_party_span(self, label: str) -> str:
        turno, rank = {"a": (TURNO_2, RANK_FIRST), "b": (TURNO_2, RANK_SECOND), "t1_first": (TURNO_1, RANK_FIRST), "t1_second": (TURNO_1, RANK_SECOND)}[label]
        return self.queries.span(
            f"Q_DESC_placar_t{turno}_rank{rank}_partido",
            PLACAR_TABLE,
            "SG_PARTIDO",
            FMT_TEXT,
            where={"NR_TURNO": turno, "rank": rank},
        )
