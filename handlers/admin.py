"""
管理员消息处理器 - aiogram 3.x 版本
"""
import logging
from typing import Optional, TYPE_CHECKING

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode

from core.config import settings
from core.store import DataStore

# 延迟导入，避免循环依赖
if TYPE_CHECKING:
    from api.nodeseek import NodeSeekAPI

logger = logging.getLogger(__name__)


class AdminHandlers:
    """管理员消息处理器"""
    
    def __init__(self, store: DataStore, bot: Bot):
        self.store = store
        self.bot = bot
        # 延迟导入
        from api.nodeseek import NodeSeekAPI
        self.ns = NodeSeekAPI()
    
    def register(self, dp: Dispatcher):
        """注册处理器"""
        # 指令处理器
        dp.message.register(self.cmd_block, Command("block"), F.chat.id == int(settings.tg_admin_uid))
        dp.message.register(self.cmd_unblock, Command("unblock"), F.chat.id == int(settings.tg_admin_uid))
        dp.message.register(self.cmd_clear_ver, Command("clear_ver"), F.chat.id == int(settings.tg_admin_uid))
        dp.message.register(self.cmd_stats, Command("stats"), F.chat.id == int(settings.tg_admin_uid))
        dp.message.register(self.cmd_test_nodeseek, Command("test_nodeseek"), F.chat.id == int(settings.tg_admin_uid))
        
        # 回复消息处理器（非指令的管理员消息）
        dp.message.register(self.handle_reply, F.reply_to_message, F.chat.id == int(settings.tg_admin_uid))
        
        # 帮助信息（纯文本指令）
        dp.message.register(self.cmd_help, F.chat.id == int(settings.tg_admin_uid))
    
    async def cmd_block(self, message: types.Message):
        """拉黑用户"""
        reply = message.reply_to_message
        if not reply:
            await message.answer('⚠️ 请回复一条用户转发的消息来拉黑。')
            return
        
        guest_id = self.store.get_msg_mapping(reply.message_id)
        if guest_id:
            self.store.block_user(guest_id)
            await message.answer(f'🚫 用户 {guest_id} 已被拉黑。')
        else:
            await message.answer('⚠️ 无法获取用户ID，可能是旧消息。')
    
    async def cmd_unblock(self, message: types.Message):
        """解封用户"""
        target_id = self._get_target_id(message.text, message.reply_to_message)
        if target_id:
            self.store.unblock_user(target_id)
            await message.answer(f'✅ 用户 {target_id} 已解封。')
        else:
            await message.answer(
                '⚠️ 格式错误。\n请回复用户消息发送 /unblock\n或发送 /unblock 123456'
            )
    
    async def cmd_clear_ver(self, message: types.Message):
        """重置验证"""
        target_id = self._get_target_id(message.text, message.reply_to_message)
        if target_id:
            self.store.clear_verification(target_id)
            await message.answer(f'🔄 用户 {target_id} 验证状态已重置。')
        else:
            await message.answer(
                '⚠️ 格式错误。\n请回复用户消息发送 /clear_ver\n或发送 /clear_ver 123456'
            )
    
    async def cmd_stats(self, message: types.Message):
        """显示统计信息"""
        stats = self.store.get_stats()
        
        stats_text = f"""📊 统计信息

已验证用户: {stats['verified_users']}
待验证验证码: {stats['pending_codes']}
黑名单用户: {stats['blocked_users']}
消息映射缓存: {stats['msg_mappings']}"""
        
        await message.answer(stats_text)
    
    async def cmd_test_nodeseek(self, message: types.Message):
        """测试 NodeSeek API"""
        await message.answer("🔍 正在测试 NodeSeek API...")
        
        try:
            result = self.ns._request('GET', '/api/notification/message/list')
            
            # 构建详细的响应信息
            response_text = """🔍 NodeSeek API 测试结果

端点: /api/notification/message/list
方法: GET

响应状态:
"""
            
            if result.get('success'):
                messages = result.get('msgArray', [])
                response_text += f"✅ 成功 (200 OK)\n\n获取到 {len(messages)} 条私信"
            else:
                error = result.get('error', '未知错误')
                response_text += f"❌ 失败\n\n错误: {error}"
            
            # 添加原始响应
            response_text += f"\n\n原始响应:\n{str(result)[:300]}"
            
            await message.answer(response_text)
        except Exception as e:
            await message.answer(
                f"❌ NodeSeek API 测试失败\n\n"
                f"错误: {e}"
            )
    
    async def handle_reply(self, message: types.Message):
        """回复访客消息"""
        reply = message.reply_to_message
        guest_id = self.store.get_msg_mapping(reply.message_id)
        
        if guest_id:
            try:
                await message.copy_to(guest_id)
            except Exception as e:
                logger.error(f"发送失败: {e}")
                await message.answer(f'❌ 发送失败: {e}')
        else:
            await message.answer('⚠️ 未找到原用户映射，可能消息太旧了。')
    
    async def cmd_help(self, message: types.Message):
        """发送帮助信息"""
        help_text = '''🤖 管理面板

<b>基本操作</b>
回复消息 = 发送给用户

<b>管理指令</b>
/block - 回复消息，拉黑该用户
/unblock - 回复消息或 /unblock 123456 解封
/clear_ver - 回复消息或 /clear_ver 123456 重置验证
/stats - 查看统计信息
/test_nodeseek - 测试 NodeSeek API

<b>说明</b>
• 拉黑后用户无法发送消息
• 重置验证后用户需要重新验证
• 消息映射缓存长期有效'''
        
        await message.answer(help_text, parse_mode=ParseMode.HTML)
    
    def _get_target_id(self, text: str, reply: Optional[types.Message]) -> Optional[str]:
        """从回复或参数获取目标 ID"""
        # 优先从回复获取
        if reply:
            guest_id = self.store.get_msg_mapping(reply.message_id)
            if guest_id:
                return guest_id
        
        # 从参数获取
        parts = text.split()
        if len(parts) > 1 and parts[1].isdigit():
            return parts[1]
        
        return None


def setup_admin_handlers(dp: Dispatcher, store: DataStore, bot: Bot):
    """设置管理员处理器"""
    handlers = AdminHandlers(store, bot)
    handlers.register(dp)
