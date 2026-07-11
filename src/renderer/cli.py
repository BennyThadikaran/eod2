from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from defs.config import config

from .dtypes import (
    BreadthCommand,
    BreadthOption,
    PlotCommand,
    PlotSource,
    ResumeCommand,
    WatchCommand,
)
from .util import load_json, write_json

BREADTH_CHOICES: list[BreadthOption] = ["50", "200", "sma", "nethighs", "adline", "osc"]
DEFAULT_BREADTH: list[BreadthOption] = ["sma", "nethighs", "adline", "osc"]

INDEX_ALIAS: dict[str, str] = dict(
    n50="nifty 50",
    n100="nifty 100",
    n200="nifty 200",
    n500="nifty 500",
    next50="nifty next 50",
    m50="nifty midcap 50",
    m100="nifty midcap 100",
    mselect="nifty midcap select",
    s100="nifty smallcap 100",
    s50="nifty smallcap 50",
    nbank="nifty bank",
    nfin="nifty financial services",
    ttlmkt="nifty total market",
)

TF_PERIOD_MAP = dict(
    d=config.PLOT_DAYS,
    w=config.PLOT_WEEKS,
    m=config.PLOT_MONTHS,
    q=config.PLOT_QUARTERS,
)

# Only these options select chart data.
SOURCE_KEYS = {"sym", "file", "breadth", "watch"}

# These are also treated as source-related for preset compatibility because they
# affect the data/source path rather than chart display configuration.
SOURCE_RELATED_KEYS = SOURCE_KEYS | {"index", "resume"}

MANAGEMENT_KEYS = {"ls", "preset_rm", "watch_add", "watch_rm"}

PRESET_IGNORED_KEYS = SOURCE_RELATED_KEYS | MANAGEMENT_KEYS | {"preset", "preset_save"}


class CliError(RuntimeError):
    """Raised for CLI errors."""


@dataclass(frozen=True)
class CliAction:
    kind: Literal["run", "list", "preset_remove", "watch_add", "watch_remove"]
    command: PlotCommand | None = None
    name: str | None = None
    path: Path | None = None


def normalize_symbol_list(symbols: list[str]) -> list[str]:
    return [INDEX_ALIAS.get(symbol.lower(), symbol.lower()) for symbol in symbols]


def normalize_index(index: str) -> str:
    index = index.lower()
    return INDEX_ALIAS.get(index, index)


