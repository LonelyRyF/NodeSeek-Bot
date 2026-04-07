# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

from __future__ import annotations

from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import LinkPreviewOptions
from loguru import logger

from api.rss import FeedClient, FeedEntry, category_label, match_keywords
from core.config import settings
from core.store import DataStore


class RSSPoller:
    """管理员专用 RSS 轮询器"""

    def __init__(self, store: DataStore, bot: Bot, proxy_host: str = '', proxy_port: int = 0):
        self.store = store
        self.bot = bot
        self.feed_client = FeedClient(
            timeout_seconds=settings.rss_http_timeout,
            max_entries_per_feed=settings.rss_max_entries,
            proxy_host=proxy_host,
            proxy_port=proxy_port,
        )

    async def poll(self) -> int:
        config = self.store.get_rss_config()
        if not config.get('enabled'):
            logger.debug('[rss] RSS 未启用，跳过轮询')
            return 0
        return await self._run_poll(config)

    async def poll_once(self) -> int:
        config = self.store.get_rss_config()
        return await self._run_poll(config)

    async def _run_poll(self, config: dict) -> int:
        try:
            result = await self.feed_client.fetch(settings.rss_url)
        except Exception as exc:
            logger.error(f'[rss] 拉取 RSS 失败: {exc}', exc_info=True)
            self.store.update_rss_config(last_poll_at=self._now_iso())
            return 0

        entries = list(reversed(result.entries))
        categories = {item.strip() for item in config.get('categories', []) if item.strip()}
        keywords = [item['keyword'] for item in self.store.list_rss_keywords(enabled_only=True)]

        self.store.update_rss_config(last_poll_at=self._now_iso())

        if not config.get('initialized'):
            for entry in entries:
                self.store.add_rss_history(
                    item_key=entry.item_key,
                    title=entry.title,
                    link=entry.link,
                    category_slug=entry.category_slug,
                    matched_keywords=[],
                )
            self.store.update_rss_config(initialized=True)
            logger.info('[rss] RSS 初始化完成，首次轮询不补发历史内容')
            return 0

        delivered_count = 0
        delivered_entries: list[tuple[FeedEntry, list[str]]] = []
        for entry in entries:
            if categories and entry.category_slug not in categories:
                continue
            if self.store.is_rss_item_delivered(entry.item_key):
                continue

            matched_keywords = match_keywords(entry.source_text, keywords)
            if not matched_keywords:
                continue

            if await self._deliver_entry(entry, matched_keywords):
                self.store.add_rss_history(
                    item_key=entry.item_key,
                    title=entry.title,
                    link=entry.link,
                    category_slug=entry.category_slug,
                    matched_keywords=matched_keywords,
                )
                self.store.bump_rss_keyword_hits(matched_keywords)
                delivered_entries.append((entry, matched_keywords))
                delivered_count += 1

        if delivered_entries:
            for entry, matched_keywords in delivered_entries:
                logger.info(
                    f"[rss] 命中推送: title={entry.title!r} link={entry.link} keywords={matched_keywords}"
                )
        return delivered_count

    async def _deliver_entry(self, entry: FeedEntry, matched_keywords: list[str]) -> bool:
        message = self.format_entry_message(entry, matched_keywords)
        try:
            await self.bot.send_message(
                chat_id=int(settings.tg_admin_uid),
                text=message,
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(
                    is_disabled=settings.rss_disable_web_page_preview,
                    url=entry.link or None,
                ),
            )
            return True
        except Exception as exc:
            logger.error(f'[rss] 推送条目失败 {entry.item_key}: {exc}', exc_info=True)
            return False

    def format_entry_message(self, entry: FeedEntry, matched_keywords: list[str]) -> str:
        category_text = category_label(entry.category_slug)
        keyword_text = '、'.join(f'#{escape(keyword)}' for keyword in matched_keywords) or '无'
        title = escape(entry.title)
        link = escape(entry.link)
        summary = self._format_summary(entry.summary)
        published = escape(entry.published_at)

        return (
            '📡 <b>NodeSeek RSS 命中</b>\n\n'
            f'<b>标题：</b><a href="{link}">{title}</a>\n'
            f'<b>版块：</b>{escape(category_text)}\n'
            f'<b>关键词：</b>{keyword_text}\n'
            f'<b>时间：</b>{published}\n'
            f'<b>摘要：</b>\n{summary}'
        )

    @staticmethod
    def _format_summary(summary: str) -> str:
        if not summary:
            return '无摘要'
        return escape(summary).replace('\n', '<br/>')

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
