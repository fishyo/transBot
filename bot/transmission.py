import transmission_rpc
import logging
from typing import List, Optional, Union
import bot.config as config

logger = logging.getLogger(__name__)

class TransmissionWrapper:
    def __init__(self):
        self.host = config.TRANSMISSION_HOST
        self.port = config.TRANSMISSION_PORT
        self.username = config.TRANSMISSION_USER
        self.password = config.TRANSMISSION_PASSWORD
        self.path = config.TRANSMISSION_PATH

    def get_client(self) -> transmission_rpc.Client:
        """Connects to the Transmission RPC server and returns a client instance."""
        return transmission_rpc.Client(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            path=self.path
        )

    def test_connection(self) -> bool:
        """Tests if connection to Transmission RPC is working."""
        try:
            client = self.get_client()
            client.get_session()
            return True
        except Exception as e:
            logger.error(f"Transmission connection failed: {e}")
            return False

    def add_torrent(self, torrent: Union[str, bytes], download_dir: Optional[str] = None) -> transmission_rpc.Torrent:
        """
        Adds a torrent by magnet link, HTTP/HTTPS URL, or raw torrent file contents (bytes).
        """
        client = self.get_client()
        # If download_dir is empty string, convert to None so Transmission uses default
        dir_arg = download_dir if download_dir else None
        
        # transmission-rpc adds torrents via add_torrent method
        # If torrent is bytes, it's a torrent file
        if isinstance(torrent, bytes):
            # Base64 encoded or raw bytes? transmission-rpc handles raw torrent file in bytes
            return client.add_torrent(torrent, download_dir=dir_arg)
        else:
            return client.add_torrent(torrent, download_dir=dir_arg)

    def get_torrents(self) -> List[transmission_rpc.Torrent]:
        """Gets all torrents from Transmission."""
        client = self.get_client()
        return client.get_torrents()

    def get_torrent(self, torrent_id: Union[int, str]) -> Optional[transmission_rpc.Torrent]:
        """Gets a single torrent by ID."""
        client = self.get_client()
        try:
            return client.get_torrent(torrent_id)
        except Exception:
            return None

    def pause_torrent(self, torrent_id: Union[int, str]):
        """Pauses a torrent."""
        client = self.get_client()
        client.stop_torrent(torrent_id)

    def resume_torrent(self, torrent_id: Union[int, str]):
        """Resumes a torrent."""
        client = self.get_client()
        client.start_torrent(torrent_id)

    def remove_torrent(self, torrent_id: Union[int, str], delete_data: bool = False):
        """Removes a torrent, optionally deleting downloaded data."""
        client = self.get_client()
        client.remove_torrent(torrent_id, delete_data=delete_data)

    def get_download_dirs(self) -> List[str]:
        """
        Returns a list of unique download directories currently in use
        or set as default in the session.
        """
        dirs = []
        try:
            client = self.get_client()
            # 1. Get default download dir
            session = client.get_session()
            if session.download_dir:
                dirs.append(session.download_dir)
            
            # 2. Get download dirs from existing torrents
            torrents = client.get_torrents()
            for t in torrents:
                if t.download_dir and t.download_dir not in dirs:
                    dirs.append(t.download_dir)
        except Exception as e:
            logger.error(f"Error fetching download directories: {e}")
            if config.DEFAULT_DOWNLOAD_DIR:
                dirs.append(config.DEFAULT_DOWNLOAD_DIR)
        
        # Deduplicate while preserving order
        seen = set()
        unique_dirs = []
        for d in dirs:
            if d not in seen:
                seen.add(d)
                unique_dirs.append(d)
        
        return unique_dirs
