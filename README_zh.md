# transBot

[![Tests](https://github.com/fishyo/transBot/actions/workflows/tests.yml/badge.svg)](https://github.com/fishyo/transBot/actions/workflows/tests.yml)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io%2Ffishyo%2Ftransbot-blue?logo=docker&logoColor=white)](https://github.com/fishyo/transBot/pkgs/container/transbot)

[English](README.md) | [简体中文](README_zh.md) | [更新日志](CHANGELOG.md)

通过 Telegram 管理 Transmission 下载任务的机器人。支持接收磁力链接与种子文件、多级目录选择、任务管理、磁盘监控及完成推送。

---

## 功能说明

- **添加任务**：直接向机器人发送单条或多条磁力链接、HTTP 种子链接，或直接发送 `.torrent` 文件。
- **目录浏览与选择**：添加任务时支持在内联键盘中选择目标保存路径，或直接在界面中新建子目录。
- **任务管理 (`/manage`)**：提供内联操作面板，支持按状态（全部 / 活跃 / 暂停 / 完成）筛选和分页浏览，可对单个任务执行暂停、继续、重命名或删除（可选手选是否保留数据文件）。
- **状态监控 (`/status`)**：查看下载与做种速度、Peers 连接数、任务进度、磁盘剩余容量及海龟模式状态。
- **海龟限速 (`/turtle`)**：快速开启或关闭 Transmission 的备用速度限制。
- **完成通知**：任务下载完成后自动向 Telegram 发送通知，支持可选的 SMTP 邮件推送。
- **访问控制**：通过配置白名单限制可操作机器人的 Telegram 用户 ID。

---

## 常用命令

| 命令 | 说明 |
| :--- | :--- |
| `/status` | 查看当前下载/做种状态、传输速度与磁盘容量 |
| `/manage` | 打开任务管理中心，支持筛选、分页、改名与删除 |
| `/dirs` | 查看默认下载路径，管理最近使用路径或浏览文件夹 |
| `/turtle` | 切换海龟限速模式（ON / OFF） |
| `/help` | 查看使用指南 |
| `/cancel` | 取消当前的目录选择、新建文件夹或改名操作 |

---

## 部署运行 (Docker Compose)

### 1. 准备配置文件

在部署目录下创建 `.env` 文件：

```ini
# Telegram Bot Token（向 @BotFather 获取）
TELEGRAM_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ

# 允许使用机器人的 Telegram 用户 ID（向 @userinfobot 获取），多个用逗号分隔
ALLOWED_USER_IDS=12345678,87654321

# Transmission RPC 连接配置
TRANSMISSION_HOST=127.0.0.1
TRANSMISSION_PORT=9091
TRANSMISSION_USER=
TRANSMISSION_PASSWORD=
TRANSMISSION_PATH=/transmission/rpc

# 默认设置
DEFAULT_DOWNLOAD_DIR=/downloads/complete
POLL_INTERVAL=10

# 邮件通知配置（可选）
ENABLE_EMAIL_NOTIFICATION=false
SMTP_SERVER=smtp.example.com
SMTP_PORT=465
SMTP_USER=user@example.com
SMTP_PASSWORD=your_password
SMTP_USE_SSL=true
EMAIL_TO=recipient@example.com
```

### 2. 编写 `docker-compose.yml`

```yaml
version: '3.8'

services:
  transmission-bot:
    image: ghcr.io/fishyo/transbot:latest
    container_name: transmission-telegram-bot
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      # 映射实际的下载路径，保持与 Transmission 容器一致
      - /path/to/your/downloads:/downloads
    env_file:
      - .env
```

### 3. 启动服务

```bash
docker compose pull
docker compose up -d
```

查看运行日志：
```bash
docker compose logs -f
```

---

## 本地开发与测试

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt pytest-asyncio

# 2. 运行测试
TELEGRAM_TOKEN="123456:dummy_token" pytest
```
