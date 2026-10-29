from __future__ import annotations
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ..config import load_config

ALL = "all"
ELECTION_YEAR = "2026"
RESULTS_SUBDIR = "resultados-2026"
CANDIDATES_SUBDIR = "candidatos-2026"
CSV_SUFFIX = ".csv"

DATASETS: dict[str, tuple[str, str]] = {
    "votacao_candidato_munzona": (RESULTS_SUBDIR, "votacao_candidato_munzona_2026.zip"),
    "votacao_partido_munzona": (RESULTS_SUBDIR, "votacao_partido_munzona_2026.zip"),
    "detalhe_votacao_munzona": (RESULTS_SUBDIR, "detalhe_votacao_munzona_2026.zip"),
    "detalhe_votacao_secao": (RESULTS_SUBDIR, "detalhe_votacao_secao_2026.zip"),
    "votacao_secao": (RESULTS_SUBDIR, "votacao_secao_2026_*.zip"),
    "consulta_cand": (CANDIDATES_SUBDIR, "consulta_cand_2026.zip"),
}


@dataclass(frozen=True)
class CsvSource:
    dataset: str
    scope: str
    zip_path: Path
    member_name: str

    @property
    def label(self) -> str:
        return f"{self.dataset}/scope={self.scope}"


def scope_of(member_name: str) -> str:
    return Path(member_name).stem.rsplit("_", 1)[-1]


def zip_paths_for(dataset: str, downloads_dir: Path) -> list[Path]:
    subdir, pattern = DATASETS[dataset]
    return sorted((downloads_dir / subdir).glob(pattern))


def csv_members(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path) as archive:
        return sorted(name for name in archive.namelist() if name.lower().endswith(CSV_SUFFIX))


def list_sources(dataset: str = ALL, scope: str = ALL) -> list[CsvSource]:
    downloads_dir = load_config()["downloads_dir"]
    selected_datasets = list(DATASETS) if dataset == ALL else [dataset]
    sources: list[CsvSource] = []
    for name in selected_datasets:
        for zip_path in zip_paths_for(name, downloads_dir):
            for member in csv_members(zip_path):
                member_scope = scope_of(member)
                if scope == ALL or member_scope == scope.upper():
                    sources.append(CsvSource(name, member_scope, zip_path, member))
    return sources
