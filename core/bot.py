# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗import asyncio

from loguru import logger
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import ReplyParameters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from core.store import DataStore
from core.code_manager import CodeManager
from core.lucky_engine import LuckyEngine
from api.forum import ForumAPI
from services.forum_poller import ForumPoller
from services.lucky_scheduler import LuckyScheduler
from handlers.admin import setup_admin_handlers
from handlers.guest import setup_guest_handlers


class BotApp:
    """Bot 应用主类"""
    
    def __init__(self):
        self.bot = Bot(token=settings.tg_bot_token)
        self.dp = Dispatcher()
        self.store = DataStore()
        self.code_mgr = CodeManager(self.store)

        proxy = (settings.proxy_host, settings.proxy_port)

        # NodeSeek（必须）
        self.ns = ForumAPI('nodeseek', 'https://www.nodeseek.com',
                           settings.nodeseek_cookies, *proxy)
        self.apis = {'nodeseek': self.ns}

        # DeepFlood（可选）
        if settings.deepflood_cookies:
            self.df = ForumAPI('deepflood', 'https://www.deepflood.com',
                               settings.deepflood_cookies, *proxy)
            self.apis['deepflood'] = self.df

        self.pollers = [ForumPoller(api, self.store, self.code_mgr, self.bot)
                        for api in self.apis.values()]

        self.lucky_engine = LuckyEngine(self.apis, self.store, self.bot, settings.tg_admin_uid)
        self.lucky_scheduler = LuckyScheduler(self.lucky_engine, self.store)

        self.scheduler = AsyncIOScheduler()
        self._webhook_secret = None

        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置消息处理器"""
        setup_admin_handlers(self.dp, self.store, self.bot, self.apis, self.lucky_engine)
        setup_guest_handlers(self.dp, self.store, self.code_mgr, self.bot, self.pollers)
    
    async def startup(self):
        """启动初始化"""
        logger.info("正在启动 Bot...")

        # 验证 cookies 并自动检测各平台 UID
        loop = asyncio.get_event_loop()
        for platform, api in self.apis.items():
            valid = await loop.run_in_executor(None, api.check_cookies)
            if not valid:
                logger.warning(f"[{platform}] cookies 无效，跳过 UID 检测")
                continue
            key = f'{platform}_admin_uid'
            if not self.store.get_config(key):
                uid = await loop.run_in_executor(None, api.get_self_uid)
                if uid:
                    self.store.set_config(key, uid)
                else:
                    logger.warning(f"[{platform}] 无法自动检测 UID，私信验证链接将无法生成")
        
        # 设置 webhook
        if settings.webhook_url:
            await self.bot.set_webhook(
                f"{settings.webhook_url}/webhook",
                secret_token=self._generate_secret()
            )
            logger.info(f"Webhook 已设置: {settings.webhook_url}")
        
        # 启动定时任务
        if not self.scheduler.running:
            # 检查是否已有相同的 job
            for poller in self.pollers:
                try:
                    self.scheduler.remove_job(f'{poller.platform}_poll')
                except Exception:
                    pass
                self.scheduler.add_job(
                    poller.poll,
                    'interval',
                    seconds=settings.poll_interval,
                    id=f'{poller.platform}_poll'
                )
            self.scheduler.add_job(
                self._cleanup_expired,
                'interval',
                hours=1,
                id='cleanup'
            )
            self.scheduler.add_job(
                self.lucky_scheduler.tick,
                'interval',
                minutes=1,
                id='lucky_tick'
            )
            self.scheduler.start()
        
        logger.info("Bot 启动完成")
    
    async def cleanup(self):
        """清理资源"""
        logger.info("正在停止 Bot...")
        
        self.scheduler.shutdown()
        await self.bot.delete_webhook()
        await self.bot.session.close()
        for api in self.apis.values():
            api.close()
        
        logger.info("Bot 已停止")
    
    async def _cleanup_expired(self):
        """定期清理"""
        try:
            self.code_mgr.cleanup_expired()
        except Exception as e:
            logger.error(f"清理异常: {e}")
    
    def _generate_secret(self) -> str:
        """生成 webhook secret（单例）"""
        if not self._webhook_secret:
            import secrets
            self._webhook_secret = secrets.token_urlsafe(32)
        return self._webhook_secret
    
    async def run(self):
        """运行 Bot"""
        if settings.webhook_url:
            # Webhook 模式 - 使用 aiohttp 启动 web 服务
            from aiohttp import web
            
            async def webhook_handler(request):
                """处理 webhook 请求"""
                secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
                if secret != self._generate_secret():
                    return web.Response(text='Unauthorized', status=403)
                
                update = types.Update(**await request.json())
                await self.dp.feed_update(self.bot, update)
                return web.Response(text='OK')
            
            async def health_check(request):
                return web.Response(text='OK')
            
            app = web.Application()
            app.router.add_post('/webhook', webhook_handler)
            app.router.add_get('/health', health_check)

            from handlers.lucky_webhook import create_lucky_webhook_handler
            app.router.add_post('/lucky-webhook', create_lucky_webhook_handler(self.store, self.lucky_engine))
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, settings.host, settings.port)
            await site.start()
            
            logger.info(f"Web 服务已启动: http://{settings.host}:{settings.port}")
            
            # 保持运行
            while True:
                await asyncio.sleep(3600)
        else:
            # Polling 模式
            logger.info("使用 Polling 模式")
            await self.dp.start_polling(self.bot)
