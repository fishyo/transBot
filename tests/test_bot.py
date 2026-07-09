import pytest
from datetime import timedelta
from bot.handlers import format_size, format_speed, format_eta, validate_new_dir_path

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
