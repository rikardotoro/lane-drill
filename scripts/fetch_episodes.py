"""Pull daily chokepoint transit counts from IMF PortWatch into the package.

Source: IMF PortWatch (https://portwatch.imf.org/), Daily Chokepoint Transit
Calls, served from the public ArcGIS endpoint — free, no API key. The slices
committed here keep only date and n_total per chokepoint (a transformation
of the source data; see examples/SOURCE.md for the attribution note).
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

EXAMPLES = Path(__file__).parent.parent / "src" / "lane_drill" / "examples"
ENDPOINT = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/"
            "Daily_Chokepoints_Data/FeatureServer/0/query")

CHOKEPOINTS = {
    "suez": "Suez Canal",
    "bab_el_mandeb": "Bab el-Mandeb Strait",
    "panama": "Panama Canal",
}

SPAN = ("2019-01-01", "2024-12-31")
PAGE = 1000  # the server clamps to 1000 records per page regardless of the ask


def fetch(portname: str) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    offset = 0
    while True:
        params = {
            "where": (f"portname='{portname}' AND date >= DATE '{SPAN[0]}' "
                      f"AND date <= DATE '{SPAN[1]}'"),
            "outFields": "date,n_total",
            "orderByFields": "date",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
            "f": "json",
        }
        with urlopen(f"{ENDPOINT}?{urlencode(params)}", timeout=120) as response:
            payload = json.load(response)
        if "error" in payload:
            raise RuntimeError(payload["error"])
        features = payload.get("features", [])
        rows += [(f["attributes"]["date"][:10], int(f["attributes"]["n_total"]))
                 for f in features]
        if len(features) < PAGE:
            return rows
        offset += PAGE


def main() -> int:
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    for slug, portname in CHOKEPOINTS.items():
        rows = fetch(portname)
        out = EXAMPLES / f"portwatch_{slug}.csv"
        out.write_text("date,n_total\n" + "\n".join(f"{d},{n}" for d, n in rows) + "\n")
        print(f"{slug}: {len(rows)} days -> {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
