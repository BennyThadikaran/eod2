class Config:
    VERSION = '2.0'
    AMIBROKER = False
    UPDATE_DAYS = 365

    def __str__(self):
        txt = 'EOD2\n'

        for p in dir(self):
            if not p.startswith('__'):
                txt += f'{p}: {getattr(self, p)}\n'
        return txt
