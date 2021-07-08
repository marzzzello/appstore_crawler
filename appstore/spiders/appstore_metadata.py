import scrapy
import json
from urllib.parse import unquote, urlencode, parse_qs, urlsplit
from time import time
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

        # load input file
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
        self._amp_dir = os.path.join(self._outputdir, 'amp')
        self._ua_dir = os.path.join(self._outputdir, 'ua')

        # load ids that are already done via amp
        try:
            (_, _, filenames_amp) = next(os.walk(self._amp_dir))
        except StopIteration:
            filenames_amp = []

        ids_amp_done = set()
        for file in set(filenames_amp):
            try:
                ids_amp_done.add(int(file.rstrip('.json')))
            except ValueError:
                # invalid id (not an int)
                pass
        self._ids_amp = ids_in - ids_amp_done
        self._num_ids_amp = len(self._ids_amp)
        self._num_ids_amp_done = 0

        # load ids that are already done via ua
        try:
            (_, _, filenames_ua) = next(os.walk(self._ua_dir))
        except StopIteration:
            filenames_ua = []

        ids_ua_done = set()
        for file in set(filenames_ua):
            try:
                ids_ua_done.add(int(file.rstrip('.json')))
            except ValueError:
                # invalid id (not an int)
                pass
        self._ids_ua = ids_in - ids_ua_done
        self._num_ids_ua = len(self._ids_ua)
        self._num_ids_ua_done = 0

        self._last_ids = {}
        self._last_status_time = 0
        self.logger.info(f'Loaded {len(ids_in)} ids from input file.')
        self.logger.info(f'{len(ids_amp_done)} ids got already crawled via the amp api. Remaining: {self._num_ids_amp}')
        self.logger.info(f'{len(ids_ua_done)} ids got already crawled via the ua api. Remaining: {self._num_ids_ua}')

        self._UA = self.settings['APPSTORE_USER_AGENT']
        self._country = getattr(self, 'country', 'us')
        self._platform = getattr(self, 'platform', 'iphone')
        self._locale = getattr(self, 'locale', 'en-US')
        use_UA = getattr(self, 'use_UA', False)
        if use_UA is False or use_UA.lower() == 'false':
            self._use_UA = False
        elif use_UA.lower() == 'true':
            self._use_UA = True

        amp_single = getattr(self, 'amp_single', False)
        if amp_single is False or amp_single.lower() == 'false':
            self._amp_single = False
        elif amp_single.lower() == 'true':
            self._amp_single = True
            self.download_delay = self.settings['DOWNLOAD_DELAY_AMP_SINGLE']
            self.logger.info(f'Download delay is {self.download_delay} seconds')

        self.logger.info(f'User-Agent is "{self._UA}"')
        self.logger.info(f'Parameters: country: {self._country}, platform: {self._platform}, locale: {self._locale}')
        self.logger.info(f'Parameters: use_UA: {self._use_UA}, amp_single: {self._amp_single}')

        # get token for amp api
        # app_id doesn't matter but has to be valid (using id of WhatsApp now)
        app_id = '310633997'
        url = 'https://apps.apple.com/' + self._country + '/app/id' + app_id
        self._token = None
        yield scrapy.Request(url, self.start_first_run)

    def start_first_run(self, response):
        self.parseJWT(response)
        return self.scrape_metadata()

    def scrape_metadata(self):
        base_url_amp = f'https://amp-api.apps.apple.com/v1/catalog/{self._country}/apps'
        header_auth = {'Authorization': 'Bearer ' + self._token}

        # curl https://apps.apple.com/us/app/whatsapp-messenger/id310633997
        #  --user-agent 'AppStore/2.0 iOS/14.4.2 model/iPhone11,2 (6; dt:185)' | jq -S > wa_ua.json
        base_url_ua = f'https://apps.apple.com/{self._country}/app/'
        header_ua = {'User-Agent': self._UA}

        while len(self._ids_amp) > 1 or (self._use_UA and len(self._ids_ua) > 1):
            if self._use_UA and len(self._ids_ua) > 1:
                app_id = self._ids_ua.pop()
                url_ua = base_url_ua + 'id' + str(app_id)
                yield scrapy.Request(url_ua, self.parse_ua, headers=header_ua)

            if len(self._ids_amp) > 1:
                if self._amp_single:
                    app_id = self._ids_amp.pop()
                    url_amp = base_url_amp + '/' + str(app_id) + '?' + self.get_params()
                else:
                    app_ids = set()
                    # get 100 ids
                    for ids in range(0, 100):
                        try:
                            app_ids.add(str(self._ids_amp.pop()))
                        except KeyError:
                            pass
                    url_amp = base_url_amp + '?' + self.get_params(ids=app_ids)
                yield scrapy.Request(url_amp, self.parse_amp, headers=header_auth)

            # self.logger.debug(f'Added {done}/{len(self._ids)} requests to queue')
        print('\n\nAll requests added to queue!\n\n')

    def parseJWT(self, response):
        content = response.xpath("//meta[@name='web-experience-app/config/environment']/@content").get()
        j = json.loads(unquote(content))
        self._token = j['MEDIA_API']['token']
        self.logger.info(f'Using token "{self._token}"')

    def parse_ua(self, response):
        try:
            _ = self._ua_dir_exists
        except AttributeError:
            os.makedirs(self._ua_dir, exist_ok=True)
            self._ua_dir_exists = True
        app_id = response.url.split('/')[-1].lstrip('id')
        filename = os.path.join(self._ua_dir, app_id + '.json')
        with open(filename, 'wb') as f:
            f.write(response.body)
        self._num_ids_ua_done += 1
        self.status(app_id, 'UA')

    def parse_amp(self, response):
        try:
            _ = self._amp_dir_exists
        except AttributeError:
            os.makedirs(self._amp_dir, exist_ok=True)
            self._amp_dir_exists = True
        u = urlsplit(response.url)
        app_id = u.path.split('/')[-1]
        # app_id = response.url.split('/')[-1].split('?')[0]
        if app_id == 'apps':
            # multiple ids
            app_ids_req = set(parse_qs(u.query)['ids'][0].split(','))
            app_ids_res = set()
            j = json.loads(response.body)

            for app in j['data']:
                app_ids_res.add(app['id'])
                filename = os.path.join(self._amp_dir, app['id'] + '.json')
                with open(filename, 'w') as f:
                    json.dump({'data': [app]}, f)
                self._num_ids_amp_done += 1
                self.status(app['id'], 'amp')
            diff = app_ids_req - app_ids_res
            if len(diff) > 0:
                self.logger.warning(f'Apps got requested but are not in response: {diff}')

        else:
            filename = os.path.join(self._amp_dir, app_id + '.json')
            with open(filename, 'wb') as f:
                f.write(response.body)
            self._num_ids_amp_done += 1
            self.status(app_id, 'amp')

    def status(self, app_id, api):
        self._last_ids[api] = app_id
        id_fmt = ''
        for api in self._last_ids:
            id_fmt += f'{api:>3}: {self._last_ids[api]:>12}; '

        amp_done = num_fmt(self._num_ids_amp_done)
        amp_total = num_fmt(self._num_ids_amp)
        ua_done = num_fmt(self._num_ids_ua_done)
        ua_total = num_fmt(self._num_ids_ua)
        status = f'{id_fmt}Amp: {amp_done:>4}/{amp_total:>4} apps; UA: {ua_done:>4}/{ua_total:>4} apps'
        # log every 30 seconds
        if (time() - self._last_status_time) >= 30:
            self.logger.info(status)
            self._last_status_time = time()
        print(status + '        ', end='\r')

    def get_params(self, ids={}):
        '''
        Multiple app ids can be requested but without the include param.
        Maximum is 100 ids
        '''
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
            'ids': ','.join(ids),
            'platform': self._platform,
            'additionalPlatforms': ','.join(platforms),
            'extend': ','.join(extend),
            'include': ','.join(include),
            'limit[reviews]': 20,
            'l': self._locale,
        }
        if ids is {}:
            del params['ids']
        else:
            del params['include']

        return urlencode(params)
