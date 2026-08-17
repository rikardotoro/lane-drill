"""Episode measurement over IMF PortWatch chokepoint data.

The capacity baseline is a 182-day rolling median LAGGED by 30 days, so a
slow-onset squeeze (the Panama drought) still reads as lost capacity instead
of being absorbed into its own baseline. Detector constants below are
measured decisions, calibrated once so that the three famous episodes —
Ever Given, Red Sea, Panama drought — fall out of the data unprompted
(see tests/test_atlas.py); no per-episode special cases exist.
"""
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from lane_drill.errors import UnknownEpisodeError

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


THRESHOLD = 0.75      # below this share of baseline capacity, the day is disrupted
MIN_DAYS = 5          # shorter dips are weather, not episodes
MERGE_GAP_DAYS = 7    # brief recoveries inside one event merge into it
SURGE_HIGH = 1.10     # recovery overshoot begins above this factor
SURGE_DONE = 1.05     # ...and ends when the factor settles back to here
SURGE_CAP_DAYS = 60


@dataclass
class Episode:
    chokepoint: str
    start: pd.Timestamp
    end: pd.Timestamp
    depth: float
    duration_days: int
    surge: float
    profile: pd.Series

    @property
    def label(self) -> str:
        return f"{self.chokepoint}:{self.start.strftime('%Y-%m')}"


def _spans(mask: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    start = None
    for day, below in mask.items():
        if below and start is None:
            start = day
        elif not below and start is not None:
            spans.append((start, day - pd.Timedelta(days=1)))
            start = None
    if start is not None:
        spans.append((start, mask.index[-1]))
    return spans


def detect_episodes(
    transits: pd.Series,
    chokepoint: str,
    threshold: float = THRESHOLD,
    min_days: int = MIN_DAYS,
) -> list["Episode"]:
    factors = capacity_factor(transits)
    spans = _spans(factors < threshold)

    merged: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for start, end in spans:
        if merged and (start - merged[-1][1]).days <= MERGE_GAP_DAYS:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))

    episodes = []
    for start, end in merged:
        if (end - start).days + 1 < min_days:
            continue
        after = factors[end + pd.Timedelta(days=1):]
        surge_end = end
        surging = False
        for day, value in after.head(SURGE_CAP_DAYS).items():
            if value > SURGE_HIGH:
                surging = True
                surge_end = day
            elif surging and value <= SURGE_DONE:
                break
        window = factors[start:surge_end]
        surge_days = factors[end + pd.Timedelta(days=1): surge_end]
        episodes.append(Episode(
            chokepoint=chokepoint,
            start=start,
            end=end,
            depth=float(factors[start:end].min()),
            duration_days=(end - start).days + 1,
            surge=float(surge_days.mean()) if len(surge_days) else 1.0,
            profile=window,
        ))
    return episodes


def atlas(examples_dir: Path) -> list["Episode"]:
    catalog: list[Episode] = []
    for path in sorted(examples_dir.glob("portwatch_*.csv")):
        chokepoint = path.stem.removeprefix("portwatch_")
        catalog += detect_episodes(load_transits(path), chokepoint)
    return sorted(catalog, key=lambda ep: ep.start)


NAMED: dict[str, tuple[str, str]] = {
    "ever-given": ("suez", "2021-03"),
    "red-sea": ("bab_el_mandeb", "2023-12"),
    # measured onset: the drought's slot cuts cross the 75% capacity threshold
    # in November 2023, not at the drought's meteorological start
    "panama-drought": ("panama", "2023-11"),
}


def resolve_episode(name: str, examples_dir: Path) -> "Episode":
    if name in NAMED:
        chokepoint, month = NAMED[name]
    elif ":" in name:
        chokepoint, month = name.split(":", 1)
    else:
        chokepoint, month = "", ""

    catalog = atlas(examples_dir)
    period = pd.Period(month, freq="M") if month else None
    for ep in catalog:
        if ep.chokepoint == chokepoint and period is not None:
            if ep.start.to_period("M") <= period <= ep.end.to_period("M"):
                return ep
    known = ", ".join(NAMED)
    listing = "; ".join(ep.label for ep in catalog)
    raise UnknownEpisodeError(
        f"unknown episode {name!r}. Named episodes: {known}. "
        f"Or use <chokepoint>:<YYYY-MM> from the atlas: {listing}."
    )


def null_episode(days: int) -> "Episode":
    index = pd.date_range("2000-01-01", periods=days, freq="D")
    return Episode(
        chokepoint="null",
        start=index[0],
        end=index[-1],
        depth=1.0,
        duration_days=days,
        surge=1.0,
        profile=pd.Series(1.0, index=index),
    )
