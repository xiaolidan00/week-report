rem 启动后端 FastAPI (端口 8000)
cd /d %~dp0
if not exist .venv (
  echo 创建虚拟环境...
  python -m venv .venv
)
if not exist .env (
  copy .env.example .env >nul
)
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
