"""Regenerate the README charts from the committed data so they can never drift.

Hand-rolled SVG (no plotting library); light and dark variants; palette
validated for GitHub's surfaces. Blue = normal/baseline, orange = disruption.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from lane_drill.data import load_shipments
from lane_drill.episodes import THRESHOLD, atlas, capacity_factor, load_transits, resolve_episode
from lane_drill.replay import drill

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "src" / "lane_drill" / "examples"
OUT = ROOT / "docs" / "charts"

FONT = "system-ui, -apple-system, Segoe UI, sans-serif"

TOKENS = {
    "light": {
        "normal": "#2a78d6", "disrupt": "#eb6834",
        "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "axis": "#c3c2b7",
    },
    "dark": {
        "normal": "#3987e5", "disrupt": "#d95926",
        "ink": "#ffffff", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "axis": "#383835",
    },
}

FAMOUS = {
    "ever-given": "Ever Given",
    "red-sea": "Red Sea crisis",
    "panama-drought": "Panama drought",
}


def _text(x, y, s, size, fill, anchor="start", weight="normal", tabular=False):
    style = "font-variant-numeric: tabular-nums;" if tabular else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" style="{style}">{s}</text>')


def _line(x1, y1, x2, y2, stroke, width=1.0, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}"{d}/>')


def _path(points, color, width=2.0):
    d = " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
    return (f'<path d="M {d}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linejoin="round"/>')


def _svg(width, height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img">\n' + "\n".join(body) + "\n</svg>\n")


# ---------------------------------------------------------------- chart 1
def chart_atlas(mode):
    t = TOKENS[mode]
    chokepoints = ("suez", "bab_el_mandeb", "panama")
    titles = {"suez": "Suez Canal", "bab_el_mandeb": "Bab el-Mandeb Strait",
              "panama": "Panama Canal"}
    famous = {name: resolve_episode(name, EXAMPLES) for name in FAMOUS}

    W, panel_h, top, bottom = 760, 118, 64, 34
    H = top + panel_h * 3 + bottom
    left, right = 52, 26
    x0, x1 = left, W - right
    t0, t1 = pd.Timestamp("2019-08-01"), pd.Timestamp("2024-12-31")

    def X(ts):
        return x0 + (ts - t0) / (t1 - t0) * (x1 - x0)

    body = [_text(20, 26, "Every disruption since 2019, measured", 16, t["ink"], weight="600"),
            _text(20, 44, "Daily capacity vs baseline, three chokepoints. Orange: below 75% — an episode. Source: IMF PortWatch.",
                  12, t["ink2"])]

    for row, slug in enumerate(chokepoints):
        factors = capacity_factor(load_transits(EXAMPLES / f"portwatch_{slug}.csv"))
        factors = factors[factors.index >= t0].clip(upper=1.8)
        y0 = top + panel_h * (row + 1) - 22
        y1 = top + panel_h * row + 14

        def Y(v):
            return y0 - min(v, 1.8) / 1.8 * (y0 - y1)

        body.append(_text(x0, y1 - 4, titles[slug], 12, t["ink"], weight="600"))
        body.append(_line(x0, Y(1.0), x1, Y(1.0), t["grid"]))
        body.append(_text(x0 - 6, Y(1.0) + 4, "100%", 10, t["muted"], anchor="end", tabular=True))

        below = factors < THRESHOLD
        # orange fill under disrupted days
        for day, is_below in below.items():
            if is_below:
                body.append(_line(X(day), y0, X(day), Y(factors[day]), t["disrupt"], 1.2))
        body.append(_path([(X(day), Y(v)) for day, v in factors.items()], t["normal"], 1.4))
        body.append(_line(x0, y0, x1, y0, t["axis"], 1.0))

        for name, ep in famous.items():
            if ep.chokepoint == slug:
                mid = ep.start + (ep.end - ep.start) / 2
                body.append(_text(X(mid), y1 + 8, FAMOUS[name], 11, t["disrupt"],
                                  anchor="middle", weight="600"))

        if row == 2:
            for year in range(2020, 2025):
                ts = pd.Timestamp(f"{year}-01-01")
                body.append(_text(X(ts), y0 + 16, str(year), 11, t["muted"],
                                  anchor="middle", tabular=True))

    count = len(atlas(EXAMPLES))
    body.append(_text(x1, H - 12, f"{count} episodes detected in total — none hand-picked",
                      11, t["muted"], anchor="end"))
    return _svg(W, H, body)


# ---------------------------------------------------------------- chart 2
def chart_impact(results, mode):
    t = TOKENS[mode]
    W, H = 760, 330
    left, right, top, bottom = 190, 130, 74, 40
    x0, x1, y0, y1 = left, W - right, H - bottom, top + 10
    max_days = max(r["median"]["p80"] for r in results.values()) * 1.15

    def X(v):
        return x0 + v / max_days * (x1 - x0)

    body = [_text(20, 26, "Fame is not damage", 16, t["ink"], weight="600"),
            _text(20, 44, "P80 transit on the demo lane, baseline vs the median drill of each real episode.",
                  12, t["ink2"])]

    row_h = (y0 - y1) / len(results)
    for row, (name, result) in enumerate(results.items()):
        base = result["baseline"]["p80"]
        med = result["median"]["p80"]
        miss = result["median"]["promise_miss"]
        cy = y1 + row_h * row
        bar_h = 16
        body.append(_text(x0 - 10, cy + row_h / 2, FAMOUS[name], 12, t["ink"],
                          anchor="end", weight="600"))
        body.append(_text(x0 - 10, cy + row_h / 2 + 15,
                          f"{result['episode']['duration_days']} days at "
                          f"{result['episode']['depth']:.0%} capacity",
                          10, t["muted"], anchor="end"))
        body.append(f'<rect x="{x0}" y="{cy + row_h / 2 - bar_h - 2:.1f}" '
                    f'width="{X(base) - x0:.1f}" height="{bar_h}" rx="3" fill="{t["normal"]}"/>')
        body.append(f'<rect x="{x0}" y="{cy + row_h / 2 + 2:.1f}" '
                    f'width="{X(med) - x0:.1f}" height="{bar_h}" rx="3" fill="{t["disrupt"]}"/>')
        body.append(_text(X(base) + 6, cy + row_h / 2 - bar_h / 2 + 3, f"{base:.0f}",
                          11, t["normal"], weight="600", tabular=True))
        body.append(_text(X(med) + 6, cy + row_h / 2 + bar_h / 2 + 5,
                          f"{med:.0f} · {miss:.0%} missed",
                          11, t["disrupt"], weight="600", tabular=True))

    body.append(_line(x0, y0, x1, y0, t["axis"], 1.2))
    for v in range(0, int(max_days) + 1, 20):
        body.append(_text(X(v), y0 + 16, str(v), 11, t["muted"], anchor="middle", tabular=True))
    body.append(_text((x0 + x1) / 2, y0 + 31, "P80 transit days over the struck quarter",
                      11, t["muted"], anchor="middle"))
    return _svg(W, H, body)


# ---------------------------------------------------------------- chart 3
def chart_timeline(frame, episode, result, mode):
    t = TOKENS[mode]
    start = result["median_replay"]["start"]
    delays = result["median_replay"]["delays"]
    day_of = ((frame["departure"].reset_index(drop=True) - start)
              // pd.Timedelta(days=1)).to_numpy()
    horizon = 46

    transits = frame["transit_days"].to_numpy()
    # delayed shipments that have departed (or queued) but not yet been delivered
    queue = np.zeros(horizon, dtype=int)
    for d in range(horizon):
        queue[d] = int(((delays > 0) & (day_of <= d)
                        & (day_of + delays + transits > d)).sum())

    factors = episode.profile.to_numpy()
    factor_by_day = [factors[d] if d < len(factors) else 1.0 for d in range(horizon)]

    W, H = 760, 360
    left, right = 52, 170
    x0, x1 = left, W - right
    cap_y0, cap_y1 = 168, 78
    q_y0, q_y1 = 306, 208

    def X(d):
        return x0 + d / (horizon - 1) * (x1 - x0)

    body = [_text(20, 26, "One week of blockage, six weeks of consequences", 16, t["ink"], weight="600"),
            _text(20, 44, "The median Ever Given replay on the demo lane, day by day.", 12, t["ink2"])]

    def Yc(v):
        return cap_y0 - min(v, 1.6) / 1.6 * (cap_y0 - cap_y1)

    body.append(_text(x0, cap_y1 - 8, "Waterway capacity vs normal", 11, t["ink2"], weight="600"))
    body.append(_line(x0, Yc(1.0), x1, Yc(1.0), t["grid"]))
    body.append(_text(x0 - 6, Yc(1.0) + 4, "100%", 10, t["muted"], anchor="end", tabular=True))
    body.append(_path([(X(d), Yc(v)) for d, v in enumerate(factor_by_day)], t["normal"]))
    body.append(_line(x0, cap_y0, x1, cap_y0, t["axis"], 1.0))

    qmax = max(int(queue.max()), 1)

    def Yq(v):
        return q_y0 - v / (qmax * 1.2) * (q_y0 - q_y1)

    body.append(_text(x0, q_y1 - 8, "Your delayed cargo not yet delivered", 11, t["ink2"], weight="600"))
    slot = (x1 - x0) / horizon
    for d in range(horizon):
        if queue[d]:
            body.append(f'<rect x="{X(d) - slot * 0.35:.1f}" y="{Yq(queue[d]):.1f}" '
                        f'width="{slot * 0.7:.1f}" height="{Yq(0) - Yq(queue[d]):.1f}" '
                        f'rx="2" fill="{t["disrupt"]}"/>')
    body.append(_line(x0, q_y0, x1, q_y0, t["axis"], 1.0))
    for d in range(0, horizon, 7):
        body.append(_text(X(d), q_y0 + 16, f"{d}", 11, t["muted"], anchor="middle", tabular=True))
    body.append(_text((x0 + x1) / 2, q_y0 + 31, "days since the closure began", 11, t["muted"], anchor="middle"))

    reopen = episode.duration_days - 1
    for panel_top, panel_bot in ((cap_y1, cap_y0), (q_y1, q_y0)):
        body.append(_line(X(reopen), panel_top, X(reopen), panel_bot, t["ink2"], 1.2, dash="4 3"))
    body.append(_text(X(reopen) + 5, cap_y1 + 10, "reopens", 11, t["ink2"], weight="600"))

    last = result["median"]["days_to_clear"] + reopen
    body.append(_text(x1 + 10, Yq(qmax * 0.35) - 4,
                      "last delayed shipment", 11, t["disrupt"], weight="600"))
    body.append(_text(x1 + 10, Yq(qmax * 0.35) + 10,
                      f"lands day {last}", 11, t["disrupt"], weight="600"))
    return _svg(W, H, body)


def main() -> int:
    frame, _ = load_shipments(EXAMPLES / "demo.csv")
    results = {}
    for name in FAMOUS:
        episode = resolve_episode(name, EXAMPLES)
        results[name] = (episode, drill(frame, episode, n_replays=300, seed=2026))

    OUT.mkdir(parents=True, exist_ok=True)
    ever_episode, ever_result = results["ever-given"]
    for mode in ("light", "dark"):
        (OUT / f"atlas-{mode}.svg").write_text(chart_atlas(mode))
        (OUT / f"impact-{mode}.svg").write_text(
            chart_impact({k: v[1] for k, v in results.items()}, mode))
        (OUT / f"timeline-{mode}.svg").write_text(
            chart_timeline(frame, ever_episode, ever_result, mode))
        print(f"wrote {mode} charts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
