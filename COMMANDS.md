# 命令列表

## 管理员命令

这些命令只有管理员（`TG_ADMIN_UID`）可以使用。

### 基本操作

| 命令 | 用法 | 说明 |
|------|------|------|
| 直接回复 | 回复用户消息 + 输入内容 | 发送消息给对应的访客 |

### 管理指令

| 命令 | 用法 | 说明 |
|------|------|------|
| `/block` | 回复消息 + `/block` | 拉黑该用户，用户无法再发送消息 |
| `/unblock` | 回复消息 + `/unblock` 或 `/unblock 123456` | 解封用户，允许用户重新发送消息 |
| `/clear_ver` | 回复消息 + `/clear_ver` 或 `/clear_ver 123456` | 重置用户验证状态，用户需要重新验证 |
| `/stats` | `/stats` | 查看统计信息（已验证用户数、待验证码数等） |

### 帮助

| 命令 | 用法 | 说明 |
|------|------|------|
| 任意文本 | 发送任意消息 | 显示帮助信息 |

## 访客命令

访客（非管理员）没有特殊命令，只需要：

1. 给 Bot 发送任意消息
2. 如果未验证，Bot 会发送验证码
3. 访客需要在 NodeSeek 论坛私信中发送验证码
4. 验证成功后，访客的消息会自动转发给管理员

## 系统命令

这些是系统级别的命令，不是 Telegram Bot 命令。

### 部署相关

| 命令 | 说明 |
|------|------|
| `python3 deploy-check.py` | 部署前检查（检查环境、依赖、配置） |
| `python3 test-config.py` | 配置验证测试 |
| `python3 main.py` | 直接运行 Bot（用于测试） |

### 系统服务

| 命令 | 说明 |
|------|------|
| `sudo systemctl start tg-nodeseek-bot` | 启动服务 |
| `sudo systemctl stop tg-nodeseek-bot` | 停止服务 |
| `sudo systemctl restart tg-nodeseek-bot` | 重启服务 |
| `sudo systemctl status tg-nodeseek-bot` | 查看服务状态 |
| `sudo journalctl -u tg-nodeseek-bot -f` | 查看实时日志 |

## 使用流程示例

### 访客验证流程

```
访客: 你好
Bot: 🛡️ 为了防止垃圾消息，请先完成验证...
     验证码: ABC123

访客在 NodeSeek 论坛私信中发送: ABC123

Bot 检测到验证码，自动验证
Bot: ✅ 验证成功！您现在可以发送消息了呢~

访客: 我想咨询一个问题
Bot 转发给管理员

管理员: 我来帮你解答...
Bot 转发给访客
```

### 管理员操作示例

```
管理员收到访客消息后，可以：

1. 直接回复 → 消息转发给访客
2. /block → 拉黑该用户
3. /unblock 123456 → 解封用户 123456
4. /clear_ver 123456 → 重置用户 123456 的验证
5. /stats → 查看统计信息
```

## 配置相关

### 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `TG_BOT_TOKEN` | 是 | Telegram Bot Token |
| `TG_ADMIN_UID` | 是 | 管理员 Telegram ID |
| `NODESEEK_COOKIES` | 是 | NodeSeek 登录 Cookies |
| `NODESEEK_ADMIN_UID` | 是 | NodeSeek 管理员 UID |
| `WEBHOOK_URL` | 否 | Webhook 地址（用于生产环境） |
| `PORT` | 否 | 服务端口（默认 8080） |
| `HOST` | 否 | 监听地址（默认 0.0.0.0） |
| `POLL_INTERVAL` | 否 | 轮询间隔秒数（默认 30） |
| `VERIFICATION_TTL` | 否 | 验证有效期秒数（默认 30 天） |
| `CODE_LENGTH` | 否 | 验证码长度（默认 6） |
| `DATA_FILE` | 否 | 数据文件路径 |

## 快速参考

### 启动 Bot

```bash
# 开发模式（直接运行）
python3 main.py

# 生产模式（systemd 服务）
sudo systemctl start tg-nodeseek-bot
```

### 查看日志

```bash
# 实时日志
sudo journalctl -u tg-nodeseek-bot -f

# 最近 100 行
sudo journalctl -u tg-nodeseek-bot -n 100

# 特定时间
sudo journalctl -u tg-nodeseek-bot --since "1 hour ago"
```

### 常见操作

```bash
# 检查配置
python3 test-config.py

# 部署前检查
python3 deploy-check.py

# 查看服务状态
sudo systemctl status tg-nodeseek-bot

# 查看统计信息（在 Telegram 中）
/stats
```
