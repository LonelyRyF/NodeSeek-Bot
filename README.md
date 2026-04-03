# Telegram + NodeSeek 验证 Bot

使用 NodeSeek 论坛私信替代人机验证的 Telegram Bot 转发系统。
使用 `curl_cffi` 绕过 Cloudflare 验证。

## 目录结构

```
/opt/tg-nodeseek-bot/
├── main.py                 # 程序入口
├── requirements.txt        # Python 依赖
├── .env.example           # 环境变量模板
├── tg-nodeseek-bot.service # systemd 服务文件
├── core/                  # 核心模块
│   ├── __init__.py
│   ├── bot.py            # 主 Bot 逻辑
│   ├── config.py         # 配置管理
│   ├── models.py         # 数据模型
│   ├── store.py          # 数据存储
│   └── code_manager.py   # 验证码管理
├── api/                   # API 客户端
│   ├── __init__.py
│   ├── telegram.py       # Telegram Bot API
│   └── nodeseek.py       # NodeSeek API (cloudscraper)
└── handlers/              # 消息处理器
    ├── __init__.py
    ├── webhook.py        # Webhook 处理器
    ├── admin.py          # 管理员消息处理
    └── guest.py          # 访客消息处理
```

## 安装

### 1. 安装依赖

```bash
# Debian/Ubuntu
apt update
apt install python3 python3-pip

# 安装 Python 包
pip3 install -r requirements.txt
```

**注意**：`curl_cffi` 需要系统支持，如果安装失败，请查看 [curl_cffi 文档](https://github.com/yifeikong/curl_cffi)。

### 2. 配置环境变量

```bash
cp .env.example .env
nano .env
```

编辑 `.env` 文件：

```bash
# Telegram Bot Token (从 @BotFather 获取)
TG_BOT_TOKEN=your_bot_token_here

# 你的 Telegram ID (给 @userinfobot 发消息获取)
TG_ADMIN_UID=123456789

# NodeSeek Cookies (登录后 F12 复制)
NODESEEK_COOKIES="session=xxx; cf_clearance=xxx; ..."

# NodeSeek 管理员 UID (你的论坛 UID)
NODESEEK_ADMIN_UID=12345

# 代理设置（可选，如果 Cloudflare 拦截则必须配置）
PROXY_HOST=127.0.0.1
PROXY_PORT=10808

# Webhook URL (你的服务器地址)
WEBHOOK_URL=https://your-domain.com

# 服务端口
PORT=8080
```

### 3. 获取 NodeSeek Cookies

1. 登录 NodeSeek 论坛
2. 按 F12 打开开发者工具
3. 切换到 Network (网络) 标签
4. 刷新页面
5. 点击任意请求，找到 Request Headers 中的 `Cookie`
6. 复制整个 Cookie 字符串

### 4. 运行

```bash
# 直接运行
python3 main.py

# 或使用 systemd
sudo cp tg-nodeseek-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tg-nodeseek-bot
sudo systemctl start tg-nodeseek-bot

# 查看日志
sudo journalctl -u tg-nodeseek-bot -f
```

## 使用流程

### 访客验证流程

1. 新访客给 Bot 发消息
2. Bot 回复 6 位验证码
3. 访客登录 NodeSeek 论坛
4. 访客给管理员发送私信，内容为验证码
5. Bot 检测到验证码，自动验证通过
6. 访客收到验证成功通知
7. 之后的消息直接转发给管理员

### 管理员指令

| 指令 | 用法 | 说明 |
|------|------|------|
| 回复消息 | 直接回复 | 发送回复给对应访客 |
| `/block` | 回复消息 + /block | 拉黑该用户 |
| `/unblock` | 回复消息 + /unblock 或 /unblock 123456 | 解封用户 |
| `/clear_ver` | 回复消息 + /clear_ver 或 /clear_ver 123456 | 重置验证 |
| `/stats` | /stats | 查看统计信息 |

## 环境变量说明

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `TG_BOT_TOKEN` | 是 | - | Bot Token |
| `TG_ADMIN_UID` | 是 | - | 管理员 Telegram ID |
| `NODESEEK_COOKIES` | 是 | - | NodeSeek Cookies |
| `NODESEEK_ADMIN_UID` | 是 | - | NodeSeek 管理员 UID |
| `WEBHOOK_URL` | 否 | - | Webhook URL |
| `PORT` | 否 | 8080 | 服务端口 |
| `HOST` | 否 | 0.0.0.0 | 监听地址 |
| `DATA_FILE` | 否 | /var/lib/... | 数据文件路径 |
| `POLL_INTERVAL` | 否 | 30 | 轮询间隔(秒) |
| `VERIFICATION_TTL` | 否 | 2592000 | 验证有效期(秒) |
| `CODE_LENGTH` | 否 | 6 | 验证码长度 |
| `PROXY_HOST` | 否 | - | SOCKS5 代理主机 |
| `PROXY_PORT` | 否 | - | SOCKS5 代理端口 |

## 注意事项

1. **Cookies 有效期**：NodeSeek 的 Cookies 可能会过期，需要定期更新
2. **Cloudflare 防护**：
   - 使用 `curl_cffi` 模拟真实浏览器 TLS 指纹，绕过 Cloudflare
   - 如果直连被拦截，请配置 `PROXY_HOST` 和 `PROXY_PORT`
   - 推荐使用住宅 IP 代理，数据中心 IP 可能被 Cloudflare 拦截
3. **数据持久化**：数据存储在 JSON 文件中，建议定期备份
4. **安全性**：妥善保管 `.env` 文件，不要泄露 Cookies 和 Bot Token
