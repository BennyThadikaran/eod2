from __future__ import annotations

import sys
from pathlib import Path

DIR = Path(__file__).parents[1]
sys.path.insert(0, str(DIR))

import pickle
from typing import Any

from util import load_json, write_json

from defs.config import config

TIMEFRAME_MAP = dict(
    daily="d",
    weekly="w",
)

COLOR_MAP = dict(
    axhline=config.PLOT_AXHLINE_COLOR,
    hline=config.PLOT_HLINE_COLOR,
    tline=config.PLOT_TLINE_COLOR,
    aline=config.PLOT_ALINE_COLOR,
)


def timestamp_to_iso(value: Any) -> str:
    """Convert pandas Timestamp / datetime-like value to ISO date string."""
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()

    return value.date().isoformat()


def number_to_float(value: Any) -> float:
    """Convert numpy/pandas scalar values to plain Python float."""
    if hasattr(value, "item"):
        value = value.item()

    return float(value)


def get_kind(url: str) -> str:
    """Extract drawing kind from URL like 'aline:jwjpwp'."""
    kind, _ = url.split(":")

    if kind not in {"aline", "axhline", "hline", "tline"}:
        raise ValueError(f"Unknown drawing kind in url: {url!r}")

    return kind


def convert_line(url: str, raw_line: Any) -> dict[str, Any]:
    """Convert one old pickle line entry into the new Drawing JSON shape."""
    kind = get_kind(url)
    color = COLOR_MAP[kind]

    if kind == "axhline":
        y = number_to_float(raw_line)

        points = [
            ["", y],
        ]

    elif kind == "hline":
        y, start_ts, end_ts = raw_line

        y = number_to_float(y)

        points = [
            [timestamp_to_iso(start_ts), y],
            [timestamp_to_iso(end_ts), y],
        ]

    elif kind in {"aline", "tline"}:
        (start_ts, y1), (end_ts, y2) = raw_line

        points = [
            [timestamp_to_iso(start_ts), number_to_float(y1)],
            [timestamp_to_iso(end_ts), number_to_float(y2)],
        ]

    else:
        raise ValueError(f"Unsupported drawing kind: {kind!r}")

    return {
        "kind": kind,
        "points": points,
        "color": color,
        "url": url,
    }


def load_pickle(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return pickle.load(f)


def migrate_symbol_file(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Convert one old symbol pickle file.

    Returns:
        timeframe -> url -> Drawing dict
    """
    old_data = load_pickle(path)
    migrated: dict[str, dict[str, dict[str, Any]]] = {}

    for old_tf, new_tf in TIMEFRAME_MAP.items():
        timeframe_data = old_data.get(old_tf, {})
        old_lines = timeframe_data.get("lines", {})

        if not old_lines:
            continue

        migrated.setdefault(new_tf, {})

        for url, raw_line in old_lines.items():
            migrated[new_tf][url] = convert_line(url, raw_line)

    return migrated


def migrate_all(
    lines_dir: Path,
    drawings_path: Path,
) -> dict[str, Any]:
    """Migrate all pickle files into drawings.json.

    Args:
        lines_dir: Directory containing old '<symbol>.p' files.
        drawings_json_path: Target drawings.json path.
        overwrite_symbol_timeframe:
            If False, merge old drawings into existing timeframe/symbol mappings.
            If True, replace each migrated symbol for each migrated timeframe.

    Returns:
        The full migrated drawings JSON data.
    """
    if not lines_dir.is_dir():
        raise NotADirectoryError(f"Folder not found or not a folder: {lines_dir}")

    if drawings_path.is_file():
        drawings = load_json(drawings_path)
    else:
        drawings = {}

    for pickle_path in lines_dir.iterdir():
        symbol = pickle_path.stem.lower()
        old_dict = migrate_symbol_file(pickle_path)

        for timeframe, url_map in old_dict.items():
            drawings.setdefault(timeframe, {})

            drawings[timeframe][symbol] = url_map

    write_json(drawings_path, drawings)

    return drawings


if __name__ == "__main__":
    LINE_DIR = DIR / "data/lines"
    DRAWING_PATH = DIR / "data/drawings.json"

    drawings = migrate_all(
        lines_dir=LINE_DIR,
        drawings_path=DRAWING_PATH,
    )

    total = sum(
        len(url_map)
        for symbol_map in drawings.values()
        for url_map in symbol_map.values()
    )

    print(f"Migrated drawings written to: {DRAWING_PATH}")
    print(f"Total drawings in file: {total}")
