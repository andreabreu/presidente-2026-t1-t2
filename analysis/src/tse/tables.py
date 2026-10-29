from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import ANALYSIS_ROOT, load_config

TABLES_SUBDIR = "tables"
FIGURES_SUBDIR = "figures"
NOTES_SUBDIR = "notes"
LOGS_DIR = ANALYSIS_ROOT / "logs"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def tables_dir() -> Path:
    return load_config()["outputs_dir"] / TABLES_SUBDIR


def figures_dir() -> Path:
    return load_config()["outputs_dir"] / FIGURES_SUBDIR


def notes_dir() -> Path:
    return load_config()["outputs_dir"] / NOTES_SUBDIR


def get_logger(module_name: str) -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(module_name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    for handler in (logging.FileHandler(LOGS_DIR / f"{module_name}.log", encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def write_table(
    frame: pd.DataFrame,
    source_id: str,
    *,
    title_pt: str,
    description_pt: str,
    script: str,
    hypothesis_ids: list[str],
    unit: str,
    columns: dict[str, str],
    method: str,
    caveats_pt: list[str],
) -> Path:
    directory = tables_dir()
    directory.mkdir(parents=True, exist_ok=True)
    frame = frame.reset_index(drop=True)
    frame.to_csv(directory / f"{source_id}.csv", index=False)
    frame.to_parquet(directory / f"{source_id}.parquet", index=False)
    metadata = {
        "source_id": source_id,
        "title_pt": title_pt,
        "description_pt": description_pt,
        "script": script,
        "hypothesis_ids": hypothesis_ids,
        "unit": unit,
        "n_rows": int(len(frame)),
        "columns": columns,
        "method": method,
        "caveats_pt": caveats_pt,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = directory / f"{source_id}.meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta_path


def write_figure(figure, name: str) -> Path:
    directory = figures_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    path.write_text(figure.to_json(), encoding="utf-8")
    return path


def write_note(module_name: str, text: str) -> Path:
    directory = notes_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{module_name}.md"
    path.write_text(text, encoding="utf-8")
    return path
