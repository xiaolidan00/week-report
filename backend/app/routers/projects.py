"""项目文件夹：添加 / 列表 / 删除。"""
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..db import get_db, now, rows_to_dicts
from ..models import ProjectCreate, ProjectOut
from ..services import git_service, rag_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate):
    raw = body.path.strip().strip('"')
    path = Path(raw).expanduser()
    try:
        norm = os.path.normpath(str(path))
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="路径不合法")
    if not Path(norm).exists():
        raise HTTPException(status_code=400, detail=f"路径不存在：{norm}")
    if not Path(norm).is_dir():
        raise HTTPException(status_code=400, detail="路径不是文件夹")
    if not git_service.is_git_repo(norm):
        raise HTTPException(status_code=400, detail="该文件夹不是 git 仓库（无法读取提交日志）")

    name = Path(norm).name or norm
    with get_db() as db:
        if db.execute("SELECT id FROM projects WHERE path=?", (norm,)).fetchone():
            raise HTTPException(status_code=409, detail="该项目已在列表中")
        cur = db.execute(
            "INSERT INTO projects(name, path, created_at) VALUES (?,?,?)",
            (name, norm, now()),
        )
        project_id = int(cur.lastrowid)
        created_at = db.execute(
            "SELECT created_at FROM projects WHERE id=?", (project_id,)
        ).fetchone()["created_at"]
    return {"id": project_id, "name": name, "path": norm, "created_at": created_at}


@router.get("", response_model=list[ProjectOut])
def list_projects():
    with get_db() as db:
        rows = db.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
    return rows_to_dicts(rows)


@router.delete("/{project_id}")
def delete_project(project_id: int):
    with get_db() as db:
        row = db.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
    rag_service.delete_project(project_id)
    return {"ok": True}
