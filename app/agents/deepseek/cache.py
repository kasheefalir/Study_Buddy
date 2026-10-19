"""Small, exact-query cache of source reads, never generated answers or intent."""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
import time

from app.config import settings


class ReadCache:
    def __init__(self, capacity=32, ttl=300):
        self.entries = OrderedDict()
        self.capacity = capacity
        self.ttl = ttl
        self.hits = 0

    def key(self, root, item, chunks, read):
        index = root / item["id"] / "embeddings.json"
        stamp = index.stat().st_mtime_ns if index.exists() else None
        content = json.dumps([str(root.resolve()), item, chunks, read.model_dump(),
                              settings.embedding_model, stamp], sort_keys=True).encode()
        return hashlib.sha256(content).hexdigest()

    def get(self, key):
        entry = self.entries.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry[0] > self.ttl:
            del self.entries[key]
            return None
        self.hits += 1
        self.entries.move_to_end(key)
        return deepcopy(entry[1])

    def put(self, key, sources):
        self.entries[key] = (time.monotonic(), deepcopy(sources))
        self.entries.move_to_end(key)
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)
