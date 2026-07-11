from __future__ import annotations

from typing import cast

import pandas as pd

from defs.config import config

from .cli import PlotCommand


def _relative_strength(close: pd.Series, index_close: pd.Series) -> pd.Series:
    """Calculate Dorsey Relative Strength."""
    return (close / index_close * 100).round(2)


def _mansfield_relative_strength(
    close: pd.Series,
    index_close: pd.Series,
    period: int,
) -> pd.Series:
    """Calculate Mansfield Relative Strength."""
    rs = _relative_strength(close, index_close)
    sma_rs = rs.rolling(period).mean()
    return ((rs / sma_rs - 1) * 100).round(2)


def get_levels(
    df: pd.DataFrame,
    threshold: float,
) -> list[tuple[tuple[pd.Timestamp, float], tuple[pd.Timestamp, float]]]:
    """Identify support and resistance levels (v1)."""
    levels: list[tuple[pd.Timestamp, float]] = []

    local_max = df.High.loc[
        (df.High.shift(1) < df.High)
        & (df.High.shift(2) < df.High.shift(1))
        & (df.High.shift(-1) < df.High)
        & (df.High.shift(-2) < df.High.shift(-1))
    ].dropna()

    local_min = df.Low.loc[
        (df.Low.shift(1) > df.Low)
        & (df.Low.shift(2) > df.Low.shift(1))
        & (df.Low.shift(-1) > df.Low)
        & (df.Low.shift(-2) > df.Low.shift(-1))
    ].dropna()

    for idx in local_max.index:
        level_val = local_max[idx]
        if is_far_from_level(level_val, levels, threshold):
            levels.append((idx, level_val))

    for idx in local_min.index:
        level_val = local_min[idx]
        if is_far_from_level(level_val, levels, threshold):
            levels.append((idx, level_val))

    last_dt = cast(pd.Timestamp, df.index[-1])

    alines: list[tuple[tuple[pd.Timestamp, float], tuple[pd.Timestamp, float]]] = []
    for dt, price in levels:
        alines.append(((dt, price), (last_dt, price)))

    return alines


def is_far_from_level(
    level: float,
    levels: list[tuple[pd.Timestamp, float]],
    threshold: float,
) -> bool:
    """Return True if level is far from all existing levels."""
    return sum(abs(level - x[1]) < threshold for x in levels) == 0


def get_levels_v2(
    df: pd.DataFrame, mean_candle_size: float
) -> list[tuple[tuple[pd.Timestamp, float], tuple[pd.Timestamp, float]]]:

    levels: list[tuple[pd.Timestamp, float]] = []

    highs_mask = (
        (df.High.shift(1) < df.High)
        & (df.High.shift(2) < df.High)
        & (df.High.shift(3) < df.High)
        & (df.High.shift(-1) < df.High)
        & (df.High.shift(-2) < df.High)
        & (df.High.shift(-3) < df.High)
    )

    lows_mask = (
        (df.Low.shift(1) > df.Low)
        & (df.Low.shift(2) > df.Low)
        & (df.Low.shift(3) > df.Low)
        & (df.Low.shift(-1) > df.Low)
        & (df.Low.shift(-2) > df.Low)
        & (df.Low.shift(-3) > df.Low)
    )

    # filter for rejection from top
    # 2 succesive highs followed by 2 succesive lower highs
    max = df["High"].loc[highs_mask].dropna()
    min = df["Low"].loc[lows_mask].dropna()

    max_min = pd.concat([max, min], axis=0)

    max_min = max_min.loc[~max_min.index.duplicated()]

    last_dt = cast(pd.Timestamp, df.index[-1])

    for i, lv in max_min.items():
        ts = cast(pd.Timestamp, i)
        lv = cast(float, lv)

        touch_count = max_min.loc[(max_min - lv).abs() < mean_candle_size].count()

        if touch_count > 1 and is_far_from_level(lv, levels, mean_candle_size):
            levels.append((ts, lv))

    return [((i, lv), (last_dt, lv)) for i, lv in levels]


