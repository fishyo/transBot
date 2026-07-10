# Analysis of Transmission False Download Completion Notification Bug

## Summary
When adding a magnet link torrent, a "Download Completed!" notification is sent immediately even though the torrent hasn't actually downloaded its files. This document details why this happened and how it was fixed.

## Root Cause Analysis
In [bot/poller.py](file:///D:/Documents/transmissionBot/bot/poller.py), the bot checks if a torrent has completed using this line:
```python
is_completed = (t.left_until_done == 0) or (t.progress >= 1.0)
```

For magnet links, the download goes through two main stages:
1. **Metadata Downloading**: Before downloading the actual files, Transmission must retrieve torrent metadata (the file list, sizes, etc.).
2. **File Downloading**: Once metadata is available, the files start downloading.

During the **Metadata Downloading** stage:
* The torrent name is fetched (usually from the magnet's `dn` parameter).
* Because Transmission does not yet know the files inside the torrent, it reports **`total_size = 0`** and **`left_until_done = 0`**.
* The criteria `(t.left_until_done == 0)` evaluates to **`True`**.
* As a result, the poller erroneously flags the torrent as completed and sends a notification.

## The Solution
To prevent this false positive, we refactored the completion detection logic into a new method `is_torrent_completed(self, t) -> bool` inside `CompletionPoller` in [bot/poller.py](file:///D:/Documents/transmissionBot/bot/poller.py). 

A torrent is now only considered completed if:
1. **Metadata is fully downloaded**: `metadata_percent_complete >= 1.0` (or defaults to `1.0` if not supported).
2. **Torrent has files**: `total_size > 0`.
3. **Download progress is complete**: `left_until_done == 0` or `progress >= 1.0`.

```python
def is_torrent_completed(self, t) -> bool:
    """
    Determines if a torrent is fully downloaded.
    Avoids false positives for newly added magnet links that don't have metadata yet.
    """
    metadata_complete = getattr(t, 'metadata_percent_complete', 1.0) >= 1.0
    has_files = getattr(t, 'total_size', 0) > 0
    download_complete = (getattr(t, 'left_until_done', 0) == 0) or (getattr(t, 'progress', 0.0) >= 1.0)
    return metadata_complete and has_files and download_complete
```

## Verification & Testing
1. We verified the behavior of a newly added magnet link during metadata download against local Transmission RPC, confirming that indeed `left_until_done` was `0` and `metadata_percent_complete` was `0.0`.
2. We added comprehensive unit tests to [tests/test_bot.py](file:///D:/Documents/transmissionBot/tests/test_bot.py) covering all scenarios:
   * Magnet link downloading metadata
   * Torrent downloading files
   * Torrent completed (with and without `metadata_percent_complete` field)
3. Ran pytest, and all tests passed successfully.
