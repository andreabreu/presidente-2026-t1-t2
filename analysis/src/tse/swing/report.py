from __future__ import annotations

import pandas as pd

from .constants import METHOD_GOODMAN_SIMPLEX

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)


def print_report(report: dict) -> None:
    presidente = report["presidente"]
    if presidente is None:
        print_governador(report)
        return
    print("== identidade contábil:", presidente["identity_ok"])
    flow = presidente["flow_national"]
    print("== fluxo nacional (Goodman simplex):")
    print(flow[flow["metodo"] == METHOD_GOODMAN_SIMPLEX][["origem", "destino", "estimativa", "ci_low", "ci_high", "bound_low", "bound_high"]].to_string(index=False))
    print("== baseline nacional:")
    print(presidente["baseline_national"][["share_a_t1_dupla", "share_a_t2_observada", "excesso_a_pp"]].to_string(index=False))
    summary = presidente["residual_summary"].groupby("nivel")[["n_unidades", "n_flag", "falsos_positivos_esperados"]].sum()
    print("== resíduos por nível:")
    print(summary.to_string())
    print("== top 10 municípios flagados:")
    top = presidente["top_flags"]
    cols = [c for c in ("nivel", "uf", "nm_municipio", "nr_zona", "nr_secao", "residuo_pp", "residuo_student", "q_fdr", "flag") if c in top]
    print(top[top["nivel"] == "municipio"].head(10)[cols].to_string(index=False))
    print("== sensibilidade:")
    print(presidente["sensitivity"].to_string(index=False))
    print_governador(report)


def print_governador(report: dict) -> None:
    if report.get("governador") and report["governador"]["resumo"] is not None:
        print("== governador resumo:")
        print(report["governador"]["resumo"].groupby(["uf", "nivel"])[["n_unidades", "n_flag"]].sum().to_string())
