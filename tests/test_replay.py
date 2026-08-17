import numpy as np
import pandas as pd
import pytest

from lane_drill.episodes import Episode, null_episode
from lane_drill.replay import base_rate, replay_once


def _departures(dates: list[str]) -> pd.Series:
    return pd.Series(pd.to_datetime(dates))


def _episode(factors: list[float], start: str = "2023-06-01") -> Episode:
    index = pd.date_range(start, periods=len(factors), freq="D")
    profile = pd.Series(factors, index=index)
    below = [f for f in factors if f < 1.0]
    return Episode(
        chokepoint="test", start=index[0], end=index[len(below) - 1] if below else index[-1],
        depth=min(factors), duration_days=len(below) or len(factors),
        surge=1.0, profile=profile,
    )


DENSE = _departures([f"2023-06-{d:02d}" for d in range(1, 29) for _ in range(3)])


def test_null_episode_changes_nothing():
    delays = replay_once(DENSE, null_episode(30), pd.Timestamp("2023-06-01"),
                         base_rate(DENSE))
    assert (delays == 0).all()


def test_full_closure_queues_everyone():
    episode = _episode([0.0] * 10 + [1.5] * 20)
    delays = replay_once(DENSE, episode, pd.Timestamp("2023-06-01"), base_rate(DENSE))
    inside = (DENSE >= pd.Timestamp("2023-06-01")) & (DENSE <= pd.Timestamp("2023-06-10"))
    assert (delays[inside.values] > 0).all()


def test_backlog_outlives_the_episode():
    episode = _episode([0.0] * 10 + [1.2] * 30)
    delays = replay_once(DENSE, episode, pd.Timestamp("2023-06-01"), base_rate(DENSE))
    service_days = DENSE + pd.to_timedelta(delays, unit="D")
    assert service_days.max() > episode.end + pd.Timedelta(days=3)


def test_fifo_order_is_preserved():
    episode = _episode([0.0] * 5 + [1.1] * 30)
    delays = replay_once(DENSE, episode, pd.Timestamp("2023-06-01"), base_rate(DENSE))
    service = (DENSE + pd.to_timedelta(delays, unit="D")).values
    order = np.argsort(DENSE.values, kind="stable")
    assert (np.diff(service[order]).astype("timedelta64[D]").astype(int) >= 0).all()


def test_shipments_outside_the_window_are_untouched():
    episode = _episode([0.0] * 5 + [1.5] * 10, start="2023-06-10")
    delays = replay_once(DENSE, episode, pd.Timestamp("2023-06-10"), base_rate(DENSE))
    before = DENSE < pd.Timestamp("2023-06-10")
    assert (delays[before.values] == 0).all()


def test_deterministic():
    episode = _episode([0.2] * 8 + [1.3] * 20)
    a = replay_once(DENSE, episode, pd.Timestamp("2023-06-05"), base_rate(DENSE))
    b = replay_once(DENSE, episode, pd.Timestamp("2023-06-05"), base_rate(DENSE))
    assert (a == b).all()
