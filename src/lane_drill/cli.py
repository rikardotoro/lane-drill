import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from lane_drill.data import filter_lane, load_shipments
from lane_drill.episodes import atlas, resolve_episode
from lane_drill.errors import LaneDrillError
from lane_drill.replay import drill
from lane_drill.report import render, to_dict

app = typer.Typer(add_completion=False,
                  help="A fire drill for one shipping lane.")
console = Console()

EXAMPLES = Path(__file__).parent / "examples"


@app.command()
def main(
    data: Annotated[Path | None, typer.Option(help="Shipment history CSV.")] = None,
    demo: Annotated[bool, typer.Option(help="Use the bundled synthetic lane.")] = False,
    lane: Annotated[str | None, typer.Option(help="ORIGIN-DEST, e.g. CNSHA-NLRTM.")] = None,
    episode: Annotated[str | None, typer.Option(help="ever-given, red-sea, panama-drought, or chokepoint:YYYY-MM.")] = None,
    list_episodes: Annotated[bool, typer.Option("--list-episodes", help="Print the measured episode atlas and exit.")] = False,
    replays: Annotated[int, typer.Option(help="Monte Carlo replays of the episode's timing.")] = 1000,
    seed: Annotated[int, typer.Option()] = 2026,
    service_level: Annotated[float, typer.Option()] = 0.8,
    min_shipments: Annotated[int, typer.Option()] = 30,
    map_: Annotated[list[str] | None, typer.Option("--map", help="canonical=column")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
    timeline: Annotated[bool, typer.Option("--timeline/--no-timeline")] = True,
) -> None:
    try:
        if list_episodes:
            catalog = Table(title="The episode atlas — measured from IMF PortWatch")
            for column in ("Episode", "Start", "End", "Depth", "Days", "Surge"):
                catalog.add_column(column)
            for ep in atlas(EXAMPLES):
                catalog.add_row(ep.label, str(ep.start.date()), str(ep.end.date()),
                                f"{ep.depth:.0%}", str(ep.duration_days),
                                f"{ep.surge:.2f}")
            console.print(catalog)
            raise typer.Exit(code=0)

        if demo:
            data = data or EXAMPLES / "demo.csv"
            lane = lane or "CNSHA-NLRTM"
            episode = episode or "ever-given"
        if data is None or episode is None:
            raise typer.BadParameter(
                "provide --data and --episode (or --demo, or --list-episodes)")

        overrides = dict(item.split("=", 1) for item in (map_ or []))
        frame, dropped = load_shipments(data, overrides or None)
        if dropped:
            console.print(f"[dim]{dropped} in-transit rows dropped — "
                          "a drill replays completed history.[/dim]")

        if lane:
            origin, _, dest = lane.partition("-")
            frame = filter_lane(frame, origin, dest)

        chosen = resolve_episode(episode, EXAMPLES)
        result = drill(frame, chosen, n_replays=replays, seed=seed,
                       service_level=service_level, min_shipments=min_shipments)
    except LaneDrillError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    if as_json:
        print(json.dumps(to_dict(result), indent=2))
    else:
        render(frame, chosen, result, timeline=timeline)


if __name__ == "__main__":
    app()
