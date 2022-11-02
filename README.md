![](https://forthebadge.com/images/badges/built-with-love.svg)
![](https://forthebadge.com/images/badges/fuck-it-ship-it.svg)
![](https://forthebadge.com/images/badges/contains-Cat-GIFs.svg)

[![Repo on GitLab](https://img.shields.io/badge/repo-GitLab-fc6d26.svg?style=for-the-badge&logo=gitlab)](https://gitlab.com/marzzzello/appstore_crawler)
[![Repo on GitHub](https://img.shields.io/badge/repo-GitHub-4078c0.svg?style=for-the-badge&logo=github)](https://github.com/marzzzello/appstore_crawler)
[![license](https://img.shields.io/github/license/marzzzello/appstore_crawler.svg?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxwYXRoIHN0eWxlPSJmaWxsOiNkZGRkZGQiIGQ9Ik03IDRjLS44MyAwLTEuNS0uNjctMS41LTEuNVM2LjE3IDEgNyAxczEuNS42NyAxLjUgMS41UzcuODMgNCA3IDR6bTcgNmMwIDEuMTEtLjg5IDItMiAyaC0xYy0xLjExIDAtMi0uODktMi0ybDItNGgtMWMtLjU1IDAtMS0uNDUtMS0xSDh2OGMuNDIgMCAxIC40NSAxIDFoMWMuNDIgMCAxIC40NSAxIDFIM2MwLS41NS41OC0xIDEtMWgxYzAtLjU1LjU4LTEgMS0xaC4wM0w2IDVINWMwIC41NS0uNDUgMS0xIDFIM2wyIDRjMCAxLjExLS44OSAyLTIgMkgyYy0xLjExIDAtMi0uODktMi0ybDItNEgxVjVoM2MwLS41NS40NS0xIDEtMWg0Yy41NSAwIDEgLjQ1IDEgMWgzdjFoLTFsMiA0ek0yLjUgN0wxIDEwaDNMMi41IDd6TTEzIDEwbC0xLjUtMy0xLjUgM2gzeiIvPjwvc3ZnPgo=)](LICENSE.md)
[![commit-activity](https://img.shields.io/github/commit-activity/m/marzzzello/appstore_crawler.svg?style=for-the-badge)](https://img.shields.io/github/commit-activity/m/marzzzello/appstore_crawler.svg?style=for-the-badge)
[![Mastodon Follow](https://img.shields.io/mastodon/follow/103207?domain=https%3A%2F%2Fsocial.tchncs.de&logo=mastodon&style=for-the-badge)](https://social.tchncs.de/@marzzzello)

# Apple App Store Crawler

This crawler is based on [scrapy](https://docs.scrapy.org/en/latest/) and can download the IDs of all apps in the Apple App Store.
It can also download the metadata for a list of IDs.

## Unmaintained

This project is not working as Apple changed their website and API. So it is not easily fixable and I don't plan on working on this project.

## Setup

Install scrapy:

```sh
pip install scrapy
```

## Usage

### Get IDs

The crawler uses `https://apps.apple.com/{country}/genre/ios/id36` to get the categories and IDs by crawling all categories, letters and pages.
Since the webserver has no rate limiting, it is not needed to set a delay. A full crawl needs about 30 minutes (10-15 pages/second).

```sh
scrapy crawl -L INFO appstore_ids -a saveurls=False -a country=us -a level=0 -O out_ids.jl
```

Parameters:

- `country`: Two letter country code (default: `us`)
- `saveurls`: In addition to the ID also save the url for each app (default: `False`)
- `level`: Crawling level:
  - `0`: max (default)
  - `1`: categories only
  - `2`: also popular apps
  - `3`+: also all apps

The output type can be speciefied by the file ending.

`-O out_us.jl` will produce a json line file.

The output in json line format can be used to generate a file with a list of IDs.

For that the `collect.py` script is used:

```
./collect.py out_us.jl US --all
```

That generates 3 files: `US.json`, `US_all_ids`, `US_popular_ids`

```
usage: collect.py [-h] [--all] [--json] [--all_ids] [--popular_ids] [--sort] input output

Process appstore jl file

positional arguments:
  input          the input file
  output         base name of the output files

optional arguments:
  -h, --help     show this help message and exit
  --all          save all files
  --json         save json file
  --all_ids      save all_ids file
  --popular_ids  save popular_ids file
  --sort         sort ids
```

### Get metadata

There are 3 methods of crawling the metadata:

1. amp api multi (default): `https://amp-api.apps.apple.com/v1/catalog/{country}/apps/?ids=...`
2. amp api single: `https://amp-api.apps.apple.com/v1/catalog/{country}/apps/{id}?...`
3. UA: fake user-agent and `https://apps.apple.com/{country}/app/id{id}`

```sh
scrapy crawl --loglevel=INFO appstore_meta -a inputfile=US_all_ids
```

Parameters:

- `inputfile`: file with IDs (use `collect.py`) (mandatory)
- `outputdir`: directory where the json files will be saved (default: `output`)
- `country`: 2 letters country shortcode (default: `us`)
- `platform`: One of these: `appletv`, `ipad`, `mac`, `watch`, `iphone` (default: `iphone`)
- `locale`: locale string (default: `en-US`)
- `use_UA`: also crawl UA endpoint (default: `False`)
- `amp_single`: just request a single app id per request (default: `False`)

### Delay and other settings

The delays can be changed in the `settings.py`

The default delay is `1.1` seconds for the amp multi method, `0.51` for the amp single method and no delay for getting the IDs.

Currently the UA method uses the same delay as the choosen amp method because it's not possible to set per domain delays in scrapy (yet).

```python
DOWNLOAD_DELAY = 1.1
DOWNLOAD_DELAY_AMP_SINGLE = 0.51
DOWNLOAD_DELAY_IDS = 0.0
```

The default delays are tested and should work well.
With the amp multi method and default settings the retrieval of metadata for 1 million apps needs about 3 hours.
