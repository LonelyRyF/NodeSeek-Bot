# NodeSeek-Bot

一个面向 Telegram 的 NodeSeek / DeepFlood 论坛桥接与自动化机器人，集成了访客验证、私聊转发、论坛签到、Lucky 抽奖任务和 RSS 推送等能力。

## 功能概览

- Telegram 私聊转发给管理员
- 通过论坛站内信验证码完成账号绑定
- 支持 NodeSeek，按配置可选支持 DeepFlood
- 管理员面板与命令系统
- 论坛签到与随机鸡腿开关
- Lucky 抽奖任务接收、调度和开奖
- RSS 关键词/版块过滤推送
- 支持 Webhook / Polling 两种运行模式

## 项目结构

```text
.
├── main.py
├── api/
├── core/
├── handlers/
├── services/
├── data/
├── logs/
├── lucky.user.js
├── Dockerfile
└── docker-compose.yml
```

主要目录说明：

- `api/`：论坛接口、RSS 解析、Drand 随机数获取
- `core/`：配置、存储、验证码管理、抽奖引擎、机器人启动
- `handlers/`：管理员、访客和 Webhook 处理逻辑
- `services/`：论坛私信轮询、RSS 轮询、抽奖调度
- `data/`：本地持久化数据目录
- `logs/`：运行日志目录

## 运行要求

- Python 3.11
- 可用的 Telegram Bot Token
- Telegram 管理员用户 ID
- NodeSeek 登录 Cookies
- 如需启用 DeepFlood，则额外提供 DeepFlood Cookies

## 配置

项目通过 `.env` 读取配置，至少需要以下内容：

```env
TG_BOT_TOKEN=your_bot_token
TG_ADMIN_UID=your_telegram_uid
NODESEEK_COOKIES=your_nodeseek_cookies
```

常用可选配置：

```env
DEEPFLOOD_COOKIES=
WEBHOOK_URL=
HOST=0.0.0.0
PORT=8080
POLL_INTERVAL=30
RSS_POLL_INTERVAL=60
LUCKY_AUTH_KEY=
PROXY_HOST=
PROXY_PORT=0
LOG_LEVEL=INFO
```

## 部署

### 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

启动后会自动创建并使用：

- `data/`
- `logs/`

### Docker Compose

```bash
docker compose up -d --build
```

项目默认会挂载以下目录：

- `./data:/app/data`
- `./logs:/app/logs`

### Webhook 模式

设置 `WEBHOOK_URL=https://your-domain.com` 后，程序会启用 Web 服务并暴露：

- `POST /webhook`
- `GET /health`
- `POST /lucky-webhook`

如果不设置 `WEBHOOK_URL`，则自动使用 Polling 模式。

## 使用说明

### 用户验证流程

1. 用户私聊机器人
2. 机器人返回验证码和论坛私信入口
3. 用户将验证码发送到论坛站内信
4. 系统轮询论坛私信并自动完成绑定
5. 验证完成后，用户消息会被转发给管理员

### 管理员功能

管理员侧主要命令：

- `/start`
- `/help`
- `/messenger`
- `/checkin`
- `/lottery`
- `/rss`

### Lucky 抽奖 Webhook

项目支持向 `/lucky-webhook` 提交抽奖任务，请求头需要携带：

```http
x-auth-key: <LUCKY_AUTH_KEY>
```

仓库附带 `lucky.user.js`，可用于在 NodeSeek 帖子页面直接推送 Lucky 链接到后端。

### RSS 推送

RSS 支持：

- 自动轮询
- 手动轮询
- 版块过滤
- 关键词过滤
- 推送历史记录
- RSS 源固定为 `https://rss.nodeseek.com`

## 数据与日志

项目默认使用以下本地目录：

- `data/`：保存验证码、用户绑定状态、消息映射、黑名单、抽奖任务、RSS 配置与历史
- `logs/`：保存运行日志，当前日志文件为 `logs/latest.log`

## 许可证

本项目采用 [MIT License](./LICENSE) 开源发布。

## 致谢与代码说明

本项目中的 **RSS 相关实现参考并借鉴了** 以下项目的代码与思路：

- https://github.com/AI-XMLY/nodeseek-rss-telegram-bot

如果你在使用或分发本项目，建议同时关注并遵守上述项目的开源许可证要求。

另外，`core/lucky_engine.py` 中的抽奖随机排序逻辑包含“算法移植”实现。

## 注意事项

- Forum Cookies 失效会影响验证、签到、私信轮询和抽奖数据读取
- DeepFlood 只有在配置 `DEEPFLOOD_COOKIES` 后才会启用
- Webhook 模式需要公网 HTTPS 地址
- Lucky Webhook 需要正确配置 `LUCKY_AUTH_KEY`
