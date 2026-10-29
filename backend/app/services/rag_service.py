"""RAG 服务：git 提交日志切块 -> embedding(8002) -> chroma -> 检索注入。

- 每条 commit 作为一个 chunk，按 project_id 分 collection
- 元数据存 date/author/subject，支持时间范围过滤 + 语义检索
- embedding 服务不可用时自动降级为直接读 git log（保证可用性）
"""
import logging
from typing import Any, Optional

import chromadb
from openai import OpenAI

from .. import config
from . import git_service

logger = logging.getLogger(__name__)

_client: Optional[chromadb.ClientAPI] = None
_embed_client: Optional[OpenAI] = None


def _chroma() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _client


def _embedder() -> OpenAI:
    global _embed_client
    if _embed_client is None:
        _embed_client = OpenAI(
            base_url=config.EMBED_MODEL_BASE_URL,
            api_key="none",
            timeout=60.0,
            max_retries=1,
        )
    return _embed_client


def embed_texts(texts: list[str]) -> list[list[float]]:
    resp = _embedder().embeddings.create(model=config.EMBED_MODEL_NAME, input=texts)
    return [item.embedding for item in resp.data]


def _collection(project_id: int):
    return _chroma().get_or_create_collection(
        name=f"project_{project_id}",
        metadata={"hnsw:space": "cosine"},
    )


def commit_to_text(commit: dict[str, Any]) -> str:
    body = f"\n{commit['body']}" if commit.get("body") else ""
    return (
        f"提交时间: {commit['date']} | 作者: {commit['author']} | "
        f"commit {commit['short_sha']}\n主题: {commit['subject']}{body}"
    )


def _date_filter(since: Optional[str], until: Optional[str]) -> Optional[dict]:
    cond = []
    if since:
        cond.append({"date": {"$gte": since}})
    if until:
        cond.append({"date": {"$lte": until}})
    if not cond:
        return None
    return cond[0] if len(cond) == 1 else {"$and": cond}


def sync_range(project_id: int, path: str, since: Optional[str], until: Optional[str]) -> int:
    """把时间范围内的 git 提交写入（upsert）chroma，返回索引条数。"""
    commits = git_service.get_log(path, since, until)
    if not commits:
        return 0
    collection = _collection(project_id)
    texts = [commit_to_text(c) for c in commits]
    embeddings = embed_texts(texts)
    collection.upsert(
        ids=[c["sha"] for c in commits],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {
                "date": c["date"],
                "author": c["author"],
                "subject": c["subject"],
                "short_sha": c["short_sha"],
            }
            for c in commits
        ],
    )
    return len(commits)


def list_range(
    project_id: int,
    since: Optional[str],
    until: Optional[str],
    limit: int = 80,
) -> list[dict[str, Any]]:
    """取出时间范围内的全部提交（按日期新→旧，截断 limit 条）。"""
    collection = _collection(project_id)
    where = _date_filter(since, until)
    kwargs: dict[str, Any] = {"include": ["metadatas", "documents"]}
    if where:
        kwargs["where"] = where
    result = collection.get(**kwargs)
    items = []
    for doc, meta in zip(result.get("documents") or [], result.get("metadatas") or []):
        items.append({**(meta or {}), "text": doc or ""})
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return items[:limit]


def search(
    project_id: int,
    query: str,
    since: Optional[str],
    until: Optional[str],
    k: int = 12,
) -> list[dict[str, Any]]:
    """按问题语义检索时间范围内的相关提交。"""
    collection = _collection(project_id)
    where = _date_filter(since, until)
    kwargs: dict[str, Any] = {
        "query_embeddings": [embed_texts([query])[0]],
        "n_results": k,
        "include": ["metadatas", "documents", "distances"],
    }
    if where:
        kwargs["where"] = where
    result = collection.query(**kwargs)
    items = []
    for doc, meta, dist in zip(
        (result.get("documents") or [[]])[0],
        (result.get("metadatas") or [[]])[0],
        (result.get("distances") or [[]])[0],
    ):
        items.append({**(meta or {}), "text": doc or "", "distance": dist})
    return items


def get_context_commits(
    project_id: int,
    path: str,
    since: Optional[str],
    until: Optional[str],
    query: Optional[str] = None,
    k: int = 12,
) -> tuple[list[dict[str, Any]], bool]:
    """获取注入 prompt 的提交片段：(提交列表, 是否走了向量检索)。

    优先 RAG（索引 + 检索/范围拉取）；embedding 服务不可用时降级直接读 git log。
    """
    try:
        sync_range(project_id, path, since, until)
        if query:
            items = search(project_id, query, since, until, k=k)
            if not items:  # 时间范围内无匹配则回退全量范围
                items = list_range(project_id, since, until)
        else:
            items = list_range(project_id, since, until)
        return items, True
    except Exception as exc:  # noqa: BLE001 - 降级保证周报可用
        logger.warning("RAG 不可用，降级直接读取 git log: %s", exc)
        commits = git_service.get_log(path, since, until)
        items = [
            {**c, "text": commit_to_text(c)} for c in commits[:80]
        ]
        return items, False


def delete_project(project_id: int) -> None:
    try:
        _chroma().delete_collection(f"project_{project_id}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("删除 chroma collection 失败: %s", exc)