def _get_delivery_levels(df: pd.DataFrame) -> None:
    """Add delivery indicator columns to DataFrame (mutates in place)."""
    avg_trd_qty = df.QTY_PER_TRADE.rolling(config.DLV_AVG_LEN).mean().round(2)
    avg_dlv_qty = df.DLV_QTY.rolling(config.DLV_AVG_LEN).mean().round(2)
    df["DQ"] = df.DLV_QTY / avg_dlv_qty
    df["TQ"] = df.QTY_PER_TRADE / avg_trd_qty
    df["IM_F"] = (df.TQ > 1.2) & (df.DQ > 1.2)
    df["MCOverrides"] = None
    df["IM"] = float("nan")

    for idx in df.index:
        dq_val, im_val = df.loc[idx, ["DQ", "IM_F"]]
        if im_val:
            df.loc[idx, "IM"] = df.loc[idx, "Low"] * 0.99
        if dq_val >= config.DLV_L3:
            df.loc[idx, "MCOverrides"] = config.PLOT_DLV_L1_COLOR
        elif dq_val >= config.DLV_L2:
            df.loc[idx, "MCOverrides"] = config.PLOT_DLV_L2_COLOR
        elif dq_val > config.DLV_L1:
            df.loc[idx, "MCOverrides"] = config.PLOT_DLV_L3_COLOR
        else:
            df.loc[idx, "MCOverrides"] = config.PLOT_DLV_DEFAULT_COLOR


class IndicatorPipeline:
    """Computes and adds technical indicators to price DataFrames.

    Does not modify the original DataFrame; returns an enriched copy.
    """

    def __init__(self, command: PlotCommand) -> None:
        """Initialize with parsed command and configuration.

        Args:
            command: Parsed PlotCommand with indicator flags
        """
        self.cmd: PlotCommand = command
        self._index_close: pd.Series | None = None

    def set_index_close(self, series: pd.Series) -> None:
        """Set the benchmark index close series for RS calculations."""
        self._index_close = series

    def enrich(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add indicator columns to a copy of the DataFrame.

        Args:
            df: OHLC DataFrame to enrich

        Returns:
            Enriched DataFrame (copy) with indicator columns added
        """
        df = df.copy()
        df_len = df.shape[0]

        # RS - Dorsey Relative Strength
        if self.cmd.rs and self._index_close is not None:
            df.loc[:, "RS"] = _relative_strength(df.Close, self._index_close)

        # M_RS - Mansfield Relative Strength
        if self.cmd.mansfield_rs and self._index_close is not None:
            match self.cmd.timeframe:
                case "d":
                    rs_period = config.PLOT_M_RS_LEN_D
                case "w":
                    rs_period = config.PLOT_M_RS_LEN_W
                case "m":
                    rs_period = config.PLOT_M_RS_LEN_M
                case "q":
                    rs_period = config.PLOT_M_RS_LEN_Q

            if df_len < rs_period:
                print(
                    f"WARN: Inadequate data to plot Mansfield RS "
                    f"(need {rs_period}, have {df_len})."
                )
            else:
                df.loc[:, "M_RS"] = _mansfield_relative_strength(
                    df.Close,
                    self._index_close,
                    rs_period,
                )

        # SMA
        for period in self.cmd.sma:
            if df_len < period:
                print(
                    f"WARN: Inadequate data to plot SMA {period} "
                    f"(need {period}, have {df_len})."
                )
                continue
            df.loc[:, f"SMA_{period}"] = df.Close.rolling(period).mean().round(2)

        # EMA
        for period in self.cmd.ema:
            if df_len < period:
                print(f"WARN: Inadequate data to plot EMA {period}")
                continue
            alpha = 2 / (period + 1)
            df.loc[:, f"EMA_{period}"] = df.Close.ewm(alpha=alpha).mean().round(2)

        # Volume SMA
        for period in self.cmd.vol_sma:
            if df_len < period:
                print(f"WARN: Inadequate data to plot Volume SMA {period}")
                continue
            df.loc[:, f"VMA_{period}"] = df.Volume.rolling(period).mean().round(2)

        # Delivery data
        if self.cmd.delivery:
            _get_delivery_levels(df)

        return df

    def get_snr_levels(
        self, df: pd.DataFrame
    ) -> list[tuple[tuple[pd.Timestamp, float], tuple[pd.Timestamp, float]]] | None:
        """Compute SNR levels if configured.

        Args:
            df: OHLC DataFrame

        Returns:
            List of level line segments, or None if SNR not enabled
        """
        if self.cmd.snr is None:
            return None

        mean_candle_size = (df.High - df.Low).median()

        if self.cmd.snr == "v1":
            return get_levels(df, mean_candle_size)
        else:
            return get_levels_v2(df, mean_candle_size)
