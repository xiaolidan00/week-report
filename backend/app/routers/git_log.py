"""git 日志预览：选择时间范围后展示提交条数/摘要。"""
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models import GitLogOut
from ..services import git_service

router = APIRouter(prefix="/api/git", tags=["git"])


@router.get("/log", response_model=GitLogOut)
def git_log(project_id: int, since: Optional[str] = None, until: Optional[str] = None):
    with get_db() as db:
        row = db.execute("SELECT path FROM projects WHERE id=?", (project_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        commits = git_service.get_log(row["path"], since, until, limit=200)
    except git_service.GitError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"commits": commits, "total": len(commits)}
