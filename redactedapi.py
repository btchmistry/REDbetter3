#!/usr/bin/env python3

import re
import json
import time
import requests
from utils import Utilities
from static import Static
import logging

# for later use: categories = {1: 'Music', 2: 'Applications', 3: 'E-Books',
# 4: 'Audiobooks', 5: 'E-Learning Videos', 6: 'Comedy', 7: 'Comics'}

ut = Utilities()
st = Static()
logger = logging.getLogger(__name__)


# TODO: Delete this function, it only refers to 1 torrent on RED
def allowed_transcodes(torrent):
    """Some torrent types have transcoding restrictions."""
    preemphasis = re.search(
        r"""pre[- ]?emphasi(s(ed)?|zed)""", torrent['remasterTitle'], flags=re.IGNORECASE)
    if preemphasis:
        return []
    else:
        return list(st.formats.keys())


class LoginException(Exception):
    pass


class RequestException(Exception):
    pass


class RedactedAPI:
    def __init__(self, page_size, api_key, sparse=False):
        self.session = requests.Session()
        self.headers = {
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'User-Agent': 'REDBetter3',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'en-US,en;q=0.8',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
            'Authorization': f'{api_key}'}
        self.session.headers.update(self.headers)
        self.page_size = page_size
        self.api_key_authenticated = False
        self.tracker = "https://flacsfor.me/"
        self.last_request = time.time()
        self.rate_limit = 1.0  # seconds between requests
        self.mainpage = "https://redacted.ch/"
        self.accountinfo = None
        self.sparse = sparse
        self._test_session()

    # using only api login method, other methods not needed
    def _test_session(self):
        try:
            # self._get_account_info()
            response = self.request('index')
            if response is not None:
                self.accountinfo = AJAXtoObj(**response)
            else:
                raise LoginException
            self.api_key_authenticated = True
            logger.info(f"Initializing with api key succes, username: {self.accountinfo.username}")
        except LoginException:
            logger.error('Accessing with api key failed, check if key is in config or server is down')
            pass

    def _get_account_info(self):
        response = self.request('index')
        if response is not None:
            self.accountinfo = AJAXtoObj(**response)
        else:
            raise LoginException

    def request(self, action, passthrough=False, **kwargs):
        '''Makes an AJAX request at a given action page'''
        while time.time() - self.last_request < self.rate_limit:
            time.sleep(0.1)

        ajaxpage = f'{self.mainpage}ajax.php'
        params = {'action': action}
        params.update(kwargs)
        r = self.session.get(ajaxpage, params=params, allow_redirects=False)
        self.last_request = time.time()
        if passthrough:
            return r.content
        try:
            parsed = json.loads(r.content)
            if parsed['status'] != 'success':
                return None
            else:
                return parsed['response']
        except ValueError as e:
            raise RequestException(e)

    # def get_artist(self, id=None, format='MP3', best_seeded=True):
    #     res = self.request('artist', id=id)
    #     torrentgroups = res['torrentgroup']
    #     keep_releases = []
    #     for release in torrentgroups:
    #         torrents = release['torrent']
    #         best_torrent = torrents[0]
    #         keeptorrents = []
    #         for t in torrents:
    #             if t['format'] == format:
    #                 if best_seeded:
    #                     if t['seeders'] > best_torrent['seeders']:
    #                         keeptorrents = [t]
    #                         best_torrent = t
    #                 else:
    #                     keeptorrents.append(t)
    #         release['torrent'] = list(keeptorrents)
    #         if len(release['torrent']):
    #             keep_releases.append(release)
    #     res['torrentgroup'] = keep_releases
    #     return res

    # def save_torrent_file(self, torrent_id: int, file_path: Path):
    #     if not self.api_key_authenticated:
    #         raise LoginException('Must have API key authentication to save'
    #                              'torrent files')
    #     torrent_file = self.request(
    #         'download', passthrough=True, id=torrent_id)
    #     with open(str(file_path), 'wb') as file:
    #         file.write(torrent_file)

    def get_snatched(self):
        if self.api_key_authenticated:
            page = 0
            while True:
                torrents = usertorrents(**self.request(
                    'user_torrents',
                    id=self.accountinfo.id,
                    type='snatched',
                    limit=self.page_size,
                    offset=page * self.page_size))
                if len(torrents.snatched) == 0:
                    break
                for item in torrents.snatched:
                    yield int(item['groupId']), int(item['torrentId'])
                page += 1
        else:
            logger.info("Not authenticated")
            return None

    def get_seeding(self):
        if self.api_key_authenticated:
            page = 0
            while True:
                torrents = usertorrents(**self.request(
                    'user_torrents',
                    id=self.accountinfo.id,
                    type='seeding',
                    limit=self.page_size,
                    offset=page * self.page_size))
                if len(torrents.seeding) == 0:
                    break
                for item in torrents.seeding:
                    yield int(item['groupId']), int(item['torrentId'])
                page += 1
        else:
            logger.info("Not authenticated")
            return None

    # def get_torrentgroup(self, groupid):
    #     if self.api_key_authenticated:
    #         tgroup = torrentgroup(**self.request('torrentgroup', id=groupid))
    #         if tgroup is not None:
    #             return tgroup
    #     else:
    #         print("Not authenticated")
    #         return None

    def get_api_torrentgroup(self, groupid):
        if self.api_key_authenticated:
            response = self.request('torrentgroup', id=groupid)
            if response and 'group' in response:
                tgroup = apiTorrentGroup(**response['group'])
                for torrent in response['torrents']:
                    tgroup.torrents.append(apiTorrent(**torrent))
                return tgroup
        else:
            logger.info("Not authenticated")
            return None

    def release_url(self, groupid, torrentid):
        return f"{self.mainpage}torrents.php?id=%s&torrentid=%s#torrent%s" % (groupid, torrentid, torrentid)

    def permalink(self, torrentid):
        return f"{self.mainpage}torrents.php?torrentid={torrentid}"

    # TODO:     # Outdated and needs to be rewritten to api key auth
    def get_better(self, search_type=3, tags=None):
        if tags is None:
            tags = []
        data = self.request('better', method='transcode',
                            type=search_type, search=' '.join(tags))
        out = []
        for row in data:
            out.append({
                'permalink': 'torrents.php?id={}'.format(row['torrentId']),
                'id': row['torrentId'],
                'torrent': row['downloadUrl'],
            })
        return out

    def get_torrent(self, torrent_id, usetoken=False):
        # URL:ajax.php?action=download
        # Arguments
        # id - TorrentID to download.
        # usetoken (optional) - Default: 0. Set to 1 to spend a FL token.
        # Will if fail a token cannot be spent on this torrent for any reason.
        '''Downloads the torrent at torrent_id'''
        while time.time() - self.last_request < self.rate_limit:
            time.sleep(0.1)

        ajaxpage = f'{self.mainpage}ajax.php'
        if usetoken:
            params = {'action': 'download', 'id': torrent_id, 'usetoken': 1}
        else:
            params = {'action': 'download', 'id': torrent_id}
        r = self.session.get(ajaxpage, params=params,
                             allow_redirects=False)

        self.last_request = time.time() + 2.0
        if r.status_code == 200 and 'application/x-bittorrent' in r.headers['content-type']:
            return r.content
        return None

    def get_torrent_info(self, id):
        return self.request('torrent', id=id)['torrent']

    def get_requests_historical(self, start_page=0, end_page=1):
        """
        https://redacted.ch/requests.php?order=bounty&sort=desc&submit=true&search=&tags=&tags_type=1&showall=on&releases%5B0%5D=1
        &releases%5B1%5D=3&releases%5B2%5D=5&releases%5B3%5D=6&releases%5B4%5D=7&releases%5B5%5D=9&releases%5B6%5D=11&releases%5B7%5D=13
        &releases%5B8%5D=14&releases%5B9%5D=15&releases%5B10%5D=16&releases%5B11%5D=17&releases%5B12%5D=18&releases%5B13%5D=19&releases%5B14%5D=21
        &formats%5B0%5D=0&formats%5B1%5D=1&formats%5B2%5D=2&formats%5B3%5D=3&formats%5B4%5D=4&bitrates%5B0%5D=0&bitrates%5B1%5D=1&bitrates%5B2%5D=
        &bitrates%5B3%5D=3&bitrates%5B4%5D=4&bitrates%5B5%5D=5&bitrates%5B6%5D=6&bitrates%5B7%5D=7&bitrates%5B8%5D=8
        &bitrates%5B9%5D=9&bitrates%5B10%5D=10&media_strict=on&media%5B0%5D=0
        """
        def quickndirty_request(page):
            while time.time() - self.last_request < self.rate_limit:
                time.sleep(0.1)

            ajaxpage = f'{self.mainpage}ajax.php'
            params = {'action': 'requests',
                      'page': page,
                      'order': 'bounty',
                      'sort': 'desc',
                      'submit': 'true',
                      'showall': 'on',
                      'media_strict': 'on',
                      'media[0]': 0,
                      'filter_cat[1]': 1
                      }

            r = self.session.get(ajaxpage, params=params,
                                 allow_redirects=False)
            self.last_request = time.time()
            try:
                parsed = json.loads(r.content)
                if parsed['status'] != 'success':
                    return None
                else:
                    return parsed['response']
            except ValueError as e:
                raise RequestException(e)

        if self.api_key_authenticated:
            page = start_page
            # if not self.sparse:
            #     print("Retrieving requests")
            while True:
                if page > end_page:
                    break
                if not self.sparse:
                    logger.info(f'Requesting page {page}')
                requests = AJAXtoObj(**quickndirty_request(page))
                if len(requests.results) == 0:
                    logger.info("requests.results = 0")
                    break
                for item in requests.results:
                    yield item
                page += 1
        else:
            logger.info("Not authenticated")
            return None

    def get_requests(self, start_page=0, end_page=1):
        """    Requests Search
        URL:ajax.php?action=requests&search=<term>&page=<page>&tag=<tags>
        Arguments:
        search - search term
        page - page to display (default: 1)
        tag - tags to search by (comma separated)
        tags_type - 0 for any, 1 for match all
        show_filled - Include filled requests in results - true or false (default: false).
        filter_cat[], releases[], bitrates[], formats[], media[] - as used on requests.php
        If no arguments are specified then the most recent requests are shown.
        Response format:
            {
                "status": "success",
                "response": {
                    "currentPage": 1,
                    "pages": 1,
                    "results": [
                        {
                            "requestId": 185971,
                            "requestorId": 498,
                            "requestorName": "Satan",
                            "timeAdded": "2012-05-06 15:43:17",
                            "lastVote": "2012-06-10 20:36:46",
                            "voteCount": 3,
                            "bounty": 245366784,
                            "categoryId": 1,
                            "categoryName": "Music",
                            "artists": [
                                [
                                    {
                                        "id": "1460",
                                        "name": "Logistics"
                                    }
                                ],
                                [
                                    {
                                        "id": "25351",
                                        "name": "Alice Smith"
                                    },
                                    {
                                        "id": "44545",
                                        "name": "Nightshade"
                                    },
                                    {
                                        "id": "249446",
                                        "name": "Sarah Callander"
                                    }
                                ]
                            ],
                            "title": "Fear Not",
                            "year": 2012,
                            "image": "http://whatimg.com/i/ralpc.jpg",
                            "description": "Thank you kindly.",
                            "catalogueNumber": "",
                            "releaseType": "",
                            "bitrateList": "1",
                            "formatList": "Lossless",
                            "mediaList": "FLAC",
                            "logCue": "CD",
                            "isFilled": false,
                            "fillerId": 0,
                            "fillerName": "",
                            "torrentId": 0,
                            "timeFilled": ""
                        },
                        // ...
                    ]
                }
            }
            # URL:ajax.php?action=requests&search=<term>&page=<page>&tag=<tags>
            # Arguments:
            # search - search term
            # page - page to display (default: 1)
            # tag - tags to search by (comma separated)
            # tags_type - 0 for any, 1 for match all
            # show_filled - Include filled requests in results - true or false (default: false).
            # filter_cat[], releases[], bitrates[], formats[], media[] - as used on requests.php
            # If no arguments are specified then the most recent requests are shown.
            """

        if self.api_key_authenticated:
            page = start_page
            if not self.sparse:
                logger.info("Retrieving requests")
            while True:
                if page >= end_page:
                    break
                requests = AJAXtoObj(**self.request(
                    'requests', page=page))
                if len(requests.results) == 0:
                    logger.info("requests.results = 0")
                    break
                for item in requests.results:
                    yield item
                page += 1
        else:
            logger.info("Not authenticated")
            return None

    def upload(self, group, torrent, new_torrent, format, description):
        """
        Upload Torrent

        This endpoint is restricted to API Key Authentication
        URL:ajax.php?action=upload
        This endpoint expects a POST method

        Arguments
    x    file_input - (file) .torrent file contents
    x    type - (int) index of category (Music, Audiobook, ...)
    x    artists[] - (str)
    x    importance[] - (int) index of artist type (Main, Guest, Composer, ...)
    x    title - (str) Album title
    x    year - (int) Album "Initial Year"
        releasetype - (int) index of release type (Album, Soundtrack, EP, ...)
        unknown - (bool) Unknown Release
    x    remaster_year - (int) Edition year
    x    remaster_title - (str) Edition title
    x    remaster_record_label - (str) Edition record label
    x    remaster_catalogue_number - (str) Edition catalog number
        scene - (bool) is this a scene release?
    x    format - (str) MP3, FLAC, etc
    x    bitrate - (str) 192, Lossless, Other, etc
        other_bitrate - (str) bitrate if Other
        vbr - (bool) other_bitrate is VBR
        logfiles[] - (files) ripping log files
        extra_file_#
        extra_format[]
        extra_bitrate[]
        extra_release_desc[]
        vanity_house - (bool) is this a Vanity House release?
        media - (str) CD, DVD, Vinyl, etc
    x    tags - (str)
        image - (str) link to album art
        album_desc - (str) Album description
    x    release_desc - (str) Release (torrent) description
        desc - (str) Description for non-music torrents
    x    groupid - (int) torrent groupID (ie album) this belongs to
        requestid - (int) requestID being filled

        Response format:

        {'status': 'success',
         'response': {'private': ,
        'source': ,
        'requestid': ,
        'torrentid': ,
        'groupid':
        }
        }
        "remasterYear": 0,
        "remasterTitle": "",
        "remasterRecordLabel": "",
        "remasterCatalogueNumber": "",
        """

        if 'V0' in format:
            format_type = 'MP3'
            bitrate = 'V0 (VBR)'
            vbr = 'true'
        elif '320' in format:
            format_type = 'MP3'
            bitrate = '320'
            vbr = 'false'
        elif 'FLAC' in format:
            format_type = 'FLAC'
            bitrate = 'Lossless'
            vbr = 'false'

        files = {"file_input": open(new_torrent, 'rb')}
        params = {'action': 'upload',
                  'type': 0,
                  'artists[]': group.musicInfo['artists'][0]['name'],
                  'importance[]': 1,
                  'title': group.name,
                  'tags': group.tags[0],
                  'remaster_year': torrent.remasterYear,
                  'remaster_title': torrent.remasterTitle,
                  'remaster_record_label': torrent.remasterRecordLabel,
                  'remaster_catalogue_number': torrent.remasterCatalogueNumber,
                  'format': format_type,
                  'bitrate': bitrate,
                  'media': torrent.media,
                  'release_desc': description,
                  'groupid': group.id}

        # Upload torrent using api key
        while time.time() - self.last_request < self.rate_limit:
            time.sleep(0.1)

        ajaxpage = f'{self.mainpage}ajax.php?action=upload'

        r = self.session.post(ajaxpage, files=files, data=params)
        self.last_request = time.time()
        try:
            parsed = json.loads(r.content)
            if parsed['status']:
                return parsed
                # Fail:
                # (b'{"status":"failure","error":"You must enter the other bitrate (max length: 9'
                # b' characters)."}')
                # Succes:
                # (b'{"status":"success","response":{"private":true,"source":true,"requestid":nul'
                #  b'l,"torrentid":3084789,"groupid":1444084}}')

        except ValueError as e:
            raise RequestException(e)

    def get_notifications(self, start_page=0, end_page=1):
        # ajax.php?action=notifications&page=<Page>
        if self.api_key_authenticated:
            page = start_page
            if not self.sparse:
                logger.info("Retrieving notifications")
            while True:
                if page >= end_page:
                    break
                requests = AJAXtoObj(**self.request(
                    'notifications', page=page))
                if len(requests.results) == 0:
                    logger.info("requests.results = 0")
                    break
                for item in requests.results:
                    yield item
                page += 1
        else:
            logger.info("Not authenticated")
            return None


