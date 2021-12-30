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
import logging

import tagging
import transcode
from redactedapi import RedactedAPI, apiTorrent, apiTorrentGroup
from cache import Cache
from static import Static

st = Static()

logger = logging.getLogger()


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


def formats_needed(group: apiTorrentGroup, torrent: apiTorrent, wanted_formats: dict):
    # compare all torrents in torrent_group and return true if media, year, title, recordlabel and catalogueNumber are same
    def same_group(t): return t.media == torrent.media and\
        t.remasterYear == torrent.remasterYear and\
        t.remasterTitle == torrent.remasterTitle and\
        t.remasterRecordLabel == torrent.remasterRecordLabel and\
        t.remasterCatalogueNumber == torrent.remasterCatalogueNumber

    # Find other torrents that belong to the same group
    others = list(filter(same_group, group.torrents))
    # Create a set of formats and encodings from exisiting torrents
    current_formats = set((t.format, t.encoding) for t in others)
    missing_formats = []
    # Create a list of missing formats
    for format, details in [(f, st.formats[f]) for f in wanted_formats]:
        if (details['format'], details['encoding']) not in current_formats:
            missing_formats.append(format)
    return missing_formats


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
    logger.info(f'Spectrograms written to {spectrogram_dir}. Are they acceptable?')
    response = get_input(['y', 'n'])
    if response == 'n':
        logger.info('Spectrograms rejected. Skipping.')
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
        config.set('redacted', 'data_dirs', '')
        config.set('redacted', 'output_dir', '')
        config.set('redacted', 'torrent_dir', '')
        config.set('redacted', 'spectral_dir', '')
        config.set('redacted', 'formats', 'flac, v0, 320')
        config.set('redacted', 'media', ', '.join(st.lossless_media))
        config.set('redacted', '24bit_behaviour', 'yes')
        config.set('redacted', 'piece_length', '18')
        with open(config_path, 'w') as config_file:
            config.write(config_file)
        logger.error(f'No config file found. Please edit the blank one created at {config_path}')
        return None
    else:
        try:
            config.read(config_path)
        except Exception as e:
            logger.error(f'Error reading config file from {config_path}')
            raise e
        return config


