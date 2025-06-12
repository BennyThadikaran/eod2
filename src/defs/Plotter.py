import pickle
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import mplfinance as mpl
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection

from defs.utils import (
    arg_parse_dict,
    getDataFrame,
    getDeliveryLevels,
    getLevels,
    getLevels_v2,
    loadJson,
    manfieldRelativeStrength,
    randomChar,
    relativeStrength,
    writeJson,
)

HELP = """                                           ## Help ##

Shift + H   Toggle help text                 R               Reset to original view

N               Next chart                          F                Fullscreen

P               Previous chart                    G               Toggle Major Grids

Q               Quit plot.py                        O               Zoom to Rect

D               Toggle draw mode

## Draw mode controls ##

Horizontal Line :            Left Mouse click
(AxHLine)

Trend Line (TLine) :       Hold Shift key + left mouse click two points on chart

Segments (ALine) :        Hold Control key + left mouse click two or more points

Horizontal Segment :     Hold Ctrl + Shift key + left mouse click two points
(HLine)

Delete Line: Right mouse click on line

Delete all lines: Hold Shift key + right mouse click
"""


def processPlot(df, plot_args):
    mpl.plot(df, **plot_args)


def format_coords(x, _):
    s = " " * 5

    if df is None:
        return

    if not x or round(x) >= df.shape[0]:
        return ""

    dt = df.index[round(x)]

    dt_str = f"{dt:%d %b %Y}".upper()

    open, high, low, close, vol = df.loc[dt, ["Open", "High", "Low", "Close", "Volume"]]

    _str = f"{dt_str}{s}O: {open}{s}H: {high}{s}L: {low}{s}C: {close}{s}V: {vol:,.0f}"

    if "M_RS" in df.columns:
        _str += f"{s}MRS: {df.loc[dt, 'M_RS']}"
    elif "RS" in df.columns:
        _str += f"{s}RS: {df.loc[dt, 'RS']}"

    return _str


