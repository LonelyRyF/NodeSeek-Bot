"""
主 Bot 逻辑 - 使用 aiogram 3.x
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import ReplyParameters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from core.store import DataStore
from core.code_manager import CodeManager
# 延迟导入，避免循环依赖
# from api.nodeseek import NodeSeekAPI
from services.nodeseek_poller import NodeSeekPoller
from handlers.admin import setup_admin_handlers
from handlers.guest import setup_guest_handlers

logger = logging.getLogger(__name__)


class BotApp:
    """Bot 应用主类"""
    
    def __init__(self):
        self.bot = Bot(token=settings.tg_bot_token)
        self.dp = Dispatcher()
        self.store = DataStore()
        self.code_mgr = CodeManager(self.store)
        
        # 延迟导入，避免循环依赖
        from api.nodeseek import NodeSeekAPI
        self.ns = NodeSeekAPI()
        
        self.scheduler = AsyncIOScheduler()
        self.poller = NodeSeekPoller(self.ns, self.store, self.code_mgr, self.bot)
        self._webhook_secret = None
        
        # 注册处理器
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置消息处理器"""
        setup_admin_handlers(self.dp, self.store, self.bot)
        setup_guest_handlers(self.dp, self.store, self.code_mgr, self.bot)
    
    async def startup(self):
        """启动初始化"""
        logger.info("正在启动 Bot...")
        
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
            try:
                self.scheduler.remove_job('nodeseek_poll')
            except:
                pass
            
            try:
                self.scheduler.remove_job('cleanup')
            except:
                pass
            
            self.scheduler.add_job(
                self.poller.poll,
                'interval',
                seconds=settings.poll_interval,
                id='nodeseek_poll'
            )
            self.scheduler.add_job(
                self._cleanup_expired,
                'interval',
                hours=1,
                id='cleanup'
            )
            self.scheduler.start()
        
        logger.info("Bot 启动完成")
    
    async def cleanup(self):
        """清理资源"""
        logger.info("正在停止 Bot...")
        
        self.scheduler.shutdown()
        await self.bot.delete_webhook()
        await self.bot.session.close()
        self.ns.close()
        self.store.close()
        
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
        await self.startup()
        
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
