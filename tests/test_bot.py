import pytest
from datetime import timedelta
from bot.handlers import (
    format_size,
    format_speed,
    format_eta,
    validate_new_dir_path,
    get_directory_page_slice,
    build_directory_pagination_row,
    DIR_PAGE_SIZE
)

def test_format_size():
    assert format_size(0) == "0 B"
    assert format_size(512) == "512.0 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1048576) == "1.0 MB"
    assert format_size(1073741824) == "1.0 GB"
    assert format_size(1099511627776) == "1.0 TB"

def test_format_speed():
    assert format_speed(0) == "0 B/s"
    assert format_speed(1024) == "1.0 KB/s"
    assert format_speed(1572864) == "1.5 MB/s"

def test_format_eta():
    assert format_eta(None) == "Unknown"
    assert format_eta(-1) == "Unknown"
    assert format_eta(86400 * 8) == "Inf"
    assert format_eta(30) == "30s"
    assert format_eta(120) == "2m"
    assert format_eta(3665) == "1h 1m 5s"
    assert format_eta(90065) == "1d 1h 1m 5s"
    assert format_eta(timedelta(seconds=120)) == "2m"

def test_validate_new_dir_path():
    # Valid subdirectory creation
    valid, path = validate_new_dir_path("/downloads", "movies")
    assert valid is True
    assert path == "/downloads/movies"

    # Deep valid subdirectory
    valid, path = validate_new_dir_path("/downloads/movies/action", "scifi")
    assert valid is True
    assert path == "/downloads/movies/action/scifi"

    # Empty folder name
    valid, path = validate_new_dir_path("/downloads", "")
    assert valid is False

    # Path traversal with double dots
    valid, path = validate_new_dir_path("/downloads/movies", "..")
    assert valid is False

    # Path traversal going outside /downloads is prevented because slashes are stripped,
    # converting "../outside" to "..outside" which is a valid subdirectory name.
    valid, path = validate_new_dir_path("/downloads", "../outside")
    assert valid is True
    assert path == "/downloads/..outside"

    # Dot directory
    valid, path = validate_new_dir_path("/downloads/movies", ".")
    assert valid is False

    # Invalid characters are sanitized and then validated
    valid, path = validate_new_dir_path("/downloads/movies", "action/comedy")
    # Slash is stripped, name becomes "actioncomedy"
    assert valid is True
    assert path == "/downloads/movies/actioncomedy"

    # Unauthorized root path traversal (current_path outside /downloads defaults to /downloads)
    valid, path = validate_new_dir_path("/etc", "movies")
    assert valid is True
    assert path == "/downloads/movies"

class MockTorrent:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_is_torrent_completed():
    from bot.poller import CompletionPoller
    poller = CompletionPoller()

    # Case 1: Magnet link downloading metadata (total_size=0, progress=0.0, left_until_done=0, metadata_percent_complete=0.0)
    t1 = MockTorrent(
        metadata_percent_complete=0.0,
        total_size=0,
        left_until_done=0,
        progress=0.0
    )
    assert poller.is_torrent_completed(t1) is False

    # Case 2: Torrent downloading files (metadata_percent_complete=1.0, total_size=1000, left_until_done=500, progress=50.0)
    t2 = MockTorrent(
        metadata_percent_complete=1.0,
        total_size=1000,
        left_until_done=500,
        progress=50.0
    )
    assert poller.is_torrent_completed(t2) is False

    # Case 3: Torrent completed (metadata_percent_complete=1.0, total_size=1000, left_until_done=0, progress=100.0)
    t3 = MockTorrent(
        metadata_percent_complete=1.0,
        total_size=1000,
        left_until_done=0,
        progress=100.0
    )
    assert poller.is_torrent_completed(t3) is True

    # Case 4: Normal torrent file (without metadata_percent_complete attribute) but completed
    t4 = MockTorrent(
        total_size=1000,
        left_until_done=0,
        progress=100.0
    )
    assert poller.is_torrent_completed(t4) is True

    # Case 5: Normal torrent file downloading (without metadata_percent_complete attribute, progress < 1.0)
    t5 = MockTorrent(
        total_size=1000,
        left_until_done=995,
        progress=0.5
    )
    assert poller.is_torrent_completed(t5) is False

    # Case 6: Normal torrent file downloading (progress > 1.0, e.g. 18.94%)
    t6 = MockTorrent(
        total_size=1000,
        left_until_done=810,
        progress=18.94
    )
    assert poller.is_torrent_completed(t6) is False


