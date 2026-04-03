"""
数据模型 - 使用 Pydantic
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VerificationCode(BaseModel):
    """验证码记录"""
    code: str
    tg_uid: str
    created_at: str
    verified: bool = False
    verified_at: Optional[str] = None
    nodeseek_uid: Optional[int] = None


class UserState(BaseModel):
    """用户状态"""
    tg_uid: str
    verified: bool
    verified_at: Optional[str] = None
    expires_at: Optional[str] = None
    nodeseek_uid: Optional[int] = None


class NodeSeekMessage(BaseModel):
    """NodeSeek 私信消息"""
    id: int
    sender_id: int
    sender_name: str
    content: str
    created_at: str
    is_markdown: bool = False
    viewed: int = 0
