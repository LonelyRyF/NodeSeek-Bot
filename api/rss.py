# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime

import feedparser

from api.http_client import HTTPClient

TAG_RE = re.compile(r"<[^>]+>")
NEWLINE_TAG_RE = re.compile(r"<(?:br\s*/?|/p|/div|/li|/tr|/h[1-6])\s*>", re.IGNORECASE)
BLOCK_TAG_RE = re.compile(r"<(?:p|div|li|tr|h[1-6])\b[^>]*>", re.IGNORECASE)
SPACE_RE = re.compile(r"[ \t\f\v]+")
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

CATEGORY_LABELS: dict[str, str] = {
    "daily": "日常",
    "tech": "技术",
    "info": "情报",
    "review": "测评",
    "trade": "交易",
    "carpool": "拼车",
    "promo": "推广",
    "life": "生活",
    "dev": "Dev",
    "photo-share": "贴图",
    "expose": "曝光",
    "inner": "内版",
    "sandbox": "沙盒",
}

CATEGORY_ALIASES: dict[str, str] = {
    "日常": "daily",
    "技术": "tech",
    "情报": "info",
    "测评": "review",
    "交易": "trade",
    "拼车": "carpool",
    "推广": "promo",
    "promotion": "promo",
    "生活": "life",
    "dev": "dev",
    "贴图": "photo-share",
    "曝光": "expose",
    "内版": "inner",
    "沙盒": "sandbox",
}

CATEGORY_ORDER: tuple[str, ...] = (
    "daily",
    "tech",
    "info",
    "review",
    "trade",
    "carpool",
    "promo",
    "life",
    "dev",
    "photo-share",
    "expose",
    "inner",
    "sandbox",
)


@dataclass(slots=True)
class FeedEntry:
    item_key: str
    title: str
    link: str
    summary: str
    published_at: str
    source_text: str
    category_slug: str | None
    category_name: str


@dataclass(slots=True)
class FeedFetchResult:
    feed_title: str
    entries: list[FeedEntry]


class FeedClient:
    def __init__(self, timeout_seconds: int, max_entries_per_feed: int, 
                 proxy_host: str = '', proxy_port: int = 0) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_entries_per_feed = max_entries_per_feed
        self.http_client = HTTPClient(timeout_seconds, proxy_host, proxy_port)

    async def fetch(self, url: str) -> FeedFetchResult:
        response = self.http_client.get(url)
        response.raise_for_status()
        raw = response.content

        parsed = feedparser.parse(raw)
        feed_title = strip_html(parsed.feed.get("title")) or url

        entries: list[FeedEntry] = []
        for item in parsed.entries[: self.max_entries_per_feed]:
            title = strip_html(item.get("title")) or "无标题"
            link = item.get("link", "").strip()
            summary = item.get("summary") or item.get("description") or ""
            plain_summary = truncate_text(strip_html(summary), 280)
            published_raw = (
                item.get("published")
                or item.get("updated")
                or item.get("created")
                or item.get("pubDate")
                or ""
            )
            item_key = (
                item.get("id")
                or item.get("guid")
                or link
                or f"{title}:{published_raw}"
            )

            tags = item.get("tags") or []
            tag_terms = [
                strip_html(tag.get("term", ""))
                for tag in tags
                if isinstance(tag, dict) and tag.get("term")
            ]
            category_slug = None
            for term in tag_terms:
                category_slug = normalize_category_slug(term)
                if category_slug:
                    break

            source_text = " ".join(
                part for part in [title, plain_summary, " ".join(tag_terms)] if part
            ).lower()
            entries.append(
                FeedEntry(
                    item_key=item_key,
                    title=title,
                    link=link,
                    summary=plain_summary,
                    published_at=format_datetime(published_raw),
                    source_text=source_text,
                    category_slug=category_slug,
                    category_name=category_label(category_slug),
                )
            )

        return FeedFetchResult(feed_title=feed_title, entries=entries)


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    plain = html.unescape(value)
    plain = NEWLINE_TAG_RE.sub("\n", plain)
    plain = BLOCK_TAG_RE.sub("\n", plain)
    plain = TAG_RE.sub(" ", plain)
    plain = plain.replace("\r\n", "\n").replace("\r", "\n")
    plain = SPACE_RE.sub(" ", plain)
    plain = re.sub(r" *\n *", "\n", plain)
    plain = MULTI_NEWLINE_RE.sub("\n\n", plain)
    return plain.strip()


def truncate_text(value: str, max_length: int) -> str:
    value = value.strip()
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "…"


def format_datetime(value: str | None) -> str:
    if not value:
        return "未知"
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def normalize_category_slug(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned in CATEGORY_LABELS:
        return cleaned
    return CATEGORY_ALIASES.get(value.strip()) or CATEGORY_ALIASES.get(cleaned)


def category_label(slug: str | None) -> str:
    if not slug:
        return "未分类"
    return CATEGORY_LABELS.get(slug, slug)


def match_keywords(source_text: str, keywords: list[str]) -> list[str]:
    lowered = source_text.lower()
    return [keyword for keyword in keywords if keyword.lower() in lowered]
