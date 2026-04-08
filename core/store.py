# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

import os
from loguru import logger
from typing import Optional, Dict, List
from datetime import datetime, timezone, timedelta

from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage

from core.models import VerificationCode, UserState, LuckyTask

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(_BASE_DIR, 'data', 'data.json')


class DataStore:
    """TinyDB 数据存储"""

    def __init__(self):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        self._db = TinyDB(DATA_FILE, storage=JSONStorage, indent=2)
        self.codes = self._db.table('codes')
        self.users = self._db.table('users')
        self.msg_map = self._db.table('msg_map')
        self.blocked = self._db.table('blocked')
        self.lucky_tasks = self._db.table('lucky_tasks')
        self.config = self._db.table('config')
        self.rss_config = self._db.table('rss_config')
        self.rss_keywords = self._db.table('rss_keywords')
        self.rss_history = self._db.table('rss_history')
    
    def close(self):
        """关闭数据库连接"""
        if self._db is not None:
            self._db.close()
            self._db = None

    # ========== 配置持久化 ==========

    def get_config(self, key: str):
        C = Query()
        r = self.config.get(C.key == key)
        return r['value'] if r else None

    def set_config(self, key: str, value):
        C = Query()
        self.config.upsert({'key': key, 'value': value}, C.key == key)

    def get_checkin_auto_enabled(self) -> bool:
        value = self.get_config('checkin_auto_enabled')
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    def set_checkin_auto_enabled(self, enabled: bool):
        self.set_config('checkin_auto_enabled', bool(enabled))

    def get_checkin_random_enabled(self, platform: Optional[str] = None) -> bool:
        key = self._checkin_random_config_key(platform)
        value = self.get_config(key)
        if value is None and platform is not None:
            value = self.get_config(self._checkin_random_config_key(None))
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    def set_checkin_random_enabled(self, enabled: bool, platform: Optional[str] = None):
        key = self._checkin_random_config_key(platform)
        self.set_config(key, bool(enabled))

    def record_checkin_result(self, platform: str, success: bool, message: Optional[str] = None):
        key = self._checkin_status_config_key(platform)
        payload = {
            'success': bool(success),
            'message': message,
            'checked_at': datetime.now(timezone.utc).isoformat(),
        }
        self.set_config(key, payload)

    def get_checkin_status(self, platform: str) -> Optional[Dict]:
        value = self.get_config(self._checkin_status_config_key(platform))
        return value if isinstance(value, dict) else None

    @staticmethod
    def is_checkin_done_today(record: Optional[Dict]) -> bool:
        if not record or not record.get('success') or not record.get('checked_at'):
            return False
        try:
            checked_at = datetime.fromisoformat(record['checked_at'])
        except (TypeError, ValueError):
            return False
        cst = timezone(timedelta(hours=8))
        return checked_at.astimezone(cst).date() == datetime.now(cst).date()

    @staticmethod
    def _checkin_status_config_key(platform: str) -> str:
        normalized = platform.strip().lower()
        return f'checkin_status:{normalized}'

    @staticmethod
    def _checkin_random_config_key(platform: Optional[str]) -> str:
        normalized = (platform or '').strip().lower()
        if normalized:
            return f'checkin_random_enabled:{normalized}'
        return 'checkin_random_enabled'

    # ========== RSS 配置 ==========

    def get_rss_config(self) -> Dict:
        record = self.rss_config.get(doc_id=1)
        if record:
            return record

        now = datetime.now(timezone.utc).isoformat()
        default_config = {
            'enabled': False,
            'initialized': False,
            'categories': [],
            'last_poll_at': None,
            'created_at': now,
            'updated_at': now,
        }
        self.rss_config.upsert({'_id': 1, **default_config}, Query()._id == 1)
        return self.rss_config.get(Query()._id == 1) or {'_id': 1, **default_config}

    def update_rss_config(self, **kwargs) -> Dict:
        current = self.get_rss_config()
        updated = {
            **current,
            **kwargs,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        self.rss_config.upsert({'_id': 1, **updated}, Query()._id == 1)
        return self.rss_config.get(Query()._id == 1) or updated

    def reset_rss_initialized(self) -> Dict:
        return self.update_rss_config(initialized=False)

    def list_rss_keywords(self, enabled_only: bool = False) -> List[Dict]:
        keywords = sorted(self.rss_keywords.all(), key=lambda item: item.get('created_at', ''))
        if enabled_only:
            keywords = [item for item in keywords if item.get('enabled', True)]
        return keywords

    def get_rss_keyword(self, keyword: str) -> Optional[Dict]:
        Keyword = Query()
        return self.rss_keywords.get(Keyword.keyword == keyword.strip().lower())

    def add_rss_keyword(self, keyword: str) -> Dict:
        cleaned = keyword.strip().lower()
        if not cleaned:
            raise ValueError('keyword 不能为空')

        existing = self.get_rss_keyword(cleaned)
        if existing:
            return existing

        now = datetime.now(timezone.utc).isoformat()
        record = {
            'keyword': cleaned,
            'enabled': True,
            'hit_count': 0,
            'created_at': now,
            'last_hit_at': None,
        }
        self.rss_keywords.insert(record)
        return record

    def delete_rss_keyword(self, keyword: str) -> bool:
        Keyword = Query()
        removed = self.rss_keywords.remove(Keyword.keyword == keyword.strip().lower())
        return len(removed) > 0

    def set_rss_keyword_enabled(self, keyword: str, enabled: bool) -> bool:
        Keyword = Query()
        updated = self.rss_keywords.update(
            {'enabled': enabled},
            Keyword.keyword == keyword.strip().lower()
        )
        return len(updated) > 0

    def bump_rss_keyword_hits(self, keywords: List[str]):
        Keyword = Query()
        now = datetime.now(timezone.utc).isoformat()
        for keyword in keywords:
            record = self.get_rss_keyword(keyword)
            if not record:
                continue
            self.rss_keywords.update(
                {
                    'hit_count': int(record.get('hit_count', 0)) + 1,
                    'last_hit_at': now,
                },
                Keyword.keyword == keyword
            )

    def is_rss_item_delivered(self, item_key: str) -> bool:
        History = Query()
        return self.rss_history.contains(History.item_key == item_key)

    def add_rss_history(self, item_key: str, title: str, link: str,
                        category_slug: Optional[str], matched_keywords: List[str]) -> Dict:
        History = Query()
        now = datetime.now(timezone.utc).isoformat()
        record = {
            'item_key': item_key,
            'title': title,
            'link': link,
            'category_slug': category_slug,
            'matched_keywords': matched_keywords,
            'delivered_at': now,
        }
        self.rss_history.upsert(record, History.item_key == item_key)
        # 导入配置获取历史上限
        from core.config import settings
        self._trim_rss_history(limit=settings.rss_history_limit)
        return record

    def list_rss_history(self, limit: int = 10) -> List[Dict]:
        items = sorted(
            self.rss_history.all(),
            key=lambda item: item.get('delivered_at', ''),
            reverse=True,
        )
        return items[:limit]

    def _trim_rss_history(self, limit: int = 200):
        items = sorted(
            self.rss_history.all(),
            key=lambda item: item.get('delivered_at', ''),
            reverse=True,
        )
        for stale in items[limit:]:
            self.rss_history.remove(doc_ids=[stale.doc_id])
    
    # ========== 验证码操作 ==========
    
    def get_code(self, code: str) -> Optional[VerificationCode]:
        """获取验证码"""
        Code = Query()
        result = self.codes.get(Code.code == code)
        if result:
            return VerificationCode(**result)
        return None
    
    def save_code(self, code: VerificationCode):
        """保存验证码"""
        Code = Query()
        self.codes.upsert(code.model_dump(), Code.code == code.code)
    
    def update_code_verified(self, code: str, forum_uid: int = None, platform: str = 'nodeseek'):
        """标记验证码已验证，用 {platform}_uid 作为键名"""
        Code = Query()
        now = datetime.now().isoformat()
        self.codes.update({
            'verified': True,
            'verified_at': now,
            'platform': platform,
            f'{platform}_uid': forum_uid,
        }, Code.code == code)

    # ========== 用户操作 ==========

    def get_user(self, tg_uid: str) -> Optional[UserState]:
        """获取用户状态"""
        User = Query()
        result = self.users.get(User.tg_uid == tg_uid)
        if result:
            return self._load_user(result)
        return None

    def _load_user(self, record: dict) -> UserState:
        """从存储记录加载 UserState，将 {platform}_uid 映射到 forum_uid"""
        platform = record.get('platform', 'nodeseek')
        uid_key = f'{platform}_uid'
        data = {**record, 'forum_uid': record.get(uid_key) or record.get('forum_uid')}
        return UserState(**data)

    def save_user(self, user: UserState):
        """保存用户状态，用 {platform}_uid 作为键名"""
        User = Query()
        data = user.model_dump()
        # 将 forum_uid 存为 {platform}_uid，保留可读性
        platform = user.platform
        data[f'{platform}_uid'] = data.pop('forum_uid')
        self.users.upsert(data, User.tg_uid == user.tg_uid)
    
    def is_verified(self, tg_uid: str) -> bool:
        """检查用户是否已验证"""
        user = self.get_user(tg_uid)
        if not user or not user.verified:
            return False
        # 检查是否过期
        if user.expires_at:
            expires = datetime.fromisoformat(user.expires_at)
            if datetime.now() > expires:
                return False
        return True
    
    def get_user_by_forum_uid(self, forum_uid: int, platform: str = 'nodeseek') -> Optional[UserState]:
        """按论坛 UID + 平台查找用户"""
        uid_key = f'{platform}_uid'
        User = Query()
        result = self.users.get(
            (User[uid_key] == forum_uid) & (User.platform == platform)
        )
        return self._load_user(result) if result else None
    
    # ========== 黑名单操作 ==========
    
    def is_blocked(self, tg_uid: str) -> bool:
        """检查用户是否被拉黑"""
        Blocked = Query()
        return self.blocked.contains(Blocked.tg_uid == tg_uid)
    
    def block_user(self, tg_uid: str):
        """拉黑用户"""
        Blocked = Query()
        if not self.blocked.contains(Blocked.tg_uid == tg_uid):
            self.blocked.insert({'tg_uid': tg_uid})
    
    def unblock_user(self, tg_uid: str):
        """解封用户"""
        Blocked = Query()
        self.blocked.remove(Blocked.tg_uid == tg_uid)
    
    def clear_verification(self, tg_uid: str):
        """清除用户验证状态"""
        User = Query()
        self.users.remove(User.tg_uid == tg_uid)
        # 清除相关验证码
        Code = Query()
        self.codes.remove(Code.tg_uid == tg_uid)
    
    # ========== 消息映射操作 ==========
    
    def get_msg_mapping(self, message_id: int) -> Optional[str]:
        """获取消息映射"""
        MsgMap = Query()
        result = self.msg_map.get(MsgMap.message_id == message_id)
        if result:
            return result.get('tg_uid')
        return None
    
    def save_msg_mapping(self, message_id: int, tg_uid: str):
        """保存消息映射"""
        MsgMap = Query()
        self.msg_map.upsert(
            {'message_id': message_id, 'tg_uid': tg_uid},
            MsgMap.message_id == message_id
        )
    
    # ========== 统计 ==========

    def has_pending_codes(self) -> bool:
        """检查是否存在待验证的验证码（用于智能轮询）"""
        Code = Query()
        return self.codes.contains(Code.verified == False)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        verified_count = len([u for u in self.users.all() if u.get('verified')])
        pending_codes = len([c for c in self.codes.all() if not c.get('verified')])

        return {
            'verified_users': verified_count,
            'pending_codes': pending_codes,
            'blocked_users': len(self.blocked.all()),
            'msg_mappings': len(self.msg_map.all())
        }

    # ========== 抽奖任务操作 ==========

    def get_pending_lucky_tasks(self) -> List[LuckyTask]:
        """获取所有待执行的抽奖任务"""
        T = Query()
        return [LuckyTask(**r) for r in self.lucky_tasks.search(T.status == 'pending')]

    def get_lucky_task(self, task_id: str) -> Optional[LuckyTask]:
        """按 ID 获取任务"""
        T = Query()
        r = self.lucky_tasks.get(T.id == task_id)
        return LuckyTask(**r) if r else None

    def get_lucky_task_by_post_time(self, post: str, time: int) -> Optional[LuckyTask]:
        """按帖子 ID + 时间戳查找任务（幂等检查用）"""
        T = Query()
        r = self.lucky_tasks.get((T.post == post) & (T.time == time))
        return LuckyTask(**r) if r else None

    def save_lucky_task(self, task: LuckyTask):
        """保存或更新任务"""
        T = Query()
        self.lucky_tasks.upsert(task.model_dump(), T.id == task.id)

    def update_lucky_task_status(self, task_id: str, status: str,
                                  winners: Optional[list] = None,
                                  completed_at: Optional[str] = None):
        """更新任务状态"""
        T = Query()
        update = {'status': status}
        if winners is not None:
            update['winners'] = winners
        if completed_at is not None:
            update['completed_at'] = completed_at
        self.lucky_tasks.update(update, T.id == task_id)

    def delete_lucky_task(self, task_id: str) -> bool:
        """删除任务"""
        T = Query()
        removed = self.lucky_tasks.remove(T.id == task_id)
        return len(removed) > 0

    def list_lucky_tasks(self, page: int = 1, page_size: int = 5):
        """分页列出任务，pending 排前"""
        all_tasks = sorted(
            self.lucky_tasks.all(),
            key=lambda t: (0 if t['status'] == 'pending' else 1, t['created_at'])
        )
        total = len(all_tasks)
        start = (page - 1) * page_size
        page_tasks = [LuckyTask(**r) for r in all_tasks[start:start + page_size]]
        return page_tasks, total
