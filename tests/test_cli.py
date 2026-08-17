import json

import numpy as np
import pandas as pd
from typer.testing import CliRunner

from lane_drill.cli import app

runner = CliRunner()


def _csv(tmp_path):
    rng = np.random.default_rng(3)
    n = 300
    dep = pd.Timestamp("2023-01-01") + pd.to_timedelta(
        np.sort(rng.integers(0, 540, size=n)), unit="D")
    transit = rng.normal(30, 3, size=n).clip(min=22).round()
    frame = pd.DataFrame({
        "shipment": [f"S{i}" for i in range(n)],
        "origin": "CNSHA", "destination": "NLRTM", "carrier": "MAEU",
        "departure": dep.date,
        "arrival": (dep + pd.to_timedelta(transit, unit="D")).date,
        "carrier_eta": (dep + pd.Timedelta(days=33)).date,
    })
    path = tmp_path / "s.csv"
    frame.to_csv(path, index=False)
    return path


def test_cli_runs_and_reports(tmp_path):
    result = runner.invoke(app, [
        "--data", str(_csv(tmp_path)), "--lane", "CNSHA-NLRTM",
        "--episode", "ever-given", "--replays", "25",
    ])
    assert result.exit_code == 0, result.stdout
    assert "Baseline" in result.stdout
    assert "what if" in result.stdout


def test_cli_json_is_valid(tmp_path):
    result = runner.invoke(app, [
        "--data", str(_csv(tmp_path)), "--lane", "CNSHA-NLRTM",
        "--episode", "ever-given", "--replays", "25", "--json",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "p80" in payload["median"]


def test_list_episodes(tmp_path):
    result = runner.invoke(app, ["--list-episodes"])
    assert result.exit_code == 0
    assert "suez" in result.stdout


def test_unknown_episode_lists_catalog(tmp_path):
    result = runner.invoke(app, [
        "--data", str(_csv(tmp_path)), "--lane", "CNSHA-NLRTM",
        "--episode", "krakatoa",
    ])
    assert result.exit_code != 0
    assert "ever-given" in result.stdout
