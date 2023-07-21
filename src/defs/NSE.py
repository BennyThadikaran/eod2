from pathlib import Path
from requests import Session
from pickle import dumps, loads
from requests.exceptions import ReadTimeout

DIR = Path(__file__).parent.parent


class NSE:
    'A class for managing downloads from NSE Website'

    def __init__(self):

        self.cookie_file = DIR / 'cookies'

        uAgent = 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'

        self.headers = {
            'User-Agent': uAgent,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www1.nseindia.com'
        }

        self.session = Session()
        self.cookies = self.__getCookies()
        self.dateFmt = '%Y%m%d'

    def __setCookies(self):
        r = self.makeRequest('https://www.nseindia.com/option-chain',
                             params=None,
                             timeout=10,
                             expectJson=False)

        if not r.ok:
            exit(f'Error: set cookie. {r.status_code}: {r.reason}')

        cookies = r.cookies

        (DIR / 'cookies').write_bytes(dumps(cookies))

        return cookies

    def __getCookies(self):
        file = DIR / 'cookies'

        if file.is_file():
            cookies = loads(file.read_bytes())

            if self.__hasCookiesExpired(cookies):
                cookies = self.__setCookies()

            return cookies

        return self.__setCookies()

    @staticmethod
    def __hasCookiesExpired(cookies):
        for cookie in cookies:
            if cookie.is_expired():
                return True

        return False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.session.close()

    def exit(self):
        self.session.close()

    def download(self, url):
        '''Download a file in chunks from the given url.
        Useful for downloading larger files.
        Returns the path of the downloaded file'''

        fname = DIR / url.split("/")[-1]

        with self.session.get(url,
                              stream=True,
                              headers=self.headers,
                              timeout=15) as r:

            with open(fname, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1000000):
                    f.write(chunk)
        return fname

    def makeRequest(self, url, params, expectJson=True, timeout=15):
        '''Make a GET request to given url with params
        with timeout that defaults to 15 seconds.
        By default returns a JSON parsed object.
        Set expectJson = False to return the response object
        '''

        cookies = self.cookies if hasattr(self, 'cookies') else None
        try:
            r = self.session.get(url, params=params, headers=self.headers,
                                 cookies=cookies, timeout=timeout)
        except ReadTimeout:
            exit('Request timed out')

        if not r.ok:
            exit(f'{r.status_code}: {r.reason}')

        if expectJson:
            return r.json()

        return r
