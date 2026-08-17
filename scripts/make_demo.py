"""Generate the synthetic demo lane. Committed because it IS the data source.

The shipments are synthetic and examples/SOURCE.md says so plainly — real
per-shipment ocean data is never published under a permissive licence. The
episode data the drill replays against is real (IMF PortWatch). The carrier
promise is set at the lane's own P80 (33 days), so the baseline promise-miss
rate is an honest ~20%, not an artefact of an absurd ETA.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent.parent / "src" / "lane_drill" / "examples"

SPAN = ("2022-01-01", "2024-06-30")
CARRIERS = ("MAEU", "MSCU", "CMA")
PROMISE_DAYS = 33


def main() -> int:
    rng = np.random.default_rng(2026)
    start, end = pd.Timestamp(SPAN[0]), pd.Timestamp(SPAN[1])
    span_days = (end - start).days

    rows = []
    counter = 0
    for day in range(span_days + 1):
        for _ in range(rng.poisson(2.2)):
            departure = start + pd.Timedelta(days=day)
            transit = max(round(rng.normal(30.0, 3.0)), 22)
            counter += 1
            rows.append({
                "shipment": f"DRL{counter:05d}",
                "origin": "CNSHA",
                "destination": "NLRTM",
                "carrier": CARRIERS[rng.integers(0, len(CARRIERS))],
                "departure": departure.date(),
                "arrival": (departure + pd.Timedelta(days=transit)).date(),
                "carrier_eta": (departure + pd.Timedelta(days=PROMISE_DAYS)).date(),
            })

    frame = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "demo.csv", index=False)
    print(f"{len(frame)} shipments over {span_days} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
