# transBot

[![Tests](https://github.com/fishyo/transBot/actions/workflows/tests.yml/badge.svg)](https://github.com/fishyo/transBot/actions/workflows/tests.yml)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io%2Ffishyo%2Ftransbot-blue?logo=docker&logoColor=white)](https://github.com/fishyo/transBot/pkgs/container/transbot)

[English](README.md) | [简体中文](README_zh.md) | [Changelog](CHANGELOG.md)

A Telegram bot to control a Transmission client. Add downloads via magnet links or `.torrent` files, browse directories, manage tasks, monitor disk usage, and receive completion alerts directly in Telegram.

---

## Features

- **Add Torrents**: Send one or multiple magnet links, HTTP torrent URLs, or upload `.torrent` files.
- **Directory Picker**: Select target save paths through an inline keyboard, or create new subdirectories directly from chat.
- **Task Management (`/manage`)**: Paginated management panel with status filters (All, Active, Paused, Complete) to pause, resume, rename, or delete torrents (with optional data removal).
- **Status Monitor (`/status`)**: Check transfer speeds, connected peers, progress, free disk space, and turtle mode status.
- **Turtle Mode (`/turtle`)**: Toggle Transmission alternative speed limits on or off.
- **Completion Alerts**: Automatic Telegram notifications when downloads complete, with optional SMTP email delivery.
- **Access Control**: Strict user whitelist based on Telegram User IDs.

---

## Commands

| Command | Description |
| :--- | :--- |
| `/status` | View speeds, active tasks, and available disk space |
| `/manage` | Open task management center to filter, rename, or delete torrents |
| `/dirs` | Show default download path, recent history, or browse directories |
| `/turtle` | Toggle alternative speed limit mode |
| `/help` | Show command usage and instructions |
| `/cancel` | Cancel any active prompt or directory navigation |

---

## Deployment (Docker Compose)

### 1. Configuration (`.env`)

Create a `.env` file in your deployment directory:

```ini
# Telegram Bot Token (from @BotFather)
TELEGRAM_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ

# Authorized Telegram user IDs (from @userinfobot), comma-separated
ALLOWED_USER_IDS=12345678,87654321

# Transmission RPC settings
TRANSMISSION_HOST=127.0.0.1
TRANSMISSION_PORT=9091
TRANSMISSION_USER=
TRANSMISSION_PASSWORD=
TRANSMISSION_PATH=/transmission/rpc

# Bot defaults
DEFAULT_DOWNLOAD_DIR=/downloads/complete
POLL_INTERVAL=10

# Email notifications (optional)
ENABLE_EMAIL_NOTIFICATION=false
SMTP_SERVER=smtp.example.com
SMTP_PORT=465
SMTP_USER=user@example.com
SMTP_PASSWORD=your_password
SMTP_USE_SSL=true
EMAIL_TO=recipient@example.com
```

### 2. Docker Compose (`docker-compose.yml`)

```yaml
version: '3.8'

services:
  transmission-bot:
    image: ghcr.io/fishyo/transbot:latest
    container_name: transmission-telegram-bot
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      # Mount your host downloads directory (should match Transmission's root path)
      - /path/to/your/downloads:/downloads
    env_file:
      - .env
```

### 3. Run

```bash
docker compose pull
docker compose up -d
```

View logs:
```bash
docker compose logs -f
```

---

## Development & Testing

```bash
# 1. Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
pip install -r requirements.txt pytest-asyncio

# 2. Run unit tests
TELEGRAM_TOKEN="123456:dummy_token" pytest
```
