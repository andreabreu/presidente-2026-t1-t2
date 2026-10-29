import numpy as np
import pandas as pd
import pytest

from tse.features.metrics import concentration_by_group, effective_number, hhi, margin_share_pp, margin_top1_top2, shares


def test_shares_sum_to_one():
    assert shares([30, 50, 20]).sum() == pytest.approx(1.0)


def test_shares_all_zero_returns_zeros():
    assert shares([0, 0]).tolist() == [0.0, 0.0]


def test_hhi_two_equal_candidates_is_half():
    assert hhi([100, 100]) == pytest.approx(0.5)


def test_effective_number_is_inverse_of_hhi():
    votes = [60, 30, 10]
    assert effective_number(votes) == pytest.approx(1 / hhi(votes))


def test_effective_number_single_candidate_is_one():
    assert effective_number([500]) == pytest.approx(1.0)


def test_margin_top1_top2_and_pp():
    votes = [600, 400]
    assert margin_top1_top2(votes) == 200
    assert margin_share_pp(votes) == pytest.approx(20.0)


def test_margin_single_candidate_uses_zero_runner_up():
    assert margin_top1_top2([7]) == 7
    assert margin_share_pp([7]) == pytest.approx(100.0)


def test_concentration_by_group():
    frame = pd.DataFrame({"g": ["a", "a", "b"], "v": [50, 50, 10]})
    result = concentration_by_group(frame, ["g"], "v").set_index("g")
    assert result.loc["a", "hhi"] == pytest.approx(0.5)
    assert result.loc["a", "n_efetivo_candidatos"] == pytest.approx(2.0)
    assert result.loc["b", "n_candidatos"] == 1
    assert result.loc["a", "margem_pp"] == pytest.approx(0.0)
