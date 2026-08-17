import json

import numpy as np
import pandas as pd
import pytest

from lane_drill.episodes import Episode
from lane_drill.errors import InsufficientDataError
from lane_drill.replay import drill


def _frame(n: int = 200, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    departures = pd.Timestamp("2023-01-01") + pd.to_timedelta(
        np.sort(rng.integers(0, 540, size=n)), unit="D"
    )
    transit = rng.normal(30, 3, size=n).clip(min=22).round()
    return pd.DataFrame({
        "shipment": [f"S{i}" for i in range(n)],
        "origin": "CNSHA", "destination": "NLRTM", "carrier": "MAEU",
        "departure": departures,
        "arrival": departures + pd.to_timedelta(transit, unit="D"),
        "carrier_eta": departures + pd.Timedelta(days=28),
        "transit_days": transit.astype(float),
    })


def _deep_episode() -> Episode:
    index = pd.date_range("2021-03-01", periods=40, freq="D")
    profile = pd.Series([0.05] * 10 + [1.4] * 30, index=index)
    return Episode(chokepoint="test", start=index[0], end=index[9],
                   depth=0.05, duration_days=10, surge=1.4, profile=profile)


def test_seeded_determinism():
    a = drill(_frame(), _deep_episode(), n_replays=50, seed=11)
    b = drill(_frame(), _deep_episode(), n_replays=50, seed=11)
    del a["median_replay"], b["median_replay"]
    assert a == b


def test_disruption_raises_the_p80():
    result = drill(_frame(), _deep_episode(), n_replays=100, seed=11)
    assert result["median"]["p80"] >= result["baseline"]["p80"]
    assert result["worst_decile"]["p80"] >= result["median"]["p80"]


def test_no_forecast_language_anywhere():
    """Trap 1: the tool answers 'what if', never 'how likely'."""
    result = drill(_frame(), _deep_episode(), n_replays=20, seed=11)
    result.pop("median_replay")
    flat = json.dumps(result).lower()
    for word in ("probab", "likelihood", "forecast", "predict"):
        assert word not in flat


def test_min_shipments_refusal():
    with pytest.raises(InsufficientDataError, match="30"):
        drill(_frame(n=10), _deep_episode(), n_replays=20, seed=11)


def test_days_to_clear_is_positive_for_a_deep_episode():
    result = drill(_frame(), _deep_episode(), n_replays=100, seed=11)
    assert result["median"]["days_to_clear"] >= 0
    assert result["worst_decile"]["days_to_clear"] >= result["median"]["days_to_clear"] - 30


def test_episode_provenance_is_carried():
    result = drill(_frame(), _deep_episode(), n_replays=20, seed=11)
    assert result["episode"]["chokepoint"] == "test"
    assert result["episode"]["duration_days"] == 10
