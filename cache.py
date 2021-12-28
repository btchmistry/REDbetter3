#!/usr/bin/env python3

from pathlib import Path
import jsonpickle


class Cache:
    """ Read cache from file and if not existing, create one
    This needs to be expanded since there are multiple reasons per id possible:
    formats or done
    """

    def __init__(self, cache_path):
        self.ids = {}
        self.cache_path = Path(cache_path)
        self.load()

    # Load cache from file and if not existing, create one
    def load(self):
        if self.cache_path.is_file():
            with open(self.cache_path, 'r') as cache_file:
                cache = jsonpickle.decode(cache_file.read())
                self.ids = {int(key): cache.ids[key] for key in cache.ids}
        else:
            with open(self.cache_path, 'w') as cache_file:
                encoded = jsonpickle.encode(self)
                cache_file.write(encoded)

    # Add item to cache and store cache in file
    def add(self, torrent_id: str, reason: str):
        self.ids[torrent_id] = reason
        with open(str(self.cache_path), 'w') as cache_file:
            encoded = jsonpickle.encode(self)
            cache_file.write(encoded)
