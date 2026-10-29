"""配置:从 partner/.env 读取环境变量。"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
# 后台任务用的强模型(慢但聪明)
DEEPSEEK_MODEL_SMART = os.getenv("DEEPSEEK_MODEL_SMART", "deepseek-v4-pro")

# 访问密码:非空时,所有请求都必须带 ?key= 或 X-Access-Key 头
# (服务开在 0.0.0.0,同一 WiFi 的人也能连到,必须设密码)
ACCESS_KEY = os.getenv("ACCESS_KEY", "").strip()

# Partner 动手操作的工作区(白名单,可多个目录,分号分隔):
# 优先读 WORKSPACE_DIRS;兼容旧的 WORKSPACE_DIR;都没配则默认 AI_agent 目录
def _workspace_roots():
    raw = os.getenv("WORKSPACE_DIRS", "") or os.getenv("WORKSPACE_DIR", "")
    if raw:
        return [Path(p.strip()) for p in raw.split(";") if p.strip()]
    return [BASE_DIR.parent]


WORKSPACE_ROOTS = _workspace_roots()

# 相对路径的锚点目录:优先 AI_agent 项目目录(若在工作区内),否则第一个工作区目录
def _relative_anchor(roots):
    base = BASE_DIR.parent
    for r in roots:
        if base == r or r in base.parents:
            return base
    return roots[0]


RELATIVE_ANCHOR = _relative_anchor(WORKSPACE_ROOTS)

PUBLIC_MEMORY_DIR = BASE_DIR / "memory" / "public"
PRIVATE_MEMORY_DIR = BASE_DIR / "memory" / "private"
