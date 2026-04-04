# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗from loguru import logger

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.store import DataStore
from core.code_manager import CodeManager

# 平台配置：(store_key, 显示名, 私信 URL 模板)
PLATFORMS = [
    ('nodeseek_admin_uid', 'NodeSeek',
     'https://www.nodeseek.com/notification#/message?mode=talk&to={uid}'),
    ('deepflood_admin_uid', 'DeepFlood',
     'https://www.deepflood.com/notification#/message?mode=talk&to={uid}'),
]


class GuestHandlers:
    """访客消息处理器"""

    def __init__(self, store: DataStore, code_mgr: CodeManager, bot: Bot, pollers: list):
        self.store = store
        self.code_mgr = code_mgr
        self.bot = bot
        self.pollers = pollers

    def register(self, dp: Dispatcher):
        """注册处理器"""
        dp.message.register(
            self.handle_guest_message,
            F.chat.id != int(settings.tg_admin_uid)
        )
        dp.callback_query.register(
            self.handle_verify_now,
            F.data == "verify_now"
        )

    def _get_pm_links(self) -> list[tuple[str, str]]:
        """返回已配置平台的 [(显示名, pm_url), ...]"""
        links = []
        for key, name, url_tpl in PLATFORMS:
            uid = self.store.get_config(key)
            if uid:
                links.append((name, url_tpl.format(uid=uid)))
        return links

    async def handle_guest_message(self, message: types.Message):
        """处理访客消息"""
        chat_id = str(message.chat.id)

        if self.store.is_blocked(chat_id):
            await message.answer('🚫 您已被管理员拉黑，无法发送消息。')
            return

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
        code = self.code_mgr.generate(chat_id)
        pm_links = self._get_pm_links()

        if not pm_links:
            await message.answer('⚠️ 验证系统尚未就绪，请稍后再试。')
            return

        buttons = []

        if len(pm_links) == 1:
            # 单平台：直接给 URL 按钮，不需要选择
            name, url = pm_links[0]
            buttons.append([InlineKeyboardButton(text=f'📨 {name} 私信', url=url)])
            platform_hint = f'在 {name} 论坛'
        else:
            # 多平台：每个平台一个 URL 按钮供选择
            buttons.append([
                InlineKeyboardButton(text=f'📨 {name}', url=url)
                for name, url in pm_links
            ])
            platform_hint = '在任意已配置的论坛'

        buttons.append([InlineKeyboardButton(text='✅ 立即验证', callback_data='verify_now')])

        msg = (
            f'🛡️ 请先完成验证：\n\n'
            f'<b>验证步骤：</b>\n'
            f'1. 点击下方按钮，{platform_hint}发送私信\n'
            f'2. 私信内容填写以下验证码：\n\n'
            f'<code>{code}</code>\n\n'
            f'3. 发送后点击「立即验证」或等待系统自动检测\n\n'
            f'⏰ 验证码有效期：30 天'
        )

        try:
            await message.answer(
                msg,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
            logger.info(f"已发送验证码给 {chat_id}")
        except Exception as e:
            logger.error(f"发送验证码失败: {e}")
            await message.answer(f'❌ 发送失败: {e}')

    async def handle_verify_now(self, callback: types.CallbackQuery):
        """处理立即验证按钮"""
        chat_id = str(callback.from_user.id)

        if self.store.is_verified(chat_id):
            await callback.answer('✅ 您已验证通过！', show_alert=True)
            return

        await callback.answer('🔄 正在检查验证状态...', show_alert=False)

        for poller in self.pollers:
            await poller.poll()

        if self.store.is_verified(chat_id):
            await callback.message.answer('✅ 验证成功！您现在可以发送消息了。')
        else:
            await callback.message.answer(
                '⚠️ 还未检测到验证消息，请确认：\n'
                '1. 已在论坛发送私信\n'
                '2. 验证码填写正确\n'
                '3. 稍等片刻后再次点击验证按钮'
            )


def setup_guest_handlers(dp: Dispatcher, store: DataStore, code_mgr: CodeManager,
                         bot: Bot, pollers: list):
    """设置访客处理器"""
    handlers = GuestHandlers(store, code_mgr, bot, pollers)
    handlers.register(dp)
