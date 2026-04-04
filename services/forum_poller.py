"""
███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

"""
from typing import Set, TYPE_CHECKING

from loguru import logger
from aiogram import Bot

if TYPE_CHECKING:
    from api.forum import ForumAPI

from core.store import DataStore
from core.code_manager import CodeManager


class ForumPoller:
    """论坛私信轮询器"""

    def __init__(self, api: 'ForumAPI', store: DataStore, code_mgr: CodeManager, bot: Bot):
        self.api = api
        self.platform = api.platform
        self.store = store
        self.code_mgr = code_mgr
        self.bot = bot
        self.processed_messages: Set[int] = set()

    async def poll(self):
        if not self.store.has_pending_codes():
            logger.debug(f"[{self.platform}] 无待验证码，跳过轮询")
            return

        try:
            logger.info(f"[{self.platform}] 正在轮询私信...")
            messages = self.api.get_messages()
            for msg in messages:
                await self._process_message(msg)
        except Exception as e:
            logger.error(f"[{self.platform}] 轮询异常: {e}", exc_info=True)

    async def _process_message(self, msg: dict):
        msg_id = msg.get('id')
        if msg_id in self.processed_messages:
            return

        try:
            sender_id = msg.get('sender_id')
            sender_name = msg.get('sender_name', '未知用户')
            content = msg.get('content', '').strip().upper()

            logger.info(f"[{self.platform}] 处理私信 {msg_id}: {sender_name} ({sender_id})")

            tg_uid, error = self.code_mgr.verify(content, forum_uid=sender_id,
                                                  platform=self.platform)

            if tg_uid:
                logger.info(f"[{self.platform}] 验证成功: tg={tg_uid} forum={sender_id}")
            elif error:
                await self._send_error(self._get_tg_uid(content), error)

            self.processed_messages.add(msg_id)
            await self._mark_viewed([msg_id])

        except Exception as e:
            logger.error(f"[{self.platform}] 处理私信异常 {msg_id}: {e}", exc_info=True)

    def _get_tg_uid(self, code: str):
        vcode = self.store.get_code(code)
        return vcode.tg_uid if vcode else None

    async def _send_error(self, tg_uid, error: str):
        if not tg_uid:
            return
        messages = {
            'invalid_code': '❌ 验证码无效，请检查是否输入正确。',
            'code_used': '❌ 该验证码已被使用，请重新获取。',
            'account_bound': f'❌ 您的 {self.platform} 账号已绑定其他 Telegram 账号。',
        }
        try:
            await self.bot.send_message(tg_uid, messages.get(error, '❌ 验证失败，请稍后重试。'))
        except Exception as e:
            logger.error(f"发送错误通知失败: {e}")

    async def _mark_viewed(self, message_ids: list):
        try:
            self.api.mark_viewed(message_ids)
        except Exception as e:
            logger.warning(f"[{self.platform}] 标记已读失败: {e}")


# 向后兼容别名
NodeSeekPoller = ForumPoller
