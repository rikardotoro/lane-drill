import subprocess
import sys
from pathlib import Path

from lane_drill.data import load_shipments

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "src" / "lane_drill" / "examples"


def test_examples_stay_under_a_megabyte():
    total = sum(f.stat().st_size for f in EXAMPLES.glob("*.csv"))
    assert total < 1_000_000


def test_demo_loads_and_is_dense_enough():
    frame, dropped = load_shipments(EXAMPLES / "demo.csv")
    assert dropped == 0
    assert len(frame) > 1500
    assert frame["carrier_eta"].notna().all()
    baseline_miss = (frame["transit_days"] >
                     (frame["carrier_eta"] - frame["departure"]).dt.days).mean()
    assert 0.10 <= baseline_miss <= 0.30   # the promise is honest, not absurd


def test_demo_is_reproducible():
    subprocess.run(
        [sys.executable, "scripts/make_demo.py"],
        capture_output=True, text=True, check=True, cwd=ROOT,
    )
    diff = subprocess.run(
        ["git", "diff", "--exit-code", "--",
         "src/lane_drill/examples/demo.csv"],
        cwd=ROOT, capture_output=True,
    )
    assert diff.returncode == 0, "regenerating the demo must produce no git diff"
