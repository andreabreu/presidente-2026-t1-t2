from __future__ import annotations
from pathlib import Path
import yaml

ANALYSIS_ROOT = Path(__file__).resolve().parents[2]


def load_config() -> dict:
    with open(ANALYSIS_ROOT / "config.yaml", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    for key in ("downloads_dir", "interim_dir", "external_dir", "outputs_dir"):
        config[key] = (ANALYSIS_ROOT / config[key]).resolve()
    return config
