# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from html import escape

from loguru import logger
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup

from core.config import settings
from core.store import DataStore
from services.rss_poller import RSSPoller


class AdminHandlers:
    """管理员消息处理器"""

    COMMANDS = [
        BotCommand(command="start", description="管理面板与快捷入口"),
        BotCommand(command="help", description="查看全部命令说明"),
        BotCommand(command="messenger", description="私聊封禁、重置、统计"),
        BotCommand(command="checkin", description="平台签到、随机鸡腿、状态"),
        BotCommand(command="lottery", description="抽奖任务列表与操作"),
        BotCommand(command="rss", description="RSS 开关、筛选、关键词"),
    ]

    def __init__(self, store: DataStore, bot: Bot, apis: dict, lucky_engine=None, rss_poller=None):
        self.store = store
        self.bot = bot
        self.apis = apis
        self.lucky_engine = lucky_engine
        self.rss_poller = rss_poller
    
    async def _send_message(self, message: types.Message, text: str, reply_markup=None, parse_mode=None):
        """发送新消息。"""
        kwargs = {"reply_markup": reply_markup}
        if parse_mode is not None:
            kwargs["parse_mode"] = parse_mode
        return await message.answer(text, **kwargs)

    async def _send_progress_message(self, message: types.Message, text: str):
        """发送进度消息，供后续结果覆盖。"""
        return await self._send_message(message, text)

    async def _send_callback_result(self, message: types.Message, text: str, reply_markup=None, parse_mode=None):
        """菜单回调结果：先发送结果消息，再更新该结果消息。"""
        progress_message = await self._send_progress_message(message, "正在处理...")
        await self._render_message(progress_message, text, reply_markup=reply_markup, parse_mode=parse_mode)
        return progress_message

    async def _render_message(self, message: types.Message, text: str, reply_markup=None, parse_mode=None):
        """优先编辑当前消息，失败时回退为发送新消息。"""
        kwargs = {"reply_markup": reply_markup}
        if parse_mode is not None:
            kwargs["parse_mode"] = parse_mode
        try:
            await message.edit_text(text, **kwargs)
        except Exception:
            await message.answer(text, **kwargs)

    def register(self, dp: Dispatcher):
        """注册处理器"""
        admin_filter = F.chat.id == int(settings.tg_admin_uid)

        # 指令处理器
        dp.message.register(self.cmd_start, Command("start"), admin_filter)
        dp.message.register(self.cmd_help, Command("help"), admin_filter)
        dp.message.register(self.cmd_messenger, Command("messenger"), admin_filter)
        dp.message.register(self.cmd_checkin, Command("checkin"), admin_filter)
        dp.message.register(self.cmd_lottery, Command("lottery"), admin_filter)
        
        # RSS 命令
        dp.message.register(self.cmd_rss, Command("rss"), admin_filter)

        # 回调处理器
        dp.callback_query.register(
            self.cb_lucky_page,
            F.data.startswith("lucky_page:"),
            F.from_user.id == int(settings.tg_admin_uid)
        )
        
        # 菜单按钮回调处理器
        dp.callback_query.register(
            self.cb_admin_menu,
            F.data.startswith("admin:"),
            F.from_user.id == int(settings.tg_admin_uid)
        )
        dp.callback_query.register(
            self.cb_messenger_menu,
            F.data.startswith("messenger:"),
            F.from_user.id == int(settings.tg_admin_uid)
        )
        dp.callback_query.register(
            self.cb_checkin_menu,
            F.data.startswith("checkin:"),
            F.from_user.id == int(settings.tg_admin_uid)
        )
        dp.callback_query.register(
            self.cb_lottery_menu,
            F.data.startswith("lottery:"),
            F.from_user.id == int(settings.tg_admin_uid)
        )
        dp.callback_query.register(
            self.cb_rss_menu,
            F.data.startswith("rss:"),
            F.from_user.id == int(settings.tg_admin_uid)
        )

        # 回复消息处理器（非指令的管理员消息）
        dp.message.register(self.handle_reply, F.reply_to_message, admin_filter)

        # 帮助信息（纯文本指令）
        dp.message.register(self.cmd_help_fallback, admin_filter)
    
    async def cmd_start(self, message: types.Message):
        """发送管理面板入口"""
        await self._send_admin_panel(message)

    async def cmd_messenger(self, message: types.Message, command: CommandObject):
        """私聊管理入口"""
        if not command.args:
            await self._send_messenger_panel(message)
            return

        parts = command.args.split(maxsplit=1)
        action = parts[0].lower()
        # 重新构造不带 @bot 的参数文本，供 _get_target_id 使用
        args_text = command.args

        if action == 'block':
            await self._messenger_block(message)
            return

        if action == 'unblock':
            await self._messenger_unblock(message, args_text)
            return

        if action == 'reset':
            await self._messenger_reset(message, args_text)
            return

        if action == 'info':
            await self._messenger_info(message)
            return

        await message.answer("用法: /messenger block|unblock|reset [tg_uid]|info")

    async def _send_admin_panel(self, message: types.Message):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="私聊管理", callback_data="admin:messenger")],
            [InlineKeyboardButton(text="签到管理", callback_data="admin:checkin")],
            [InlineKeyboardButton(text="抽奖管理", callback_data="admin:lottery")],
            [InlineKeyboardButton(text="RSS 订阅", callback_data="admin:rss")],
        ])
        text = """管理面板

请选择需要管理的功能模块："""
        
        await self._render_message(message, text, reply_markup=keyboard)

    async def _send_messenger_panel(self, message: types.Message):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="查看统计", callback_data="messenger:info")],
            [InlineKeyboardButton(text="解封用户", switch_inline_query_current_chat="/messenger unblock ")],
            [InlineKeyboardButton(text="重置验证", switch_inline_query_current_chat="/messenger reset ")],
            [InlineKeyboardButton(text="返回主菜单", callback_data="admin:start")],
        ])
        text = """私聊管理

功能说明：
• 查看统计 - 查看已验证用户、待验证验证码、黑名单用户及消息缓存数量
• 解封用户 - 解除指定用户的封禁状态，解封后用户可重新参与验证
• 重置验证 - 清除指定用户的验证状态，重置后用户需重新进行验证
• 拉黑用户 - 回复用户转发的消息后发送 /messenger block，将该用户加入黑名单"""
        
        await self._render_message(message, text, reply_markup=keyboard)

    async def _send_checkin_panel(self, message: types.Message):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="全部平台签到", callback_data="checkin:run:all")],
            [InlineKeyboardButton(text="NodeSeek 签到", callback_data="checkin:run:nodeseek")],
            [InlineKeyboardButton(text="DeepFlood 签到", callback_data="checkin:run:deepflood")],
            [InlineKeyboardButton(text="查看状态", callback_data="checkin:status")],
            [InlineKeyboardButton(text="签到设置", callback_data="checkin:settings")],
            [InlineKeyboardButton(text="返回主菜单", callback_data="admin:start")],
        ])
        text = """签到管理

功能说明：
• 全部平台签到 - 在所有已配置的平台上执行签到操作
• NodeSeek 签到 - 仅在 NodeSeek 平台执行签到
• DeepFlood 签到 - 仅在 DeepFlood 平台执行签到
• 查看状态 - 查看各平台的随机鸡腿开关状态及今日是否已签到
• 签到设置 - 打开签到相关设置子菜单"""
        
        await self._render_message(message, text, reply_markup=keyboard)

    async def _send_checkin_settings_panel(self, message: types.Message):
        auto_enabled = self.store.get_checkin_auto_enabled()
        auto_text = '已启用' if auto_enabled else '已禁用'
        random_enabled = any(self.store.get_checkin_random_enabled(platform) for platform in self.apis.keys())
        random_text = '已启用' if random_enabled else '已禁用'
        auto_button_text = "关闭自动签到" if auto_enabled else "开启自动签到"
        random_button_text = "关闭随机鸡腿" if random_enabled else "开启随机鸡腿"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=auto_button_text, callback_data="checkin:auto:toggle")],
            [InlineKeyboardButton(text=random_button_text, callback_data="checkin:switch:toggle")],
            [InlineKeyboardButton(text="返回签到管理", callback_data="admin:checkin")],
        ])
        text = f"""签到设置

功能说明：
• 自动签到：{auto_text}（每天北京时间 00:05 执行）
• 随机鸡腿：{random_text}
• 点击按钮可直接切换对应状态"""

        await self._render_message(message, text, reply_markup=keyboard)

    async def _send_lottery_panel(self, message: types.Message):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="任务列表", callback_data="lottery:list:1")],
            [InlineKeyboardButton(text="上一页", callback_data="lottery:list:prev"), 
             InlineKeyboardButton(text="下一页", callback_data="lottery:list:next")],
            [InlineKeyboardButton(text="查看任务详情", switch_inline_query_current_chat="/lottery view ")],
            [InlineKeyboardButton(text="重置任务状态", switch_inline_query_current_chat="/lottery reset ")],
            [InlineKeyboardButton(text="删除任务", switch_inline_query_current_chat="/lottery del ")],
            [InlineKeyboardButton(text="返回主菜单", callback_data="admin:start")],
        ])
        text = """抽奖任务管理

功能说明：
• 任务列表 - 显示所有抽奖任务（每页显示 5 条）
• 查看详情 - 输入任务 ID 前缀查看完整任务信息和中奖名单
• 重置任务 - 输入任务 ID 前缀将任务状态重置为待执行
• 删除任务 - 输入任务 ID 前缀永久删除任务"""
        
        await self._render_message(message, text, reply_markup=keyboard)

    async def _send_rss_panel(self, message: types.Message):
        config = self.store.get_rss_config()
        enabled = bool(config.get('enabled'))
        enabled_text = '已启用' if enabled else '已禁用'
        toggle_text = '关闭自动轮询' if enabled else '开启自动轮询'
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="查看状态", callback_data="rss:status")],
            [InlineKeyboardButton(text=toggle_text, callback_data="rss:toggle")],
            [InlineKeyboardButton(text="手动轮询一次", callback_data="rss:poll")],
            [InlineKeyboardButton(text="查看推送历史", callback_data="rss:history:10")],
            [InlineKeyboardButton(text="版块筛选", callback_data="rss:scope_panel")],
            [InlineKeyboardButton(text="关键词管理", callback_data="rss:keyword_panel")],
            [InlineKeyboardButton(text="返回主菜单", callback_data="admin:start")],
        ])
        text = f"""RSS 订阅管理

功能说明：
• 自动轮询：{enabled_text}
• 点击“{toggle_text}”可直接切换 RSS 自动轮询状态
• 手动轮询一次 - 立即执行一次 RSS 源的拉取和内容检查
• 查看推送历史 - 显示已推送给管理员的历史记录
• 版块筛选 - 配置推送内容的版块过滤规则
• 关键词管理 - 添加、删除、启用或禁用关键词过滤"""

        await self._render_message(message, text, reply_markup=keyboard)

    async def _send_rss_scope_panel(self, message: types.Message):
        config = self.store.get_rss_config()
        categories = config.get('categories', [])
        from api.rss import category_label
        current = ', '.join(category_label(c) for c in categories) if categories else '无限制（推送全部版块）'

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="查看当前设置", callback_data="rss:scope:list")],
            [InlineKeyboardButton(text="设置版块（如：技术,日常）", switch_inline_query_current_chat="/rss scope set ")],
            [InlineKeyboardButton(text="清除版块筛选", callback_data="rss:scope:reset")],
            [InlineKeyboardButton(text="返回 RSS 管理", callback_data="rss:panel")],
        ])
        text = f"""RSS 版块筛选

当前设置：{current}

功能说明：
• 查看当前设置 - 显示当前已配置的版块筛选列表
• 设置版块 - 点击后输入版块名称，多个版块用英文逗号分隔
• 清除版块筛选 - 清空筛选条件，恢复推送全部版块

可用版块（部分）：
技术、日常、问答、资讯、优惠、交易、福利、测评"""

        await self._render_message(message, text, reply_markup=keyboard)

    async def _send_rss_keyword_panel(self, message: types.Message):
        keywords = self.store.list_rss_keywords()
        if keywords:
            lines = []
            for kw in keywords[:10]:
                status = "启用" if kw.get('enabled', True) else "禁用"
                hits = kw.get('hit_count', 0)
                lines.append(f"• [{status}] {escape(kw['keyword'])} (命中 {hits} 次)")
            kw_preview = '\n'.join(lines)
            if len(keywords) > 10:
                kw_preview += f'\n... 共 {len(keywords)} 个关键词'
        else:
            kw_preview = '暂无关键词'

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="查看全部关键词", callback_data="rss:keyword:list")],
            [InlineKeyboardButton(text="添加关键词", switch_inline_query_current_chat="/rss keyword add ")],
            [InlineKeyboardButton(text="删除关键词", switch_inline_query_current_chat="/rss keyword del ")],
            [InlineKeyboardButton(text="启用关键词", switch_inline_query_current_chat="/rss keyword on ")],
            [InlineKeyboardButton(text="禁用关键词", switch_inline_query_current_chat="/rss keyword off ")],
            [InlineKeyboardButton(text="返回 RSS 管理", callback_data="rss:panel")],
        ])
        text = f"""RSS 关键词管理

当前关键词：
{kw_preview}

功能说明：
• 查看全部关键词 - 显示所有关键词及命中统计
• 添加关键词 - 点击后输入要添加的关键词
• 删除关键词 - 点击后输入要删除的关键词
• 启用/禁用关键词 - 点击后输入关键词名称"""

        await self._render_message(message, text, reply_markup=keyboard)

    async def _messenger_block(self, message: types.Message):
        """拉黑用户"""
        reply = message.reply_to_message
        if not reply:
            await self._send_message(message, '请回复一条用户转发的消息后执行此操作。')
            return

        guest_id = self.store.get_msg_mapping(reply.message_id)
        if guest_id:
            self.store.block_user(guest_id)
            await self._send_message(message, f'已将用户 {guest_id} 加入黑名单。')
        else:
            await self._send_message(message, '无法获取用户信息，可能是消息过旧。')

    async def _messenger_unblock(self, message: types.Message, args_text: str = ''):
        """解封用户"""
        target_id = self._get_target_id(args_text, message.reply_to_message)
        if target_id:
            self.store.unblock_user(target_id)
            await message.answer(f'已解除用户 {target_id} 的黑名单。')
        else:
            await message.answer(
                '格式错误。请回复用户消息执行解封，或发送：\n'
                '/messenger unblock <用户ID>'
            )

    async def _messenger_reset(self, message: types.Message, args_text: str = ''):
        """重置验证"""
        target_id = self._get_target_id(args_text, message.reply_to_message)
        if target_id:
            self.store.clear_verification(target_id)
            await message.answer(f'已重置用户 {target_id} 的验证状态。')
        else:
            await message.answer(
                '格式错误。请回复用户消息执行重置，或发送：\n'
                '/messenger reset <用户ID>'
            )

    async def _messenger_info(self, message: types.Message, *, callback_result: bool = False):
        """显示统计信息"""
        stats = self.store.get_stats()
        text = (
            f"用户统计信息\n\n"
            f"已验证用户：{stats['verified_users']}\n"
            f"待验证验证码：{stats['pending_codes']}\n"
            f"黑名单用户：{stats['blocked_users']}\n"
            f"消息映射缓存：{stats['msg_mappings']}"
        )
        if callback_result:
            await self._send_callback_result(message, text)
        else:
            await self._render_message(message, text)

    async def handle_reply(self, message: types.Message):
        """回复访客消息"""
        reply = message.reply_to_message
        guest_id = self.store.get_msg_mapping(reply.message_id)

        if guest_id:
            try:
                await message.copy_to(guest_id)
            except Exception as e:
                logger.error(f"发送失败: {e}")
                await message.answer(f'消息发送失败：{e}')
        else:
            await message.answer('未找到原用户映射，可能消息过旧。')
    
    async def cmd_help(self, message: types.Message):
        """发送帮助信息"""
        help_text = '''管理面板

<b>基本操作</b>
回复消息 = 发送给用户

<b>管理指令</b>
/messenger block - 回复消息，拉黑该用户
/messenger unblock &lt;tg_uid&gt; - 回复消息或按 TG UID 解封
/messenger reset &lt;tg_uid&gt; - 回复消息或按 TG UID 重置验证
/messenger info - 查看统计信息

<b>签到</b>
/checkin [nodeseek|deepflood] [random] - 立即签到（可指定平台，random=随机鸡腿）
/checkin switch on|off [nodeseek|deepflood] - 开关随机鸡腿模式（不带平台则作用于全部平台）
/checkin status - 查看签到状态与今日是否已签到

<b>抽奖</b>
/lottery list [page] - 查看抽奖任务列表
/lottery view &lt;id&gt; - 查看任务详情
/lottery del &lt;id&gt; - 删除任务
/lottery reset &lt;id&gt; - 重置任务为待执行

<b>RSS 订阅</b>
/rss on|off - 启用/禁用 RSS 自动轮询
/rss status - 查看 RSS 状态
/rss history [limit] - 查看历史记录（最多50条）
/rss poll - 手动轮询一次（不受启用状态限制）
/rss init reset - 重置初始化状态
/rss scope list - 查看版块筛选
/rss scope set &lt;分类1,分类2&gt; - 设置版块
/rss scope reset - 清除版块筛选
/rss keyword list - 查看所有关键词
/rss keyword add &lt;词&gt; - 添加关键词
/rss keyword del &lt;词&gt; - 删除关键词
/rss keyword on &lt;词&gt; - 启用关键词
/rss keyword off &lt;词&gt; - 禁用关键词'''

        await message.answer(help_text, parse_mode=ParseMode.HTML)

    async def cmd_help_fallback(self, message: types.Message):
        """管理员文本回退帮助"""
        if message.text and message.text.startswith('/'):
            return
        await self.cmd_help(message)

    async def cmd_checkin(self, message: types.Message, command: CommandObject):
        """签到入口"""
        if not command.args:
            await self._send_checkin_panel(message)
            return

        parts = command.args.split()
        action = parts[0].lower()
        if action == 'switch':
            await self._switch_checkin_random(message, parts[1:])
            return

        if action == 'status':
            await self._send_checkin_status(message)
            return

        await self._run_checkin(message, parts)

    def _normalize_checkin_platform(self, platform: str) -> Optional[str]:
        aliases = {
            'ns': 'nodeseek',
            'nodeseek': 'nodeseek',
            'df': 'deepflood',
            'deepflood': 'deepflood',
        }
        return aliases.get(platform.lower())

    async def _run_checkin(self, message: types.Message, args: list[str], *, render_result: bool = False):
        """执行签到"""
        selected_platform = None
        explicit_random = None

        for arg in args:
            value = arg.lower()
            normalized_platform = self._normalize_checkin_platform(value)
            if normalized_platform:
                selected_platform = normalized_platform
                continue
            if value in ('random', 'true'):
                explicit_random = True
                continue
            if value in ('normal', 'false'):
                explicit_random = False
                continue
            await self._send_message(
                message,
                "用法: /checkin [nodeseek|deepflood] [random]"
            )
            return

        target_platforms = [selected_platform] if selected_platform else list(self.apis.keys())
        missing = [platform for platform in target_platforms if platform not in self.apis]
        if missing:
            await self._send_message(message, f"平台不存在：{', '.join(missing)}")
            return

        progress_message = await self._send_progress_message(message, "正在执行签到...")
        loop = asyncio.get_event_loop()

        async def do_checkin(platform, api):
            random_mode = explicit_random if explicit_random is not None else self.store.get_checkin_random_enabled(platform)
            try:
                result = await loop.run_in_executor(None, api.checkin, random_mode)
                ok = result.get('success') is True
                result_message = result.get('message', str(result))
                self.store.record_checkin_result(platform, ok, result_message)
                return f"[{platform}] {'成功' if ok else '失败'} - {result_message}"
            except Exception as e:
                self.store.record_checkin_result(platform, False, str(e))
                return f"[{platform}] 异常：{e}"

        results = await asyncio.gather(*[do_checkin(platform, self.apis[platform]) for platform in target_platforms])
        result_text = '\n'.join(results)
        if render_result:
            await self._render_message(progress_message, result_text)
        else:
            await self._send_message(message, result_text)

    async def _send_checkin_status(self, message: types.Message, *, callback_result: bool = False):
        """显示签到状态"""
        text = f"""签到状态统计

自动签到：{'启用' if self.store.get_checkin_auto_enabled() else '禁用'}（每天北京时间 00:05 执行）
"""
        lines = [text]
        for platform in self.apis.keys():
            random_enabled = self.store.get_checkin_random_enabled(platform)
            status_record = self.store.get_checkin_status(platform)
            done_today = self.store.is_checkin_done_today(status_record)
            random_text = '启用' if random_enabled else '禁用'
            done_text = '已签到' if done_today else '未签到'
            last_message = status_record.get('message') if status_record else None
            lines.append(f"[{platform}]")
            lines.append(f"  随机鸡腿：{random_text}")
            lines.append(f"  今日：{done_text}")
            if status_record and status_record.get('checked_at'):
                lines.append(f"  最后执行：{status_record['checked_at']}")
            if last_message:
                lines.append(f"  结果：{last_message}")
            lines.append("")

        text = '\n'.join(lines)
        if callback_result:
            await self._send_callback_result(message, text)
        else:
            await self._render_message(message, text)

    async def _switch_checkin_auto(self, message: types.Message, enabled: Optional[bool] = None, *, callback_result: bool = False):
        """切换自动签到"""
        if enabled is None:
            enabled = not self.store.get_checkin_auto_enabled()
        self.store.set_checkin_auto_enabled(enabled)
        if callback_result:
            await self._send_checkin_settings_panel(message)
        else:
            status = '启用' if enabled else '禁用'
            text = f"已{status}自动签到，将于每天北京时间 00:05 执行。"
            await message.answer(text)

    async def _switch_checkin_random(self, message: types.Message, args: Optional[list[str]] = None, *, callback_result: bool = False):
        """切换签到随机模式"""
        if not args:
            current_enabled = any(self.store.get_checkin_random_enabled(platform) for platform in self.apis.keys())
            args = ['off' if current_enabled else 'on']

        value = args[0].lower()
        if value not in {'on', 'off'}:
            await message.answer("用法：/checkin switch on|off [平台名称]")
            return

        platform = None
        if len(args) > 1:
            platform = self._normalize_checkin_platform(args[1])
            if platform is None or platform not in self.apis:
                await message.answer(f"平台不存在：{args[1]}")
                return

        enabled = value == 'on'
        if platform is None:
            for platform_name in self.apis.keys():
                self.store.set_checkin_random_enabled(enabled, platform_name)
            scope = '全部平台'
        else:
            self.store.set_checkin_random_enabled(enabled, platform)
            scope = platform
        if callback_result:
            await self._send_checkin_settings_panel(message)
        else:
            status = '启用' if enabled else '禁用'
            text = f"已对{scope}的随机鸡腿模式执行{status}操作。"
            await message.answer(text)

    async def cmd_lottery(self, message: types.Message, command: CommandObject):
        """抽奖管理入口"""
        if not command.args:
            await self._send_lottery_panel(message)
            return

        parts = command.args.split()
        action = parts[0].lower()
        # lottery 子处理函数期望 parts[2] 作为 id，这里补位使其兼容
        full_parts = [None, action] + parts[1:]
        if action == 'list':
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            await self._send_lucky_list(message, page)
            return

        if action == 'view':
            await self._lottery_view(message, full_parts)
            return

        if action == 'del':
            await self._lottery_delete(message, full_parts)
            return

        if action == 'reset':
            await self._lottery_reset(message, full_parts)
            return

        await message.answer("用法: /lottery list [page]|view <id前缀>|del <id前缀>|reset <id前缀>")


    async def _send_lucky_list(self, message: types.Message, page: int, *, callback_result: bool = False):
        tasks, total = self.store.list_lucky_tasks(page=page, page_size=5)
        total_pages = max(1, (total + 4) // 5)

        if not tasks:
            text = "暂无抽奖任务。"
            if callback_result:
                await self._send_callback_result(message, text)
            else:
                await self._render_message(message, text)
            return

        lines = [f"抽奖任务列表 ({page}/{total_pages})\n"]
        for t in tasks:
            status_text = {'pending': '待执行', 'completed': '已完成', 'failed': '失败'}.get(t.status, '未知')
            dt = datetime.fromtimestamp(t.time / 1000, tz=timezone(timedelta(hours=8)))
            time_str = dt.strftime('%m-%d %H:%M')
            lines.append(f"[{t.id[:8]}] {t.title[:20]} | {status_text} | {time_str}")

        keyboard = []
        nav = []
        if page > 1:
            nav.append(types.InlineKeyboardButton(text="上一页", callback_data=f"lucky_page:{page-1}"))
        if page < total_pages:
            nav.append(types.InlineKeyboardButton(text="下一页", callback_data=f"lucky_page:{page+1}"))
        if nav:
            keyboard.append(nav)

        markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
        text = '\n'.join(lines)
        if callback_result:
            await self._send_callback_result(message, text, reply_markup=markup)
        else:
            await self._render_message(message, text, reply_markup=markup)

    async def cb_lucky_page(self, callback: types.CallbackQuery):
        page = int(callback.data.split(':')[1])
        await callback.answer()
        await self._send_lucky_list(callback.message, page, callback_result=True)

    async def cb_admin_menu(self, callback: types.CallbackQuery):
        """管理面板菜单回调"""
        action = callback.data.split(':')[1]
        await callback.answer()
        
        if action == 'start':
            await self._send_admin_panel(callback.message)
        elif action == 'messenger':
            await self._send_messenger_panel(callback.message)
        elif action == 'checkin':
            await self._send_checkin_panel(callback.message)
        elif action == 'lottery':
            await self._send_lottery_panel(callback.message)
        elif action == 'rss':
            await self._send_rss_panel(callback.message)

    async def cb_messenger_menu(self, callback: types.CallbackQuery):
        """私聊管理菜单回调"""
        action = callback.data.split(':')[1]
        await callback.answer()

        if action == 'info':
            await self._messenger_info(callback.message, callback_result=True)

    async def cb_checkin_menu(self, callback: types.CallbackQuery):
        """签到管理菜单回调"""
        parts = callback.data.split(':')
        action = parts[1]
        await callback.answer()

        message = callback.message
        if action == 'status':
            await self._send_checkin_status(message, callback_result=True)
        elif action == 'settings':
            await self._send_checkin_settings_panel(message)
        elif action == 'auto':
            enabled = None if len(parts) <= 2 or parts[2] == 'toggle' else parts[2] == 'on'
            await self._switch_checkin_auto(message, enabled, callback_result=True)
        elif action == 'run':
            platform = parts[2] if len(parts) > 2 else 'all'
            args = [] if platform == 'all' else [platform]
            await self._run_checkin(message, args, render_result=True)
        elif action == 'switch':
            args = None if len(parts) <= 2 or parts[2] == 'toggle' else [parts[2]]
            await self._switch_checkin_random(message, args, callback_result=True)

    async def cb_lottery_menu(self, callback: types.CallbackQuery):
        """抽奖管理菜单回调"""
        parts = callback.data.split(':')
        action = parts[1]
        await callback.answer()

        if action == 'list':
            page = int(parts[2]) if len(parts) > 2 and parts[2] != 'prev' and parts[2] != 'next' else 1
            if len(parts) > 2 and parts[2] == 'prev':
                try:
                    current_page = int(callback.message.text.split('(')[1].split('/')[0])
                    page = max(1, current_page - 1)
                except Exception:
                    page = 1
            elif len(parts) > 2 and parts[2] == 'next':
                try:
                    current_page = int(callback.message.text.split('(')[1].split('/')[0])
                    page = current_page + 1
                except Exception:
                    page = 2
            await self._send_lucky_list(callback.message, page, callback_result=True)

    async def cb_rss_menu(self, callback: types.CallbackQuery):
        """RSS 管理菜单回调"""
        parts = callback.data.split(':')
        action = parts[1]
        await callback.answer()

        message = callback.message
        config = self.store.get_rss_config()

        if action == 'panel':
            await self._send_rss_panel(message)
        elif action == 'scope_panel':
            await self._send_rss_scope_panel(message)
        elif action == 'keyword_panel':
            await self._send_rss_keyword_panel(message)
        elif action == 'status':
            await self._send_rss_status(message, config, callback_result=True)
        elif action == 'toggle':
            self.store.update_rss_config(enabled=not bool(config.get('enabled')))
            await self._send_rss_panel(message)
        elif action == 'on':
            if not config.get('enabled'):
                self.store.update_rss_config(enabled=True)
            await self._send_rss_panel(message)
        elif action == 'off':
            if config.get('enabled'):
                self.store.update_rss_config(enabled=False)
            await self._send_rss_panel(message)
        elif action == 'poll':
            await self._run_rss_poll(message, callback_result=True)
        elif action == 'history':
            limit = int(parts[2]) if len(parts) > 2 else 10
            await self._send_rss_history(message, limit, callback_result=True)
        elif action == 'scope':
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'list':
                await self._send_rss_scope_panel(message)
            elif subaction == 'reset':
                self.store.update_rss_config(categories=[])
                await self._send_rss_scope_panel(message)
        elif action == 'keyword':
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'list':
                await self._send_rss_keyword_panel(message)

    async def _lottery_view(self, message: types.Message, parts: list[str]):
        """查看任务详情"""
        if len(parts) < 3:
            await message.answer("用法: /lottery view <id前缀>")
            return

        task_id_prefix = parts[2]
        task = self.store.get_lucky_task(task_id_prefix)
        if not task:
            all_tasks, _ = self.store.list_lucky_tasks(page=1, page_size=1000)
            matches = [t for t in all_tasks if t.id.startswith(task_id_prefix)]
            task = matches[0] if len(matches) == 1 else None

        if not task:
            await message.answer("未找到任务。")
            return

        dt = datetime.fromtimestamp(task.time / 1000, tz=timezone(timedelta(hours=8)))
        lines = [
            f"任务标题：{task.title}",
            f"任务 ID：`{task.id}`",
            f"帖子链接：{task.post}",
            f"开奖时间：{dt.strftime('%Y-%m-%d %H:%M:%S CST')}",
            f"中奖人数：{task.count}",
            f"起始楼层：{task.start}",
            f"允许重复：{'是' if task.duplicate else '否'}",
            f"当前状态：{task.status}",
        ]
        if task.winners:
            lines.append("\n中奖名单：")
            for i, w in enumerate(task.winners):
                lines.append(f"  {i+1}. {w['name']} ({w['floor']} 楼)")

        await message.answer('\n'.join(lines), parse_mode=ParseMode.MARKDOWN)

    async def _lottery_delete(self, message: types.Message, parts: list[str]):
        """删除任务"""
        if len(parts) < 3:
            await message.answer("用法: /lottery del <id前缀>")
            return
        ok = self.store.delete_lucky_task(parts[2])
        if not ok:
            all_tasks, _ = self.store.list_lucky_tasks(page=1, page_size=1000)
            matches = [t for t in all_tasks if t.id.startswith(parts[2])]
            if len(matches) == 1:
                ok = self.store.delete_lucky_task(matches[0].id)
        await message.answer("已删除任务。" if ok else "未找到任务。")

    async def _lottery_reset(self, message: types.Message, parts: list[str]):
        """重置任务为 pending"""
        if len(parts) < 3:
            await message.answer("用法: /lottery reset <id前缀>")
            return

        task_id = parts[2]
        task = self.store.get_lucky_task(task_id)
        if not task:
            all_tasks, _ = self.store.list_lucky_tasks(page=1, page_size=1000)
            matches = [t for t in all_tasks if t.id.startswith(task_id)]
            task = matches[0] if len(matches) == 1 else None

        if not task:
            await message.answer("未找到任务。")
            return

        self.store.update_lucky_task_status(task.id, status='pending', winners=None, completed_at=None)
        await message.answer(f"任务 {task.id[:8]} 已重置为待执行状态。")

    def _get_target_id(self, text: str, reply: Optional[types.Message]) -> Optional[str]:
        """从回复或参数获取目标 ID"""
        if reply:
            guest_id = self.store.get_msg_mapping(reply.message_id)
            if guest_id:
                return guest_id

        parts = text.split()
        for part in reversed(parts[1:]):
            if part.isdigit():
                return part

        return None

    # ========== RSS 命令 ==========

    async def cmd_rss(self, message: types.Message, command: CommandObject):
        """RSS 管理入口"""
        if not command.args:
            await self._send_rss_panel(message)
            return

        raw_parts = command.args.split()
        action = raw_parts[0].lower()
        config = self.store.get_rss_config()

        if action == 'on':
            if config.get('enabled'):
                await message.answer("RSS 已经处于启用状态。")
            else:
                self.store.update_rss_config(enabled=True)
                await message.answer("RSS 已启用，自动轮询将在下一个周期开始。")
            return

        if action == 'off':
            if not config.get('enabled'):
                await message.answer("RSS 已经处于禁用状态。")
            else:
                self.store.update_rss_config(enabled=False)
                await message.answer("RSS 已禁用，自动轮询将停止。")
            return

        if action == 'status':
            await self._send_rss_status(message, config)
            return

        if action == 'history':
            limit = 10
            if len(raw_parts) > 1 and raw_parts[1].isdigit():
                limit = min(int(raw_parts[1]), 50)
            await self._send_rss_history(message, limit)
            return

        if action == 'poll':
            await self._run_rss_poll(message)
            return

        if action == 'init':
            if len(raw_parts) < 2 or raw_parts[1].strip().lower() != 'reset':
                await message.answer("用法: /rss init reset")
                return
            self.store.reset_rss_initialized()
            await message.answer("RSS 初始化状态已重置，下次轮询将不补发历史内容。")
            return

        if action == 'scope':
            await self._handle_rss_scope(message, raw_parts[1:], config)
            return

        if action == 'keyword':
            await self._handle_rss_keyword(message, raw_parts[1:])
            return

        await message.answer(
            "用法: /rss on|off|status|history|poll|init reset|scope ...|keyword ..."
        )

    async def _handle_rss_keyword(self, message: types.Message, parts: list[str]):
        """管理 RSS 关键词（parts 已去掉 'keyword' 前缀）"""
        if not parts:
            await self._send_rss_keyword_panel(message)
            return

        subaction = parts[0].lower()

        if subaction == 'list':
            keywords = self.store.list_rss_keywords()
            if not keywords:
                await message.answer("暂无关键词。")
                return

            lines = ["关键词列表：\n"]
            for kw in keywords:
                status = "启用" if kw.get('enabled', True) else "禁用"
                hits = kw.get('hit_count', 0)
                lines.append(f"• [{status}] {escape(kw['keyword'])} (命中 {hits} 次)")

            await message.answer('\n'.join(lines), parse_mode=ParseMode.HTML)
            return

        if subaction in ('add', 'del', 'on', 'off'):
            if len(parts) < 2:
                await message.answer(f"用法: /rss keyword {subaction} <词>")
                return

            keyword = ' '.join(parts[1:]).strip()
            if not keyword:
                await message.answer("关键词不能为空。")
                return

            if subaction == 'add':
                try:
                    self.store.add_rss_keyword(keyword)
                    await message.answer(f"关键词 '{escape(keyword)}' 已添加。")
                except ValueError as e:
                    await message.answer(f"操作失败：{e}")
                return

            if subaction == 'del':
                if self.store.delete_rss_keyword(keyword):
                    await message.answer(f"关键词 '{escape(keyword)}' 已删除。")
                else:
                    await message.answer(f"关键词 '{escape(keyword)}' 不存在。")
                return

            if subaction == 'on':
                if self.store.set_rss_keyword_enabled(keyword, True):
                    await message.answer(f"关键词 '{escape(keyword)}' 已启用。")
                else:
                    await message.answer(f"关键词 '{escape(keyword)}' 不存在。")
                return

            if self.store.set_rss_keyword_enabled(keyword, False):
                await message.answer(f"关键词 '{escape(keyword)}' 已禁用。")
            else:
                await message.answer(f"关键词 '{escape(keyword)}' 不存在。")
            return

        await message.answer("用法: /rss keyword list|add|del|on|off <词>")

    async def _handle_rss_scope(self, message: types.Message, parts: list[str], config: dict):
        """管理 RSS 版块筛选（parts 已去掉 'scope' 前缀）"""
        if not parts:
            await self._send_rss_scope_panel(message)
            return

        subaction = parts[0].lower()

        if subaction == 'list':
            categories = config.get('categories', [])
            if not categories:
                await message.answer("当前版块筛选：无限制（推送全部版块）。")
            else:
                from api.rss import category_label
                cat_names = [category_label(cat) for cat in categories]
                await message.answer(f"当前版块筛选：{', '.join(cat_names)}")
            return

        if subaction == 'set':
            if len(parts) < 2:
                await message.answer("用法: /rss scope set <分类1,分类2,...>")
                return

            cat_input = ' '.join(parts[1:])
            from api.rss import normalize_category_slug, category_label
            categories = []
            for cat in cat_input.split(','):
                normalized = normalize_category_slug(cat.strip())
                if normalized:
                    categories.append(normalized)

            if not categories:
                await message.answer("无效的分类，请检查输入。")
                return

            self.store.update_rss_config(categories=categories)
            cat_names = [category_label(cat) for cat in categories]
            await message.answer(f"版块筛选已设置：{', '.join(cat_names)}")
            return

        if subaction == 'reset':
            self.store.update_rss_config(categories=[])
            await message.answer("版块筛选已清除，将推送所有版块。")
            return

        await message.answer("用法: /rss scope list|set <分类1,分类2,...>|reset")

    async def _send_rss_status(self, message: types.Message, config: dict, *, callback_result: bool = False):
        """查看 RSS 状态"""
        keywords = self.store.list_rss_keywords(enabled_only=True)
        categories = config.get('categories', [])

        from api.rss import category_label

        enabled = "已启用" if config.get('enabled') else "已禁用"
        initialized = "已初始化" if config.get('initialized') else "未初始化"
        last_poll = config.get('last_poll_at') or "未轮询"

        cat_text = ', '.join(category_label(c) for c in categories) if categories else "无限制"

        status_text = (
            f"<b>RSS 状态</b>\n\n"
            f"状态：{enabled}\n"
            f"初始化：{initialized}\n"
            f"最后轮询：{last_poll}\n"
            f"活跃关键词：{len(keywords)}\n"
            f"版块筛选：{cat_text}\n"
            f"RSS 地址：<code>{escape(settings.rss_url)}</code>"
        )

        if callback_result:
            await self._send_callback_result(message, status_text, parse_mode=ParseMode.HTML)
        else:
            await self._render_message(message, status_text, parse_mode=ParseMode.HTML)

    async def _send_rss_history(self, message: types.Message, limit: int, *, callback_result: bool = False):
        """查看 RSS 历史"""
        history = self.store.list_rss_history(limit=limit)
        if not history:
            text = "暂无历史记录。"
            if callback_result:
                await self._send_callback_result(message, text)
            else:
                await self._render_message(message, text)
            return

        lines = [f"RSS 历史记录（最近 {len(history)} 条）\n"]
        for item in history:
            title = escape(item['title'][:30])
            keywords = ', '.join(f"#{escape(kw)}" for kw in item.get('matched_keywords', []))
            delivered = item.get('delivered_at', '未知')[:10]
            lines.append(f"• {title}\n  关键词: {keywords}\n  时间: {delivered}\n")

        text = '\n'.join(lines)
        if callback_result:
            await self._send_callback_result(message, text, parse_mode=ParseMode.HTML)
        else:
            await self._render_message(message, text, parse_mode=ParseMode.HTML)

    async def _run_rss_poll(self, message: types.Message, *, callback_result: bool = False):
        """手动轮询一次"""
        if not self.rss_poller:
            text = "RSS 轮询器未初始化。"
            if callback_result:
                await self._send_callback_result(message, text)
            else:
                await self._render_message(message, text)
            return

        if callback_result:
            progress_message = await self._send_progress_message(message, "正在执行 RSS 轮询，请稍候。")
            try:
                count = await self.rss_poller.poll_once()
                await self._render_message(progress_message, f"轮询完成，本次推送 {count} 条内容。")
            except Exception as e:
                logger.error(f"手动轮询失败: {e}", exc_info=True)
                await self._render_message(progress_message, f"轮询失败：{e}")
            return

        await self._render_message(message, "正在执行 RSS 轮询，请稍候。")
        try:
            count = await self.rss_poller.poll_once()
            await self._render_message(message, f"轮询完成，本次推送 {count} 条内容。")
        except Exception as e:
            logger.error(f"手动轮询失败: {e}", exc_info=True)
            await self._render_message(message, f"轮询失败：{e}")


def setup_admin_handlers(dp: Dispatcher, store: DataStore, bot: Bot, apis: dict, lucky_engine=None, rss_poller=None):
    """设置管理员处理器"""
    handlers = AdminHandlers(store, bot, apis, lucky_engine, rss_poller)
    handlers.register(dp)