def test_email_notifier_disabled():
    from bot.email_notifier import _send_email_sync
    import bot.config as config
    config.ENABLE_EMAIL_NOTIFICATION = False
    assert _send_email_sync("Test.mkv", "/downloads", "1.0 GB") is False

def test_email_notifier_enabled_mock(monkeypatch):
    from unittest.mock import MagicMock
    from bot.email_notifier import _send_email_sync
    import bot.config as config

    config.ENABLE_EMAIL_NOTIFICATION = True
    config.SMTP_SERVER = "smtp.test.com"
    config.SMTP_PORT = 465
    config.SMTP_USER = "test@example.com"
    config.SMTP_PASSWORD = "secretpassword"
    config.SMTP_USE_SSL = True
    config.EMAIL_TO = ["recipient@example.com"]

    mock_smtp = MagicMock()
    monkeypatch.setattr("smtplib.SMTP_SSL", lambda host, port, timeout: mock_smtp)
    mock_smtp.__enter__.return_value = mock_smtp

    res = _send_email_sync("Silo.S03E04.mkv", "/downloads", "2.5 GB")
    assert res is True
    mock_smtp.login.assert_called_once_with("test@example.com", "secretpassword")
    assert mock_smtp.sendmail.called


def test_extract_torrents_from_text():
    from bot.handlers import extract_torrents_from_text

    # Case 1: Empty or invalid text
    assert extract_torrents_from_text("") == []
    assert extract_torrents_from_text("Hello world, this is a test.") == []

    # Case 2: Single magnet link
    mag1 = "magnet:?xt=urn:btih:1111111111111111111111111111111111111111&dn=Movie1"
    assert extract_torrents_from_text(mag1) == [mag1]

    # Case 3: Multiple magnet links separated by newlines
    mag2 = "magnet:?xt=urn:btih:2222222222222222222222222222222222222222&dn=Movie2"
    mag3 = "magnet:?xt=urn:btih:3333333333333333333333333333333333333333&dn=Movie3"
    text_multi = f"{mag1}\n{mag2}\n{mag3}"
    assert extract_torrents_from_text(text_multi) == [mag1, mag2, mag3]

    # Case 4: Multiple magnet links embedded in conversational text with trailing punctuation
    text_convo = f"Hey! Download these:\n1. {mag1}.\n2. {mag2},\n3. {mag3})"
    assert extract_torrents_from_text(text_convo) == [mag1, mag2, mag3]

    # Case 5: HTTP/HTTPS torrent links
    url1 = "https://example.com/test1.torrent"
    url2 = "http://example.com/test2.torrent"
    assert extract_torrents_from_text(f"{url1} and {url2}") == [url1, url2]

    # Case 6: Duplicate links in same message
    assert extract_torrents_from_text(f"{mag1}\n{mag1}\n{mag2}") == [mag1, mag2]


def test_storage_recent_dirs(tmp_path):
    from bot.storage import Storage

    test_json = str(tmp_path / "test_storage.json")
    st = Storage(filepath=test_json)

    # Initial state
    assert st.get_recent_dirs() == []

    # Add directories
    st.add_recent_dir("/downloads/movies")
    st.add_recent_dir("/downloads/anime")
    st.add_recent_dir("/downloads/tv")
    assert st.get_recent_dirs() == ["/downloads/tv", "/downloads/anime", "/downloads/movies"]

    # Remove single directory
    st.remove_recent_dir("/downloads/anime")
    assert st.get_recent_dirs() == ["/downloads/tv", "/downloads/movies"]

    # Clear all recent directories
    st.clear_recent_dirs()
    assert st.get_recent_dirs() == []

    # Reload from disk to verify persistence
    st_reloaded = Storage(filepath=test_json)
    assert st_reloaded.get_recent_dirs() == []


