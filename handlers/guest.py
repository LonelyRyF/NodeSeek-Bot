"""
访客消息处理器 - aiogram 3.x 版本
"""
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.store import DataStore
from core.code_manager import CodeManager

logger = logging.getLogger(__name__)


class GuestHandlers:
    """访客消息处理器"""
    
    def __init__(self, store: DataStore, code_mgr: CodeManager, bot: Bot):
        self.store = store
        self.code_mgr = code_mgr
        self.bot = bot
    
    def register(self, dp: Dispatcher):
        """注册处理器"""
        # 访客消息（非管理员）
        dp.message.register(
            self.handle_guest_message,
            F.chat.id != int(settings.tg_admin_uid)
        )
        # 立即验证按钮回调
        dp.callback_query.register(
            self.handle_verify_now,
            F.data == "verify_now"
        )
    
    async def handle_guest_message(self, message: types.Message):
        """处理访客消息"""
        chat_id = str(message.chat.id)
        
        # 检查黑名单
        if self.store.is_blocked(chat_id):
            await message.answer('🚫 您已被管理员拉黑，无法发送消息。')
            return
        
        # 检查是否已验证
        if self.store.is_verified(chat_id):
            await self._forward_to_admin(message, chat_id)
        else:
            await self._send_verification_request(message, chat_id)
    
    async def _forward_to_admin(self, message: types.Message, chat_id: str):
        """转发消息给管理员"""
        try:
            forwarded = await message.forward(settings.tg_admin_uid)
            self.store.save_msg_mapping(forwarded.message_id, chat_id)
            logger.info(f"消息已转发: {chat_id} -> {forwarded.message_id}")
        except Exception as e:
            logger.error(f"转发消息失败: {e}")
            await message.answer(f'❌ 发送失败: {e}')
    
    async def _send_verification_request(self, message: types.Message, chat_id: str):
        """发送验证请求"""
        # 生成验证码
        code = self.code_mgr.generate(chat_id)
        
        # 私信链接
        pm_link = f"https://www.nodeseek.com/notification#/message?mode=talk&to={settings.nodeseek_admin_uid}"
        
        msg = f'''🛡️ 为了防止垃圾消息，请先完成验证：

<b>验证步骤：</b>
1. <a href="{pm_link}">点击这里发送私信给管理员</a>

2. 在私信中发送以下验证码：

<code>{code}</code>

3. 等待系统自动验证通过或点击下方按钮立即验证...

⏰ 验证码有效期：30 天
💡 提示：复制上面的验证码，在论坛私信中粘贴发送即可'''
        
        # 创建内联按钮
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ 立即验证", callback_data="verify_now")]
        ])
        
        try:
            await message.answer(
                msg,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            logger.info(f"已发送验证码给 {chat_id}")
        except Exception as e:
            logger.error(f"发送验证码失败: {e}")
            await message.answer(f'❌ 发送失败: {e}')
    
    async def handle_verify_now(self, callback: types.CallbackQuery):
        """处理立即验证按钮"""
        chat_id = str(callback.from_user.id)
        
        # 检查是否已验证
        if self.store.is_verified(chat_id):
            await callback.answer("✅ 您已验证通过！", show_alert=True)
            return
        
        # 触发一次轮询检查
        await callback.answer("🔄 正在检查验证状态...", show_alert=False)
        
        # 导入 NodeSeekPoller 并手动触发一次轮询
        from services.nodeseek_poller import NodeSeekPoller
        from api.nodeseek import NodeSeekAPI
        
        api = NodeSeekAPI()
        poller = NodeSeekPoller(api, self.store, self.code_mgr, self.bot)
        await poller.poll()
        
        # 再次检查验证状态
        if self.store.is_verified(chat_id):
            await callback.message.answer("✅ 验证成功！您现在可以发送消息了。")
        else:
            await callback.message.answer(
                "⚠️ 还未检测到验证消息，请确认：\n"
                "1. 已在 NodeSeek 论坛发送私信\n"
                "2. 验证码填写正确\n"
                "3. 稍等片刻后再次点击验证按钮"
            )


def setup_guest_handlers(dp: Dispatcher, store: DataStore, code_mgr: CodeManager, bot: Bot):
    """设置访客处理器"""
    handlers = GuestHandlers(store, code_mgr, bot)
    handlers.register(dp)
