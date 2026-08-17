import numpy as np
import pandas as pd

from lane_drill.episodes import Episode
from lane_drill.replay import drill
from lane_drill.report import timeline_events, to_dict


def _frame(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(9)
    dep = pd.Timestamp("2023-01-01") + pd.to_timedelta(
        np.sort(rng.integers(0, 400, size=n)), unit="D")
    transit = rng.normal(30, 3, size=n).clip(min=22).round()
    return pd.DataFrame({
        "shipment": [f"S{i}" for i in range(n)],
        "origin": "CNSHA", "destination": "NLRTM", "carrier": "MAEU",
        "departure": dep,
        "arrival": dep + pd.to_timedelta(transit, unit="D"),
        "carrier_eta": dep + pd.Timedelta(days=33),
        "transit_days": transit.astype(float),
    })


def _episode() -> Episode:
    index = pd.date_range("2021-03-01", periods=30, freq="D")
    profile = pd.Series([0.0] * 8 + [1.3] * 22, index=index)
    return Episode(chokepoint="test", start=index[0], end=index[7],
                   depth=0.0, duration_days=8, surge=1.3, profile=profile)


def test_timeline_events_are_ordered_and_complete():
    frame = _frame()
    result = drill(frame, _episode(), n_replays=60, seed=5)
    events = timeline_events(frame, _episode(), result["median_replay"])
    days = [day for day, _ in events]
    assert days == sorted(days)
    text = " ".join(label for _, label in events).lower()
    assert "closes" in text and "reopen" in text


def test_to_dict_is_json_serialisable():
    import json

    result = drill(_frame(), _episode(), n_replays=30, seed=5)
    json.dumps(to_dict(result))  # must not raise
