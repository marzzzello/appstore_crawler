import scrapy
import json


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


class AppstoreIDsSpider(scrapy.Spider):
    name = "appstore_ids"

    def start_requests(self):
        print('\nStarting')
        self.country = getattr(self, 'country', 'us')
        saveurls = getattr(self, 'saveurls', None)
        if saveurls is None or saveurls.lower() == 'false':
            self._saveurls = False
        elif saveurls.lower() == 'true':
            self._saveurls = True
        else:
            self.logger.error('Set saveurl to True or False')
            return

        self._level = int(getattr(self, 'level', 0))
        self._apps = 0
        self._pages = 0

        self.logger.info(f'Crawling the appstore for country "{self.country}"')
        self.logger.info(f'saveurls is set to {self._saveurls}')
        explanation = '(0: max (default), 1: categories only, 2: also popular apps, 3+: also all apps)'
        self.logger.info(f'level is set to {self._level} {explanation}')

        self.download_delay = self.settings['DOWNLOAD_DELAY_IDS']
        self.logger.info(f'Download delay is {self.download_delay} seconds')
        url = f'https://apps.apple.com/{self.country}/genre/ios/id36'
        yield scrapy.Request(url, self.parse_main)

    def parse_main(self, response):

        categories = []
        # main categorie that has no subcategories
        for categorie in response.css('a.top-level-genre:only-child'):
            categories.append(
                {
                    'id': categorie.attrib['href'].split('/id')[1],
                    'title': categorie.attrib['title'].split(' - ')[0],
                    'url': categorie.attrib['href'],
                }
            )

        main_categories_without_sub_urls = response.css('a.top-level-genre:only-child::attr(href)').getall()
        # main_categories_with_sub = response.css('a.top-level-genre:not(:only-child)::attr(href)').getall()
        # subcategories = response.css('ul.top-level-subgenres a::attr(href)').getall()

        # main categorie that has multiple subcategories
        for categorie in response.css('a.top-level-genre:not(:only-child)'):
            subcategories = []
            for subcat in categorie.css('a + ul a'):
                subcategories.append(
                    {
                        'id': subcat.attrib['href'].split('/id')[1],
                        'title': subcat.attrib['title'].split(' - ')[0],
                        'url': subcat.attrib['href'],
                    }
                )

            categories.append(
                {
                    'id': categorie.attrib['href'].split('/id')[1],
                    'title': categorie.attrib['title'].split(' - ')[0],
                    'url': categorie.attrib['href'],
                    'subcategories': subcategories,
                }
            )
        with open(f'categories_{self.country}.json', 'w') as f:
            json.dump(categories, f, indent=2)

        if self._level != 1:
            for url in main_categories_without_sub_urls:
                url = response.urljoin(url)
                yield scrapy.Request(url, callback=self.parse_categorie)

    def parse_categorie(self, response):
        cat_id = response.url.split('/id')[1]
        apps = []
        for url in response.css('.grid3-column a::attr(href)').getall():
            app_id = int(url.split('/')[-1].lstrip('id').split('?')[0])
            if self._saveurls:
                apps.append({'id': app_id, 'url': url})
            else:
                apps.append(app_id)

        yield {
            'category_id': cat_id,
            'popular-apps': apps,
        }

        # get letters
        if self._level >= 3 or self._level == 0:
            for url in response.css('ul.alpha li a::attr(href)').getall():
                url = response.urljoin(url)
                yield scrapy.Request(url, callback=self.parse_categorie_letter)

    def parse_categorie_letter(self, response):
        cat_id, end = response.url.split('/id')[1].split('?letter=')
        if len(end) == 1:
            letter = end
            page = '0'
        else:
            letter, page = end.split('&page=')

        print(f'Parsing {cat_id} {letter} {page:>3};', end=' ')
        print(
            f'Done {num_fmt(self._pages):>4}/~15k pages, {num_fmt(self._apps):>5}/~1.6M apps   ',
            end='\r',
        )

        # skip initial page as it would create dupicates
        if page != '0':
            self._pages += 1
            apps = []

            # yes, there are duplicates...
            urls_unique = set(response.css('.grid3-column a::attr(href)').getall())
            for url in urls_unique:
                app_id = int(url.split('/')[-1].lstrip('id').split('?')[0])
                self._apps += 1
                if self._saveurls:
                    apps.append({'id': app_id, 'url': url})
                else:
                    apps.append(app_id)

            yield {
                'category_id': cat_id,
                'letter': letter,
                'page': page,
                'apps': apps,
            }

        # get pages
        for url in response.css('ul.paginate a::attr(href)').getall():
            url = response.urljoin(url)
            yield scrapy.Request(url, callback=self.parse_categorie_letter)
