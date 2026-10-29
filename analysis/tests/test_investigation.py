from datetime import time

import numpy as np
import pandas as pd
import pytest

from tse.investigation.estimators import margin, scenario_totals, votes_to_flip, within_estimator
from tse.investigation.timestamps import (
    count_by_minute,
    find_gaps,
    lag_quantiles,
    lag_seconds,
    parse_summary,
    parse_tse_timestamp,
    reception_band,
    timezone_group,
)


def test_parse_tse_timestamp_handles_format_and_null_markers():
    values = pd.Series(["25/10/2026 19:03:38", "#NULO", None, "garbage"])
    parsed = parse_tse_timestamp(values)
    assert parsed.iloc[0] == pd.Timestamp("2026-10-25 19:03:38")
    assert parsed.iloc[1:].isna().all()


def test_parse_summary_counts_nulls_and_unparseable_separately():
    summary = parse_summary(pd.Series(["25/10/2026 19:03:38", "#NULO", "garbage"]), "col")
    assert summary["n_null_marker"] == 1
    assert summary["n_unparseable"] == 1
    assert summary["share_parseable"] == pytest.approx(1 / 3)


def test_timezone_group_maps_offsets():
    groups = timezone_group(pd.Series(["AC", "AM", "SP", "ZZ"]))
    assert groups.tolist() == ["UTC-5 (AC)", "UTC-4 (AM/RO/RR/MT/MS)", "UTC-3 (demais)", "UTC-3 (demais)"]


def test_reception_band_boundaries():
    stamps = pd.Series(pd.to_datetime([
        "2026-10-25 16:59:59", "2026-10-25 17:00:00", "2026-10-25 17:30:00",
        "2026-10-25 18:59:59", "2026-10-25 19:00:00", "2026-10-25 20:00:00",
    ]))
    assert reception_band(stamps).tolist() == [
        "antes_17h", "17h00_17h30", "17h30_18h00", "18h00_19h00", "19h00_20h00", "apos_20h"]


def test_count_by_minute_groups():
    stamps = pd.Series(pd.to_datetime(["2026-10-25 19:03:01", "2026-10-25 19:03:59", "2026-10-25 19:04:00"]))
    groups = pd.DataFrame({"uf": ["SP", "SP", "RJ"]})
    counts = count_by_minute(stamps, groups)
    assert counts.set_index(["uf", "minuto"])["n_secoes"].to_dict() == {
        ("SP", pd.Timestamp("2026-10-25 19:03")): 2, ("RJ", pd.Timestamp("2026-10-25 19:04")): 1}


def test_find_gaps_returns_longest_interval_with_counts():
    stamps = pd.Series(pd.to_datetime([
        "2026-10-25 17:05:00", "2026-10-25 17:06:00", "2026-10-25 17:07:00",
        "2026-10-25 19:03:00", "2026-10-25 19:03:30", "2026-10-25 19:10:00",
    ]))
    gaps = find_gaps(stamps, pd.Timestamp("2026-10-25 17:00"), pd.Timestamp("2026-10-25 23:59:59"))
    top = gaps.iloc[0]
    assert top["gap_inicio"] == pd.Timestamp("2026-10-25 17:07:00")
    assert top["gap_fim"] == pd.Timestamp("2026-10-25 19:03:00")
    assert top["duracao_s"] == 116 * 60
    assert top["n_antes_5min"] == 3
    assert top["n_depois_5min"] == 2


def test_lag_quantiles_and_negative_lag():
    reception = pd.Series(pd.to_datetime(["2026-10-25 19:03:00", "2026-10-25 19:03:00"]))
    totalization = pd.Series(pd.to_datetime(["2026-10-25 19:04:00", "2026-10-25 19:02:00"]))
    lags = lag_seconds(reception, totalization)
    assert lags.tolist() == [60.0, -60.0]
    quantiles = lag_quantiles(lags, (0.0, 1.0))
    assert quantiles["q0"] == -60.0 and quantiles["q1"] == 60.0 and quantiles["n"] == 2


def test_margin_and_votes_to_flip():
    assert margin(10, 4) == 6
    assert votes_to_flip(10, 4) == {"margem": 6, "votos_trocados_para_inverter": 4,
                                    "votos_adicionais_segundo_para_inverter": 7}


def test_scenario_totals_excludes_rows():
    frame = pd.DataFrame({"a": [10, 20, 30], "b": [5, 25, 10]})
    result = scenario_totals(frame, pd.Series([False, True, False]), "a", "b")
    assert result == {"n_secoes_excluidas": 1, "votos_lider_cenario": 40, "votos_segundo_cenario": 15,
                      "margem_cenario": 25, "share_lider_cenario": 40 / 55}


def test_within_estimator_recovers_treatment_effect_with_group_shifts():
    rng = np.random.default_rng(20261028)
    groups = np.repeat(np.arange(50), 20)
    group_effect = rng.normal(size=50)[groups]
    treatment = rng.integers(0, 2, size=groups.size)
    outcome = 0.4 + group_effect + 0.05 * treatment + rng.normal(scale=0.01, size=groups.size)
    estimate = within_estimator(pd.Series(outcome), pd.Series(treatment), pd.Series(groups), pd.Series(np.ones(groups.size)))
    assert estimate.beta == pytest.approx(0.05, abs=0.005)
    assert estimate.ci_low < 0.05 < estimate.ci_high
    assert estimate.n_groups == 50


def test_within_estimator_without_variation_returns_nan():
    estimate = within_estimator(pd.Series([1.0, 2.0]), pd.Series([1, 1]), pd.Series([0, 0]), pd.Series([1.0, 1.0]))
    assert np.isnan(estimate.beta)
