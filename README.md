# Transbot - Transmission Telegram Bot 🚀

[![Python Tests and Docker Release](https://github.com/fishyo/transBot/actions/workflows/tests.yml/badge.svg)](https://github.com/fishyo/transBot/actions/workflows/tests.yml)
[![Docker Image Version](https://img.shields.io/github/v/release/fishyo/transBot?label=version&color=blue)](https://github.com/fishyo/transBot/releases)
[![Container Registry](https://img.shields.io/badge/registry-GHCR-orange.svg)](https://github.com/fishyo/transBot/pkgs/container/transbot)

这是一个专为个人 NAS/OMV 挂载环境打造的 **Transmission Telegram 智能控制机器人**。它能通过 Telegram 消息，让您随时随地远程控制下载、监控磁盘空间、管理种子，以及接收下载完成推送。

本项目现已通过 GitHub Actions 实现持续集成（CI/CD），并在 **GitHub Container Registry (GHCR)** 发布了预编译的免编译 Docker 镜像包。您无需在 NAS 上安装任何开发依赖，即可直接一键拉取运行。

---

## 🌟 主要功能特点

1. **🔗 便捷添加任务**：直接向机器人发送 **磁力链接 (Magnet Link)**、**种子 URL 地址**，或上传 **`.torrent` 种子文件** 即可开始下载。
2. **📂 交互式目录浏览器**：添加种子时，会唤起直观的**多级目录选择器**，支持直接创建新文件夹，并选择任意子文件夹作为下载保存目标。
3. **📊 超简洁状态监控 (`/status`)**：精简版展示正在下载/做种的任务状态，实时显示 OMV 挂载硬盘的剩余空间以及备用限速（乌龟模式）状态。
4. **🎛️ 独立控制中心 (`/manage`)**：支持对具体种子进行单独管理，提供暂停/恢复、删除（可选保留或删除本地数据）及**直接重命名文件夹**的功能。
5. **🐢 乌龟限速模式一键切换 (`/turtle`)**：一键开关 Transmission 备用速度限制，方便网络错峰管理。
6. **🔔 完成通知推送**：后台常驻 poller 进程，下载完成时会自动发送 Telegram 通知消息。
7. **🐳 生产级免编译部署**：使用 GitHub Actions 自动构建并发布至 GHCR，NAS 部署无需本地 `build`，开箱即用。
8. **🛡️ 用户权限锁与安全保障**：在配置中锁定您的专属 Telegram ID。对新建文件夹名称使用 `os.path.commonpath` 进行校验，防范路径越界和目录逃逸。

---

## 🛠️ 指令手册

* `/status` - **查看状态**。获取下载/做种简表、实时速度、Peers 连接数、磁盘可用空间及限速模式。
* `/manage` - **控制中心**。提供种子的暂停、继续、删除及**重命名**等操作入口。
* `/dirs` - **目录管理**。查看当前默认保存路径，或直接浏览文件夹并将其设为全局默认。
* `/turtle` - **限速开关**。一键切换 Transmission 的乌龟限速模式。
* `/cancel` - **取消会话**。随时终止新建文件夹、目录导航或重命名等输入对话。
* `/help` - **使用手册**。输出详细的功能与指令对照指南。

---

## 🚀 部署配置步骤 (OMV/NAS)

### 1. 准备环境变量 (`.env`)
在您的 NAS 部署目录下创建一个 `.env` 文件，填写以下内容：

```ini
# Telegram 机器人 Token (通过 @BotFather 获取)
TELEGRAM_TOKEN=您的_BOT_TOKEN

# 授权可访问机器人的用户 Telegram ID 列表 (通过 @userinfobot 获取)，多用户用英文逗号分隔
ALLOWED_USER_IDS=your_telegram_id_here

# 本地 Transmission RPC 服务的连接参数
TRANSMISSION_HOST=127.0.0.1
TRANSMISSION_PORT=9091
TRANSMISSION_USER=您的用户名
TRANSMISSION_PASSWORD=您的密码
TRANSMISSION_PATH=/transmission/rpc

# 机器人基本设置
DEFAULT_DOWNLOAD_DIR=/downloads/complete
POLL_INTERVAL=10
```

### 2. 配置 Compose 编排 (`docker-compose.yml`)
在同目录下创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  transmission-bot:
    image: ghcr.io/fishyo/transbot:latest  # 直接从 GHCR 拉取官方打包镜像
    container_name: transmission-telegram-bot
    restart: unless-stopped
    volumes:
      # 挂载数据持久化目录
      - ./data:/app/data
      # 挂载您的 NAS 存储/下载目录（必须与 Transmission 的实际下载根路径映射一致）
      - /srv/dev-disk-by-uuid-XXXXXX/downloads:/downloads
    env_file:
      - .env
```

### 3. 启动容器
在终端中进入该目录，直接运行：

```bash
# 拉取最新镜像
docker compose pull

# 启动容器并后台运行
docker compose up -d
```

### 4. 日常维护常用命令
* **查看运行日志**：`docker compose logs -f`
* **重启机器人**（例如在更新 `.env` 之后）：`docker compose restart`
* **停止运行**：`docker compose down`

---

## 🧪 开发者指南 (Developer Guide)

如果您想对本项目进行二次开发或本地贡献：

### 1. 本地开发环境初始化
```bash
# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows 下使用: .\.venv\Scripts\activate

# 安装开发与运行依赖
pip install -r requirements.txt
```

### 2. 运行本地单元测试
项目引入了 `pytest` 用于保障关键格式化和防目录逃逸的安全校验：
```bash
python -m pytest
```

### 3. CI/CD 工作流
* 每次推送代码到 `main`/`master` 分支或提交 PR 时，GitHub Actions 会自动运行测试。
* 测试成功后，会自动触发 Docker 镜像打包，并推送最新版至 `ghcr.io/fishyo/transbot:latest`。
