"""对话框：创建 / 列表 / 删除 / 历史消息。"""
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..db import get_db, now, rows_to_dicts
from ..models import ChatCreate, ChatOut, MessageOut

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.post("", response_model=ChatOut)
def create_chat(body: ChatCreate):
    with get_db() as db:
        project = db.execute("SELECT id FROM projects WHERE id=?", (body.project_id,)).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        count = db.execute(
            "SELECT COUNT(*) AS n FROM chats WHERE project_id=?", (body.project_id,)
        ).fetchone()["n"]
        title = body.title.strip() if body.title and body.title.strip() else f"对话 {count + 1}"
        cur = db.execute(
            "INSERT INTO chats(project_id, title, created_at) VALUES (?,?,?)",
            (body.project_id, title, now()),
        )
        chat_id = int(cur.lastrowid)
        row = db.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
    return dict(row)


@router.get("", response_model=list[ChatOut])
def list_chats(project_id: Optional[int] = None):
    with get_db() as db:
        if project_id is None:
            rows = db.execute("SELECT * FROM chats ORDER BY id").fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM chats WHERE project_id=? ORDER BY id", (project_id,)
            ).fetchall()
    return rows_to_dicts(rows)


@router.delete("/{chat_id}")
def delete_chat(chat_id: int):
    with get_db() as db:
        row = db.execute("SELECT id FROM chats WHERE id=?", (chat_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="对话不存在")
        db.execute("DELETE FROM chats WHERE id=?", (chat_id,))  # messages 级联删除
    return {"ok": True}


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
def list_messages(chat_id: int):
    with get_db() as db:
        chat = db.execute("SELECT id FROM chats WHERE id=?", (chat_id,)).fetchone()
        if chat is None:
            raise HTTPException(status_code=404, detail="对话不存在")
        rows = db.execute(
            "SELECT * FROM messages WHERE chat_id=? ORDER BY id", (chat_id,)
        ).fetchall()
    return rows_to_dicts(rows)
