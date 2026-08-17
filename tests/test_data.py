from pathlib import Path

import pandas as pd
import pytest

from lane_drill.data import detect_columns, filter_lane, load_shipments
from lane_drill.errors import InvalidDataError, MissingColumnError


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "s.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_detects_canonical_names():
    cols = ["shipment", "origin", "destination", "carrier", "departure", "arrival"]
    assert detect_columns(cols)["origin"] == "origin"


def test_detects_common_aliases():
    cols = ["BL Number", "POL", "POD", "Shipping Line", "ATD", "ATA", "Promised"]
    mapping = detect_columns(cols)
    assert mapping["shipment"] == "BL Number"
    assert mapping["origin"] == "POL"
    assert mapping["destination"] == "POD"
    assert mapping["carrier"] == "Shipping Line"
    assert mapping["departure"] == "ATD"
    assert mapping["arrival"] == "ATA"
    assert mapping["carrier_eta"] == "Promised"


def test_override_beats_detection():
    cols = ["shipment", "origin", "destination", "carrier", "departure", "arrival", "gate_out"]
    mapping = detect_columns(cols, overrides={"departure": "gate_out"})
    assert mapping["departure"] == "gate_out"


def test_missing_required_column_names_the_column():
    cols = ["shipment", "origin", "destination", "carrier", "departure"]
    with pytest.raises(MissingColumnError, match="arrival"):
        detect_columns(cols)


def test_load_computes_transit_days(tmp_path):
    path = _write(tmp_path, [
        {"shipment": "S1", "origin": "CNSHA", "destination": "NLRTM",
         "carrier": "MAEU", "departure": "2023-01-01", "arrival": "2023-01-24"},
    ])
    frame, dropped = load_shipments(path)
    assert frame.loc[0, "transit_days"] == 23.0
    assert dropped == 0


def test_in_transit_rows_are_dropped_and_counted(tmp_path):
    path = _write(tmp_path, [
        {"shipment": "S1", "origin": "A", "destination": "B", "carrier": "X",
         "departure": "2023-01-01", "arrival": "2023-01-24"},
        {"shipment": "S2", "origin": "A", "destination": "B", "carrier": "X",
         "departure": "2023-01-05", "arrival": None},
        {"shipment": "S3", "origin": "A", "destination": "B", "carrier": "X",
         "departure": "2023-01-06", "arrival": None},
    ])
    frame, dropped = load_shipments(path)
    assert len(frame) == 1 and dropped == 2


def test_unparseable_date_names_the_row(tmp_path):
    path = _write(tmp_path, [
        {"shipment": "S1", "origin": "A", "destination": "B", "carrier": "X",
         "departure": "not-a-date", "arrival": "2023-01-24"},
    ])
    with pytest.raises(InvalidDataError, match="row 0"):
        load_shipments(path)


def test_arrival_before_departure_is_rejected(tmp_path):
    path = _write(tmp_path, [
        {"shipment": "S1", "origin": "A", "destination": "B", "carrier": "X",
         "departure": "2023-02-01", "arrival": "2023-01-24"},
    ])
    with pytest.raises(InvalidDataError, match="row 0"):
        load_shipments(path)


def test_filter_lane_is_case_insensitive():
    frame = pd.DataFrame({
        "shipment": ["S1", "S2"],
        "origin": ["cnsha", "CNSHA"], "destination": ["nlrtm", "DEHAM"],
        "carrier": ["MAEU", "MAEU"],
        "departure": pd.to_datetime(["2023-01-01", "2023-01-02"]),
        "arrival": pd.to_datetime(["2023-01-24", "2023-01-26"]),
    })
    assert len(filter_lane(frame, "CNSHA", "NLRTM")) == 1
