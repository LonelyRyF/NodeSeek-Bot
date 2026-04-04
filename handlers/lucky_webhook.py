"""
███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

"""
import asyncio
import time
import uuid
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from loguru import logger
from aiohttp import web

from core.config import settings
from core.models import LuckyTask

PLATFORM_DOMAINS = {
    'nodeseek.com': 'nodeseek',
    'deepflood.com': 'deepflood',
}


def _detect_platform(url_str: str) -> str:
    host = urlparse(url_str).hostname or ''
    for domain, platform in PLATFORM_DOMAINS.items():
        if domain in host:
            return platform
    return 'nodeseek'


def create_lucky_webhook_handler(store, engine):
    """工厂函数，返回 aiohttp 路由处理器"""

    async def handler(request: web.Request) -> web.Response:
        if request.headers.get('x-auth-key') != settings.lucky_auth_key:
            return web.json_response({'error': 'unauthorized'}, status=401)

        try:
            body = await request.json()
            url_str = body.get('url', '')
            title = body.get('title', '')

            parsed = urlparse(url_str)
            params = parse_qs(parsed.query)

            post = params.get('post', [None])[0]
            time_str = params.get('time', [None])[0]

            if not post or not time_str:
                return web.json_response({'error': 'invalid_params'}, status=400)

            time_ms = int(time_str)
            count = int(params.get('count', ['1'])[0])
            start = int(params.get('start', ['1'])[0])
            duplicate = params.get('duplicate', ['false'])[0].lower() == 'true'

            # 幂等检查
            existing = store.get_lucky_task_by_post_time(post, time_ms)
            if existing:
                status_msg = 'already_exists' if existing.status == 'pending' else existing.status
                return web.json_response({'success': True, 'message': status_msg, 'id': existing.id})

            task = LuckyTask(
                id=str(uuid.uuid4()),
                post=post,
                title=title or f'帖子 {post}',
                time=time_ms,
                count=count,
                start=start,
                duplicate=duplicate,
                status='pending',
                platform=_detect_platform(url_str),
                created_at=datetime.now().isoformat()
            )
            store.save_lucky_task(task)
            logger.info(f"[Webhook] 新抽奖任务: {task.id} post={post}")

            # 时间已过则立即执行，否则通知管理员
            if time.time() * 1000 >= time_ms:
                asyncio.create_task(engine.run_draw(task))
            else:
                from datetime import timezone, timedelta
                dt = datetime.fromtimestamp(time_ms / 1000, tz=timezone(timedelta(hours=8)))
                time_str_fmt = dt.strftime('%Y-%m-%d %H:%M:%S CST')
                asyncio.create_task(
                    engine.bot.send_message(
                        settings.tg_admin_uid,
                        f"新抽奖任务: {task.title}\n"
                        f"平台: {task.platform}\n"
                        f"开奖时间: {time_str_fmt}\n"
                        f"链接: {url_str}"
                    )
                )

            return web.json_response({'success': True, 'message': 'saved', 'id': task.id})

        except (ValueError, KeyError) as e:
            return web.json_response({'error': f'invalid_request: {e}'}, status=400)
        except Exception as e:
            logger.error(f"[Webhook] 处理异常: {e}", exc_info=True)
            return web.json_response({'error': 'internal_error'}, status=500)

    return handler