def parse_date(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use ISO format YYYY-MM-DD") from exc


def validate_file(path: Path) -> None:
    if not path.exists():
        raise CliError(f"File not found: {path}")

    if not path.is_file():
        raise CliError(f"Not a file: {path}")


def plugin_option_name(plugin_key: str, plugin_config: dict[str, Any]) -> str:
    option_name = (
        plugin_config.get("option") or plugin_config.get("name") or plugin_key.lower()
    )
    return str(option_name).lstrip("-").replace("_", "-").lower()


def plugin_dest(plugin_key: str, plugin_config: dict[str, Any]) -> str:
    return plugin_option_name(plugin_key, plugin_config).replace("-", "_")


def selected_plugins_from_args(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    selected = dict()

    for plugin_key, plugin_config in config.CHART_PLUGINS.items():
        if not isinstance(plugin_config, dict):
            raise CliError(f"Plugin config for '{plugin_key}' must be an object")

        if not getattr(args, plugin_dest(plugin_key, plugin_config), False):
            continue

        selected_config = dict(plugin_config)
        selected_config.setdefault("name", str(plugin_key).lower())
        selected[str(plugin_key).upper()] = selected_config

    return selected


def build_parser(
    *,
    require_source: bool = True,
    suppress_defaults: bool = False,
    include_preset: bool = False,
    include_management: bool = False,
) -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        prog="chart.py",
        argument_default=argparse.SUPPRESS if suppress_defaults else None,
    )

    mode_group = parser.add_argument_group(
        "Mode",
        description="One of these options must be present.",
    )

    mode_exclusive = mode_group.add_mutually_exclusive_group(required=require_source)

    indicator_group = parser.add_argument_group(
        "Indicators", description="Chart Indicators"
    )

    mode_exclusive.add_argument(
        "--sym",
        nargs="+",
        metavar="SYM",
        help="Space separated list of stock symbols.",
    )

    mode_exclusive.add_argument(
        "-f",
        "--file",
        type=Path,
        help="Path to symbol file.",
    )

    mode_exclusive.add_argument(
        "-b",
        "--breadth",
        nargs="*",
        choices=BREADTH_CHOICES,
        help="Plot market breadth indicators. With no values, defaults to: sma nethighs adline osc.",
    )

    mode_exclusive.add_argument(
        "--watch",
        metavar="NAME",
        help="Load a watchlist file by NAME.",
    )

    if include_management:
        mode_exclusive.add_argument(
            "--watch-add",
            nargs=2,
            metavar=("NAME", "FILENAME"),
            help="Save a watchlist by NAME and FILENAME.",
        )

        mode_exclusive.add_argument(
            "--watch-rm",
            metavar="NAME",
            help="Remove a watchlist by NAME.",
        )

        mode_exclusive.add_argument(
            "--preset-rm",
            metavar="NAME",
            help="Remove preset by NAME.",
        )

        mode_exclusive.add_argument(
            "--ls",
            action="store_true",
            help="List available presets and watchlists.",
        )

    if include_preset:
        parser.add_argument(
            "--preset",
            metavar="NAME",
            help="Load chart settings saved by NAME. Must be combined with --sym, --watch, -f/--file, or --breadth.",
        )

    parser.add_argument(
        "--preset-save",
        metavar="NAME",
        help="Save chart display settings by NAME. Source options are not stored.",
    )

    indicator_group.add_argument(
        "-v",
        "--volume",
        action="store_true",
        help="Add Volume",
    )

    indicator_group.add_argument(
        "--rs",
        action="store_true",
        help="Dorsey Relative strength indicator.",
    )

    indicator_group.add_argument(
        "--m-rs",
        action="store_true",
        help="Mansfield Relative strength indicator.",
    )

    indicator_group.add_argument(
        "--sma",
        type=int,
        nargs="+",
        metavar="int",
        help="Simple Moving average",
    )

    indicator_group.add_argument(
        "--ema",
        type=int,
        nargs="+",
        metavar="int",
        help="Exponential Moving average",
    )

    indicator_group.add_argument(
        "--vol-sma",
        type=int,
        nargs="+",
        metavar="int",
        help="Volume Moving average",
    )

    indicator_group.add_argument(
        "--snr",
        nargs="?",
        choices=("v1", "v2"),
        const="v1",
        help="Add Support and Resistance levels on chart. Use v2 for multiple touch points. Default v1.",
    )

    indicator_group.add_argument(
        "--dlv",
        action="store_true",
        help="Delivery Mode. Plot delivery data on chart.",
    )

    if config.CHART_PLUGINS:
        plugin_group = parser.add_argument_group(
            "Plugins", description="Custom indicator plugins"
        )

        for plugin_key, plugin_config in config.CHART_PLUGINS.items():
            if not isinstance(plugin_config, dict):
                raise CliError(f"Plugin config for '{plugin_key}' must be an object")

            option_name = plugin_option_name(plugin_key, plugin_config)

            help_text = plugin_config.get("help") or f"Add {plugin_key} plugin"

            plugin_group.add_argument(
                f"--{option_name}",
                action="store_true",
                dest=plugin_dest(plugin_key, plugin_config),
                help=help_text,
            )

    parser.add_argument(
        "-d",
        "--date",
        type=parse_date,
        metavar="str",
        help="ISO format date YYYY-MM-DD.",
    )

    parser.add_argument(
        "--period",
        action="store",
        type=int,
        metavar="int",
        help="Number of Candles to plot.",
    )

    parser.add_argument(
        "-r",
        "--resume",
        action="store_true",
        help="Resume a watchlist from last viewed chart.",
    )

    parser.add_argument(
        "-s",
        "--save",
        action="store_true",
        help="Save chart as png.",
    )

    parser.add_argument(
        "--tf",
        action="store",
        metavar="{d,w,m,q}",
        choices=("d", "w", "m", "q"),
        help="Timeframe. Default 'd'.",
    )

    parser.add_argument(
        "-i",
        "--index",
        nargs="?",
        const="nifty 500",
        help="Index to use alongside breadth indicators (default: nifty 500). Usage: -i 'nifty 50'. Only works with `-b` or `--breadth`.",
        default=None if suppress_defaults else "nifty 500",
    )

    return parser


def normalize_source(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> PlotSource:
    if args.sym:
        return PlotSource(kind="symbols", symbols=normalize_symbol_list(args.sym))

    if args.file:
        validate_file(args.file)

        return PlotSource(kind="file", file=args.file)

    if args.breadth is not None:
        return PlotSource(
            kind="breadth",
            mode="breadth",
            breadth=BreadthCommand(
                index=normalize_index(args.index),
                indicators=args.breadth or DEFAULT_BREADTH,
            ),
        )

    if args.watch:
        resume = None
        watch_name = args.watch.upper()

        if args.resume and config.CHART_RESUME is not None:
            resume_config = config.CHART_RESUME

            if watch_name in resume_config:
                resume = ResumeCommand(watch=watch_name, idx=resume_config[watch_name])

        return PlotSource(
            kind="watch", watch=WatchCommand(name=watch_name, resume=resume)
        )

    parser.error(
        "a chart source is required: use one of --sym, --watch, -f/--file, or --breadth"
    )


def parse_cli(
    argv: list[str] | None = None,
    *,
    config_path: Path | None = None,
) -> CliAction:
    raw_argv = sys.argv[1:] if argv is None else argv

    # Run a first pass and suppress any default values defined in argparse, so we know
    # what the user explicitly typed in the command line.
    # Parse preset and management options like --watch-add, --preset-save, etc.
    # Handle the management options first and resolve any preset, before a second parsing
    explicit_parser = build_parser(
        require_source=False,
        suppress_defaults=True,
        include_preset=True,
        include_management=True,
    )

    explicit_args = explicit_parser.parse_args(raw_argv)
    explicit = vars(explicit_args).copy()

    # Look for management options, these can be dispatched early
    management_key = next(
        (key for key in MANAGEMENT_KEYS if key in explicit),
        None,
    )

    if management_key is not None:
        if "preset" in explicit:
            explicit_parser.error(
                "--preset cannot be combined with management commands"
            )

        if "preset_save" in explicit:
            explicit_parser.error("--preset-save must be used with a chart source")

        return management_action_from_args(explicit, management_key, explicit_parser)

    # Remove any preset arguments
    preset_name = explicit.pop("preset", None)
    preset_save_name = explicit.pop("preset_save", None)

    preset_args: dict[str, Any] = {}

    # Load the preset if required and merge with explicit options typed by the user
    if preset_name:
        preset_args = filter_preset_chart_args(get_preset_args(preset_name.upper()))

    explicit_args_for_merge = namespace_values_to_preset_args(explicit)

    if not (SOURCE_KEYS & explicit_args_for_merge.keys()):
        explicit_parser.error(
            "a chart source is required: use one of --sym, --watch, -f/--file, or --breadth"
        )

    merged_args = merge_preset_args(preset_args, explicit_args_for_merge)
    command = parse_cli_command(preset_dict_to_argv(merged_args))

    if preset_save_name:
        if config_path is None:
            raise CliError("Cannot save preset: config path was not provided")

        save_preset(preset_save_name.upper(), config_path, command)

    return CliAction(kind="run", command=command)


def parse_cli_command(argv: list[str] | None = None) -> PlotCommand:
    raw_argv = sys.argv[1:] if argv is None else argv

    parser = build_parser(
        require_source=True,
        suppress_defaults=False,
        include_preset=False,
        include_management=False,
    )

    args = parser.parse_args(raw_argv)

    try:
        validate_run_args(args, parser)
        return command_from_namespace(args, parser)
    except CliError as exc:
        parser.error(str(exc))


def management_action_from_args(
    explicit: dict[str, Any],
    key: str,
    parser: argparse.ArgumentParser,
) -> CliAction:
    match key:
        case "ls":
            return CliAction(kind="list")

        case "preset_rm":
            return CliAction(kind="preset_remove", name=explicit[key].upper())

        case "watch_rm":
            return CliAction(kind="watch_remove", name=explicit[key].upper())

        case "watch_add":
            name, filename = explicit[key]
            file_path = Path(filename)

            try:
                validate_file(file_path)
            except CliError as exc:
                parser.error(str(exc))

            return CliAction(kind="watch_add", name=name.upper(), path=file_path)

    parser.error("Unknown management command")


def validate_run_args(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    if args.resume and not args.watch:
        parser.error("--resume/-r must be combined with --watch")

    if args.period is not None and args.period <= 0:
        parser.error("--period must be greater than zero")

    if args.breadth is None and args.index != "nifty 500":
        parser.error("--index/-i can only be combined with --breadth")


def command_from_namespace(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> PlotCommand:
    tf = args.tf or "d"

    period = TF_PERIOD_MAP[tf] if args.period is None else args.period

    return PlotCommand(
        source=normalize_source(args, parser),
        user_set_timeframe=bool(args.tf),
        save=args.save,
        volume=args.volume,
        rs=args.rs,
        mansfield_rs=args.m_rs,
        timeframe=tf,
        sma=args.sma or [],
        ema=args.ema or [],
        vol_sma=args.vol_sma or [],
        date=args.date,
        period=period,
        snr=args.snr,
        delivery=args.dlv,
        plugins=selected_plugins_from_args(args),
    )


def namespace_values_to_preset_args(data: dict[str, Any]) -> dict[str, Any]:
    args: dict[str, Any] = {}

    for key, value in data.items():
        # --breadth with no values is a valid source and must survive merging.
        if key == "breadth" and value == []:
            args[key] = []
            continue

        if value in (None, False, [], ""):
            continue

        if key == "date" and isinstance(value, datetime):
            args[key] = value.isoformat()
        elif key == "file" and isinstance(value, Path):
            args[key] = str(value)
        else:
            args[key] = value

    return args


def preset_dict_to_argv(data: dict[str, Any]) -> list[str]:
    argv: list[str] = []

    for key, value in data.items():
        option = "--" + key.replace("_", "-")

        # --breadth by itself means "use the default breadth indicators".
        if key == "breadth" and value == []:
            argv.append(option)
            continue

        if value in (None, False, [], ""):
            continue

        if isinstance(value, bool):
            # Backward compatibility with older presets that saved snr_v2=True.
            if option == "--snr-v2":
                argv.extend(["--snr", "v2"])
            else:
                argv.append(option)

        elif isinstance(value, list):
            argv.append(option)
            argv.extend(str(item) for item in value)

        else:
            if option == "--tf":
                value = str(value)[0].lower()
            elif isinstance(value, datetime):
                value = value.isoformat()

            argv.extend([option, str(value)])

    return argv


def filter_preset_chart_args(data: dict[str, Any]) -> dict[str, Any]:
    """Return only source-agnostic chart display settings from a preset."""
    dct = {}

    for key, value in data.items():
        key = key.replace("-", "_")

        if key not in PRESET_IGNORED_KEYS:
            dct[key] = value

    return dct


def get_preset_args(name: str) -> dict[str, Any]:
    presets = config.PRESET
    preset = presets.get(name) or presets.get(name.lower())

    if preset is None:
        raise CliError(f"Error: No preset named '{name}'")

    return dict(preset)


def merge_preset_args(
    preset: dict[str, Any],
    cli_overrides: dict[str, Any],
) -> dict[str, Any]:
    merged = filter_preset_chart_args(preset)

    merged.update(cli_overrides)
    return merged


def load_preset_command(
    name: str,
    cli_overrides: dict[str, Any],
) -> PlotCommand:
    merged = merge_preset_args(get_preset_args(name), cli_overrides)

    return parse_cli_command(preset_dict_to_argv(merged))


def command_to_preset_args(command: PlotCommand) -> dict[str, Any]:
    """Serialize only source-agnostic chart settings for preset storage."""
    args: dict[str, Any] = {}

    if command.user_set_timeframe:
        args["tf"] = command.timeframe

    if command.save:
        args["save"] = True

    if command.volume:
        args["volume"] = True

    if command.rs:
        args["rs"] = True

    if command.mansfield_rs:
        args["m_rs"] = True

    if command.sma:
        args["sma"] = command.sma

    if command.ema:
        args["ema"] = command.ema

    if command.vol_sma:
        args["vol_sma"] = command.vol_sma

    if command.date:
        args["date"] = command.date.isoformat()

    default_period = TF_PERIOD_MAP[command.timeframe]

    if command.period != default_period:
        args["period"] = command.period

    if command.snr:
        args["snr"] = command.snr

    if command.delivery:
        args["dlv"] = True

    for plugin_key, plugin_config in command.plugins.items():
        args[plugin_dest(plugin_key, plugin_config)] = True

    return args


def save_preset(name: str, config_path: Path, command: PlotCommand) -> PlotCommand:
    user_config = load_json(config_path) if config_path.is_file() else {}

    presets = user_config.get("PRESET", {})

    presets[name] = command_to_preset_args(command)
    user_config["PRESET"] = presets

    write_json(config_path, user_config)

    config.reload()

    print(f"Preset saved as '{name}'")

    return command


def remove_preset(config_path: Path, name: str) -> None:
    user_config = load_json(config_path) if config_path.is_file() else {}

    presets = user_config.get("PRESET", {})

    key = name if name in presets else name.lower()

    if key not in presets:
        raise CliError(f"Error: No preset named '{name}'")

    del presets[key]

    write_json(config_path, user_config)

    config.reload()

    print(f"Preset '{name}' removed")


def remove_watch(name: str, config_path: Path) -> None:
    user_config = load_json(config_path) if config_path.is_file() else {}

    watch_map = user_config.get("WATCH", {})
    resume_map = user_config.get("CHART_RESUME", {})

    if name not in watch_map:
        raise CliError(f"Watchlist '{name}' does not exist")

    del watch_map[name]

    if name in resume_map:
        del resume_map[name]

    write_json(config_path, user_config)

    config.reload()

    print(f"Removed watchlist '{name}'")


def add_watch(name: str, file_path: Path, config_path: Path) -> None:
    validate_file(file_path)

    user_config = load_json(config_path) if config_path.is_file() else {}

    watch_map = user_config.get("WATCH", {})
    watch_map[name] = str(file_path)

    user_config["WATCH"] = watch_map

    write_json(config_path, user_config)

    config.reload()

    print(f"Watchlist '{name}' -> {file_path}")


def load_symbols_from_file(path: Path) -> list[str]:
    """
    Read symbols from a file.
    One symbol per line.
    """
    path = path.expanduser().resolve()

    validate_file(path)

    return [
        line.strip().lower()
        for line in path.read_text(encoding="utf-8-sig").strip().splitlines()
    ]


def print_available() -> None:
    watchlists = config.WATCH.keys()
    presets = config.PRESET.keys()

    watchlist_text = (
        ", ".join(watch.lower() for watch in watchlists) if watchlists else "-"
    )
    preset_text = ", ".join(presets) if presets else "-"

    print(f"Available watchlists: {watchlist_text}")
    print(f"Available presets: {preset_text}")
    print("\nAvailable index aliases (--sym, -i/--index):")

    padding = 10

    for alias, full_name in sorted(INDEX_ALIAS.items()):
        print(f"  {alias:<{padding}} → {full_name}")


def resolve_symbols(command: PlotCommand) -> list[str] | list[BreadthOption]:
    source = command.source

    if source.kind == "symbols":
        return source.symbols

    if source.kind == "file" and source.file:
        return load_symbols_from_file(source.file)

    if source.kind == "breadth" and source.breadth:
        return source.breadth.indicators

    if source.kind == "watch" and source.watch:
        watch_map = config.WATCH
        name = source.watch.name

        if name not in watch_map:
            raise CliError(f"Unknown watchlist: {name}")

        return load_symbols_from_file(Path(watch_map[name]))

    raise CliError("No symbols available for selected source")


def compute_max_period(cmd: PlotCommand) -> int:
    """Compute the maximum period needed to cover all indicators."""
    dlv_len = config.DLV_AVG_LEN if cmd.delivery else 0

    if cmd.mansfield_rs:
        match cmd.timeframe:
            case "w":
                m_rs_len = config.PLOT_M_RS_LEN_W
            case "m":
                m_rs_len = config.PLOT_M_RS_LEN_M
            case "q":
                m_rs_len = config.PLOT_M_RS_LEN_Q
            case "d":
                m_rs_len = config.PLOT_M_RS_LEN_D
    else:
        m_rs_len = 0

    plugin_lengths: list[int] = []

    for plugin_config in cmd.plugins.values():
        lookback = plugin_config.get("lookback")

        if lookback is None:
            continue

        try:
            plugin_lengths.append(int(lookback))
        except (TypeError, ValueError) as exc:
            plugin_name = plugin_config.get("name", "unknown")
            raise CliError(
                f"Plugin lookback must be an integer: {plugin_name}"
            ) from exc

    indicator_lengths = [
        *cmd.sma,
        *cmd.ema,
        *cmd.vol_sma,
        m_rs_len,
        dlv_len,
        *plugin_lengths,
    ]

    add_period = max(indicator_lengths, default=0)

    return cmd.period + add_period
