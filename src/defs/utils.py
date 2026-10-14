from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional

import pandas as pd
from fast_csv_loader import csv_loader

ohlc_dct = dict(
    Open="first",
    High="max",
    Low="min",
    Close="last",
    Volume="sum",
)


class DateEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def load_json(fpath: Path):
    return json.loads(fpath.read_text(encoding="utf-8-sig"))


def write_json(fpath: Path, data):
    fpath.write_text(
        json.dumps(data, indent=2, cls=DateEncoder),
        encoding="utf-8",
    )


def get_dataframe(
    fpath: Path,
    period: int,
    tf: Literal["daily", "weekly"] = "daily",
    columns: Optional[List[str]] = None,
    toDate: Optional[datetime] = None,
) -> pd.DataFrame:
    candle_count = period * 5 if tf == "weekly" else period

    df = csv_loader(fpath, candle_count, end_date=toDate, use_columns=columns)

    if tf == "weekly":
        if columns:
            # Guard against non existent keys and remove columns not required.
            dct = {k: ohlc_dct[k] for k in columns if k in ohlc_dct}
        else:
            dct = ohlc_dct

        return df.resample("W", label="left").apply(dct).iloc[-period:]

    return df.iloc[-period:]
