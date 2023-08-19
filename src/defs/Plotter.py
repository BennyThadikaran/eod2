from pathlib import Path
from defs.utils import arg_parse_dict, getDataFrame, getScreenSize, getLevels, getDeliveryLevels, writeJson, loadJson
from mplfinance import plot, make_addplot
from datetime import timedelta
from numpy import NaN
from pandas import Series


def processPlot(df, plot_args):
    plot(df, **plot_args)


class Plotter:
    DIR = Path(__file__).parent.parent
    daily_dir = DIR / 'eod2_data' / 'daily'
    dlv_dir = DIR / 'eod2_data' / 'delivery'
    configPath = DIR / 'defs' / 'user.json'

    def __init__(self, args, config, parser):
        self.args = args
        self.config = config
        self.parser = parser

        self.tf = args.tf

        if args.preset and args.preset_save:
            exit(
                'plot.py: error: argument --preset: not allowed with argument --preset_save')

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

        if args.preset:
            args = self._loadPreset(args.preset)
            self.args = args

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
            'xrotation': 40,
            'datetime_format': '%d %b %y',
            'figscale': 2,
            'scale_padding': {
                'left': 0.3,
                'right': 0.6,
                'top': 0.4,
                'bottom': 0.6
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
        df = self._prepData(sym)

        self._prepArguments(sym, df)

        if self.args.save:
            return df

        plot(df, **self.plot_args)

    def _prepArguments(self, sym, df):
        added_plots = []
        self.plot_args['title'] = f'{sym.upper()}, {self.tf[0].upper()}'
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
                dq['TTL_TRD_QNTY'] / dq['NO_OF_TRADES']
            ).round(2)

        return dq

    def _prepData(self, sym):
        fpath = self.daily_dir / f'{sym.lower()}.csv'

        if not fpath.is_file():
            exit(f"Error: File not found: {fpath}")

        df = getDataFrame(fpath,
                          self.tf,
                          self.max_period,
                          fromDate=self.args.date)

        plot_period = min(df.shape[0], self.period)

        if self.args.rs or self.args.m_rs:
            df['RS'] = (df['Close'] / self.idx_cl) * 100

        if self.args.m_rs:
            if self.tf == 'weekly':
                rs_period = self.config.PLOT_M_RS_LEN_W
            else:
                rs_period = self.config.PLOT_M_RS_LEN_D

            sma_rs = df['RS'].rolling(rs_period).mean()
            df['M_RS'] = ((df['RS'] / sma_rs) - 1) * 100

        if self.args.sma:
            for period in self.args.sma:
                df[f'SMA_{period}'] = df['Close'].rolling(
                    period).mean().round(2)

        if self.args.ema:
            for period in self.args.ema:
                alpha = 2 / (period + 1)
                df[f'EMA_{period}'] = df['Close'].ewm(
                    alpha=alpha).mean().round(2)

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

        if self.args.sma or self.args.ema:
            sma = self.args.sma if self.args.sma else []
            ema = self.args.ema if self.args.ema else []

            add_period = max(*sma, *ema, m_rs_len, dlv_len)
            return add_period + self.period
        elif self.args.m_rs:
            return max(m_rs_len, dlv_len) + self.period
        elif self.args.dlv:
            return dlv_len + self.period

        return self.period
