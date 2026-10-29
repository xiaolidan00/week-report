"""对话核心：组装上下文（git/RAG + 历史）并以 SSE 流式产出回答。"""
import asyncio
import json
from typing import Any, AsyncIterator, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from ..db import get_db, now
from . import llm_service, rag_service

HISTORY_LIMIT = 20

SYSTEM_PROMPT = """你是一个专业的工作周报助手，服务于「AI周报系统」。你会依据用户提供的 git 提交记录（可能经过 RAG 语义检索截断）回答问题。

要求：
1. 一律使用 Markdown 输出，结构清晰、层次分明。
2. 信息不足时基于提交记录合理归纳，不要编造事实。
3. 所有结论必须来自提供的提交记录；提交记录不足时明确说明。
4. 需要表达流程、时间线、架构时，可使用 mermaid 代码块（flowchart/timeline/gantt 等）。
5. 使用与用户一致的语言（默认中文）。"""


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _format_commits(items: list[dict[str, Any]], since: Optional[str], until: Optional[str]) -> str:
    lines = [f"时间范围: {since or '不限'} ~ {until or '不限'}，共 {len(items)} 条提交记录：", ""]
    for i, item in enumerate(items, 1):
        head = item.get("subject") or item.get("text", "")
        lines.append(f"### {i}. [{item.get('date', '?')}] {head}")
        meta = f"- 作者: {item.get('author', '?')} | commit: {item.get('short_sha') or item.get('sha', '')[:8]}"
        lines.append(meta)
        body = item.get("body") or ""
        text = item.get("text") or ""
        detail = body or text
        if detail:
            lines.append(detail)
        lines.append("")
    return "\n".join(lines)


def _load_history(chat_id: int) -> list[dict[str, str]]:
    with get_db() as db:
        rows = db.execute(
            "SELECT role, content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (chat_id, HISTORY_LIMIT),
        ).fetchall()
    records = [dict(r) for r in reversed(rows)]
    return records


def _save_message(chat_id: int, role: str, content: str) -> int:
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO messages(chat_id, role, content, created_at) VALUES (?,?,?,?)",
            (chat_id, role, content, now()),
        )
        return int(cur.lastrowid)


def _delete_message(msg_id: int) -> None:
    with get_db() as db:
        db.execute("DELETE FROM messages WHERE id=?", (msg_id,))


# ---------- 生成暂停（前端「暂停」按钮 -> POST /api/chats/{id}/stop） ----------
_active_streams: set[int] = set()
_stop_flags: set[int] = set()


def request_stop(chat_id: int) -> bool:
    """请求停止该对话正在进行的生成；返回是否确实存在进行中的生成。"""
    if chat_id not in _active_streams:
        return False
    _stop_flags.add(chat_id)
    return True


def _consume_stop(chat_id: int) -> bool:
    """若存在停止请求则消费并返回 True。"""
    if chat_id in _stop_flags:
        _stop_flags.discard(chat_id)
        return True
    return False


def _get_chat_context(chat_id: int) -> dict[str, Any]:
    with get_db() as db:
        row = db.execute(
            """SELECT c.id AS chat_id, c.title, p.id AS project_id, p.name AS project_name, p.path AS project_path
               FROM chats c JOIN projects p ON p.id = c.project_id WHERE c.id=?""",
            (chat_id,),
        ).fetchone()
    if row is None:
        raise KeyError(f"chat {chat_id} not found")
    return dict(row)


async def stream_chat(
    chat_id: int,
    content: str,
    since: Optional[str] = None,
    until: Optional[str] = None,
    generate: bool = False,
) -> AsyncIterator[str]:
    """SSE 事件：
    - {"meta": {...}}   上下文信息（检索方式、条数）
    - {"token": "..."}  流式增量
    - {"done": true, "id": N, "title": "..."} 结束（id 为助手消息 id；首条消息时 title 为自动重命名结果，否则为 null）
    - {"stopped": true, "question": "..."} 用户点击暂停（撤回刚发送的问题，不落库助手回答）
    - {"error": "..."}  错误
    """
    try:
        ctx = _get_chat_context(chat_id)
    except KeyError:
        yield _sse({"error": "对话不存在，可能已被删除"})
        return

    _active_streams.add(chat_id)
    try:
        # 1. 历史（先取历史再落库，避免把本次用户消息重复计入）
        history = _load_history(chat_id)

        # 2. RAG / git 上下文
        commits: list[dict[str, Any]] = []
        rag_used = False
        if since or until:
            commits, rag_used = await asyncio.to_thread(
                rag_service.get_context_commits,
                ctx["project_id"],
                ctx["project_path"],
                since,
                until,
                content if not generate else None,
            )
        if _consume_stop(chat_id):
            yield _sse({"stopped": True, "question": content})
            return
        yield _sse(
            {
                "meta": {
                    "commits": len(commits),
                    "rag": rag_used,
                    "project": ctx["project_name"],
                    "since": since,
                    "until": until,
                    "generate": generate,
                }
            }
        )

        # 3. 组装消息
        messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        if commits:
            messages.append(
                HumanMessage(
                    content=(
                        f"以下是项目「{ctx['project_name']}」的 git 提交记录（RAG 上下文）：\n\n"
                        + _format_commits(commits, since, until)
                    )
                )
            )
        for item in history:
            if item["role"] == "user":
                messages.append(HumanMessage(content=item["content"]))
            else:
                messages.append(AIMessage(content=item["content"]))
        messages.append(HumanMessage(content=content))

        # 4. 落库用户消息
        user_msg_id = _save_message(chat_id, "user", content)

        # 首条消息时预告「时间范围 / 第一个问题」作为新标题（回答成功后才落库改名）
        new_title: Optional[str] = None
        if not history:
            if since or until:
                new_title = f"{since or '不限'} ~ {until or '不限'}"
            else:
                line = " ".join(content.split())
                new_title = line[:30] + ("…" if len(line) > 30 else "")

        # 5. 流式产出（每 token 之间检查暂停请求）
        parts: list[str] = []
        try:
            async for token in llm_service.stream_llm(messages):
                if _consume_stop(chat_id):
                    # 撤回：删除刚落库的用户消息，不保存助手消息
                    _delete_message(user_msg_id)
                    yield _sse({"stopped": True, "question": content})
                    return
                parts.append(token)
                yield _sse({"token": token})
        except Exception as exc:  # noqa: BLE001
            yield _sse({"error": f"模型调用失败：{exc}"})
            return

        answer = "".join(parts).strip()
        if not answer:
            yield _sse({"error": "模型返回为空，请确认 llama-server(8001) 已启动"})
            return
        if new_title:
            with get_db() as db:
                db.execute("UPDATE chats SET title=? WHERE id=?", (new_title, chat_id))
        msg_id = _save_message(chat_id, "assistant", answer)
        yield _sse({"done": True, "id": msg_id, "title": new_title})
    finally:
        _active_streams.discard(chat_id)
        _stop_flags.discard(chat_id)
