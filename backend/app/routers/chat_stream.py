"""SSE 流式对话 + 服务健康检查。"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..models import ChatRequest
from ..services import chat_service, llm_service

router = APIRouter(prefix="/api", tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # 反向代理不缓冲
}


@router.post("/chats/{chat_id}/messages")
async def chat_messages(chat_id: int, body: ChatRequest):
    return StreamingResponse(
        chat_service.stream_chat(
            chat_id=chat_id,
            content=body.content.strip(),
            since=body.since,
            until=body.until,
            generate=body.generate,
        ),
        media_type="text/event-stream; charset=utf-8",
        headers=SSE_HEADERS,
    )


@router.post("/chats/{chat_id}/stop")
async def stop_generation(chat_id: int):
    """暂停或取消该对话正在进行的生成（由前端「暂停」或「取消思考」按钮触发）。"""
    return {"ok": chat_service.request_cancel(chat_id)}


@router.get("/health")
async def health():
    import httpx

    from .. import config

    embed_ok = False
    root = config.EMBED_MODEL_BASE_URL.rsplit("/v1", 1)[0]
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{root}/health")
            embed_ok = resp.status_code == 200
    except Exception:  # noqa: BLE001
        embed_ok = False
    return {
        "chat": await llm_service.check_chat_available(),
        "embed": embed_ok,
    }
