#!/usr/bin/env python3

class Static:
    def __init__(self):
        self.good_audio_formats = ['audio/x-flac', 'audio/mpeg']
        self.questioable_audio_formats = ['audio/x-hx-aac-adts', 'audio/vnd.dolby.dd-raw']
        self.undefinable = ['application/octet-stream']

        self.archive_mimes = ['application/gzip',
                              'application/x-iso9660-image',
                              'application/x-rar',
                              'application/zip',
                              'application/x-tar',
                              'application/x-archive',
                              'application/x-cpio',
                              'application/x-shar',
                              'application/x-sbx',
                              'application/x-bzip2',
                              'application/x-lzip',
                              'application/x-lzma',
                              'application/x-lzop',
                              'application/x-snappy-framed',
                              'application/x-xz',
                              'application/x-compress',
                              'application/x-compress',
                              'application/zstd',
                              'application/x-7z-compressed',
                              'application/x-ace-compressed',
                              'application/x-astrotite-afa',
                              'application/x-alz-compressed',
                              'application/vnd.android.package-archive',
                              'application/octet-stream',
                              'application/x-freearc',
                              'application/x-arj',
                              'application/x-b1',
                              'application/vnd.ms-cab-compressed',
                              'application/x-cfs-compressed',
                              'application/x-dar',
                              'application/x-dgc-compressed',
                              'application/x-apple-diskimage',
                              'application/x-gca-compressed',
                              'application/java-archive',
                              'application/x-lzh',
                              'application/x-lzx',
                              'application/x-rar-compressed',
                              'application/x-stuffit',
                              'application/x-stuffitx',
                              'application/x-gtar',
                              'application/x-ms-wim',
                              'application/x-zoo']

        self.archive_suffixes = ['.rar', '.zip', '.tar', '.gz', '.iso', '.a', '.ar', '.cpio', '.shar', '.lbr', '.mar', '.sbx', '.bz2',
                                 '.lz', '.lz4', '.lzma', '.lzo', '.rz', '.sfark', '.sz', '.xz', '.z', '.zst', '.7z', '.s7z', '.ace', '.afa',
                                 '.alz', '.apk', '.arc', '.ark', '.cdx', '.arj', '.b1', '.b6z', '.ba', '.bh', '.cab', '.car', '.cfs', '.cpt',
                                 '.dar', '.dd', '.dgc', '.dmg', '.ear', '.gca', '.genozip', '.ha', '.hki', '.ice', '.jar', '.kgb', '.lzh',
                                 '.lha', '.lzx', '.pak', '.partimg', '.paq6, .paq7, .paq8', '.pea', '.phar', '.pim', '.pit', '.qda', '.rk',
                                 '.sda', '.sea', '.sen', '.sfx', '.shk', '.sit', '.sitx', '.sqx', '.tar.gz', '.tgz', '.tar.z', '.tar.bz2',
                                 '.tbz2', '.tar.lz', '.tlz.', '.tar.xz', '.txz', '.tar.zst', '.uc', '.uc0', '.uc2', '.ucn', '.ur2', '.ue2',
                                 '.uca', '.uha', '.war', '.wim', '.xar', '.xp3', '.yz1', '.zipx', '.zoo', '.zpaq', '.zz']

        self.video_suffixes = ['.webm', '.mkv', '.flv', '.flv', '.vob', '.ogv', '.ogg', '.drc', '.gif', '.gifv', '.mng', '.avi', '.MTS',
                               '.M2TS', '.TS', '.mov', '.qt', '.wmv', '.yuv', '.rm', '.rmvb', '.viv', '.asf', '.amv', '.mp4', '.m4p',
                               '.m4v', '.mpg', '.mp2', '.mpeg', '.mpe', '.mpv', '.mpg', '.mpeg', '.m2v', '.m4v', '.svi', '.3gp', '.3g2',
                               '.mxf', '.roq', '.nsv', '.flv', '.f4v', '.f4p', '.f4a', '.f4b']

        self.scene_names = ['FLACME', 'GRAVEWISH', '401', 'FiXIE', 'WRE', '6DM', 'BOCKSCAR', 'LoKET', 'PERFECT', 'mwndX', 'MAHOU', 'FATHEAD',
                            'WiSHLiST', 'HOUND', 'oNePiEcE', 'PEGiDA', 'FAiNT', 'MUNDANE', 'KOMA', 'RiBS', 'DARKAUDiO', 'FAWN', 'CRUELTY',
                            'RUiL', 'FREGON', 'FiH', 'CALiFLAC', 'CHS', 'FORSAKEN', 'THEVOiD', 'CEBAD', 'MLS', 'LzY', 'c05', 'YEHNAH', 'OLDSWE',
                            'D2H', 'Mrflac', 'MenInFlac', 'mwnd', 'NBFLAC', 'MUSICSCENEISDEAD', 'RUIDOS', 'MyDad', '86D', 'TOTENKVLT', 'k4',
                            'ERP', 'VOiCE', 'GARLICKNOTS', 'YARD', 'AMOK', 'SCORN', 'TiLLMYDEATH', 'DeVOiD', 'STAX', 'BEATOCUL', 'L4L', 'YUK',
                            'CUSTODES', 'CMC', 'OUTERSPACE', 'FrB', 'FLACON', 'LEB', 'BAB', 'REDFLAC', 'AUDiOFiLE', 'ORDER', 'DDAS_INT',
                            'THEVOiD_INT', 'DDAS', 'OND', 'ESGFLAC', 'NACHOS', 'HUNNiT', 'PTC', 'BABAS', 'EMP', 'TVRf', 'uCFLAC', 'dL', 'LSS',
                            'dh', 'SHGZ', 'EMX', 'KALEVALA', 'MyMom', 'BITOCUL', 'PSYMiND', 'FADED', 'JLM', 'RAGEFLAC', '2Eleven', 'L0sS',
                            'PiLONE', 'ESGFLAC_INT', 'LiTF', 'WRS', 'OAG', 'CORONAVIRUS', '20', 'VOLDiES', 'TALiON', 'BOTT', 'RLG', 'VhV',
                            'GWI', 'OBSERVER', 'ZgbK', 'CB', 'FWYH', 'BLuBB', 'EMG', '420', 'hbZ', 'SPANK', 'MAJiKNiNJAZ', 'GrOpE', 'NLs',
                            'FiXiE', '0MNi', 'JUST', 'TaBoo', 'KFB', '201', 'CT', 'HQFLAC', 'BTTR', 'ATX', 'UGS', 'FLA', 'EOS', 'DJM', 'ZABRA',
                            'JAZZflac', 'ITSp2PEE', 'mbs', 'WTFLAC', 'EiTheL', 'BUDDHA', 'Gully', 'FRAY', '199', 'PZH', 'POWDER', 'SCF', 'JRO',
                            'HUE', '2006', 'SPL', 'QdM', 'UQ', 'FOX']

        self.characters = ['.', ',', '?', '!', '/', '\\', '-', '_', ':', '~', ' ', '[', ']', '{', '}', '(', ')',
                           '│', '|', '"', '&', '@', '+', 'ー', '！', '・', '～', ';', '…', '—', '*', '∕', '〜', '•']

        pass
