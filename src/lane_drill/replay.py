"""The capacity-queue replay.

The queue rule: each day, fresh departures join the queue behind any backlog.
If the backlog is empty AND the day's capacity factor is >= 1, the lane
operates normally — everyone departing that day sails with zero delay (this
preserves the null-episode exactness: ordinary day-to-day demand fluctuation
must never create a queue on its own). Otherwise the day serves
base_rate x factor units of accumulated fractional capacity, FIFO; unserved
shipments roll to the next day. After the profile ends, any remaining
backlog drains at base_rate x max(surge, 1). A shipment's delay is its
service day minus its departure day.
"""
import numpy as np
import pandas as pd

from lane_drill.episodes import Episode
from lane_drill.errors import InsufficientDataError


def base_rate(departures: pd.Series) -> float:
    span_days = max((departures.max() - departures.min()).days, 1)
    return max(len(departures) / span_days, 1e-9)


def replay_once(
    departures: pd.Series,
    episode: Episode,
    start: pd.Timestamp,
    rate: float,
) -> np.ndarray:
    factors = episode.profile.to_numpy()
    profile_days = len(factors)

    days = ((departures - start) // pd.Timedelta(days=1)).to_numpy()
    order = np.argsort(days, kind="stable")
    delays = np.zeros(len(departures), dtype=int)

    affected = order[(days[order] >= 0)]
    if affected.size == 0:
        return delays

    queue: list[int] = []
    credit = 0.0
    position = 0
    surge_rate = rate * max(episode.surge, 1.0)
    day = 0
    horizon = int(days.max()) + profile_days + 3660  # hard stop, never binds

    while day <= horizon:
        while position < affected.size and days[affected[position]] == day:
            queue.append(affected[position])
            position += 1

        factor = factors[day] if day < profile_days else None
        backlog = any(days[i] < day for i in queue)

        if factor is None:
            normal = not backlog
            capacity = surge_rate
        else:
            normal = factor >= 1.0 and not backlog
            capacity = rate * factor

        if normal:
            queue.clear()
            credit = 0.0
        else:
            credit += capacity
            while queue and credit >= 1.0:
                shipment = queue.pop(0)
                credit -= 1.0
                delays[shipment] = day - days[shipment]

        if position >= affected.size and not queue:
            break
        day += 1

    return delays


def _metrics(
    transits: np.ndarray,
    delays: np.ndarray,
    promises: np.ndarray,
    departures: pd.Series,
    episode_end_day: float,
    start: pd.Timestamp,
    service_level: float,
) -> dict:
    disrupted = transits + delays
    arrival_days = ((departures - start) // pd.Timedelta(days=1)).to_numpy() + disrupted
    delayed = delays > 0
    last_late_day = float(arrival_days[delayed].max()) if delayed.any() else episode_end_day
    return {
        "p50": float(np.quantile(disrupted, 0.50)),
        "p80": float(np.quantile(disrupted, 0.80)),
        "p90": float(np.quantile(disrupted, 0.90)),
        "promise_miss": float((disrupted > promises).mean()),
        "pct_delayed": float(delayed.mean()),
        "max_delay": int(delays.max()),
        "days_to_clear": max(int(round(last_late_day - episode_end_day)), 0),
    }


def drill(
    frame: pd.DataFrame,
    episode: Episode,
    n_replays: int = 1000,
    seed: int = 2026,
    service_level: float = 0.8,
    min_shipments: int = 30,
) -> dict:
    if len(frame) < min_shipments:
        raise InsufficientDataError(
            f"{len(frame)} completed shipments is below the minimum of "
            f"{min_shipments}; a drill on this little history would not be "
            "trustworthy. Lower it with --min-shipments if you accept that."
        )

    departures = frame["departure"].reset_index(drop=True)
    transits = frame["transit_days"].to_numpy()
    if "carrier_eta" in frame.columns and frame["carrier_eta"].notna().all():
        promises = (
            (frame["carrier_eta"] - frame["departure"]) // pd.Timedelta(days=1)
        ).to_numpy(dtype=float)
    else:
        promises = np.full(len(frame), np.ceil(np.quantile(transits, service_level)))

    baseline = {
        "p50": float(np.quantile(transits, 0.50)),
        "p80": float(np.quantile(transits, 0.80)),
        "p90": float(np.quantile(transits, 0.90)),
        "promise_miss": float((transits > promises).mean()),
    }

    rate = base_rate(departures)
    profile_days = len(episode.profile)
    episode_end_day = float(episode.duration_days - 1)

    span_start = departures.min()
    span_days = max((departures.max() - span_start).days - profile_days, 1)
    rng = np.random.default_rng(seed)
    starts = [span_start + pd.Timedelta(days=int(offset))
              for offset in rng.integers(0, span_days, size=n_replays)]

    replays = []
    for start in starts:
        delays = replay_once(departures, episode, start, rate)
        replays.append((start, delays,
                        _metrics(transits, delays, promises, departures,
                                 episode_end_day, start, service_level)))

    key = f"p{int(service_level * 100)}"
    ordered = sorted(replays, key=lambda item: item[2].get(key, item[2]["p80"]))
    median_start, median_delays, median_metrics = ordered[len(ordered) // 2]
    _, _, worst_metrics = ordered[int(len(ordered) * 0.9)]

    return {
        "baseline": baseline,
        "median": median_metrics,
        "worst_decile": worst_metrics,
        "median_replay": {"start": median_start, "delays": median_delays},
        "n_replays": n_replays,
        "seed": seed,
        "service_level": service_level,
        "episode": {
            "chokepoint": episode.chokepoint,
            "start": str(episode.start.date()),
            "end": str(episode.end.date()),
            "depth": episode.depth,
            "duration_days": episode.duration_days,
            "surge": episode.surge,
        },
    }
