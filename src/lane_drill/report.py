import pandas as pd
from rich.console import Console
from rich.table import Table

from lane_drill.episodes import Episode


def timeline_events(
    frame: pd.DataFrame, episode: Episode, median_replay: dict
) -> list[tuple[int, str]]:
    start = median_replay["start"]
    delays = median_replay["delays"]
    departures = frame["departure"].reset_index(drop=True)
    day_of = ((departures - start) // pd.Timedelta(days=1)).to_numpy()

    events: list[tuple[int, str]] = [
        (0, f"the waterway closes to {episode.depth:.0%} of normal capacity")
    ]

    queued = delays > 0
    if queued.any():
        first = int(day_of[queued].min())
        events.append((first, "your first shipment joins the queue"))

    reopen = episode.duration_days - 1
    waiting_at_reopen = int(
        ((day_of <= reopen) & (day_of + delays > reopen)).sum()
    )
    events.append((reopen, f"the waterway reopens — {waiting_at_reopen} of your "
                           "shipments still waiting"))

    if queued.any():
        served = day_of + delays
        cleared = int(served[queued].max())
        events.append((cleared, "your backlog finally clears"))
        transits = frame["transit_days"].to_numpy()
        last_arrival = int((day_of + delays + transits)[queued].max())
        events.append((last_arrival,
                       f"your last delayed shipment lands — "
                       f"{last_arrival - reopen} days after the reopening"))

    return sorted(events, key=lambda item: item[0])


def to_dict(result: dict) -> dict:
    payload = {k: v for k, v in result.items() if k != "median_replay"}
    return payload


def render(frame: pd.DataFrame, episode: Episode, result: dict,
           timeline: bool = True) -> None:
    console = Console()

    table = Table(title=f"The drill — {episode.chokepoint} "
                        f"{result['episode']['start']} shape, "
                        f"{result['n_replays']} replays on your lane")
    table.add_column("Transit days")
    table.add_column("Baseline", justify="right")
    table.add_column("Median drill", justify="right")
    table.add_column("Worst decile", justify="right")
    for key, label in (("p50", "P50"), ("p80", "P80"), ("p90", "P90")):
        table.add_row(
            label,
            f"{result['baseline'][key]:.0f}",
            f"{result['median'][key]:.0f}",
            f"{result['worst_decile'][key]:.0f}",
            style="bold" if key == "p80" else None,
        )
    table.add_row(
        "Promises missed",
        f"{result['baseline']['promise_miss']:.0%}",
        f"{result['median']['promise_miss']:.0%}",
        f"{result['worst_decile']['promise_miss']:.0%}",
    )
    console.print(table)

    median = result["median"]
    console.print(
        f"\nIn the median replay, {median['pct_delayed']:.0%} of the struck "
        f"quarter's shipments are delayed (worst single delay "
        f"{median['max_delay']} days), and the last disruption-delayed shipment "
        f"lands [bold]{median['days_to_clear']} days after the waterway "
        f"reopened[/bold]."
    )

    if timeline:
        console.print("\n[bold]The median replay, day by day:[/bold]")
        for day, label in timeline_events(frame, episode, result["median_replay"]):
            console.print(f"  [orange3]day {day:>3}[/orange3]  {label}")

    console.print(
        f"\nEpisode shape measured from IMF PortWatch, {episode.chokepoint}, "
        f"{result['episode']['start']} to {result['episode']['end']} "
        f"(depth {result['episode']['depth']:.0%}, "
        f"{result['episode']['duration_days']} days)."
    )
    console.print("This answers [bold]what if[/bold], never how likely.")
