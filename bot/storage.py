import os
import json
import logging
from typing import List, Set

logger = logging.getLogger(__name__)

class Storage:
    def __init__(self, filepath: str = "data/storage.json"):
        self.filepath = filepath
        self.completed_notified: Set[str] = set()  # Set of torrent hashes or IDs that we already notified
        self.recent_dirs: List[str] = []           # List of recently used download directories
        self.load()

    def _ensure_dir(self):
        dirname = os.path.dirname(self.filepath)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)

    def load(self):
        self._ensure_dir()
        if not os.path.exists(self.filepath):
            self.save()
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.completed_notified = set(data.get("completed_notified", []))
                self.recent_dirs = data.get("recent_dirs", [])
        except Exception as e:
            logger.error(f"Error loading storage: {e}. Starting fresh.")
            self.completed_notified = set()
            self.recent_dirs = []

    def save(self):
        self._ensure_dir()
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({
                    "completed_notified": list(self.completed_notified),
                    "recent_dirs": self.recent_dirs
                }, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving storage: {e}")

    def add_completed_torrent(self, torrent_hash: str):
        if torrent_hash not in self.completed_notified:
            self.completed_notified.add(torrent_hash)
            self.save()

    def is_torrent_completed_notified(self, torrent_hash: str) -> bool:
        return torrent_hash in self.completed_notified

    def add_recent_dir(self, directory: str):
        if not directory:
            return
        # Remove if already exists to move it to the front (most recent)
        if directory in self.recent_dirs:
            self.recent_dirs.remove(directory)
        self.recent_dirs.insert(0, directory)
        # Limit to last 5 directories
        self.recent_dirs = self.recent_dirs[:5]
        self.save()

    def get_recent_dirs(self) -> List[str]:
        return self.recent_dirs
