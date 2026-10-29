from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .constants import ECOLOGICAL_CAVEAT_PT, SCRIPT_NAME


def write_table(
    frame: pd.DataFrame,
    tables_dir: Path,
    source_id: str,
    title_pt: str,
    description_pt: str,
    hypothesis_ids: list[str],
    unit: str,
    columns: dict[str, str],
    method: str,
    caveats_pt: list[str],
    csv_rows: int | None = None,
) -> None:
    tables_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(tables_dir / f"{source_id}.parquet", index=False)
    csv_frame = frame if csv_rows is None else frame.head(csv_rows)
    csv_frame.to_csv(tables_dir / f"{source_id}.csv", index=False)
    meta = {
        "source_id": source_id,
        "title_pt": title_pt,
        "description_pt": description_pt,
        "script": SCRIPT_NAME,
        "hypothesis_ids": hypothesis_ids,
        "unit": unit,
        "n_rows": int(len(frame)),
        "n_rows_csv": int(len(csv_frame)),
        "columns": {name: columns.get(name, "") for name in frame.columns},
        "method": method,
        "caveats_pt": [ECOLOGICAL_CAVEAT_PT, *caveats_pt],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (tables_dir / f"{source_id}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
