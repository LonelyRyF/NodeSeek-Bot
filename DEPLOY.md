# 部署指南

## 前置要求

- Python 3.8+
- pip 包管理器
- systemd (用于服务管理)
- 一个 Telegram Bot Token (从 @BotFather 获取)
- NodeSeek 论坛账号和 Cookies

## 部署步骤

### 1. 环境准备

```bash
# 克隆或下载项目
cd /opt/tg-nodeseek-bot

# 安装依赖
pip install -r requirements.txt

# 创建数据目录
sudo mkdir -p /var/lib/tg-nodeseek-bot
sudo chown $USER:$USER /var/lib/tg-nodeseek-bot
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
nano .env
```

编辑 `.env` 文件，填写以下信息：

| 配置项 | 说明 | 获取方式 |
|--------|------|--------|
| `TG_BOT_TOKEN` | Telegram Bot Token | 给 @BotFather 发 `/newbot` |
| `TG_ADMIN_UID` | 你的 Telegram ID | 给 @userinfobot 发消息 |
| `NODESEEK_COOKIES` | NodeSeek 登录 Cookies | 登录后 F12 → Network → 复制 Cookie |
| `NODESEEK_ADMIN_UID` | 你的 NodeSeek UID | 论坛个人资料页面 URL 中的数字 |
| `WEBHOOK_URL` | (可选) Webhook 地址 | 你的服务器域名，如 `https://example.com` |
| `PORT` | (可选) 服务端口 | 默认 8080 |

### 3. 部署前检查

```bash
# 运行检查脚本
python3 deploy-check.py
```

如果所有检查都通过，继续下一步。

### 4. 测试运行

```bash
# 直接运行 Bot（测试）
python3 main.py
```

如果看到日志输出且没有错误，说明配置正确。按 `Ctrl+C` 停止。

### 5. 安装为系统服务

```bash
# 复制 systemd 服务文件
sudo cp tg-nodeseek-bot.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务（开机自启）
sudo systemctl enable tg-nodeseek-bot

# 启动服务
sudo systemctl start tg-nodeseek-bot

# 查看服务状态
sudo systemctl status tg-nodeseek-bot

# 查看实时日志
sudo journalctl -u tg-nodeseek-bot -f
```

### 6. 验证部署

```bash
# 检查服务是否运行
sudo systemctl is-active tg-nodeseek-bot

# 查看最近的日志
sudo journalctl -u tg-nodeseek-bot -n 50
```

## 常见问题

### Bot 无法启动

**症状：** `systemctl status tg-nodeseek-bot` 显示 failed

**解决：**
1. 检查日志：`sudo journalctl -u tg-nodeseek-bot -n 100`
2. 检查 `.env` 文件配置是否正确
3. 检查 Python 依赖是否安装完整

### 验证码无法验证

**症状：** 用户发送验证码后没有反应

**解决：**
1. 检查 NodeSeek Cookies 是否过期（需要重新获取）
2. 检查 `NODESEEK_ADMIN_UID` 是否正确
3. 查看日志中是否有错误信息

### Webhook 无法连接

**症状：** Telegram 无法连接到 Webhook

**解决：**
1. 确保 `WEBHOOK_URL` 配置正确
2. 确保防火墙允许 8080 端口（或配置的端口）
3. 使用 `curl` 测试连接：`curl https://your-domain.com/health`

## 更新和维护

### 更新代码

```bash
# 停止服务
sudo systemctl stop tg-nodeseek-bot

# 更新代码
git pull origin main

# 安装新依赖（如果有）
pip install -r requirements.txt

# 启动服务
sudo systemctl start tg-nodeseek-bot
```

### 查看日志

```bash
# 实时日志
sudo journalctl -u tg-nodeseek-bot -f

# 查看最近 100 行
sudo journalctl -u tg-nodeseek-bot -n 100

# 查看特定时间的日志
sudo journalctl -u tg-nodeseek-bot --since "2 hours ago"
```

### 重启服务

```bash
sudo systemctl restart tg-nodeseek-bot
```

### 停止服务

```bash
sudo systemctl stop tg-nodeseek-bot
```

## 数据备份

数据存储在 `/var/lib/tg-nodeseek-bot/data.json`，建议定期备份：

```bash
# 手动备份
sudo cp /var/lib/tg-nodeseek-bot/data.json /backup/data.json.$(date +%Y%m%d)

# 或使用 cron 定时备份
# 编辑 crontab
sudo crontab -e

# 添加每天凌晨 2 点备份
0 2 * * * cp /var/lib/tg-nodeseek-bot/data.json /backup/data.json.$(date +\%Y\%m\%d)
```

## 获取帮助

如有问题，请查看：
- 日志文件：`sudo journalctl -u tg-nodeseek-bot -f`
- README.md：项目说明文档
- 代码注释：各模块的详细说明
