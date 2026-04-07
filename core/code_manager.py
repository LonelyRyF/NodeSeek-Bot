# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

import random
import string
from loguru import logger
from datetime import datetime, timedelta
from typing import Optional

from tinydb import Query

from core.config import settings
from core.store import DataStore
from core.models import VerificationCode, UserState


class CodeManager:
    """验证码管理器"""
    
    def __init__(self, store: DataStore):
        self.store = store
    
    def generate(self, tg_uid: str) -> str:
        """生成验证码"""
        # 先检查是否已有未使用的验证码
        Code = Query()
        existing = self.store.codes.get(
            (Code.tg_uid == tg_uid) & (Code.verified == False)
        )
        
        if existing:
            logger.info(f"用户 {tg_uid} 已有未使用的验证码: {existing['code']}")
            return existing['code']
        
        code = ''.join(random.choices(
            string.ascii_uppercase + string.digits,
            k=settings.code_length
        ))
        
        now = datetime.now().isoformat()
        vcode = VerificationCode(
            code=code,
            tg_uid=tg_uid,
            created_at=now
        )
        self.store.save_code(vcode)
        
        logger.info(f"生成验证码: {code} -> {tg_uid}")
        return code
    
    def verify(self, code: str, forum_uid: int = None,
               platform: str = 'nodeseek') -> tuple[Optional[str], Optional[str]]:
        """验证验证码

        Returns:
            (tg_uid, error_msg): 成功返回 (tg_uid, None)，失败返回 (None, error_msg)
        """
        code = code.upper().strip()

        vcode = self.store.get_code(code)
        if not vcode:
            logger.warning(f"验证码不存在: {code}")
            return None, "invalid_code"

        if vcode.verified:
            logger.warning(f"验证码已被使用: {code}")
            return None, "code_used"

        # 检查该论坛账号是否已绑定其他 TG 账号
        if forum_uid:
            existing_user = self.store.get_user_by_forum_uid(forum_uid, platform)
            if existing_user and existing_user.tg_uid != vcode.tg_uid:
                logger.warning(
                    f"[{platform}] 账号 {forum_uid} 已绑定 TG {existing_user.tg_uid}，"
                    f"无法绑定到 {vcode.tg_uid}"
                )
                return None, "account_bound"

        # 标记验证码已验证
        self.store.update_code_verified(code, forum_uid, platform)

        # 更新用户状态
        now = datetime.now()

        user = UserState(
            tg_uid=vcode.tg_uid,
            verified=True,
            verified_at=now.isoformat(),
            expires_at=None,
            forum_uid=forum_uid,
            platform=platform,
        )
        self.store.save_user(user)

        logger.info(f"验证成功: {code} -> {vcode.tg_uid} ({platform}:{forum_uid})")
        return vcode.tg_uid, None
    
    def cleanup_expired(self):
        """清理过期未使用的验证码"""
        Code = Query()
        now = datetime.now()
        expired = []
        
        for item in self.store.codes.all():
            if item.get('verified'):
                continue
            created = datetime.fromisoformat(item['created_at'])
            if now - created > timedelta(minutes=3):
                expired.append(item['code'])
        
        for code in expired:
            self.store.codes.remove(Code.code == code)
        
        if expired:
            logger.info(f"清理 {len(expired)} 个过期验证码")
