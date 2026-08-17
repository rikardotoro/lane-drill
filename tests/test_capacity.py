from pathlib import Path

import pandas as pd

from lane_drill.episodes import capacity_factor, load_transits

EXAMPLES = Path(__file__).parent.parent / "src" / "lane_drill" / "examples"


def test_slices_exist_and_load():
    for slug in ("suez", "bab_el_mandeb", "panama"):
        series = load_transits(EXAMPLES / f"portwatch_{slug}.csv")
        assert len(series) > 2000
        assert (series.index[-1] - series.index[0]).days > 5 * 365


def test_capacity_factor_is_near_one_in_calm_seas():
    series = load_transits(EXAMPLES / "portwatch_suez.csv")
    factors = capacity_factor(series)
    calm = factors["2020-06-01":"2020-12-31"]
    assert 0.9 <= calm.median() <= 1.1


def test_ever_given_day_collapses_the_factor():
    series = load_transits(EXAMPLES / "portwatch_suez.csv")
    factors = capacity_factor(series)
    assert factors[pd.Timestamp("2021-03-26")] < 0.2


def test_factors_have_no_gaps():
    series = load_transits(EXAMPLES / "portwatch_suez.csv")
    factors = capacity_factor(series)
    assert not factors.isna().any()
    assert (factors >= 0).all()
