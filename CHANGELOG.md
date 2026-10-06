# Change Log (更新日志)

All notable changes to the Transbot project will be documented in this file.
本项目的所有重大更新与改动都将在此文件中记录。

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed (修复)
- **Directory Browser Pagination (目录浏览器分页与加载更多文件夹)**:
  - Fixed an issue where folders beyond the first 10 could not be loaded or viewed in the directory selection browser due to a placeholder "noop" button.
  - Implemented interactive multi-page navigation (`◀️ Prev`, `📄 Page X/Y`, `Next ▶️`, and `⏮ 1` / `N ⏭` fast-jump controls) with 10 folders per page.
  - Added unit test coverage for directory pagination and button construction in `tests/test_bot.py`.

---

## [v1.1.0] - 2026-08-05

### Added (新增)
- **Multi-Magnet & Torrent Link Extraction (多磁力链接与 Torrent 地址批量解析)**:
  - Support parsing and extracting multiple magnet links or `.torrent` URLs from a single message, text block, or bulleted list.
  - Automatic link deduplication within a single payload.
  - Unit tests in `test_extract_torrents_from_text` to verify regex link extraction edge cases.
- **Recent Directory Management (近期下载目录管理)**:
  - Display recently used download target directories in `/dirs` menu and interactive directory browser.
  - Support single directory removal and one-click clear all recent path history (`clear_recent_dirs`).
  - Unit tests in `test_storage_recent_dirs` for storage persistence and directory removal verification.
- **SemVer Release Tagging in CI/CD (SemVer 语义化镜像构建与发布)**:
  - Updated GitHub Actions workflow to support SemVer git tags matching `v*.*.*`.
  - Automatically tag Docker images in GHCR with `vX.Y.Z`, `vX.Y`, `vX`, `latest`, and commit SHA.

---

## [v1.0.0] - 2026-07-24

### Added (新增)
- **SMTP Email Notifications (下载完成邮件通知)**:
  - Support optional SMTP email notifications upon download completion (`ENABLE_EMAIL_NOTIFICATION`).
  - Added modern minimalist receipt-style (Style 2B) HTML email template designed for high cross-client email rendering compatibility.
- **Bilingual Documentation (双语文档支持)**:
  - Standardized English `README.md` as default and added dedicated Chinese `README_zh.md` with language switcher badges.

### Fixed (修复)
- **Poller Completion Calculation (下载完成度判定逻辑修复)**:
  - Corrected completion progress threshold calculation in `CompletionPoller` from `1.0` to `100.0`.
  - Added test coverage verifying magnet link metadata fetching phase vs completed torrent states.

---

## [v0.9.0] - 2026-07-10

### Added (新增)
- **Transmission Remote Management (Transmission 远程控制)**:
  - Remotely add downloads via Magnet links, `.torrent` HTTP/HTTPS URLs, and `.torrent` file uploads.
  - Multi-level interactive directory browser for selecting subfolders or creating new directories on the fly.
  - Interactive `/manage` center allowing torrent pause, resume, deletion (with or without local data files), and folder renaming.
  - Real-time `/status` command monitoring active downloads, speeds, peer counts, OMV disk space, and turtle mode.
  - `/turtle` fast toggle for Transmission Alternative Speed Limits.
  - `/cancel` command to abort any active input session.
- **Security & Path Traversal Guard (权限控制与路径逃逸防护)**:
  - Telegram User ID whitelist authorization system (`ALLOWED_USER_IDS`).
  - Sanitized directory input with `os.path.commonpath` verification to protect against path traversal security vulnerabilities.
- **CI/CD & Docker (自动化 CI/CD 与 Docker 部署)**:
  - GitHub Actions automated test runner using `pytest`.
  - Pre-built Docker container image build and publishing to GitHub Container Registry (GHCR).
