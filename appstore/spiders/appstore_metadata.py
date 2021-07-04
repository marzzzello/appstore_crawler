import scrapy
import json
from urllib.parse import unquote, urlencode
from time import sleep
import os


def num_fmt(num):
    '''
    Format big numbers human readable
    '''
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])


class AppstoreMetaSpider(scrapy.Spider):
    name = "appstore_meta"

    def start_requests(self):
        print('\nStarting')
        inputfile = getattr(self, 'inputfile', None)
        if inputfile is None:
            self.logger.error('An input file with app ids is needed (add inputfile=filename)')
            return
        ids_in = set()
        with open(inputfile) as f:
            for line in f:
                try:
                    ids_in.add(int(line.strip()))
                except ValueError:
                    self.logger.error('line is not an int:', line.strip())
                    return
        self._outputdir = getattr(self, 'outputdir', 'output')
        try:
            (_, _, filenames) = next(os.walk(self._outputdir))
        except StopIteration:
            filenames = []

        ids_done = set()
        for file in set(filenames):
            try:
                ids_done.add(int(file.rstrip('.json')))
            except ValueError:
                # invalid id (not an int)
                pass

        self._ids = ids_in - ids_done
        self.logger.info(f'ids_in: {min(ids_in)}  ids_done: {min(ids_done)}')
        self.logger.info(f'ids_in: {max(ids_in)}  ids_done: {max(ids_done)};; {min(ids_done) in ids_in}')
        self._num_ids = len(self._ids)
        self._num_ids_done = 0
        self.is_paused = False
        self.logger.info(f'Loaded {len(ids_in)} ids from input file from which {len(ids_done)} got already crawled')
        self.logger.info(f'Crawling the {self._num_ids} remaining ids')

        # self._UA = self.settings['APPSTORE_USER_AGENT']
        self._country = getattr(self, 'country', 'us')
        self._platform = getattr(self, 'platform', 'iphone')
        self._locale = getattr(self, 'locale', 'en-US')

        self._level = int(getattr(self, 'level', 0))
        self._apps = 0
        self._pages = 0

        # self.logger.info(f'User-Agent is "{self._UA}"')
        self.logger.info(f'Parameters: country: {self._country} platform: {self._platform} locale: {self._locale}')
        # explanation = '(0: max (default), 1: categories only, 2: also popular apps, 3+: also all apps)<'
        # self.logger.info(f'level is set to {self._level} {explanation}')

        # app_id doesn't matter but has to be valid (using id of WhatsApp now)
        app_id = '310633997'
        url = 'https://apps.apple.com/' + self._country + '/app/id' + app_id
        self._token = None
        yield scrapy.Request(url, self.start_first_run)

    def start_first_run(self, response):
        self.parseJWT(response)
        return self.scrape_metadta()

    def scrape_metadta(self):
        base_url_amp = f'https://amp-api.apps.apple.com/v1/catalog/{self._country}/apps/'
        header_auth = {'Authorization': 'Bearer ' + self._token}

        # curl https://apps.apple.com/us/app/whatsapp-messenger/id310633997 --user-agent 'AppStore/2.0 iOS/14.4.2 model/iPhone11,2 (6; dt:185)' | jq -S > wa_ua.json
        # base_url_ua = f'https://apps.apple.com/{self._country}/app/'
        # header_ua = {'User-Agent': self._UA}
        self.logger.info('Start adding requests to queue')
        done = 0
        params = self.get_params()
        for app_id in self._ids:
            url_amp = base_url_amp + str(app_id) + '?' + params
            if not self.is_paused:
                yield scrapy.Request(url_amp, self.parse_amp, headers=header_auth)
            else:
                sleep(1)
            done += 1
            self.logger.info(f'Added {done}/{len(self._ids)} requests to queue')
        self.logger.info('Done requests to queue')

        # Rate limited after ~200 requests:
        # url_ua = base_url_ua + app_id
        # yield scrapy.Request(url_ua, self.parse_ua, headers=header_ua)

    def parseJWT(self, response):
        print(123)
        content = response.xpath("//meta[@name='web-experience-app/config/environment']/@content").get()
        j = json.loads(unquote(content))
        self._token = j['MEDIA_API']['token']
        self.logger.info(f'Using token "{self._token}"')

    # def parse_ua(self, response):
    #     try:
    #         _ = self._ua_dir_exists
    #     except AttributeError:
    #         os.makedirs(os.path.join('output', 'ua'), exist_ok=True)
    #         self._ua_dir_exists = True
    #     app_id = response.url.split('/')[-1].lstrip('id')
    #     filename = os.path.join('output', 'ua', app_id + '.json')
    #     with open(filename, 'wb') as f:
    #         f.write(response.body)
    #     self.logger.info(f'Saved file {filename}')

    def parse_amp(self, response):
        try:
            _ = self._amp_dir_exists
        except AttributeError:
            os.makedirs(self._outputdir, exist_ok=True)
            self._amp_dir_exists = True
        app_id = response.url.split('/')[-1].split('?')[0]
        filename = os.path.join(self._outputdir, app_id + '.json')
        with open(filename, 'wb') as f:
            f.write(response.body)
        self._num_ids_done += 1
        status = f'Saved {app_id:>12}; Done {num_fmt(self._num_ids_done):>4}/{num_fmt(self._num_ids):>4} apps'
        self.logger.debug(status)
        # print(status + '        ', end='\r')

    def get_params(self):
        platforms = ['appletv', 'ipad', 'mac', 'watch', 'iphone']
        platforms.remove(self._platform)
        extend = [
            'description',
            'editorialVideo',
            'expectedReleaseDateDisplayFormat',
            'fileSizeByDevice',
            'maxPlayers',
            'messagesScreenshots',
            'minPlayers',
            'minimumOSVersion',
            'privacyDetails',
            'privacyPolicyUrl',
            'promotionalText',
            'remoteControllerRequirement',
            'requirementsByDeviceFamily',
            'screenshotsByType',
            'supportURLForLanguage',
            'supportsFunCamera',
            'versionHistory',
            'videoPreviewsByType',
            'websiteUrl',
        ]
        include = [
            'alternate-apps',
            'app-bundles',
            'customers-also-bought-apps',
            'developer',
            'developer-other-apps',
            'merchandised-in-apps',
            'related-editorial-items',
            'reviews',
            'top-in-apps',
        ]
        params = {
            'platform': self._platform,
            'additionalPlatforms': ','.join(platforms),
            'extend': ','.join(extend),
            'include': ','.join(include),
            'limit[reviews]': 20,
            'l': self._locale,
        }
        return urlencode(params)
