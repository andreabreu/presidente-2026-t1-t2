from __future__ import annotations

import argparse

from .constants import BOOTSTRAP_REPLICATES
from .pipeline import RunOptions, run
from .report import print_report


def parse_args() -> RunOptions:
    parser = argparse.ArgumentParser(prog="python -m tse.swing", description="Virada 1º→2º turno: saldos, inferência ecológica e resíduos.")
    parser.add_argument("--sem-secao", action="store_true", help="pula o nível de seção (Presidente)")
    parser.add_argument("--sem-governador", action="store_true", help="pula Governador")
    parser.add_argument("--so-governador", action="store_true", help="roda apenas Governador")
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAP_REPLICATES, help="réplicas bootstrap")
    args = parser.parse_args()
    return RunOptions(include_secao=not args.sem_secao, include_governador=not args.sem_governador, include_presidente=not args.so_governador, bootstrap_replicates=args.bootstrap)


def main() -> None:
    report = run(parse_args())
    print_report(report)


if __name__ == "__main__":
    main()
