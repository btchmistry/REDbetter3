#!/usr/bin/env python3

# Very basic script to match uchicago CD entries with requests

from configparser import ConfigParser
import argparse
from pathlib import Path
import sys

import html

from cache import Cache
import redactedapi
import uchicago as uc
from utils import Utilities


def parse_config(config_path: Path):
    config = ConfigParser()
    if not config_path.is_file():
        print('Please run REDBetter3 first to create config file or specify \
            config location')
        sys.exit(2)
    else:
        try:
            config.read(config_path)
        except Exception as e:
            print(f'Error reading config file from {config_path}')
            raise e
        return config


def main():
    # MW_API_HOST = "https://catalog.lib.uchicago.edu"
    # Processing command line arguments:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     prog='./crequestmatch.py')
    parser.add_argument('-p', '--page-size', type=int,
                        help='Number of results per request', default=500)
    parser.add_argument('-f', '--page-range-from', type=int,
                        help='Start page number, needs to be specified together with --page-range-to', default=None)
    parser.add_argument('-t', '--page-range-to', type=int,
                        help='End page number, needs to be specified together with --page-range-from', default=None)
    parser.add_argument('-r', '--retry-all', action='store_true',
                        help='Ignore cached requests', default=False)
    parser.add_argument('-s', '--sparse', action='store_true',
                        help='Only print RequestIds', default=False)
    parser.add_argument('--cache', help='the location of the cache',
                        default=Path('~/.redactedbetter/libchicagomatchrequestscache').expanduser())
    parser.add_argument('--config', help='the location of the configuration file',
                        default=Path('~/.redactedbetter/config').expanduser())

    args = parser.parse_args()

    ut = Utilities()

    # Set amount of 'result pages' will be requested
    page_start = 0
    page_end = 1
    if (args.page_range_from is not None) and (args.page_range_to is not None):
        page_start = args.page_range_from
        page_end = args.page_range_to
    elif (args.page_range_from is not None) or (args.page_range_to is not None):
        if not args.sparse:
            print("Both --page-range-from and --page-range-to need to be specified")
            print("Using system defaults (first page only)")
    else:
        if not args.sparse:
            print("Unknown error with page range")
            print("Using system defaults (first page only)")

    # loading configuration from config file
    config = parse_config(Path(args.config))

    api_key = config.get('redacted', 'api_key')

    # print('Initializing with API key')
    api = redactedapi.RedactedAPI(args.page_size, api_key, args.sparse)

    cache = Cache(args.cache)

    # load requests and start processing them, the goal is to identify easily
    # fillable requests: transcodes: No MP3 requested
    cache_count = 0
    for request in api.get_requests_historical(start_page=page_start,
                                               end_page=page_end):

        if request["requestId"] in cache.ids and not args.retry_all:
            cache_count += 1
            continue
        artist = ''
        albumtitle = ''

        if request["artists"]:
            artist = html.unescape(request["artists"][0][0]["name"])
            albumtitle = html.unescape(request["title"])
        else:
            albumtitle = html.unescape(request["title"])
            print(
                f'****************************No artist name! https://redacted.ch/requests.php?action=view&id={request["requestId"]}')
        # print(html.unescape(searchstring))
        mwresult = uc.get_records(artist, albumtitle)
        if not mwresult:
            cache.add(request["requestId"], 'no match')
            continue
        bounty_pretty = ut.prettify_bytes(int(request["bounty"]))

        print(f'########## Potential match! Bounty: {bounty_pretty}')
        print(f'{artist} - {albumtitle} (https://redacted.ch/requests.php?action=view&id={request["requestId"]})')
        print("+++")
        if "Record" in mwresult:
            print(mwresult)
        else:
            print(f'No Record, but a response: {mwresult}')
        print("+++")
        print('##########')
        cache.add(request["requestId"], 'match')

    if not args.sparse:
        print(f'Searched pages {page_start} to {page_end}')
        print(f'Skipped {cache_count} cached requests')


if __name__ == "__main__":
    main()
