# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗import os
from loguru import logger
from typing import Optional, Dict, List
from datetime import datetime

from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage

from core.models import VerificationCode, UserState, LuckyTask

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(_BASE_DIR, 'data', 'data.json')


class DataStore:
    """TinyDB 数据存储"""

    def __init__(self):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        db = TinyDB(DATA_FILE, storage=JSONStorage)
        self.codes = db.table('codes')
        self.users = db.table('users')
        self.msg_map = db.table('msg_map')
        self.blocked = db.table('blocked')
        self.lucky_tasks = db.table('lucky_tasks')
        self.config = db.table('config')

    # ========== 配置持久化 ==========

    def get_config(self, key: str):
        C = Query()
        r = self.config.get(C.key == key)
        return r['value'] if r else None

    def set_config(self, key: str, value):
        C = Query()
        self.config.upsert({'key': key, 'value': value}, C.key == key)
    
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
