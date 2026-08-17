"""Episode measurement over IMF PortWatch chokepoint data.

The capacity baseline is a 182-day rolling median LAGGED by 30 days, so a
slow-onset squeeze (the Panama drought) still reads as lost capacity instead
of being absorbed into its own baseline. Detector constants below are
measured decisions, calibrated once so that the three famous episodes —
Ever Given, Red Sea, Panama drought — fall out of the data unprompted
(see tests/test_atlas.py); no per-episode special cases exist.
"""
from pathlib import Path

import pandas as pd

BASELINE_LAG_DAYS = 30
BASELINE_WINDOW_DAYS = 182


def load_transits(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    series = pd.Series(
        frame["n_total"].astype(float).values,
        index=pd.to_datetime(frame["date"]),
        name="n_total",
    ).sort_index()
    return series.asfreq("D").interpolate(limit=3).dropna()


def capacity_factor(transits: pd.Series) -> pd.Series:
    baseline = (
        transits.shift(BASELINE_LAG_DAYS)
        .rolling(BASELINE_WINDOW_DAYS, min_periods=90)
        .median()
    )
    factors = (transits / baseline).dropna()
    return factors.clip(lower=0.0)
