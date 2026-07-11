from __future__ import annotations

import sys
from pathlib import Path

import renderer.cli as cli
from defs.config import config
from renderer.annotations import DrawingManager, DrawingTool
from renderer.breadth_render import BreadthRenderer
from renderer.candle_render import CandlestickRenderer
from renderer.coordinator import PlotCoordinator
from renderer.dtypes import TF_MAP, AppPaths, RenderContext
from renderer.indicators import IndicatorPipeline
from renderer.loader import EODFileLoader
from renderer.navigation import NavigationList
from renderer.persistence import SessionStore


def main(argv: list[str] | None = None) -> int:
    paths = AppPaths.from_root(Path(__file__).parent)

    try:
        action = cli.parse_cli(argv, config_path=paths.config_path)

        return run_action(action, paths)
    except cli.CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def run_action(action: cli.CliAction, paths: AppPaths) -> int:
    match action.kind:
        case "list":
            cli.print_available()
            return 0
        case "preset_remove":
            if not action.name:
                raise cli.CliError("Missing preset name")

            cli.remove_preset(paths.config_path, action.name)
            return 0
        case "watch_add":
            if not action.name or action.path is None:
                raise cli.CliError("Missing watchlist name or path")

            cli.add_watch(action.name, action.path, paths.config_path)
            return 0
        case "watch_remove":
            if not action.name:
                raise cli.CliError("Missing watchlist name")

            cli.remove_watch(action.name, paths.config_path)
            return 0
        case "run":
            return run_chart(action.command, paths)

    raise cli.CliError(f"Unsupported CLI action: {action.kind}")


def run_chart(cmd, paths: AppPaths) -> int:
    if cmd.timeframe in {"w", "m", "q"} and cmd.delivery:
        print("WARN: Delivery data not available on weekly timeframe or higher")
        return 0

    cli.validate_file(paths.breadth_file)
    sym_list = cli.resolve_symbols(cmd)

    if cmd.source.mode == "stock":
        context = build_stock_context(cmd, paths)
    else:
        context = build_breadth_context(cmd, paths)

    if cmd.save:
        save_all(cmd, paths, sym_list, context)
        return 0

    run_interactive(cmd, sym_list, context)
    return 0


def build_stock_context(cmd, paths: AppPaths) -> RenderContext:

    from renderer.panels import allocate_indicator_panels

    indicator_pipeline = IndicatorPipeline(cmd)

    panel_layout = allocate_indicator_panels(cmd)

    plot_args = dict(
        type=config.PLOT_CHART_TYPE,
        style=config.PLOT_CHART_STYLE,
        volume=cmd.volume,
        xrotation=0,
        datetime_format="%d %b %y",
        scale_padding=dict(left=0.28, right=0.65, top=0.3, bottom=0.38),
    )

    if cmd.volume:
        plot_args["volume_panel"] = 1

    loader = EODFileLoader(
        timeframe=cmd.timeframe,
        data_path=paths.data_path,
        breadth_filepath=paths.breadth_file,
        period=cli.compute_max_period(cmd),
        index_name="nifty 500",
        end_date=cmd.date,
    )

    if cmd.rs or cmd.mansfield_rs:
        cli.validate_file(paths.rs_index_file)

        idx_df = loader.load(config.PLOT_RS_INDEX)

        if idx_df is None:
            print(f"WARN: Could not load index data for {config.PLOT_RS_INDEX}")
            exit(1)

        indicator_pipeline.set_index_close(idx_df.Close)

    plugin_runner = None

    if cmd.plugins:
        from renderer.plugins.runner import PluginRunner

        plugin_runner = PluginRunner(
            cmd.plugins,
            panel_layout=panel_layout,
        )

    drawing_manager = DrawingManager(timeframe=cmd.timeframe)

    session_store = SessionStore(
        paths.config_path,
        paths.drawings,
        paths.selections,
        timeframe=cmd.timeframe,
    )

    return RenderContext(
        loader=loader,
        renderer=CandlestickRenderer(panel_layout),
        indicator_pipeline=indicator_pipeline,
        drawing_manager=drawing_manager,
        plot_args=plot_args,
        session_store=session_store,
        plugin_runner=plugin_runner,
        panel_layout=panel_layout,
    )


def build_breadth_context(cmd, paths: AppPaths) -> RenderContext:
    if cmd.source.breadth is None:
        raise cli.CliError("Breadth command missing breadth source details")

    breadth = cmd.source.breadth

    return RenderContext(
        loader=EODFileLoader(
            timeframe=cmd.timeframe,
            data_path=paths.data_path,
            breadth_filepath=paths.breadth_file,
            period=cmd.period,
            index_name=breadth.index,
            end_date=cmd.date,
        ),
        renderer=BreadthRenderer(
            index_name=breadth.index, timeframe=TF_MAP[cmd.timeframe]
        ),
        indicator_pipeline=None,
        drawing_manager=None,
        plot_args=dict(
            figsize=(12, 6) if config.PLOT_SIZE is None else config.PLOT_SIZE,
            constrained_layout=True,
        ),
        session_store=None,
    )


def save_all(cmd, paths: AppPaths, sym_list, context: RenderContext) -> None:
    from renderer.batch import BatchRender

    if context.drawing_manager is not None and paths.drawings.is_file():
        drawings = cli.load_json(paths.drawings)

        context.drawing_manager.from_dict(drawings[cmd.timeframe])

    batch = BatchRender(
        cmd=cmd,
        context=context,
        save_dir=paths.save_dir,
        sym_list=sym_list,
    )

    batch.save_all()


def run_interactive(cmd, sym_list, context: RenderContext) -> None:
    nav = NavigationList(
        items=sym_list,
        length=len(sym_list),
        current_index=resume_index(cmd, len(sym_list)),
    )

    drawing_tool = None

    if context.drawing_manager is not None:
        drawing_tool = DrawingTool(
            magnet_mode=config.MAGNET_MODE if cmd.source.mode == "stock" else False,
            drawing_manager=context.drawing_manager,
        )

    coordinator = PlotCoordinator(
        cmd=cmd,
        nav=nav,
        context=context,
        drawing_tool=drawing_tool,
    )

    coordinator.run()


def resume_index(cmd, symbol_count: int) -> int:
    if cmd.source.mode != "stock":
        return 0

    if not cmd.source.watch or not cmd.source.watch.resume:
        return 0

    idx = cmd.source.watch.resume.idx

    return idx if idx < symbol_count else 0


if __name__ == "__main__":
    exit(main())
