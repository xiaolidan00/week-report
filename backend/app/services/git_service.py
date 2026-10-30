"""git 命令封装：校验仓库、按时间范围读取提交日志。"""
import subprocess
from typing import Any, Optional

# 记录分隔符：0x1e 为记录分隔，0x1f 为字段分隔（git log 正文几乎不可能出现）
_RS = "\x1e"
_FS = "\x1f"


class GitError(Exception):
    pass


def _run(args: list[str], cwd: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except FileNotFoundError as exc:  # pragma: no cover
        raise GitError("未找到 git 命令，请确认已安装 Git 并加入 PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("git 命令执行超时") from exc
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise GitError(msg or "git 命令执行失败")
    return proc.stdout


def is_git_repo(path: str) -> bool:
    try:
        out = _run(["rev-parse", "--is-inside-work-tree"], path)
    except GitError:
        return False
    return out.strip() == "true"


def get_log(
    path: str,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """读取时间范围内的提交日志（新→旧）。"""
    args = ["log","--all", f"--max-count={limit}", f"--pretty=format:{_RS}%H{_FS}%h{_FS}%ad{_FS}%an{_FS}%s{_FS}%b"]
    args.append("--date=short")
    if since:
        args.append(f"--since={since}")
    if until:
        # until 当天包含在内：用户选到 10-29 则包含 10-29 全天
        args.append(f"--until={until} 23:59:59")
    out = _run(args, path)
    commits: list[dict[str, Any]] = []
    for record in out.split(_RS):
        if not record.strip():
            continue
        parts = record.split(_FS)
        if len(parts) < 6:
            continue
        sha, short, date, author, subject, body = parts[0], parts[1], parts[2], parts[3], parts[4], _FS.join(parts[5:])
        commits.append(
            {
                "sha": sha,
                "short_sha": short,
                "date": date,
                "author": author,
                "subject": subject,
                "body": body.strip(),
            }
        )
    return commits