class AJAXtoObj:
    def __init__(self, **entries):
        self.__dict__.update(entries)


class REDuserprofile:
    def __init__(self, id, **entries):
        self.id = id
        self.__dict__.update(entries)


class usertorrents:
    def __init__(self, **entries):
        self.__dict__.update(entries)


class apiTorrent():
    def __init__(self, **entries):
        self.description = None
        self.encoding = None
        self.fileCount = None
        self.fileList = []
        self.filePath = None
        self.format = None
        self.freeTorrent = None
        self.hasCue = None
        self.hasLog = None
        self.has_snatched = None
        self.id = None
        self.leechers = None
        self.logScore = None
        self.lossyMasterApproved = None
        self.lossyWebApproved = None
        self.media = None
        self.remasterCatalogueNumber = None
        self.remasterRecordLabel = None
        self.remasterTitle = None
        self.remasterYear = None
        self.remastered = None
        self.reported = None
        self.scene = None
        self.seeders = None
        self.size = None
        self.snatched = None
        self.time = None
        self.trumpable = None
        self.userId = None
        self.username = None
        self.__dict__.update(entries)
        if self.fileList:
            self.fileList = ut.split_filelist(self.fileList)


class apiTorrentGroup():
    def __init__(self, **entries):
        self.wikiBody = None
        self.bbBody = None
        self.wikiImage = None
        self.id = None
        self.name = None
        self.year = None
        self.recordLabel = None
        self.catalogueNumber = None
        self.releaseType = None
        self.categoryId = None
        self.categoryName = None
        self.time = None
        self.collages = []
        self.personalCollages = []
        self.numComments = None
        self.vanityHouse = None
        self.isBookmarked = None
        self.musicInfo = {'composers': [],
                          'dj': [],
                          'artists': [],
                          'with': [],
                          'conductor': [],
                          'remixedBy': [],
                          'producer': []}
        self.tags = []
        self.torrents = []
        self.__dict__.update(entries)
