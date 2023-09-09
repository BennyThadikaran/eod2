from pathlib import Path
from defs.utils import arg_parse_dict, getDataFrame, getScreenSize, getLevels, getDeliveryLevels, writeJson, loadJson, randomChar
from mplfinance import plot, make_addplot, show
from matplotlib.collections import LineCollection
from matplotlib.pyplot import close, ion
from datetime import timedelta
from numpy import NaN
from pandas import Series
from defs.DateTickFormatter import DateTickFormatter
from pickle import loads, dumps

HELP = '''## Help ##

H            Toggle help text

N            Next chart

P            Previous chart

Q            Quit plot.py

D            Toggle draw mode

## Draw mode controls ##

Left click on chart to add a horizontal line across X axis.

Hold Shift key and left click two points on chart, to add a trend line.

Hold Control key and left click two or more points to add segments,
that connect at each end.

Hold Ctrl + Shift key and left click two points to add a horizontal segment.

Right click on line to delete line.

Hold Shift key and right click on chart to delete all lines.
'''


def processPlot(df, plot_args):
    plot(df, **plot_args)


def format_coords(x, _):
    s = ' ' * 5
    if not x or round(x) >= df.shape[0]:
        return ''

    dt = df.index[round(x)]

    dt_str = f'{dt:%d %b %Y}'.upper()

    O, H, L, C, V = df.loc[dt, ['Open', 'High', 'Low', 'Close', 'Volume']]

    _str = f'{dt_str}{s}O: {O}{s}H: {H}{s}L: {L}{s}C: {C}{s}V: {V:,.0f}'

    if 'M_RS' in df.columns:
        _str += f'{s}MRS: {df.loc[dt, "M_RS"]}'
    elif 'RS' in df.columns:
        _str += f'{s}RS: {df.loc[dt, "RS"]}'

    return _str


