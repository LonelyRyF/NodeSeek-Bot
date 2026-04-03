"""
数据存储 - 使用 TinyDB
"""
import os
import logging
from typing import Optional, Set, Dict
from datetime import datetime

from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

from core.config import settings
from core.models import VerificationCode, UserState

logger = logging.getLogger(__name__)


class DataStore:
    """TinyDB 数据存储"""
    
    def __init__(self):
        self._ensure_dir()
        # 使用 CachingMiddleware 提高性能
        self.db = TinyDB(
            settings.data_file,
            storage=CachingMiddleware(JSONStorage)
        )
        self.codes = self.db.table('codes')
        self.users = self.db.table('users')
        self.msg_map = self.db.table('msg_map')
        self.blocked = self.db.table('blocked')
    
    def _ensure_dir(self):
        """确保数据目录存在"""
        dir_path = os.path.dirname(settings.data_file)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, mode=0o755)
            logger.info(f"创建数据目录: {dir_path}")
    
    def close(self):
        """关闭数据库"""
        self.db.close()
    
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
    
    def update_code_verified(self, code: str, nodeseek_uid: int = None):
        """标记验证码已验证"""
        Code = Query()
        now = datetime.now().isoformat()
        self.codes.update({
            'verified': True,
            'verified_at': now,
            'nodeseek_uid': nodeseek_uid
        }, Code.code == code)
    
    # ========== 用户操作 ==========
    
    def get_user(self, tg_uid: str) -> Optional[UserState]:
        """获取用户状态"""
        User = Query()
        result = self.users.get(User.tg_uid == tg_uid)
        if result:
            return UserState(**result)
        return None
    
    def save_user(self, user: UserState):
        """保存用户状态"""
        User = Query()
        self.users.upsert(user.model_dump(), User.tg_uid == user.tg_uid)
    
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
    
    def get_user_by_nodeseek_uid(self, nodeseek_uid: int) -> Optional[UserState]:
        """通过 NodeSeek UID 获取用户"""
        User = Query()
        result = self.users.get(User.nodeseek_uid == nodeseek_uid)
        if result:
            return UserState(**result)
        return None
    
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
