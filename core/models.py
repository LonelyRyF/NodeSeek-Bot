# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VerificationCode(BaseModel):
    """验证码记录"""
    code: str
    tg_uid: str
    created_at: str
    verified: bool = False
    verified_at: Optional[str] = None
    platform: str = 'nodeseek'
    forum_uid: Optional[int] = None   # 存储时用 {platform}_uid 键，见 store.update_code_verified


class UserState(BaseModel):
    """用户状态"""
    tg_uid: str
    verified: bool
    platform: str = 'nodeseek'
    verified_at: Optional[str] = None
    expires_at: Optional[str] = None
    forum_uid: Optional[int] = None   # 存储时用 {platform}_uid 键，见 store.save_user


class ForumMessage(BaseModel):
    """论坛 私信消息"""
    id: int
    sender_id: int
    sender_name: str
    content: str
    created_at: str
    is_markdown: bool = False
    viewed: int = 0


class LuckyTask(BaseModel):
    """抽奖任务"""
    id: str
    post: str
    title: str
    time: int                        # 开奖时间戳（毫秒）
    count: int = 1
    start: int = 1                   # 从第几楼开始参与
    duplicate: bool = False          # 是否允许同一用户多次中奖
    status: str = 'pending'          # pending / completed / failed
    created_at: str
    completed_at: Optional[str] = None
    winners: Optional[list] = None   # [{"name": str, "floor": int}]
