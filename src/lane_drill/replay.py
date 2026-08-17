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
