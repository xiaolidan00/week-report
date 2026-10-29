"""Pydantic 请求/响应模型。"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    path: str = Field(min_length=1, description="本地 git 仓库文件夹绝对路径")


class ProjectOut(BaseModel):
    id: int
    name: str
    path: str
    created_at: str


class ChatCreate(BaseModel):
    project_id: int
    title: Optional[str] = None


class ChatOut(BaseModel):
    id: int
    project_id: int
    title: str
    created_at: str


class MessageOut(BaseModel):
    id: int
    chat_id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class GitLogOut(BaseModel):
    commits: list[dict]
    total: int


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, description="用户消息 / 周报指令")
    since: Optional[str] = Field(default=None, description="时间范围起 YYYY-MM-DD")
    until: Optional[str] = Field(default=None, description="时间范围止 YYYY-MM-DD")
    generate: bool = Field(default=False, description="是否为生成周报模式")
