"""全局配置：从 .env / 环境变量读取。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))

CHAT_MODEL_BASE_URL = os.getenv("CHAT_MODEL_BASE_URL", "http://127.0.0.1:8001/v1")
CHAT_MODEL_NAME = os.getenv("CHAT_MODEL_NAME", "Qwen3.5-4B")
CHAT_MODEL_TEMPERATURE = float(os.getenv("CHAT_MODEL_TEMPERATURE", "0.3"))

EMBED_MODEL_BASE_URL = os.getenv("EMBED_MODEL_BASE_URL", "http://127.0.0.1:8002/v1")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "bge-small-zh-v1.5")


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = BACKEND_DIR / p
    return p


DB_PATH = _resolve(os.getenv("DB_PATH", "./week_report.db"))
CHROMA_DIR = _resolve(os.getenv("CHROMA_DIR", "./chroma"))
