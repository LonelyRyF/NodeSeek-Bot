"""
NodeSeek 私信轮询服务
定期检查 NodeSeek 私信，自动验证访客
"""
import logging
from typing import Set, TYPE_CHECKING

from aiogram import Bot
from aiogram.enums import ParseMode

# 延迟导入，避免循环依赖
if TYPE_CHECKING:
    from api.nodeseek import NodeSeekAPI

from core.store import DataStore
from core.code_manager import CodeManager

logger = logging.getLogger(__name__)


class NodeSeekPoller:
    """NodeSeek 私信轮询器"""
    
    def __init__(self, ns_api: "NodeSeekAPI", store: DataStore, code_mgr: CodeManager, bot: Bot):
        self.ns = ns_api
        self.store = store
        self.code_mgr = code_mgr
        self.bot = bot
        self.processed_messages: Set[int] = set()
    
    async def poll(self):
        """轮询 NodeSeek 私信"""
        try:
            logger.info("正在轮询 NodeSeek 私信...")
            messages = self.ns.get_messages()
            logger.info(f"获取到 {len(messages)} 条私信")
            
            if not messages:
                logger.debug("没有新私信")
                return
            
            for msg in messages:
                await self._process_message(msg)
        
        except Exception as e:
            logger.error(f"轮询异常: {e}", exc_info=True)
    
    async def _process_message(self, msg: dict):
        """处理单条私信"""
        msg_id = msg.get('id')
        if msg_id in self.processed_messages:
            logger.debug(f"私信 {msg_id} 已处理过")
            return
        
        try:
            sender_id = msg.get('sender_id')
            sender_name = msg.get('sender_name', '未知用户')
            content = msg.get('content', '').strip().upper()
            
            logger.info(f"处理私信 {msg_id}: 来自 {sender_name} ({sender_id}), 内容: {content[:20]}")
            
            # 尝试验证
            tg_uid, error = self.code_mgr.verify(content, nodeseek_uid=sender_id)
            
            if tg_uid:
                logger.info(f"验证成功: {tg_uid} (NS: {sender_id})")
            elif error:
                # 发送错误提示给用户
                await self._send_error_notification(tg_uid or self._get_tg_uid_from_code(content), error)
                logger.debug(f"验证失败: {content}, 原因: {error}")
            
            self.processed_messages.add(msg_id)
            
            # 标记已读
            await self._mark_viewed([msg_id])
        
        except Exception as e:
            logger.error(f"处理私信异常 {msg_id}: {e}", exc_info=True)
    
    def _get_tg_uid_from_code(self, code: str) -> str:
        """从验证码获取对应的 TG UID"""
        vcode = self.store.get_code(code)
        return vcode.tg_uid if vcode else None
    
    async def _send_error_notification(self, tg_uid: str, error: str):
        """发送错误通知给用户"""
        if not tg_uid:
            return
        
        error_messages = {
            "invalid_code": "❌ 验证码无效，请检查是否输入正确。",
            "code_used": "❌ 该验证码已被使用过，请重新获取验证码。",
            "account_bound": "❌ 您的 NodeSeek 账号已绑定其他 Telegram 账号，一个 NodeSeek 账号只能绑定一个 Telegram 账号。"
        }
        
        msg = error_messages.get(error, "❌ 验证失败，请稍后重试。")
        
        try:
            await self.bot.send_message(tg_uid, msg)
            logger.info(f"已发送错误通知给 {tg_uid}: {error}")
        except Exception as e:
            logger.error(f"发送错误通知失败: {e}")
    
    async def _mark_viewed(self, message_ids: list):
        """标记私信已读"""
        try:
            self.ns.mark_viewed(message_ids)
            logger.debug(f"已标记 {len(message_ids)} 条私信为已读")
        except Exception as e:
            logger.warning(f"标记已读失败: {e}")
