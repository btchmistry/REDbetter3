#!/usr/bin/env python3

___name__ = "utils"

import re
from pathlib import Path
import html.parser

import discogs_client


class Utilities:
    def __init__(self):
        pass

    # utilities
    # test a lists of paths which matches up to the correct data_dir
    def get_correct_datadir(self, data_dir: list, file_path: str, file: str):
        for path in data_dir:
            check_path = Path(path, file_path, file)
            if check_path.is_file():
                return path
        return ''

    # Filter out discogs url from arbitrary text
    def get_discogs_url(self, text: str):
        # https://www.discogs.com/Eminem-Slim-Shady-Music-To-Be-Murdered-By/release/15929508
        url = re.search(r"\"?(?P<url>https?://www\.discogs[^\s'\"\[]+)", text).group("url")
        if 'release' in url:
            release_id = re.search(r"(?P<release>release/[0-9]+)", url).group("release").strip('release/')
        else:
            release_id = None

        return (url, release_id)

    # Download release information from discogs using release_id
    def get_discogs_releaseinfo(self, discogs_release_id, discogs_user_token):
        d = discogs_client.Client('MusicUpdater/0.1', user_token=discogs_user_token)
        return d.release(discogs_release_id)

    # Split the filelist in torrent and retrieve as a list of [filename, filesize] lists
    def split_filelist(self, file_list: str):
        filelist = []
        for file in html.unescape(file_list).split("|||"):
            filename, file_size = file.strip("}}}").split("{{{")
            file_size_int = int(file_size)
            filelist.append([filename, file_size_int])
        return filelist

    # Convert bytes to KB, MB, GB or TB, return round number
    def prettify_bytes(self, bytes: int):
        bytes_pretty = str(bytes)
        if bytes >= 1024 ** 4:
            return f'{round(bytes/(1024 ** 4))} TB'
        elif bytes >= 1024 ** 3:
            return f'{round(bytes/(1024 ** 3))} GB'
        elif bytes >= 1024 ** 2:
            return f'{round(bytes/(1024 ** 2))} MB'
        elif bytes >= 1024:
            return f'{round(bytes/1024)} KB'
        else:
            return bytes_pretty