class Plotter:
    idx = len = 0
    line = []
    events = []
    title = None
    draw_mode = False
    helpText = None

    line_args = {
        "linewidth": 1,
        "mouseover": True,
        "pickradius": 3,
        "picker": True,
    }

    segment_args = {"pickradius": 3, "picker": True, "colors": ["crimson"]}

    title_args = {"loc": "right", "fontdict": {"fontweight": "bold"}}

    def __init__(self, args, config, plugins, parser, DIR: Path):
        plt.ion()
        self.args = args
        self.config = config
        self.plugins = plugins
        self.parser = parser
        self.DIR = DIR
        self.daily_dir = DIR / "eod2_data" / "daily"
        self.configPath = DIR / "defs" / "user.json"

        self.key = None

        if args.preset and args.preset_save:
            exit(
                "plot.py: error: argument --preset: not allowed with argument --preset_save"
            )

        if args.preset:
            args = self._loadPreset(args.preset)
            self.args = args

        self.tf = args.tf

        if args.watch_add:
            self._addWatch(*args.watch_add)

        if args.preset_save:
            self._savePreset(args.preset_save)

        if args.watch_rm:
            self._removeWatch(args.watch_rm)

        if args.preset_rm:
            self._removePreset(args.preset_rm)

        if args.ls:
            self._list()

        if args.period:
            self.period = args.period
        else:
            if self.tf == "Weekly":
                self.period = config.PLOT_WEEKS
            else:
                self.period = config.PLOT_DAYS

        self.plot_args = {
            "type": config.PLOT_CHART_TYPE,
            "style": config.PLOT_CHART_STYLE,
            "volume": args.volume,
            "xrotation": 0,
            "datetime_format": "%d %b %y",
            "returnfig": True,
            "scale_padding": {
                "left": 0.28,
                "right": 0.65,
                "top": 0.3,
                "bottom": 0.38,
            },
        }

        if args.save:
            if hasattr(config, "PLOT_SIZE"):
                self.plot_args["figsize"] = config.PLOT_SIZE
            else:
                self.plot_args["figsize"] = (14, 9)

            self.plot_args["figscale"] = 1

            self.save_dir = self.DIR / "SAVED_CHARTS"

            if args.preset:
                self.save_dir = self.save_dir / args.preset
            elif args.preset_save:
                self.save_dir = self.save_dir / args.preset_save
            elif args.watch:
                self.save_dir = self.save_dir / args.watch

            if not self.save_dir.exists():
                self.save_dir.mkdir(parents=True)

        if args.watch:
            self.symList = self._loadWatchList(args.watch)

        if args.sym:
            self.symList = args.sym

        # add some period for sma, ema calculation
        self.max_period = self._getMaxPeriod()

        if args.rs or args.m_rs:
            idx_path = self.daily_dir / f"{self.config.PLOT_RS_INDEX}.csv"

            if not idx_path.is_file():
                exit(f"Index file not found: {idx_path}")

            self.idx_cl = getDataFrame(
                idx_path,
                self.tf,
                self.max_period,
                "Close",
                toDate=self.args.date,
            )

    def plot(self, sym):
        global df

        self.draw_mode = False
        self.has_updated = False

        meta = None

        if "," in sym:
            sym, *meta = sym.lower().split(",")

        df = self._prepData(sym)

        if df is None:
            self.key = "n"
            print(f"WARN: Could not find symbol - {sym.upper()}")
            return

        self._prepArguments(sym, df, meta)

        self.plugins.run(df, self.plot_args, self.args, self.config)

        if self.args.save:
            return df

        fig, axs = mpl.plot(df, **self.plot_args)

        # A workaround using ConciseDateFormatter and AutoDateLocator
        # with mplfinance
        # See github issue https://github.com/matplotlib/mplfinance/issues/643

        # Locator sets the major tick locations on xaxis
        locator = mdates.AutoDateLocator(minticks=3, maxticks=7)

        # Formatter set the tick labels for the xaxis
        concise_formatter = mdates.ConciseDateFormatter(locator=locator)

        # Extract the tick values from locator.
        # These are matplotlib dates not python datetime
        tick_mdates = locator.tick_values(df.index[0], df.index[-1])

        # Extract the ticks labels from ConciseDateFormatter
        labels = concise_formatter.format_ticks(tick_mdates)

        ticks = self._get_tick_locs(tick_mdates, df.index)

        # Initialise FixedFormatter and FixedLocator
        # passing the tick labels and tick positions
        fixed_formatter = ticker.FixedFormatter(labels)
        fixed_locator = ticker.FixedLocator(ticks)

        fixed_formatter.set_offset_string(concise_formatter.get_offset())

        for ax in axs:
            ax.xaxis.set_major_locator(fixed_locator)
            ax.xaxis.set_major_formatter(fixed_formatter)
            ax.format_coord = format_coords

        fig.canvas.mpl_connect("key_press_event", self._on_key_press)
        self.fig = fig
        self.main_ax = axs[0]

        self.main_ax.set_title(
            f"#{self.idx + 1} of {self.len}",
            loc="left",
            color="black",
            fontdict={"fontweight": "bold"},
        )

        lines_path = self.DIR / "data" / "lines" / f"{sym}.p"

        default_lines = {
            "artists": [],
            "daily": {"length": 0, "lines": {}},
            "weekly": {"length": 0, "lines": {}},
        }

        if lines_path.exists():
            lines = pickle.loads(lines_path.read_bytes())
        else:
            lines = default_lines

        if lines[self.tf]["length"] > 0:
            self._loadLines(lines)
        else:
            self.lines = lines

        # Open chart window in fullscreen mode by default
        plt.get_current_fig_manager().full_screen_toggle()

        mpl.show(block=True)

        if "addplot" in self.plot_args:
            self.plot_args["addplot"].clear()

        daily_len = self.lines["daily"]["length"]
        weekly_len = self.lines["weekly"]["length"]

        if daily_len == 0 and weekly_len == 0 and lines_path.is_file():
            return lines_path.unlink()

        if self.has_updated:
            if not lines_path.parent.exists():
                lines_path.parent.mkdir(parents=True)

            lines_path.write_bytes(pickle.dumps(self.lines))

    def _on_pick(self, event):
        if event.mouseevent.button == 3:
            self._deleteLine("", artist=event.artist)

    def _on_key_release(self, event):
        if event.key in ("control", "shift", "ctrl+shift"):
            if event.key == "ctrl+shift" and len(self.line) == 2:
                # On release after first click,
                # Draw a horizontal segment from xmin to x-axis end
                y, xmin = self.line
                self._add_horizontal_segment(event.inaxes, y, xmin)

            self.main_ax.set_title("DRAW MODE", **self.title_args)
            self.line.clear()

    def _on_button_press(self, event):
        if df is None:
            return

        # right mouse click to delete lines
        if event.button == 3:
            return self._deleteLine(event.key)

        # add horizontal line
        # return if data is out of bounds
        if event.xdata is None or event.xdata > df.shape[0]:
            return

        x = round(event.xdata)
        y = round(event.ydata, 2)

        if self.config.MAGNET_MODE:
            y = self._getClosestPrice(x, y)

        if event.key is None:
            self._add_hline(event.inaxes, y)

        if event.key not in ("control", "shift", "ctrl+shift"):
            return

        # shift + mouse click to assign coord for trend line
        # Draw trendline
        # first click to get starting coordinates
        self.main_ax.set_title("LINE MODE", **self.title_args)

        if event.key == "control":
            if len(self.line) == 0:
                return self.line.append((x, y))

            self.line.append((x, y))

            if len(self.line) == 2:
                coord = self.line.copy()
                self.line[0] = self.line.pop()
                return self._add_aline(event.inaxes, coord)

        if event.key == "ctrl+shift":
            if len(self.line) == 0:
                return self.line.extend((y, x))

            self.line.append(x)

            # ctrl + shift to add a horizontal segment between two dates
            self._add_horizontal_segment(event.inaxes, *self.line)
            return self.line.clear()

        if event.key == "shift":
            # Cannot draw a line through identical points
            if len(self.line) == 1 and y == self.line[0][1]:
                return

            self.line.append((x, y))

            if len(self.line) == 2:
                self._add_tline(event.inaxes, self.line)
                self.line.clear()
                self.main_ax.set_title("DRAW MODE", **self.title_args)

    def _on_key_press(self, event):
        if event.key in ("n", "p", "q", "d", "h"):
            if event.key == "d":
                return self._toggleDrawMode()

            if event.key == "h":
                if self.helpText is None:
                    x = self.main_ax.get_xlim()[0]
                    y = self.main_ax.get_ylim()[0]
                    self.helpText = self.main_ax.text(
                        x,
                        y,
                        HELP,
                        color="darkslategrey",
                        backgroundcolor="mintcream",
                        fontweight="bold",
                    )
                else:
                    self.helpText.remove()
                    self.helpText = None
                return

            # artists are not json serializable
            self.lines["artists"].clear()

            if event.key == "p" and self.idx == 0:
                print("\nAt first Chart")
                return

            self.key = event.key
            plt.close("all")

    def _toggleDrawMode(self):
        if self.draw_mode:
            self.draw_mode = False
            for event in self.events:
                self.fig.canvas.mpl_disconnect(event)
            self.main_ax.set_title("", **self.title_args)
            self.events.clear()
        else:
            self.draw_mode = True
            self.main_ax.set_title("DRAW MODE", **self.title_args)

            self.events.append(
                self.fig.canvas.mpl_connect("key_release_event", self._on_key_release)
            )

            self.events.append(
                self.fig.canvas.mpl_connect("button_press_event", self._on_button_press)
            )

            self.events.append(self.fig.canvas.mpl_connect("pick_event", self._on_pick))

    def _loadLines(self, lines):
        if df is None:
            return

        self.lines = lines

        if self.tf not in self.lines:
            return

        for url in self.lines[self.tf]["lines"]:
            _type, _ = url.split(":")

            coord = self.lines[self.tf]["lines"][url]

            if _type == "axhline":
                self._add_hline(self.main_ax, coord, url=url)
                continue

            if _type == "hline":
                y, xmin, xmax = coord

                # check for DataFrame index out of bounds errors
                try:
                    # Draw line to specified point on x-axis else draw to end
                    if xmax is not None:
                        xmax = df.index.get_loc(xmax)

                    coord = (y, df.index.get_loc(xmin), xmax)
                except KeyError:
                    continue

                self._add_horizontal_segment(self.main_ax, *coord, url=url)
                continue

            try:
                coord = tuple((df.index.get_loc(x), y) for x, y in coord)
            except KeyError:
                continue

            if _type == "tline":
                self._add_tline(self.main_ax, coord, url=url)
            elif _type == "aline":
                self._add_aline(self.main_ax, coord, url=url)

    def _add_hline(self, axes, y, url=None):
        """Draw a horizontal that extends both sides"""

        if url is None:
            # increment only if its newly drawn line
            self.lines[self.tf]["length"] += 1
            url = f"axhline:{randomChar(6)}"
            self.lines[self.tf]["lines"][url] = y
            self.has_updated = True

        self.line_args["color"] = self.config.PLOT_AXHLINE_COLOR
        line = axes.axhline(y, url=url, **self.line_args)
        self.lines["artists"].append(line)

    def _add_tline(self, axes, coords, url=None):
        """Draw trendlines passing through 2 points"""

        if df is None:
            return

        if url is None:
            # increment only if its newly drawn line
            self.lines[self.tf]["length"] += 1
            url = f"tline:{randomChar(6)}"
            self.lines[self.tf]["lines"][url] = tuple(
                (df.index[x], y) for x, y in coords
            )

            self.has_updated = True

        self.line_args["color"] = self.config.PLOT_TLINE_COLOR

        # second click to get ending coordinates
        line = axes.axline(*coords, url=url, **self.line_args)

        self.lines["artists"].append(line)

    def _add_aline(self, axes, coords, url=None):
        """Draw arbitary lines connecting 2 points"""

        if df is None:
            return

        if url is None:
            # increment only if its newly drawn line
            self.lines[self.tf]["length"] += 1
            url = f"aline:{randomChar(6)}"

            self.lines[self.tf]["lines"][url] = tuple(
                (df.index[x], y) for x, y in coords
            )

            self.has_updated = True

        self.segment_args["colors"] = (self.config.PLOT_ALINE_COLOR,)

        line = LineCollection([coords], url=url, **self.segment_args)

        axes.add_collection(line)

        self.lines["artists"].append(line)

    def _add_horizontal_segment(self, axes, y, xmin, xmax=None, url=None):
        if df is None:
            return

        if url is None:
            # increment only if its newly drawn line
            self.lines[self.tf]["length"] += 1
            url = f"hline:{randomChar(6)}"

            self.lines[self.tf]["lines"][url] = (
                y,
                df.index[xmin],
                df.index[xmax] if xmax else None,
            )

            self.has_updated = True

        if xmax is None:
            # draw line till end of x-axis
            xmax = df.index.get_loc(df.index[-1])

        self.segment_args["colors"] = (self.config.PLOT_HLINE_COLOR,)

        line = axes.hlines(y, xmin, xmax, url=url, **self.segment_args)

        self.lines["artists"].append(line)

    def _deleteLine(self, key, artist=None):
        if key == "shift":
            for lineArtist in self.lines["artists"].copy():
                lineArtist.remove()

            self.lines[self.tf]["length"] = 0
            self.lines["artists"].clear()
            self.lines[self.tf]["lines"].clear()
            self.has_updated = True
            return

        if artist and artist in self.lines["artists"]:
            url = artist.get_url()

            artist.remove()
            self.lines["artists"].remove(artist)
            self.lines[self.tf]["lines"].pop(url)
            self.lines[self.tf]["length"] -= 1
            self.has_updated = True

    def _getClosestPrice(self, x, y):
        if df is None:
            return

        _open, high, low, close, *_ = df.iloc[x]

        if y >= high:
            # if pointer is at or above high snap to high
            closest = high
        elif y <= low:
            # if pointer is at or below low snap to low
            closest = low
        else:
            # else if pointer is inside the candle and
            # snap to the nearest open or close (absolute distance)
            o_dist = abs(_open - y)
            c_dist = abs(close - y)

            closest = _open if o_dist < c_dist else close

        return closest

    def _prepArguments(self, sym, df, meta):
        added_plots = []

        self.title = f"{sym.upper()} - {self.tf.capitalize()}"

        if meta is not None:
            self.title += f" | {'  '.join(meta).upper()}"

        self.plot_args["title"] = self.title

        self.plot_args["xlim"] = (0, df.shape[0] + 15)

        if self.args.save:
            img_name = f"{sym.replace(' ', '-')}.png"
            self.plot_args["savefig"] = dict(fname=self.save_dir / img_name, dpi=300)

        if self.args.snr:
            mean_candle_size = (df["High"] - df["Low"]).median()

            self.plot_args["alines"] = {
                "alines": getLevels(df, mean_candle_size),
                "linewidths": 0.7,
            }

        if self.args.snr_v2:
            mean_candle_size = (df["High"] - df["Low"]).median()

            self.plot_args["alines"] = {
                "alines": getLevels_v2(df, mean_candle_size),
                "linewidths": 0.7,
            }

        if self.args.rs:
            added_plots.append(
                mpl.make_addplot(
                    df["RS"],
                    panel="lower",
                    color=self.config.PLOT_RS_COLOR,
                    width=2.5,
                    ylabel="Dorsey RS",
                )
            )

        if self.args.m_rs and "M_RS" in df.columns:
            zero_line = pd.Series(data=0, index=df.index)

            added_plots.extend(
                [
                    mpl.make_addplot(
                        df["M_RS"],
                        panel="lower",
                        color=self.config.PLOT_M_RS_COLOR,
                        width=2.5,
                        ylabel="Mansfield RS",
                    ),
                    mpl.make_addplot(
                        zero_line,
                        panel="lower",
                        color=self.config.PLOT_M_RS_COLOR,
                        linestyle="dashed",
                        width=1.5,
                    ),
                ]
            )

        if self.args.sma:
            for period in self.args.sma:
                if f"SMA_{period}" not in df.columns:
                    continue

                added_plots.append(
                    mpl.make_addplot(df[f"SMA_{period}"], label=f"SM{period}")
                )

        if self.args.ema:
            for period in self.args.ema:
                if f"EMA_{period}" not in df.columns:
                    continue

                added_plots.append(
                    mpl.make_addplot(df[f"EMA_{period}"], label=f"EM{period}")
                )

        if self.args.vol_sma:
            for period in self.args.vol_sma:
                if f"VMA_{period}" not in df.columns:
                    continue

                added_plots.append(
                    mpl.make_addplot(
                        df[f"VMA_{period}"],
                        label=f"MA{period}",
                        panel="lower",
                        linewidths=0.7,
                    )
                )

        if self.args.dlv and not df["DLV_QTY"].dropna().empty:
            getDeliveryLevels(df, self.config)

            self.plot_args["marketcolor_overrides"] = df["MCOverrides"].values

            added_plots.append(
                mpl.make_addplot(
                    df["IM"],
                    type="scatter",
                    marker="*",
                    color="midnightblue",
                    label="IM",
                )
            )

        if len(added_plots) > 0:
            self.plot_args["addplot"] = added_plots

    @lru_cache(maxsize=6)
    def _prepData(self, sym):
        fpath = self.daily_dir / f"{sym.lower()}.csv"

        if not fpath.is_file():
            fpath = self.daily_dir / f"{sym.lower()}_sme.csv"

            if not fpath.is_file():
                return None

        df = getDataFrame(fpath, self.tf, self.max_period, toDate=self.args.date)

        df_len = df.shape[0]

        plot_period = min(df_len, self.period)

        if self.args.rs:
            df["RS"] = relativeStrength(df["Close"], self.idx_cl)

        if self.args.m_rs:
            if self.tf == "weekly":
                rs_period = self.config.PLOT_M_RS_LEN_W
            else:
                rs_period = self.config.PLOT_M_RS_LEN_D

            # prevent crash if plot period is less than RS period
            if df_len < rs_period:
                print(f"WARN: {sym.upper()} - Inadequate data to plot Mansfield RS.")
            else:
                df["M_RS"] = manfieldRelativeStrength(
                    df["Close"], self.idx_cl, rs_period
                )

        if self.args.sma:
            for period in self.args.sma:
                if df_len < period:
                    print(
                        f"WARN: {sym.upper()} - Inadequate data to plot SMA {period}."
                    )
                    continue

                df[f"SMA_{period}"] = df["Close"].rolling(period).mean().round(2)

        if self.args.ema:
            for period in self.args.ema:
                if df_len < period:
                    print(
                        f"WARN: {sym.upper()} - Inadequate data to plot EMA {period}."
                    )
                    continue

                alpha = 2 / (period + 1)

                df[f"EMA_{period}"] = df["Close"].ewm(alpha=alpha).mean().round(2)

        if self.args.vol_sma:
            for period in self.args.vol_sma:
                if df_len < period:
                    print(
                        f"WARN: {sym.upper()} - Inadequate data to plot Volume SMA {period}."
                    )
                    continue

                df[f"VMA_{period}"] = df["Volume"].rolling(period).mean().round(2)

        if self.tf == "weekly":
            start_dt = df.index[-plot_period] - timedelta(7)
        else:
            start_dt = df.index[-plot_period] - timedelta(1)

        df.loc[start_dt] = np.nan
        df = df.sort_index()

        return df[start_dt:]

    def _list(self):
        if hasattr(self.config, "WATCH"):
            watch_lst = [i.lower() for i in self.config.WATCH.keys()]
        else:
            watch_lst = []

        if hasattr(self.config, "PRESET"):
            preset_lst = [i.lower() for i in self.config.PRESET.keys()]
        else:
            preset_lst = []

        if not len(watch_lst):
            print("No Watchlists")
        else:
            print("WatchLists:", ", ".join(watch_lst))

        if not len(preset_lst):
            print("No Presets")
        else:
            print("Preset:", ", ".join(preset_lst))

        exit()

    def _loadPreset(self, preset):
        if preset not in getattr(self.config, "PRESET"):
            exit(f"Error: No preset named '{preset}'")

        args_dct = getattr(self.config, "PRESET")[preset]

        if self.args.resume:
            args_dct["resume"] = True

        return self.parser.parse_args(arg_parse_dict(args_dct))

    def _savePreset(self, preset):
        if self.args.watch and self.args.watch.upper() not in self.config.WATCH:
            exit(f"Error: No watchlist named '{self.args.watch}'")

        data = loadJson(self.configPath) if self.configPath.is_file() else {}

        # get a copy of __dict__ and filter only truthy values into a dict
        opts = {k: v for k, v in vars(self.args).copy().items() if v}

        del opts["preset_save"]

        if "PRESET" not in data:
            data["PRESET"] = {}

        data["PRESET"][preset] = opts
        writeJson(self.configPath, data)
        print(f"Preset saved as '{preset}'")

    def _removePreset(self, preset):
        if preset not in getattr(self.config, "PRESET"):
            exit(f"Error: No preset named: '{preset}'")

        if not self.configPath.is_file():
            exit(f"File not found: {self.configPath}")

        data = loadJson(self.configPath)

        if "PRESET" not in data or preset not in data["PRESET"]:
            exit(f"Error: No preset named: '{preset}'")

        del data["PRESET"][preset]

        writeJson(self.configPath, data)
        exit(f"Preset '{preset}' removed.")

    def _loadWatchList(self, watch):
        watch = watch.upper()
        if watch not in self.config.WATCH:
            exit(f"Error: No watchlist named '{watch}'")

        file = Path(self.config.WATCH[watch]).expanduser()

        if not file.is_file():
            print(self.config.WATCH[watch])
            exit(f"Error: File not found {file}")

        return file.read_text().strip("\n").split("\n")

    def _addWatch(self, name, fpath: str):
        data = loadJson(self.configPath) if self.configPath.is_file() else {}

        if "WATCH" not in data:
            data["WATCH"] = {}

        fpath = str(Path(fpath).resolve())

        data["WATCH"][name.upper()] = fpath
        writeJson(self.configPath, data)
        exit(f"Added watchlist '{name}' with value '{fpath}'")

    def _removeWatch(self, name):
        if name.upper() not in getattr(self.config, "WATCH"):
            exit(f"Error: No watchlist named: '{name}'")

        if not self.configPath.is_file():
            exit("No config file")

        data = loadJson(self.configPath)

        if "WATCH" not in data or name.upper() not in data["WATCH"]:
            exit(f"Error: No watchlist named: '{name}'")

        del data["WATCH"][name.upper()]

        writeJson(self.configPath, data)
        exit(f"Watchlist '{name}' removed.")

    def _getMaxPeriod(self):
        dlv_len = self.config.DLV_AVG_LEN if self.args.dlv else 0

        if self.args.m_rs:
            if self.tf == "weekly":
                m_rs_len = self.config.PLOT_M_RS_LEN_W
            else:
                m_rs_len = self.config.PLOT_M_RS_LEN_D
        else:
            m_rs_len = 0

        if self.args.sma or self.args.ema or self.args.vol_sma:
            sma = self.args.sma if self.args.sma else []
            ema = self.args.ema if self.args.ema else []
            vsma = self.args.vol_sma if self.args.vol_sma else []

            add_period = max(*sma, *ema, *vsma, m_rs_len, dlv_len)
            return add_period + self.period

        if self.args.m_rs:
            return max(m_rs_len, dlv_len) + self.period

        if self.args.dlv:
            return dlv_len + self.period

        return self.period

    def _get_tick_locs(self, tick_mdates, dtix: pd.DatetimeIndex):
        """Return the tick locs to be passed to Locator instance."""

        ticks = []

        # Convert the matplotlib dates to python datetime and iterate
        for dt in mdates.num2date(tick_mdates):
            # remove the timezone info to match the DataFrame index
            dt = dt.replace(tzinfo=None)

            # Get the index position if available
            # else get the next available index position
            idx = (
                dtix.get_loc(dt) if dt in dtix else dtix.searchsorted(dt, side="right")
            )
            # store the tick positions to be displayed on chart
            ticks.append(idx)

        return ticks
