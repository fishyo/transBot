# Transmission Telegram Bot

这是一个专为个人 NAS/OMV 打造的 **Transmission Telegram 智能控制机器人**。它能通过 Telegram 消息，让您随时随地远程控制下载、监控磁盘空间、管理种子，以及接收下载完成推送。

---

## 🌟 主要功能特点

1. **🔗 便捷添加任务**：直接向机器人发送 **磁力链接 (Magnet Link)**、**种子 URL 地址**，或上传 **`.torrent` 种子文件** 即可开始。
2. **📂 交互式目录浏览器**：添加种子时，会唤起直观的**多级目录选择器**，支持直接创建新文件夹，并选择任意子文件夹作为下载保存目标。
3. **📊 超简洁状态监控 (`/status`)**：精简版双行列表展示正在下载/上传的任务状态。头部实时显示 OMV 挂载硬盘的剩余空间以及备用限速（乌龟模式）状态。
4. **🎛️ 独立控制中心 (`/manage`)**：支持对具体种子进行单独管理，提供单独暂停/恢复、删除（可选保留或删除本地数据）及**直接重命名文件夹**的功能。
5. **🐢 乌龟限速模式一键切换 (`/turtle`)**：一键开关 Transmission 备用速度限制，方便网络错峰管理。
6. **🔔 完成通知推送**：后台每 10 秒扫描一次，下载完成时会自动发送通知消息，并贴心提供“查看状态”按钮。
7. **🐳 标准容器化构建**：基于 Dockerfile 进行预编译和依赖打包，支持使用 Docker Compose 一键编译部署，运行环境完全隔离。
8. **🛡️ 用户权限锁**：在 `.env` 中锁定您的专属 Telegram ID，防止未授权账户访问您的下载器。

---

## 🛠️ 指令手册

* `/status` - **查看状态**。获取下载/做种简表、实时速度、Peers 连接数、磁盘可用空间及限速模式。
* `/manage` - **控制中心**。提供种子的暂停、继续、删除及**重命名**等操作入口。
* `/dirs` - **目录管理**。查看当前默认保存路径，或直接浏览文件夹并将其设为全局默认。
* `/turtle` - **限速开关**。一键切换 Transmission 的乌龟限速模式。
* `/cancel` - **取消会话**。随时终止新建文件夹、目录导航或重命名等输入对话。
* `/help` - **使用手册**。输出详细的功能与指令对照指南。

---

## 🚀 部署配置步骤

### 1. 配置环境变量 (`.env`)
在项目根目录下创建一个 `.env` 文件，填写以下内容：

```ini
# Telegram 机器人 Token (通过 @BotFather 获取)
TELEGRAM_TOKEN=您的_BOT_TOKEN

# 授权可访问机器人的用户 Telegram ID 列表 (通过 @userinfobot 获取)，多用户用英文逗号分隔
ALLOWED_USER_IDS=your_telegram_id_here

# 本地 Transmission RPC 服务的连接参数
TRANSMISSION_HOST=127.0.0.1
TRANSMISSION_PORT=9091
TRANSMISSION_USER=
TRANSMISSION_PASSWORD=
```

### 2. 检查宿主机硬盘挂载
打开 `docker-compose.yml`，核对其中的磁盘挂载。确保将您的 OMV 外置硬盘路径正确映射到容器内的 `/downloads` 目录，以供目录浏览器读取：

```yaml
    volumes:
      # 挂载数据持久化目录
      - ./data:/app/data
      # 挂载 OMV 外置硬盘路径
      - /path/to/your/nas/downloads:/downloads
```

### 3. 一键编译并启动容器
在终端中进入项目根目录，直接运行：

```bash
docker compose up -d --build
```

系统将自动下载基础镜像、在镜像内预编译安装 Python 依赖，随后直接拉起容器开始运行。

### 4. 日常维护常用命令
* **查看容器日志**：`docker compose logs -f`
* **停止机器人**：`docker compose down`
* **常规重启机器人**（例如在更新 `.env` 之后）：`docker compose restart`
* **重新构建并启动**（例如在更新代码或修改 `requirements.txt` 之后）：`docker compose up -d --build`
