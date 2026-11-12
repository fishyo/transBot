# transBot 代码审查问题记录与追踪清单

> 本文档用于系统性记录 transBot 项目在代码审查（Code Review）中识别出的设计缺陷、安全隐患、性能瓶颈与架构技术债，并持续跟踪各条目的整改状态。

---

## 缺陷与改进追踪总表

| 问题编号 | 分类 | 摘要 | 严重程度 | 状态 | 关联文件 |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **SEC-01** | 安全性 | `check_user` 鉴权空白名单越权漏洞（默认完全放行未授权用户） | 🔴 严重 | ✅ 已修复 | `bot/handlers.py` |
| **SEC-02** | 健壮性 | 消息解析模式混合使用 Markdown 与 HTML，易因未转义字符报错崩溃 | 🟡 中度 | ✅ 已修复 | `bot/handlers.py` |
| **UX-01** | 交互体验 | 缺少 Telegram 客户端原生左下角命令菜单注册 (`set_my_commands`) | 🟡 中度 | ✅ 已优化 | `main.py` |
| **UX-02** | 交互体验 | `/manage` 管理列表任务上限被死锁在 15 个，缺少分类过滤与分页 | 🟡 中度 | ✅ 已优化 | `bot/handlers.py` |
| **UX-03** | 交互体验 | `/status` 状态面板缺少联动快捷操作按钮（管理、海龟模式、目录） | 🟢 轻度 | ✅ 已优化 | `bot/handlers.py` |
| **PERF-01** | 性能 | `asyncio` 事件循环内执行同步阻塞 I/O (`transmission-rpc`, `os.listdir`, `shutil`) | 🟠 较高 | 📋 待处理 | `bot/handlers.py`, `bot/transmission.py` |
| **PERF-02** | 性能 | `TransmissionWrapper` 每次方法调用重新实例化 Client，缺少连接复用与超时 | 🟡 中度 | 📋 待处理 | `bot/transmission.py` |
| **ARCH-01** | 架构设计 | `handlers.py` 文件膨胀达 1200+ 行，业务逻辑、UI 渲染、工具函数严重耦合 | 🟡 中度 | 📋 待处理 | `bot/handlers.py` |
| **ENV-01** | 跨平台 | `/downloads` 路径全局硬编码，Windows 本地调试及自定义容器挂载路径受限 | 🟡 中度 | 📋 待处理 | `bot/handlers.py`, `bot/config.py` |
| **DEPS-01** | 工程规范 | `requirements.txt` 混入开发依赖 `pytest`；`docker-compose.yml` 包含宿主机特定 UUID | 🟢 轻度 | 📋 待处理 | `requirements.txt`, `docker-compose.yml` |
| **DATA-01** | 数据持久化 | `storage.json` 已完成种子哈希集合无淘汰清理机制，可能无界膨胀 | 🟢 轻度 | 📋 待处理 | `bot/storage.py` |

---

## 详细问题分析与解决方案

### 1. [SEC-01] `check_user` 鉴权空白名单越权漏洞
- **严重级别**：🔴 严重 (High)
- **位置**：`bot/handlers.py` (L33-L45)
- **描述**：
  原代码逻辑使用 `if config.ALLOWED_USER_IDS and user_id not in config.ALLOWED_USER_IDS:`。当使用者未设置或遗漏配置 `ALLOWED_USER_IDS` 时，条件直接为假并跳过鉴权，导致公网任意用户均可向该 Bot 下发下载、删除文件等指令。
- **解决方案**：
  改为严格默认拒绝策略：`if not config.ALLOWED_USER_IDS or user_id not in config.ALLOWED_USER_IDS:`，确保只有显式列入白名单的用户 ID 才能访问。

### 2. [UX-01] Telegram 原生命令菜单注册
- **严重级别**：🟡 中度
- **位置**：`main.py`
- **描述**：
  未向 Telegram Bot API 注册 `BotCommand`，用户输入 `/` 时无法查看命令提示与中文释义。
- **解决方案**：
  在应用启动钩子 `on_startup` 中调用 `await application.bot.set_my_commands(...)` 注册常用指令。

### 3. [UX-02 & UX-03] 操作菜单与任务管理中心体验升级
- **严重级别**：🟡 中度
- **位置**：`bot/handlers.py`
- **描述**：
  - `/start` 仅输出静态文本，缺乏快捷交互入口。
  - `/status` 仅提供单个刷新按钮。
  - `/manage` 仅硬编码截取前 15 个任务，任务较多时后面的种子完全无法查看或管理，且缺乏按状态筛选功能。
- **解决方案**：
  - 升级 `/start` 为仪表盘面板，增加功能快捷入口。
  - `/status` 增加直达【任务管理】、【切换海龟模式】、【目录设置】等按钮。
  - 重构 `/manage`，增加状态过滤标签（全部 / 下载中 / 已暂停 / 已完成）与动态分页控制（每页 8 个），且在详情卡片返回时记忆当前分页与过滤状态。

### 4. [PERF-01 & PERF-02] 异步事件循环阻塞与 RPC 客户端优化
- **严重级别**：🟠 较高
- **位置**：`bot/transmission.py`, `bot/handlers.py`
- **描述**：
  `transmission-rpc` 底层为同步阻塞式 HTTP 请求，且多处调用了阻塞型文件系统 I/O (`os.listdir`, `shutil.disk_usage`)。在 NAS 磁盘唤醒或网络微卡时会直接冻结 Telegram Bot 协程调度。同时客户端缺少单例连接池复用与超时设置。
- **后续改造方案**：
  - 引入 `asyncio.to_thread` 封装磁盘 I/O 与 RPC 操作。
  - 将 `TransmissionWrapper` 改造为单例长连接并配置 `timeout=10`。

### 5. [ARCH-01] 拆分 `handlers.py`
- **严重级别**：🟡 中度
- **位置**：`bot/handlers.py`
- **描述**：
  1200+ 行的大文件阻碍代码维护与测试。
- **后续改造方案**：
  拆分为 `bot/utils/`、`bot/ui/` 以及独立的子业务 handler。