class Plotter:

    idx = len = 0
    line = []
    events = []
    title = None
    draw_mode = False
    helpText = None

    line_args = {
        'linewidth': 1,
        'mouseover': True,
        'pickradius': 3,
        'picker': True
    }

    segment_args = {
        'pickradius': 3,
        'picker': True,
        'colors': ['crimson']
    }

    title_args = {
        'loc': 'right',
        'fontdict': {'fontweight': 'bold'}
    }

    def __init__(self, args, config, plugins, parser, DIR: Path):
        ion()
        self.args = args
        self.config = config
        self.plugins = plugins
        self.parser = parser
        self.DIR = DIR
        self.daily_dir = DIR / 'eod2_data' / 'daily'
        self.dlv_dir = DIR / 'eod2_data' / 'delivery'
        self.configPath = DIR / 'defs' / 'user.json'

        if args.preset and args.preset_save:
            exit(
                'plot.py: error: argument --preset: not allowed with argument --preset_save')

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
            if self.tf == 'Weekly':
                self.period = config.PLOT_WEEKS
            else:
                self.period = config.PLOT_DAYS

        self.plot_args = {
            'type': config.PLOT_CHART_TYPE,
            'style': config.PLOT_CHART_STYLE,
            'volume': args.volume,
            'xrotation': 0,
            'datetime_format': '%d %b %y',
            'figscale': 2,
            'returnfig': True,
            'scale_padding': {
                'left': 0.28,
                'right': 0.65,
                'top': 0.3,
                'bottom': 0.38
            }
        }

        if args.save:
            if hasattr(config, 'PLOT_SIZE'):
                self.plot_args['figsize'] = config.PLOT_SIZE
            else:
                self.plot_args['figsize'] = getScreenSize()

            self.plot_args['figscale'] = 1

            self.save_dir = self.DIR / 'SAVED_CHARTS'

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
            idx_path = self.daily_dir / f'{self.config.PLOT_RS_INDEX}.csv'

            if not idx_path.is_file():
                exit(f'Index file not found: {idx_path}')

            self.idx_cl = getDataFrame(idx_path,
                                       self.tf,
                                       self.max_period,
                                       'Close',
                                       fromDate=self.args.date)

    def plot(self, sym):
        global df

        self.draw_mode = False

        meta = None

        if ',' in sym:
            sym, *meta = sym.split(',')

        df = self._prepData(sym)

        self._prepArguments(sym, df, meta)

        self.plugins.run(df, self.plot_args, self.args, self.config)

        if self.args.save:
            return df

        fig, axs = plot(df, **self.plot_args)

        locator, formatter = DateTickFormatter(df.index).getLabels()

        for ax in axs:
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)
            ax.format_coord = format_coords

        fig.canvas.mpl_connect('key_press_event', self._on_key_press)
        self.fig = fig
        self.main_ax = axs[0]

        self.main_ax.set_title(f'#{self.idx + 1} of {self.len}',
                               loc='left',
                               color='black',
                               fontdict={'fontweight': 'bold'})

        tf = f'_{self.tf[0]}'

        lines_path = self.DIR / 'data' / 'lines' / f'{sym}{tf}.p'

        default_lines = {'length': 0, 'artists': [], 'lines': {}}

        lines = loads(lines_path.read_bytes()
                      ) if lines_path.is_file() else default_lines

        if lines['length'] > 0:
            self._loadLines(lines)
        else:
            self.lines = lines

        show(block=True)

        length = self.lines['length']

        if length == 0 and lines_path.is_file():
            return lines_path.unlink()

        if length > 0:
            lines_path.write_bytes(dumps(self.lines))

    def _on_pick(self, event):
        if event.mouseevent.button == 3:
            self._deleteLine('', artist=event.artist)

    def _on_key_release(self, event):
        if event.key in ('control', 'shift', 'ctrl+shift'):
            self.main_ax.set_title('DRAW MODE', **self.title_args)
            self.line.clear()

    def _on_button_press(self, event):
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

        if not event.key in ('control', 'shift', 'ctrl+shift'):
            return

        # shift + mouse click to assign coord for trend line
        # Draw trendline
        # first click to get starting coordinates
        self.main_ax.set_title('LINE MODE', **self.title_args)

        if event.key == 'control':
            if len(self.line) == 0:
                return self.line.append((x, y))

            self.line.append((x, y))

            if len(self.line) == 2:
                coord = self.line.copy()
                self.line[0] = self.line.pop()
                return self._add_aline(event.inaxes, coord)

        if event.key == 'ctrl+shift':
            if len(self.line) == 0:
                return self.line.extend((y, x))

            self.line.append(x)

            # ctrl + shift to add a horizontal segment between two dates
            self._add_horizontal_segment(event.inaxes, *self.line)
            return self.line.clear()

        if event.key == 'shift':
            # Cannot draw a line through identical points
            if len(self.line) == 1 and y == self.line[0][1]:
                return

            self.line.append((x, y))

            if len(self.line) == 2:
                self._add_tline(event.inaxes, self.line)
                self.line.clear()
                self.main_ax.set_title('DRAW MODE', **self.title_args)

    def _on_key_press(self, event):
        if event.key in ('n', 'p', 'q', 'd', 'h'):
            if event.key == 'd':
                return self._toggleDrawMode()

            if event.key == 'h':
                if self.helpText is None:
                    x = self.main_ax.get_xlim()[0]
                    y = self.main_ax.get_ylim()[0]
                    self.helpText = self.main_ax.text(x, y,
                                                      HELP,
                                                      color='darkslategrey',
                                                      backgroundcolor='mintcream',
                                                      fontweight='bold')
                else:
                    self.helpText.remove()
                    self.helpText = None
                return

            # artists are not json serializable
            self.lines['artists'].clear()

            if event.key == 'p' and self.idx == 0:
                print('\nAt first Chart')
                return

            self.key = event.key
            close('all')

    def _toggleDrawMode(self):
        if self.draw_mode:
            self.draw_mode = False
            for event in self.events:
                self.fig.canvas.mpl_disconnect(event)
            self.main_ax.set_title('', **self.title_args)
            self.events.clear()
        else:
            self.draw_mode = True
            self.main_ax.set_title('DRAW MODE', **self.title_args)

            self.events.append(self.fig.canvas.mpl_connect('key_release_event',
                                                           self._on_key_release))

            self.events.append(self.fig.canvas.mpl_connect('button_press_event',
                                                           self._on_button_press))

            self.events.append(self.fig.canvas.mpl_connect('pick_event',
                                                           self._on_pick))

    def _loadLines(self, lines):
        self.lines = lines

        for url in self.lines['lines']:
            _type, _ = url.split(':')

            coord = self.lines['lines'][url]

            if _type == 'axhline':
                self._add_hline(self.main_ax, coord, url=url)
                continue

            if _type == 'hline':
                y, xmin, xmax = coord

                coord = (y, df.index.get_loc(xmin), df.index.get_loc(xmax))
                self._add_horizontal_segment(self.main_ax, *coord, url=url)
                continue

            coord = tuple((df.index.get_loc(x), y) for x, y in coord)

            if _type == 'tline':
                self._add_tline(self.main_ax, coord, url=url)
            elif _type == 'aline':
                self._add_aline(self.main_ax, coord, url=url)

    def _add_hline(self, axes, y, url=None):
        '''Draw a horizontal that extends both sides'''

        if url is None:
            # increment only if its newly drawn line
            self.lines['length'] += 1
            url = f'axhline:{randomChar(6)}'

        self.line_args['color'] = self.config.PLOT_AXHLINE_COLOR
        line = axes.axhline(y, url=url, **self.line_args)
        self.lines['artists'].append(line)
        self.lines['lines'][url] = y

    def _add_tline(self, axes, coords, url=None):
        '''Draw trendlines passing through 2 points'''

        if url is None:
            # increment only if its newly drawn line
            self.lines['length'] += 1
            url = f'tline:{randomChar(6)}'

        self.line_args['color'] = self.config.PLOT_TLINE_COLOR

        # second click to get ending coordinates
        line = axes.axline(*coords, url=url, **self.line_args)

        self.lines['lines'][url] = tuple((df.index[x], y) for x, y in coords)
        self.lines['artists'].append(line)

    def _add_aline(self, axes, coords, url=None):
        '''Draw arbitary lines connecting 2 points'''

        if url is None:
            # increment only if its newly drawn line
            self.lines['length'] += 1
            url = f'aline:{randomChar(6)}'

        self.segment_args['colors'] = (self.config.PLOT_ALINE_COLOR,)

        line = LineCollection([coords], url=url, **self.segment_args)

        axes.add_collection(line)

        self.lines['lines'][url] = tuple((df.index[x], y) for x, y in coords)

        self.lines['artists'].append(line)

    def _add_horizontal_segment(self, axes, y, xmin, xmax, url=None):
        if url is None:
            # increment only if its newly drawn line
            self.lines['length'] += 1
            url = f'hline:{randomChar(6)}'

        self.segment_args['colors'] = (self.config.PLOT_HLINE_COLOR,)

        line = axes.hlines(y, xmin, xmax, url=url, **self.segment_args)

        self.lines['lines'][url] = (y, df.index[xmin], df.index[xmax])
        self.lines['artists'].append(line)

    def _deleteLine(self, key, artist=None):

        if key == 'shift':
            for lineArtist in self.lines['artists'].copy():
                lineArtist.remove()
            self.lines['length'] = 0
            self.lines['artists'].clear()
            self.lines['lines'].clear()
            return

        if artist and artist in self.lines['artists']:
            url = artist.get_url()

            artist.remove()
            self.lines['artists'].remove(artist)
            self.lines['lines'].pop(url)
            self.lines['length'] -= 1

    def _getClosestPrice(self, x, y):
        _open, high, low, close, * _ = df.iloc[x]

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

        self.title = f'{sym.upper()} - {self.tf.capitalize()}'

        if not meta is None:
            self.title += f' | {"  ".join(meta).upper()}'

        self.plot_args['title'] = self.title

        self.plot_args['xlim'] = (0, df.shape[0] + 14)

        if self.args.save:
            img_name = f'{sym.replace(" ", "-")}.png'
            self.plot_args['savefig'] = dict(fname=self.save_dir / img_name,
                                             dpi=300)

        if self.args.snr:
            mean_candle_size = (df['High'] - df['Low']).mean()

            self.plot_args['alines'] = {
                'alines': getLevels(df, mean_candle_size),
                'linewidths': 0.7
            }

        if self.args.rs:
            added_plots.append(make_addplot(df['RS'],
                                            panel='lower',
                                            color=self.config.PLOT_RS_COLOR,
                                            width=2.5,
                                            ylabel='Dorsey RS'))

        if self.args.m_rs:
            zero_line = Series(data=0, index=df.index)

            added_plots.extend([
                make_addplot(df['M_RS'],
                             panel='lower',
                             color=self.config.PLOT_M_RS_COLOR,
                             width=2.5,
                             ylabel='Mansfield RS'),

                make_addplot(zero_line,
                             panel='lower',
                             color=self.config.PLOT_M_RS_COLOR,
                             linestyle='dashed',
                             width=1.5)
            ])

        if self.args.sma:
            for period in self.args.sma:
                added_plots.append(make_addplot(df[f'SMA_{period}'],
                                                label=f'SM{period}'))

        if self.args.ema:
            for period in self.args.ema:
                added_plots.append(make_addplot(df[f'EMA_{period}'],
                                                label=f'EM{period}'))

        if self.args.vol_sma:
            for period in self.args.vol_sma:
                added_plots.append(make_addplot(df[f'VMA_{period}'],
                                                label=f'MA{period}',
                                                panel='lower',
                                                linewidths=0.7))

        if self.args.dlv:
            dlv_path = self.dlv_dir / f'{sym}.csv'

            if dlv_path.exists():
                getDeliveryLevels(df,
                                  self._loadDeliveryData(dlv_path),
                                  self.config)

                self.plot_args['marketcolor_overrides'] = df['MCOverrides'].values

                added_plots.append(make_addplot(df['IM'],
                                                type='scatter',
                                                marker='*',
                                                color='midnightblue',
                                                label="IM"))
            else:
                print('No delivery data found')

        if len(added_plots) > 0:
            self.plot_args['addplot'] = added_plots

    def _loadDeliveryData(self, fPath):
        dct = {
            'TTL_TRD_QNTY': 'sum',
            'NO_OF_TRADES': 'sum',
            'QTY_PER_TRADE': 'sum',
            'DELIV_QTY': 'sum'
        }

        dq = getDataFrame(fPath,
                          self.tf,
                          self.max_period,
                          customDict=dct,
                          fromDate=self.args.date)

        if self.tf == 'weekly':
            dq = dq.drop('QTY_PER_TRADE', axis=1)

            dq['QTY_PER_TRADE'] = (
                dq['TTL_TRD_QNTY'] / dq['NO_OF_TRADES']).round(2)

        return dq

    def _prepData(self, sym):
        fpath = self.daily_dir / f'{sym.lower()}.csv'

        if not fpath.is_file():
            fpath = self.daily_dir / f'{sym.lower()}_sme.csv'

            if not fpath.is_file():
                exit(f"Error: File not found: {fpath}")

        df = getDataFrame(fpath,
                          self.tf,
                          self.max_period,
                          fromDate=self.args.date)

        plot_period = min(df.shape[0], self.period)

        if self.args.rs or self.args.m_rs:
            df['RS'] = ((df['Close'] / self.idx_cl) * 100).round(2)

        if self.args.m_rs:
            if self.tf == 'weekly':
                rs_period = self.config.PLOT_M_RS_LEN_W
            else:
                rs_period = self.config.PLOT_M_RS_LEN_D

            sma_rs = df['RS'].rolling(rs_period).mean()
            df['M_RS'] = (((df['RS'] / sma_rs) - 1) * 100).round(2)

            # prevent crash if plot period is less than RS period
            if df.shape[0] < rs_period:
                df['M_RS'] = 0

        if self.args.sma:
            for period in self.args.sma:
                df[f'SMA_{period}'] = df['Close'].rolling(
                    period).mean().round(2)

        if self.args.ema:
            for period in self.args.ema:
                alpha = 2 / (period + 1)
                df[f'EMA_{period}'] = df['Close'].ewm(
                    alpha=alpha).mean().round(2)

        if self.args.vol_sma:
            for period in self.args.vol_sma:
                df[f'VMA_{period}'] = df['Volume'].rolling(
                    period).mean().round(2)

        if self.tf == 'weekly':
            start_dt = df.index[-plot_period] - timedelta(7)
        else:
            start_dt = df.index[-plot_period] - timedelta(1)

        df.loc[start_dt] = NaN
        df = df.sort_index()

        return df[start_dt:]

    def _list(self):
        watch_lst = [i.lower() for i in self.config.WATCH.keys()]
        preset_lst = [i.lower() for i in self.config.PRESET.keys()]

        if not len(watch_lst):
            print('No Watchlists')
        else:
            print("WatchLists:", ', '.join(watch_lst))

        if not len(preset_lst):
            print('No Presets')
        else:
            print("Preset:", ', '.join(preset_lst))

        exit()

    def _loadPreset(self, preset):
        if not preset in getattr(self.config, 'PRESET'):
            exit(f"Error: No preset named '{preset}'")

        args_dct = getattr(self.config, 'PRESET')[preset]

        if self.args.resume:
            args_dct['resume'] = True

        return self.parser.parse_args(arg_parse_dict(args_dct))

    def _savePreset(self, preset):
        if self.args.watch and not self.args.watch.upper() in self.config.WATCH:
            exit(f"Error: No watchlist named '{self.args.watch}'")

        data = loadJson(self.configPath) if self.configPath.is_file() else {}

        opts = vars(self.args).copy()

        del opts['preset_save']

        if not 'PRESET' in data:
            data['PRESET'] = {}

        data['PRESET'][preset] = opts
        writeJson(self.configPath, data)
        print(f"Preset saved as '{preset}'")

    def _removePreset(self, preset):
        if not preset in getattr(self.config, 'PRESET'):
            exit(f"Error: No preset named: '{preset}'")

        if not self.configPath.is_file():
            exit(f'File not found: {self.configPath}')

        data = loadJson(self.configPath)

        if not 'PRESET' in data or not preset in data['PRESET']:
            exit(f"Error: No preset named: '{preset}'")

        del data['PRESET'][preset]

        writeJson(self.configPath, data)
        exit(f"Preset '{preset}' removed.")

    def _loadWatchList(self, watch):
        if not watch.upper() in self.config.WATCH:
            exit(f"Error: No watchlist named '{watch}'")

        file = self.DIR / 'data' / self.config.WATCH[watch.upper()]

        if not file.is_file():
            exit(f'Error: File not found {file}')

        return file.read_text().strip('\n').split('\n')

    def _addWatch(self, name, fName):
        data = loadJson(self.configPath) if self.configPath.is_file() else {}

        if not 'WATCH' in data:
            data['WATCH'] = {}

        data['WATCH'][name.upper()] = fName
        writeJson(self.configPath, data)
        exit(f"Added watchlist '{name}' with value '{fName}'")

    def _removeWatch(self, name):
        if not name.upper() in getattr(self.config, 'WATCH'):
            exit(f"Error: No watchlist named: '{name}'")

        if not self.configPath.is_file():
            exit(f'No config file')

        data = loadJson(self.configPath)

        if not 'WATCH' in data or not name.upper() in data['WATCH']:
            exit(f"Error: No watchlist named: '{name}'")

        del data['WATCH'][name.upper()]

        writeJson(self.configPath, data)
        exit(f"Watchlist '{name}' removed.")

    def _getMaxPeriod(self):
        dlv_len = self.config.DLV_AVG_LEN if self.args.dlv else 0

        if self.args.m_rs:
            if self.tf == 'weekly':
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
