"""本地对话模型封装：LangChain ChatOpenAI -> llama-server (OpenAI 兼容, 8001)。"""
from typing import AsyncIterator

import httpx
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from .. import config


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=config.CHAT_MODEL_BASE_URL,
        model=config.CHAT_MODEL_NAME,
        api_key="none",  # llama-server 不校验
        temperature=config.CHAT_MODEL_TEMPERATURE,
        streaming=True,
        max_retries=1,
        timeout=httpx.Timeout(120.0, connect=5.0),
    )


def _chunk_text(content) -> str:
    """兼容 str / content blocks 两种返回。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", "") or item.get("content", ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content) if content else ""


async def stream_llm(messages: list[BaseMessage]) -> AsyncIterator[str]:
    llm = get_llm()
    async for chunk in llm.astream(messages):
        text = _chunk_text(chunk.content)
        if text:
            yield text


async def check_chat_available() -> bool:
    """llama-server 提供 /health 端点。"""
    root = config.CHAT_MODEL_BASE_URL.rsplit("/v1", 1)[0]
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{root}/health")
            return resp.status_code == 200
    except Exception:
        return False