def main():
    # Processing command line arguments:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('release_urls', nargs='*', help='the URL where the release is located')
    parser.add_argument('-s', '--single', action='store_true', help='only add one format per release (useful for getting unique groups)')
    parser.add_argument('-j', '--threads', type=int, help='number of threads to use when transcoding', default=max(cpu_count() - 1, 1))
    parser.add_argument('--config', help='the location of the configuration file', default=Path('~/.redactedbetter/config').expanduser())
    parser.add_argument('--cache', help='the location of the cache', default=Path('~/.redactedbetter/cache').expanduser())
    parser.add_argument('-p', '--page-size', type=int, help='Number of snatched results to fetch at once', default=500)
    parser.add_argument('-f', '--force-format', default=None,  help='Force any of these formats: ''FLAC'', ''V0'', ''320''')
    parser.add_argument('--skip-missing', action='store_true', default=False, help='Skip snatches that have missing data directories')
    parser.add_argument('-r', '--retry', nargs='*', default=[], help='Retries certain classes of previous exit statuses')
    parser.add_argument('--skip-spectral', action='store_true', default=False, help='Skips spectrograph verification')
    parser.add_argument('--skip-hashcheck', action='store_true', default=False, help='Skip source file integrity verification')
    parser.add_argument('--no-upload', action='store_true', default=False, help='don\'t upload new torrents (in case you want to do it manually)')
    parser.add_argument('-l', '--loglevel', default='INFO', help='Loglevel, options are: NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL')

    args = parser.parse_args()

    # loading configuration from config file, or create one at first pass
    config = parse_config(Path(args.config))
    if config is None:
        sys.exit(2)

    logging.basicConfig(level=args.loglevel.upper())
    logger = logging.getLogger(__name__)

    api_key = config.get('redacted', 'api_key', fallback=None)

    data_dirs = config.get('redacted', 'data_dirs').split(', ')

    output_dir = Path(config.get('redacted', 'output_dir')).expanduser()
    torrent_dir = Path(config.get('redacted', 'torrent_dir')).expanduser()
    wanted_formats = [format.strip().upper() for format in config.get('redacted', 'formats').split(',')]

    do_24_bit = config.get('redacted', '24bit_behaviour')

    api = RedactedAPI(args.page_size, api_key,)

    cache = Cache(args.cache)

    logger.info('Searching for transcode candidates...')
    if args.release_urls:
        logger.info('You supplied one or more release URLs, ignoring your configuration\'s media types.')
        candidates = [(int(query['id']), int(query['torrentid'])) for query in
                      [dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query)) for url in args.release_urls]]
    else:
        candidates = api.get_seeding()

    # TODO: remove or fix retry modes, its broken now
    retry_modes = set(args.retry)
    logger.debug(retry_modes)

    # Main loop that does all the transcoding, etc.
    cache_count = 0
    for groupid, torrentid in candidates:
        logger.debug(torrentid)
        # Test if torrent is in cache to reduce calls to server
        if torrentid in cache.ids and not args.force_format:
            retry = False
            if cache.ids[torrentid] in retry_modes:
                retry = True
            if not retry:
                logger.debug(f'Torrent ID {torrentid} present in cache. Skipping.')
                cache_count += 1
                continue

        torrent_group = api.get_api_torrentgroup(groupid)

        for torrent in torrent_group.torrents:
            if torrent.id == torrentid:
                api_torrent = torrent
        logger.debug(f'{torrentid} type: {type(torrentid)} {api_torrent.id} type: {type(api_torrent.id)}')

        # Test if torrent is flac
        if "FLAC" not in api_torrent.format and "Lossless" not in api_torrent.encoding:
            logger.info(f"Torrent {api.permalink(torrentid)} is not in flac format, transcode not possible")
            cache.add(torrentid, 'no flac')
            continue

        # Check for scene release: must be manually descened, so not supported
        if api_torrent.scene:
            logger.info(f"Torrent {api.permalink(torrentid)} is a scene release, must be manually descened")
            cache.add(torrentid, 'scene')
            continue

        # Check if torrent is trumpable, if so, it can only be uploaded if it is put in manually
        if api_torrent.trumpable and not args.release_urls:
            logger.info(f"Torrent {api.permalink(torrentid)} torrent is marked as trumpable, this will only be transcoded if added manually")
            cache.add(torrentid, 'trumpable')
            continue

        # Create infoblock
        artist = ""
        if len(torrent_group.musicInfo['artists']) > 1:
            artist = "Various Artists"
        else:
            artist = torrent_group.musicInfo['artists'][0]['name']

        year = str(api_torrent.remasterYear)
        if year == "0":
            year = str(torrent_group.year)

        releaseartist = f'Release artist(s): {html.unescape(artist)}'
        releasename = f'Release name     : {html.unescape(torrent_group.name)}'
        releaseyear = f'Release year     : {year}'
        releaseurl = f'Release URL      : {api.release_url(torrent_group.id, api_torrent.id)}'

        logger.info(border_msg(releaseartist
                               + "\n" + releasename
                               + "\n" + releaseyear
                               + "\n" + releaseurl))

        # Test if torrent is in it's own folder, if not, create one
        if not api_torrent.filePath:
            file_name = html.unescape(api_torrent.fileList)[0][0]
            # find correct data_dir
            data_dir = ''
            for path in data_dirs:
                flac_file = Path(path, file_name)
                if flac_file.exists():
                    data_dir = path
            if data_dir == '':
                logger.info(f"Path not found - skipping: {file_name}")
                continue
            # Flac folder name convention: Release Name (year) [FLAC]
            flac_dir = Path(data_dir, f'{html.unescape(torrent_group.name)} ({torrent_group.year}) [FLAC]')
            if not flac_dir.exists():
                flac_dir.mkdir()
            shutil.copy(flac_file, flac_dir)
        else:
            file_name = html.unescape(api_torrent.fileList)[0][0]
            data_dir = ''
            # find correct data_dir
            for path in data_dirs:
                flac_file = Path(path, html.unescape(api_torrent.filePath), file_name)
                if flac_file.exists():
                    data_dir = path
            if data_dir == '':
                logger.info(f'Path not found - skipping: {file_name}')
                continue
            flac_dir = Path(data_dir, html.unescape(api_torrent.filePath))

        # TODO: correct 24bit behaviour, its broken now
        if do_24_bit == 'yes':
            try:
                if transcode.is_24bit(flac_dir) and torrent['encoding'] != '24bit Lossless':
                    # A lot of people are uploading FLACs from Bandcamp without realizing
                    # that they're actually 24 bit files (usually 24/44.1). Since we know for
                    # sure whether the files are 24 bit, we might as well correct the listing
                    # on the site (and get an extra upload in the process).

                    # TODO: check 24 bit behaviour
                    if args.no_24bit_edit:
                        logger.info("Release is actually 24-bit lossless, skipping.")
                        continue
                    if do_24_bit == 'yes':
                        confirmation = input(
                            "Mark release as 24bit lossless? y/n: ")
                        if confirmation != 'y':
                            continue
                    logger.info("Marking release as 24bit lossless.")
                    api.set_24bit(torrent)
                    # group = api.request('torrentgroup', id=groupid)
                    # torrent = [t for t in group['torrents']
                    #            if t['id'] == torrentid][0]
                    continue
            except Exception as e:
                logger.error(f'Can\'t edit 24-bit torrent - skipping: {e}')
                continue

        if transcode.is_multichannel(flac_dir):
            logger.info("This is a multichannel release, which is unsupported - skipping")
            continue

        if args.force_format is not None:
            needed = [args.force_format]  # manually declare which formats
        else:
            # needed = formats_needed(group, torrent, supported_formats)
            needed = formats_needed(torrent_group, api_torrent, wanted_formats)

        if len(needed) < 1:
            logger.info("No transcode needed")
            cache.add(torrentid, 'done')
            continue
        else:
            logger.info(f'Formats needed: {", ".join(needed)}')

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
                    logger.info(f'A FLAC file in this release has unacceptable tags - skipping: {msg}'
                                f'You might be able to trump it.')
                    broken_tags = True
                    break
            if broken_tags:
                continue

        for format in needed:
            if Path(flac_dir).exists():
                logger.info(f'Adding format {format}')

                with tempfile.TemporaryDirectory() as tmpdir:
                    if len(api_torrent.remasterTitle) >= 1:
                        basename = html.unescape(artist) + " - " + html.unescape(torrent_group.name) + " (" + html.unescape(
                            api_torrent.remasterTitle) + ") " + "(" + year + ") [" + api_torrent.media + " - "
                    else:
                        basename = html.unescape(artist) + " - " + html.unescape(torrent_group.name) + " (" + year + ") [" + api_torrent.media + " - "

                    transcode_dir = transcode.transcode_release(
                        flac_dir, output_dir, basename, format, max_threads=args.threads)
                    if transcode_dir is False:
                        logger.info('Skipping - some file(s) in this release were incorrectly marked as 24bit.')
                        cache.add(torrentid, '24bit')
                        break

                    logger.info("Finished transcoding, creating torrent file")

                    new_torrent = transcode.make_torrent(
                        transcode_dir, tmpdir, api.tracker,
                        api.accountinfo.passkey,
                        config.get('redacted', 'piece_length'))

                    permalink = api.permalink(torrentid)
                    description = create_description(
                        api_torrent, flac_dir, format, permalink)

                    if not args.no_upload:
                        logger.info('Uploading torrent!')
                        shutil.copy(new_torrent, torrent_dir)
                        response = api.upload(torrent_group, api_torrent, new_torrent, format, description)
                        if response['status'] == 'success':
                            logger.info(f'New torrent uploaded: {api.permalink(response["response"]["torrentid"])}')
                            cache.add(torrentid, 'done')
                        elif response['status'] == 'failure':
                            errorcode = response['error']
                            logger.error(f'An error occured while uploading:\n{errorcode}')
                            cache.add(torrentid, 'no_upload')
                        else:
                            logger.error('Unknown error while uploading')
                            cache.add(torrentid, 'error')
                        # shutil.copy(new_torrent, torrent_dir)
                    else:
                        logger.info('\nTorrent ready for manual upload!')
                        logger.info(f'Flac directory: {flac_dir}')
                        logger.info(f'Transcode directory: {transcode_dir}')
                        logger.info('Files:')
                        for file_name in Path(transcode_dir).glob('**/*'):
                            logger.info(file_name)
                        logger.info('Upload info:')
                        logger.info(f'FLAC URL: {permalink}')
                        logger.info(f'Edition: {year} - {torrent["remasterRecordLabel"]}')
                        logger.info(f'Format: {format}')
                        logger.info('Description:')
                        logger.info(f'{description}\n')
                        shutil.copy(new_torrent, torrent_dir)
                        logger.info("Done! Did you upload it?")
                        response = get_input(['Hit enter to continue'])
                        if response == '':
                            # Actually does not really matter what response
                            # we get, just keep going
                            pass
                    if args.single:
                        break
                    cache.add(torrentid, 'done')

    logger.info(f'Skipped {cache_count} torrents in cache')


if __name__ == "__main__":
    main()
