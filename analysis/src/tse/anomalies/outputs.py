from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tse.config import ANALYSIS_ROOT, load_config

SCRIPT_NAME = "src/tse/anomalies"
LOG_PATH = ANALYSIS_ROOT / "logs" / "anomalies.log"


def configure_logging() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tse.anomalies")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        for handler in (logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()):
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    return logger


def tables_dir() -> Path:
    path = load_config()["outputs_dir"] / "tables"
    path.mkdir(parents=True, exist_ok=True)
    return path


def figures_dir() -> Path:
    path = load_config()["outputs_dir"] / "figures"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_table(
    frame: pd.DataFrame,
    source_id: str,
    title_pt: str,
    description_pt: str,
    hypothesis_ids: list[str],
    unit: str,
    columns: dict[str, str],
    method: str,
    caveats_pt: list[str],
) -> Path:
    directory = tables_dir()
    frame = frame.reset_index(drop=True)
    frame.to_csv(directory / f"{source_id}.csv", index=False)
    frame.to_parquet(directory / f"{source_id}.parquet", index=False)
    meta = {
        "source_id": source_id,
        "title_pt": title_pt,
        "description_pt": description_pt,
        "script": SCRIPT_NAME,
        "hypothesis_ids": hypothesis_ids,
        "unit": unit,
        "n_rows": int(len(frame)),
        "columns": columns,
        "method": method,
        "caveats_pt": caveats_pt,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (directory / f"{source_id}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return directory / f"{source_id}.parquet"


def read_optional_table(source_id: str) -> pd.DataFrame | None:
    directory = tables_dir()
    for suffix in (".parquet", ".csv"):
        path = directory / f"{source_id}{suffix}"
        if path.exists():
            return pd.read_parquet(path) if suffix == ".parquet" else pd.read_csv(path)
    return None
