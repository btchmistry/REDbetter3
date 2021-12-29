#!/usr/bin/env python3

from configparser import ConfigParser
import argparse
from pathlib import Path
from typing import List, Optional
import html.parser

import shutil
import sys
import tempfile
import urllib.parse
from multiprocessing import cpu_count

import tagging
import transcode
import redactedapi
from cache import Cache


def create_description(torrent, flac_dir, format, permalink):
    # Create an example command to document the transcode process.
    cmds = transcode.transcode_commands(format,
                                        transcode.needs_resampling(flac_dir),
                                        transcode.resample_rate(flac_dir),
                                        'input.flac', 'output'
                                        + transcode.encoders[format]['ext'])
    description = '\n'.join([
        f'Transcode of [url={permalink}]{permalink}[/url]\n',
        'Transcode process:',
        f'[code]{" | ".join(cmds)}[/code]\n'
        'Created using REDBetter3 (btchmistry fork)'
    ])
    return description


def formats_needed(group, torrent, supported_formats):
    def same_group(t): return t['media'] == torrent['media'] and\
        t['remasterYear'] == torrent['remasterYear'] and\
        t['remasterTitle'] == torrent['remasterTitle'] and\
        t['remasterRecordLabel'] == torrent['remasterRecordLabel'] and\
        t['remasterCatalogueNumber'] == torrent['remasterCatalogueNumber']

    others = list(filter(same_group, group.torrents))
    current_formats = set((t['format'], t['encoding']) for t in others)
    missing_formats = [format for format, details in
                       [(f, redactedapi.formats[f]) for f in supported_formats]
                       if (details['format'], details['encoding'])
                       not in current_formats]
    allowed_formats = redactedapi.allowed_transcodes(torrent)
    return [format for format in missing_formats if format in allowed_formats]


# Not used at the moment
def validate_spectrograms(flac_dir_str: str, threads: int) -> bool:
    # flac_dir = Path(flac_dir_str)
    spectrogram_dir = Path('/tmp/spectrograms')
    if spectrogram_dir.exists():
        shutil.rmtree(spectrogram_dir)
    spectrogram_dir.mkdir()
    # if not make_spectrograms(flac_dir, spectrogram_dir, threads):
    #     # make_spectrograms is UNDEFINED
    #     return False
    print(f'Spectrograms written to {spectrogram_dir}. Are they acceptable?')
    response = get_input(['y', 'n'])
    if response == 'n':
        print('Spectrograms rejected. Skipping.')
        return False
    return True


def get_input(choices: List[str]) -> str:
    choice_set = set(choices)
    response = ''
    while response not in choice_set:
        response = input(f'Please enter one of {", ".join(choices)}: ').lower()
    return response


def border_msg(msg):
    width = 0
    for line in msg.splitlines():
        length = len(line)
        if length > width:
            width = length

    dash = "-" * (width - 1)
    return "+{dash}+\n{msg}\n+{dash}+".format(dash=dash, msg=msg)


def parse_config(config_path: Path) -> Optional[ConfigParser]:
    config = ConfigParser()
    if not config_path.is_file():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config.add_section('redacted')
        config.set('redacted', 'api_key', '')
        config.set('redacted', 'data_dir', '')
        config.set('redacted', 'output_dirs', '')
        config.set('redacted', 'torrent_dir', '')
        config.set('redacted', 'spectral_dir', '')
        config.set('redacted', 'formats', 'flac, v0, 320')
        config.set('redacted', 'media', ', '.join(redactedapi.lossless_media))
        config.set('redacted', '24bit_behaviour', 'yes')
        config.set('redacted', 'piece_length', '18')
        with open(config_path, 'w') as config_file:
            config.write(config_file)
        print(f'No config file found. Please edit the blank one created '
              f'at {config_path}')
        return None
    else:
        try:
            config.read(config_path)
        except Exception as e:
            print(f'Error reading config file from {config_path}')
            raise e
        return config


