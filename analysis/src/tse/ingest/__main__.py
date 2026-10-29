from __future__ import annotations
import argparse
import logging
import sys

from ..config import ANALYSIS_ROOT
from .convert import run_ingest
from .datasets import ALL, DATASETS

LOG_FILE = ANALYSIS_ROOT / "logs" / "ingest.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stderr)],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tse.ingest", description="Convert TSE 2026 CSV zips to partitioned Parquet")
    parser.add_argument("--dataset", default=ALL, choices=[ALL, *DATASETS])
    parser.add_argument("--scope", default=ALL, help="UF sigla, BR, BRASIL or all")
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    results = run_ingest(args.dataset, args.scope)
    return 1 if any(rows == -2 for rows in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