def test_directory_page_slice():
    # 0 items
    page, total, start, end = get_directory_page_slice(0, 0, DIR_PAGE_SIZE)
    assert (page, total, start, end) == (0, 1, 0, 0)

    # 5 items (less than 1 page)
    page, total, start, end = get_directory_page_slice(5, 0, 10)
    assert (page, total, start, end) == (0, 1, 0, 5)

    # Exact 10 items (exactly 1 page)
    page, total, start, end = get_directory_page_slice(10, 0, 10)
    assert (page, total, start, end) == (0, 1, 0, 10)

    # 15 items: page 0 and page 1
    page, total, start, end = get_directory_page_slice(15, 0, 10)
    assert (page, total, start, end) == (0, 2, 0, 10)

    page, total, start, end = get_directory_page_slice(15, 1, 10)
    assert (page, total, start, end) == (1, 2, 10, 15)

    # Clamping out-of-bounds page numbers
    page, total, start, end = get_directory_page_slice(15, 5, 10)
    assert (page, total, start, end) == (1, 2, 10, 15)

    page, total, start, end = get_directory_page_slice(15, -2, 10)
    assert (page, total, start, end) == (0, 2, 0, 10)

    # 35 items (4 pages)
    page, total, start, end = get_directory_page_slice(35, 2, 10)
    assert (page, total, start, end) == (2, 4, 20, 30)

    page, total, start, end = get_directory_page_slice(35, 3, 10)
    assert (page, total, start, end) == (3, 4, 30, 35)


def test_build_directory_pagination_row():
    # Single page: no pagination row needed
    assert build_directory_pagination_row(0, 1) == []

    # 2 pages: first page
    row_2_0 = build_directory_pagination_row(0, 2)
    assert len(row_2_0) == 2
    assert row_2_0[0].callback_data == "nav_page_info"
    assert row_2_0[1].callback_data == "nav_page:1"

    # 2 pages: second page
    row_2_1 = build_directory_pagination_row(1, 2)
    assert len(row_2_1) == 2
    assert row_2_1[0].callback_data == "nav_page:0"
    assert row_2_1[1].callback_data == "nav_page_info"

    # 3 pages: middle page
    row_3_1 = build_directory_pagination_row(1, 3)
    assert len(row_3_1) == 3
    assert row_3_1[0].callback_data == "nav_page:0"
    assert row_3_1[1].callback_data == "nav_page_info"
    assert row_3_1[2].callback_data == "nav_page:2"

    # 5 pages: first page (includes fast-forward last page button)
    row_5_0 = build_directory_pagination_row(0, 5)
    assert len(row_5_0) == 3
    assert row_5_0[0].callback_data == "nav_page_info"
    assert row_5_0[1].callback_data == "nav_page:1"
    assert row_5_0[2].callback_data == "nav_page:4"

    # 5 pages: middle page (includes first, prev, info, next, last)
    row_5_2 = build_directory_pagination_row(2, 5)
    assert len(row_5_2) == 5
    assert row_5_2[0].callback_data == "nav_page:0"
    assert row_5_2[1].callback_data == "nav_page:1"
    assert row_5_2[2].callback_data == "nav_page_info"
    assert row_5_2[3].callback_data == "nav_page:3"
    assert row_5_2[4].callback_data == "nav_page:4"

    # 5 pages: last page
    row_5_4 = build_directory_pagination_row(4, 5)
    assert len(row_5_4) == 3
    assert row_5_4[0].callback_data == "nav_page:0"
    assert row_5_4[1].callback_data == "nav_page:3"
    assert row_5_4[2].callback_data == "nav_page_info"




