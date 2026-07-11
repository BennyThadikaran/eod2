from __future__ import annotations

from pathlib import Path
from typing import cast

import matplotlib as mpl
import pandas as pd

from defs.config import config

from .breadth_render import BREADTH_INDICATORS, BreadthRenderer
from .candle_render import CandlestickRenderer
from .dtypes import TF_MAP, BreadthOption, PlotCommand, RenderContext


class NoDataError(RuntimeError):
    pass


def worker(
    symbol: str,
    cmd: PlotCommand,
    save_dir: Path,
    is_stock_mode: bool,
    plot_args: dict,
    context: RenderContext,
) -> bool:
    file = save_dir / f"{symbol.replace(' ', '-')}.png"

    if is_stock_mode:
        if not context.indicator_pipeline:
            raise RuntimeError("IndicatorPipeline not set")

        df = context.loader.load(symbol)

        if df is None or df.empty:
            raise NoDataError(f"No data for {symbol}")

        # Enrich with indicators
        df = context.indicator_pipeline.enrich(df)

        data_len = len(df)
        period = min(data_len, cmd.period)

        if context.plugin_runner:
            context.plugin_runner.apply(df, plot_args, period)
        df = df[-period:]
        df = cast(pd.DataFrame, df)

        # Add SNR levels
        if cmd.snr and is_stock_mode:
            snr_levels = context.indicator_pipeline.get_snr_levels(df)
            if snr_levels:
                plot_args["alines"] = dict(
                    alines=snr_levels,
                    linewidths=0.7,
                )

        # Check for marketcolor overrides (delivery)
        if "MCOverrides" in df.columns:
            plot_args["marketcolor_overrides"] = df["MCOverrides"].values
    else:
        df = context.loader.load_breadth_indicators()

        breadth_info = BREADTH_INDICATORS[symbol]
        df = df[breadth_info.columns]
        df = cast(pd.DataFrame, df)

    plot_args["xlim"] = (-2, df.shape[0] + 15)

    # Render with mplfinance
    fig, axs = context.renderer.render(df, plot_args, symbol=symbol)

    if context.drawing_manager is not None:
        context.drawing_manager.set_axes(axs[0])

        drawings = context.drawing_manager.get(symbol)
        assert isinstance(context.renderer, CandlestickRenderer)
        context.renderer.overlay_drawings(axs[0], drawings, df)

    fig.savefig(file, format="png")
    return True


class BatchRender:
    def __init__(
        self,
        cmd: PlotCommand,
        context: RenderContext,
        save_dir: Path,
        sym_list: list[str] | list[BreadthOption],
    ) -> None:

        self.sym_list = sym_list

        self.cmd = cmd

        self.context = context
        self.save_dir = save_dir

        if cmd.source.watch:
            self.save_dir = save_dir / cmd.source.watch.name

        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.plot_args = context.plot_args.copy()

        if config.PLOT_SIZE is None:
            self.plot_args["figsize"] = (14, 9)
        else:
            self.plot_args["figsize"] = config.PLOT_SIZE

        self.plot_args["figscale"] = 1

        mpl.use("Agg")

    def save_all(self):
        import traceback
        from concurrent.futures import ProcessPoolExecutor, as_completed

        futures = {}
        plot_args = self.plot_args.copy()

        with ProcessPoolExecutor() as executor:
            for sym in self.sym_list:
                symbol, _, meta = sym.partition(",")

                title = symbol.upper()

                if meta:
                    title += f" • {meta.upper()}"

                title += f" • {TF_MAP[self.cmd.timeframe]}"

                plot_args["title"] = title

                future = executor.submit(
                    worker,
                    symbol=symbol,
                    cmd=self.cmd,
                    save_dir=self.save_dir,
                    is_stock_mode=self.cmd.source.mode == "stock",
                    plot_args=plot_args,
                    context=self.context,
                )

                futures[future] = sym

            length = len(futures)
            count = 0
            for future in as_completed(futures):
                sym = futures[future]

                count += 1
                print(f"{count} of {length}", end="\r", flush=True)

                try:
                    future.result()
                except NoDataError as e:
                    print(f"{sym}: {e}")
                except Exception:
                    traceback.print_exc()
