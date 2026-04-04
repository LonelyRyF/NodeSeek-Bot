# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode

from core.config import settings
from core.store import DataStore


class AdminHandlers:
    """管理员消息处理器"""

    def __init__(self, store: DataStore, bot: Bot, apis: dict, lucky_engine=None):
        self.store = store
        self.bot = bot
        self.apis = apis
        self.lucky_engine = lucky_engine
    
    def register(self, dp: Dispatcher):
        """注册处理器"""
        admin_filter = F.chat.id == int(settings.tg_admin_uid)

        # 指令处理器
        dp.message.register(self.cmd_block, Command("block"), admin_filter)
        dp.message.register(self.cmd_unblock, Command("unblock"), admin_filter)
        dp.message.register(self.cmd_clear_ver, Command("clear_ver"), admin_filter)
        dp.message.register(self.cmd_stats, Command("stats"), admin_filter)
        dp.message.register(self.cmd_checkin, Command("checkin"), admin_filter)
        dp.message.register(self.cmd_list_lucky, Command("list_lucky"), admin_filter)
        dp.message.register(self.cmd_view_lucky, Command("view_lucky"), admin_filter)
        dp.message.register(self.cmd_del_lucky, Command("del_lucky"), admin_filter)
        dp.message.register(self.cmd_reset_lucky, Command("reset_lucky"), admin_filter)

        # 回调处理器
        dp.callback_query.register(
            self.cb_lucky_page,
            F.data.startswith("lucky_page:"),
            F.from_user.id == int(settings.tg_admin_uid)
        )

        # 回复消息处理器（非指令的管理员消息）
        dp.message.register(self.handle_reply, F.reply_to_message, admin_filter)

        # 帮助信息（纯文本指令）
        dp.message.register(self.cmd_help, admin_filter)
    
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
        await message.answer(
            f"📊 统计信息\n\n"
            f"已验证用户: {stats['verified_users']}\n"
            f"待验证验证码: {stats['pending_codes']}\n"
            f"黑名单用户: {stats['blocked_users']}\n"
            f"消息映射缓存: {stats['msg_mappings']}"
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

<b>签到</b>
/checkin [random] - 签到（random=随机积分）

<b>抽奖</b>
/list_lucky [page] - 查看抽奖任务列表
/view_lucky &lt;id&gt; - 查看任务详情
/del_lucky &lt;id&gt; - 删除任务
/reset_lucky &lt;id&gt; - 重置任务为待执行'''

        await message.answer(help_text, parse_mode=ParseMode.HTML)

    async def cmd_checkin(self, message: types.Message):
        """签到所有已配置平台"""
        args = message.text.split()
        random_mode = len(args) > 1 and args[1].lower() in ('random', 'true')

        await message.answer("⏳ 正在签到...")
        loop = asyncio.get_event_loop()

        async def do_checkin(platform, api):
            try:
                result = await loop.run_in_executor(None, api.checkin, random_mode)
                ok = result.get('success') is True
                return f"{'✅' if ok else '❌'} [{platform}] {result.get('message', str(result))}"
            except Exception as e:
                return f"❌ [{platform}] 请求失败: {e}"

        results = await asyncio.gather(*[do_checkin(p, a) for p, a in self.apis.items()])
        await message.answer('\n'.join(results))

    async def cmd_list_lucky(self, message: types.Message):
        """列出抽奖任务"""
        args = message.text.split()
        page = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
        await self._send_lucky_list(message, page)

    async def _send_lucky_list(self, message: types.Message, page: int):
        tasks, total = self.store.list_lucky_tasks(page=page, page_size=5)
        total_pages = max(1, (total + 4) // 5)

        if not tasks:
            await message.answer("暂无抽奖任务。")
            return

        lines = [f"📋 抽奖任务 ({page}/{total_pages})\n"]
        for t in tasks:
            status_icon = {'pending': '⏳', 'completed': '✅', 'failed': '❌'}.get(t.status, '❓')
            dt = datetime.fromtimestamp(t.time / 1000, tz=timezone(timedelta(hours=8)))
            time_str = dt.strftime('%m-%d %H:%M')
            lines.append(f"{status_icon} [{t.id[:8]}] {t.title[:20]} ({time_str})")

        keyboard = []
        nav = []
        if page > 1:
            nav.append(types.InlineKeyboardButton(text="◀️", callback_data=f"lucky_page:{page-1}"))
        if page < total_pages:
            nav.append(types.InlineKeyboardButton(text="▶️", callback_data=f"lucky_page:{page+1}"))
        if nav:
            keyboard.append(nav)

        markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
        await message.answer('\n'.join(lines), reply_markup=markup)

    async def cb_lucky_page(self, callback: types.CallbackQuery):
        page = int(callback.data.split(':')[1])
        await callback.answer()
        await self._send_lucky_list(callback.message, page)

    async def cmd_view_lucky(self, message: types.Message):
        """查看任务详情"""
        args = message.text.split()
        if len(args) < 2:
            await message.answer("用法: /view_lucky <id前缀>")
            return

        task_id_prefix = args[1]
        task = self.store.get_lucky_task(task_id_prefix)
        if not task:
            # 尝试前缀匹配
            all_tasks, _ = self.store.list_lucky_tasks(page=1, page_size=1000)
            matches = [t for t in all_tasks if t.id.startswith(task_id_prefix)]
            task = matches[0] if len(matches) == 1 else None

        if not task:
            await message.answer("未找到任务。")
            return

        dt = datetime.fromtimestamp(task.time / 1000, tz=timezone(timedelta(hours=8)))
        lines = [
            f"📌 {task.title}",
            f"ID: `{task.id}`",
            f"帖子: {task.post}",
            f"开奖时间: {dt.strftime('%Y-%m-%d %H:%M:%S CST')}",
            f"中奖人数: {task.count}",
            f"起始楼层: {task.start}",
            f"允许重复: {'是' if task.duplicate else '否'}",
            f"状态: {task.status}",
        ]
        if task.winners:
            lines.append("\n🏆 中奖名单:")
            for i, w in enumerate(task.winners):
                lines.append(f"  {i+1}. {w['name']} ({w['floor']} 楼)")

        await message.answer('\n'.join(lines), parse_mode=ParseMode.MARKDOWN)

    async def cmd_del_lucky(self, message: types.Message):
        """删除任务"""
        args = message.text.split()
        if len(args) < 2:
            await message.answer("用法: /del_lucky <id前缀>")
            return
        ok = self.store.delete_lucky_task(args[1])
        if not ok:
            # 前缀匹配
            all_tasks, _ = self.store.list_lucky_tasks(page=1, page_size=1000)
            matches = [t for t in all_tasks if t.id.startswith(args[1])]
            if len(matches) == 1:
                ok = self.store.delete_lucky_task(matches[0].id)
        await message.answer("✅ 已删除。" if ok else "❌ 未找到任务。")

    async def cmd_reset_lucky(self, message: types.Message):
        """重置任务为 pending"""
        args = message.text.split()
        if len(args) < 2:
            await message.answer("用法: /reset_lucky <id前缀>")
            return

        task_id = args[1]
        task = self.store.get_lucky_task(task_id)
        if not task:
            all_tasks, _ = self.store.list_lucky_tasks(page=1, page_size=1000)
            matches = [t for t in all_tasks if t.id.startswith(task_id)]
            task = matches[0] if len(matches) == 1 else None

        if not task:
            await message.answer("❌ 未找到任务。")
            return

        self.store.update_lucky_task_status(task.id, status='pending', winners=None, completed_at=None)
        await message.answer(f"🔄 任务 {task.id[:8]} 已重置为待执行。")
    
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


def setup_admin_handlers(dp: Dispatcher, store: DataStore, bot: Bot, apis: dict, lucky_engine=None):
    """设置管理员处理器"""
    handlers = AdminHandlers(store, bot, apis, lucky_engine)
    handlers.register(dp)