def main():

    # Processing command line arguments:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     prog='REDbetter3')
    parser.add_argument('release_urls', nargs='*',
                        help='the URL where the release is located')
    parser.add_argument('-s', '--single', action='store_true',
                        help='only add one format per release (useful for getting unique groups)')
    parser.add_argument('-j', '--threads', type=int,
                        help='number of threads to use when transcoding', default=max(cpu_count() - 1, 1))
    parser.add_argument('--config', help='the location of the configuration file',
                        default=Path('~/.redactedbetter/config').expanduser())
    parser.add_argument('--cache', help='the location of the cache',
                        default=Path('~/.redactedbetter/cache').expanduser())
    parser.add_argument('-p', '--page-size', type=int,
                        help='Number of snatched results to fetch at once', default=500)
    parser.add_argument('-f', '--force-format', default=None,
                        help='Force any of these formats: ''FLAC'', ''V0'', ''320''')
    parser.add_argument('--skip-missing', action='store_true', default=False,
                        help='Skip snatches that have missing data directories')
    parser.add_argument('-r', '--retry', nargs='*', default=[],
                        help='Retries certain classes of previous exit statuses')
    parser.add_argument('--skip-spectral', action='store_true', default=False,
                        help='Skips spectrograph verification')
    parser.add_argument('--skip-hashcheck', action='store_true', default=False,
                        help='Skip source file integrity verification')
    parser.add_argument('--no-upload', action='store_true', default=False,
                        help='don\'t upload new torrents (in case you want to do it manually)')

    args = parser.parse_args()

    # loading configuration from config file, or create one at first pass
    config = parse_config(Path(args.config))
    if config is None:
        sys.exit(2)

    api_key = config.get('redacted', 'api_key', fallback=None)

    # data_dir = Path(config.get('redacted', 'data_dir')).expanduser()
    data_dirs = config.get('redacted', 'data_dirs').split(', ')

    output_dir = Path(config.get('redacted', 'output_dir')).expanduser()
    torrent_dir = Path(config.get('redacted', 'torrent_dir')).expanduser()
    supported_formats = [format.strip().upper()
                         for format in config.get('redacted', 'formats').split(',')]
    # validate_formats(supported_formats)
    do_24_bit = config.get('redacted', '24bit_behaviour')

    # print('Initializing with API key')
    api = redactedapi.RedactedAPI(args.page_size, api_key,)

    cache = Cache(args.cache)
    # TODO: rewrite spectrals (if we want or delete traces to it)
    # pp = pprint.PrettyPrinter(indent=4)
    # pp.pprint(cache.ids)
    # spectral_dir = Path(config.get('redacted', 'spectral_dir', fallback='/tmp/spectrograms'))
    # spectral_dir.mkdir(parents=True, exist_ok=True)

    print('Searching for transcode candidates...')
    if args.release_urls:
        print('You supplied one or more release URLs, ignoring your configuration\'s media types.')
        candidates = [(int(query['id']), int(query['torrentid'])) for query in
                      [dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query)) for url in args.release_urls]]
    else:
        candidates = api.get_seeding()

    retry_modes = set(args.retry)

    # Main loop that does all the transcoding, etc.
    cache_count = 0
    for groupid, torrentid in candidates:
        # Test if torrent is in cache to reduce calls to server
        if torrentid in cache.ids and not args.force_format:
            retry = False
            if cache.ids[torrentid] in retry_modes:
                retry = True
            if not retry:
                # print(f'Torrent ID {torrentid} present in cache. Skipping.')
                cache_count += 1
                continue

        group = api.get_torrentgroup(groupid)

        # Get the torrent from torrentgroup
        for t in group.torrents:
            if t['id'] == torrentid:
                torrent = t

        # Test if torrent is flac
        if "FLAC" not in torrent['format'] and "Lossless" not in torrent['encoding']:
            print(
                f"Torrent {api.permalink(torrentid)} is not in flac format, transcode not possible")
            cache.add(torrentid, 'no flac')
            continue

        # Check for scene release: must be manually descened, so not supported
        if torrent['scene']:
            print(
                f"Torrent {api.permalink(torrentid)} is a scene release, must be manually descened")
            cache.add(torrentid, 'scene')
            continue
        # Check if torrent is trumpable, if so, it can only be uploaded if it is put in manually
        # Some trumpable torrents are still fine to upload, like the ones without Lineage
        if torrent['trumpable'] and not args.release_urls:
            print(
                f"Torrent {api.permalink(torrentid)} torrent is marked as trumpable, this will only be transcoded if added manually")
            cache.add(torrentid, 'trumpable')
            continue

        # Create infoblock
        artist = ""
        if len(group.group['musicInfo']['artists']) > 1:
            artist = "Various Artists"
        else:
            artist = group.group['musicInfo']['artists'][0]['name']

        year = str(group.torrents[0]['remasterYear'])
        if year == "0":
            year = str(group.group['year'])

        releaseartist = "Release artist(s): %s" % html.unescape(artist)
        releasename = "Release name     : %s" % html.unescape(
            group.group['name'])
        releaseyear = "Release year     : %s" % year
        releaseurl = "Release URL      : %s" % api.release_url(
            group.group['id'], group.torrents[0]['id'])

        print(border_msg(releaseartist
                         + "\n" + releasename
                         + "\n" + releaseyear
                         + "\n" + releaseurl))

        # Test if torrent is in it's own folder, if not, create one
        if not torrent['filePath']:
            file_name = html.unescape(torrent['fileList']).split('{{{')[0]
            # find correct data_dir
            data_dir = ''
            for path in data_dirs:
                flac_file = Path(path, file_name)
                if flac_file.exists():
                    data_dir = path
            if data_dir == '':
                print(f"Path not found - skipping: {flac_file}")
                continue
            # Flac folder name convention: Release Name (year) [FLAC]
            flac_dir = Path(data_dir, f"{html.unescape(group.group['name'])} \
                                        ({group.group['year']}) [FLAC]")
            if not flac_dir.exists():
                flac_dir.mkdir()
            shutil.copy(flac_file, flac_dir)
        else:
            file_name = html.unescape(torrent['fileList']).split('{{{')[0]
            data_dir = ''
            # find correct data_dir
            for path in data_dirs:
                flac_file = Path(path, html.unescape(torrent['filePath']), file_name)
                if flac_file.exists():
                    data_dir = path
            if data_dir == '':
                print(f"Path not found - skipping: {flac_file}")
                continue
            flac_dir = Path(data_dir, html.unescape(torrent['filePath']))

        if do_24_bit == 'yes':
            try:
                if transcode.is_24bit(flac_dir) and torrent['encoding'] != '24bit Lossless':
                    # A lot of people are uploading FLACs from Bandcamp without realizing
                    # that they're actually 24 bit files (usually 24/44.1). Since we know for
                    # sure whether the files are 24 bit, we might as well correct the listing
                    # on the site (and get an extra upload in the process).

                    # TODO: check 24 bit behaviour
                    if args.no_24bit_edit:
                        print("Release is actually 24-bit lossless, skipping.")
                        continue
                    if do_24_bit == 'yes':
                        confirmation = input(
                            "Mark release as 24bit lossless? y/n: ")
                        if confirmation != 'y':
                            continue
                    print("Marking release as 24bit lossless.")
                    api.set_24bit(torrent)
                    # group = api.request('torrentgroup', id=groupid)
                    # torrent = [t for t in group['torrents']
                    #            if t['id'] == torrentid][0]
                    continue
            except Exception as e:
                print("Error: can't edit 24-bit torrent - skipping: %s" % e)
                continue

        if transcode.is_multichannel(flac_dir):
            print("This is a multichannel release, which is unsupported - skipping")
            continue

        if args.force_format is not None:
            needed = [args.force_format]  # manually declare which formats
        else:
            needed = formats_needed(group, torrent, supported_formats)

        if len(needed) < 1:
            print("No transcode needed")
            cache.add(torrentid, 'done')
            continue
        else:
            print("Formats needed: %s" % ', '.join(needed))

        if needed:
            # Before proceeding, do the basic tag checks on the source
            # files to ensure any uploads won't be reported, but put
            # on the tracknumber formatting; problems with tracknumber
            # may be fixable when the tags are copied.
            broken_tags = False
            for flac_file in transcode.locate(flac_dir, transcode.ext_matcher('.flac')):
                (ok, msg) = tagging.check_tags(
                    flac_file, check_tracknumber_format=False)
                if not ok:
                    print(
                        "A FLAC file in this release has unacceptable tags - skipping: %s" % msg)
                    print("You might be able to trump it.")
                    broken_tags = True
                    break
            if broken_tags:
                continue

        # while os.path.exists(flac_dir) == False:
        #     print("Path not found: %s" % flac_dir)
        #     alternative_file_path_exists = ""
        #     while (alternative_file_path_exists.lower() != "y") and (alternative_file_path_exists.lower() != "n"):
        #         alternative_file_path_exists = input(
        #             "Do you wish to provide an alternative file path? (y/n): ")
        #
        #     if alternative_file_path_exists.lower() == "y":
        #         flac_dir = input("Alternative file path: ")
        #     else:
        #         print("Skipping: %s" % flac_dir)
        #         break

        # Perform the transcode
        for format in needed:
            if Path(flac_dir).exists():
                print('Adding format %s...' % format, end=' ')

                with tempfile.TemporaryDirectory() as tmpdir:
                    if len(torrent['remasterTitle']) >= 1:
                        basename = html.unescape(artist) + " - " + html.unescape(group.group['name']) + " (" + html.unescape(
                            torrent['remasterTitle']) + ") " + "(" + year + ") [" + torrent['media'] + " - "
                    else:
                        basename = html.unescape(artist) + " - " + html.unescape(
                            group.group['name']) + " (" + year + ") [" + torrent['media'] + " - "

                    transcode_dir = transcode.transcode_release(
                        flac_dir, output_dir, basename, format, max_threads=args.threads)
                    if transcode_dir is False:
                        print(
                            "Skipping - some file(s) in this release were incorrectly marked as 24bit.")
                        cache.add(torrentid, '24bit')
                        break

                    print("Finished transcoding, creating torrent file")

                    new_torrent = transcode.make_torrent(
                        transcode_dir, tmpdir, api.tracker,
                        api.accountinfo.passkey,
                        config.get('redacted', 'piece_length'))

                    permalink = api.permalink(torrentid)
                    description = create_description(
                        torrent, flac_dir, format, permalink)

                    if not args.no_upload:
                        print('Uploading torrent!')
                        shutil.copy(new_torrent, torrent_dir)
                        response = api.upload(
                            group, torrent, new_torrent, format, description)
                        if response['status'] == 'success':
                            print(
                                f'New torrent uploaded: {api.permalink(response["response"]["torrentid"])}')
                            cache.add(torrentid, 'done')
                        elif response['status'] == 'failure':
                            errorcode = response['error']
                            print(
                                f'An error occured while uploading:\n{errorcode}')
                            cache.add(torrentid, 'no_upload')
                        else:
                            print('Unknown error while uploading')
                            cache.add(torrentid, 'error')
                        # shutil.copy(new_torrent, torrent_dir)
                    else:
                        print('\nTorrent ready for manual upload!')
                        print(f'Flac directory: {flac_dir}')
                        print(f'Transcode directory: {transcode_dir}')
                        print('Files:')
                        for file_name in Path(transcode_dir).glob('**/*'):
                            print(file_name)
                        print('Upload info:')
                        print(f'FLAC URL: {permalink}')
                        print(
                            f'Edition: {year} - {torrent["remasterRecordLabel"]}')
                        print(f'Format: {format}')
                        print('Description:')
                        print(f'{description}\n')
                        shutil.copy(new_torrent, torrent_dir)
                        print("Done! Did you upload it?")
                        response = get_input(['Hit enter to continue'])
                        if response == '':
                            # Actually does not really matter what response
                            # we get, just keep going
                            pass
                    if args.single:
                        break
                    cache.add(torrentid, 'done')

    print(f'Skipped {cache_count} torrents in cache')


if __name__ == "__main__":
    main()
