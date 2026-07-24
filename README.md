# Transbot - Transmission Telegram Bot 🚀

[![Language](https://img.shields.io/badge/Language-English-blue.svg)](README.md)
[![语言](https://img.shields.io/badge/语言-简体中文-red.svg)](README_zh.md)
[![Python Tests and Docker Release](https://github.com/fishyo/transBot/actions/workflows/tests.yml/badge.svg)](https://github.com/fishyo/transBot/actions/workflows/tests.yml)
[![GHCR Registry](https://img.shields.io/badge/registry-ghcr.io%2Ffishyo%2Ftransbot-blue?logo=docker&logoColor=white)](https://github.com/fishyo/transBot/pkgs/container/transbot)
[![Docker Image Version](https://img.shields.io/badge/version-latest-brightgreen?logo=github)](https://github.com/fishyo/transBot/pkgs/container/transbot)

[English](README.md) | [简体中文](README_zh.md)

---

A feature-rich, intelligent **Transmission Telegram Control Bot** designed specifically for personal NAS and OpenMediaVault (OMV) environments. It enables you to remotely manage downloads, monitor disk space, control torrents, and receive completion notifications anytime, anywhere via Telegram.

This project features Continuous Integration and Continuous Deployment (CI/CD) via GitHub Actions, releasing pre-built Docker containers on **GitHub Container Registry (GHCR)**. You can run it instantly on your NAS without installing any development dependencies.

---

## 🌟 Key Features

1. **🔗 Easy Task Addition**: Send **Magnet Links**, **Torrent File URLs**, or upload **`.torrent` files** directly to the bot to start downloading instantly.
2. **📂 Interactive Directory Browser**: When adding a torrent, an intuitive **multi-level folder picker** is triggered, allowing you to select any subfolder as the download target or create new directories on the fly.
3. **📊 Concise Status Monitor (`/status`)**: View active downloads, seeding tasks, real-time speeds, peer counts, available NAS disk space, and alt-speed limit status at a glance.
4. **🎛️ Control Center (`/manage`)**: Manage specific torrents interactively with options to pause, resume, delete (with or without local data removal), and **rename download folders**.
5. **🐢 Turtle Mode Toggle (`/turtle`)**: One-tap toggle for Transmission's Alternative Speed Limits to manage bandwidth usage during peak hours.
6. **🔔 Completion Notifications**: A background poller process monitors downloads and automatically sends Telegram completion alerts, with support for optional **SMTP Email Notifications** (styled HTML cards).
7. **🐳 Production-Grade Docker Deployment**: Built and published automatically to GHCR via GitHub Actions. Zero local build required on NAS.
8. **🛡️ Access Control & Security**: Restrict bot commands to specific authorized Telegram User IDs. Input paths are sanitized and validated using `os.path.commonpath` to prevent path traversal vulnerabilities.

---

## 🛠️ Command Reference

* `/status` - **View Status**. Display download/seeding summary, real-time speeds, peer count, free disk space, and turtle mode status.
* `/manage` - **Control Center**. Interactive menu to pause, resume, delete, or **rename** torrents.
* `/dirs` - **Directory Manager**. Inspect current default save path, or browse NAS folders to set a new default.
* `/turtle` - **Speed Limit Toggle**. Quickly enable or disable Transmission's alt-speed limit.
* `/cancel` - **Cancel Session**. Terminate any ongoing interactive conversation (e.g., directory browsing, folder creation, or renaming).
* `/help` - **User Manual**. Display detailed command usage and guidance.

---

## 🚀 Deployment Guide (OMV / NAS)

### 1. Create Environment File (`.env`)
Create a `.env` file in your deployment directory on your NAS:

```ini
# Telegram Bot Token (Obtain from @BotFather on Telegram)
TELEGRAM_TOKEN=your_telegram_bot_token_here

# Authorized Telegram User IDs (Obtain from @userinfobot), comma-separated for multiple users
ALLOWED_USER_IDS=12345678,87654321

# Transmission RPC Configuration
TRANSMISSION_HOST=127.0.0.1
TRANSMISSION_PORT=9091
TRANSMISSION_USER=
TRANSMISSION_PASSWORD=
TRANSMISSION_PATH=/transmission/rpc

# Bot Settings
DEFAULT_DOWNLOAD_DIR=/downloads/complete
POLL_INTERVAL=10

# Email Notification Configuration (Optional)
ENABLE_EMAIL_NOTIFICATION=false
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_USE_SSL=false
EMAIL_TO=recipient@example.com
```

### 2. Configure Docker Compose (`docker-compose.yml`)
Create a `docker-compose.yml` file in the same directory:

```yaml
version: '3.8'

services:
  transmission-bot:
    image: ghcr.io/fishyo/transbot:latest  # Pull official pre-built image from GHCR
    container_name: transmission-telegram-bot
    restart: unless-stopped
    volumes:
      # Data persistence mount
      - ./data:/app/data
      # Mount your NAS storage/download root directory (must match Transmission's host path)
      - /srv/dev-disk-by-uuid-XXXXXX/downloads:/downloads
    env_file:
      - .env
```

### 3. Launch Container
Run the following commands in your NAS terminal:

```bash
# Pull the latest image
docker compose pull

# Start the service in detached mode
docker compose up -d
```

### 4. Maintenance Commands
* **View logs**: `docker compose logs -f`
* **Restart service**: `docker compose restart`
* **Stop service**: `docker compose down`

---

## 🧪 Developer Guide

To contribute or develop locally:

### 1. Initialize Development Environment
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Unit Tests
Unit tests use `pytest` to verify string formatting and security checks against directory traversal:
```bash
python -m pytest
```

### 3. CI/CD Workflow
* Pushing to `main` or submitting a PR automatically runs the pytest test suite via GitHub Actions.
* Upon successful build and test execution, GitHub Actions builds and publishes the updated Docker image to `ghcr.io/fishyo/transbot:latest`.
