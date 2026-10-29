# -*- coding: utf-8 -*-
"""社区养老便民助手 - FastAPI 服务。

回答管线:问题 -> 知识库检索(字符重叠打分,按用户地区加权) -> 无命中直接答"不知道"
         -> 有命中交给 DeepSeek,只许依据参考资料用大白话回答并标注来源编号。
账户:注册/登录存在本地 SQLite(data.db),对话接口需登录。
启动:python app.py (默认 http://127.0.0.1:8090)
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

import auth_db
import knowledge
import locate

BASE = Path(__file__).parent
load_dotenv(BASE.parent / ".env")      # 复用 D:\AI_agent\.env 里的 DEEPSEEK_API_KEY
load_dotenv(BASE / ".env", override=True)

API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
client = OpenAI(api_key=API_KEY, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")) if API_KEY else None
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

COOKIE = "yl_token"
COOKIE_OPTS = {"httponly": True, "path": "/", "max_age": 30 * 86400, "samesite": "lax"}

SYSTEM = (
    "你是社区的养老便民助手，帮居民查养老政策。铁规矩：\n"
    "1. 只允许依据【参考资料】回答。资料里没有的内容，必须直接说\"这个我这边没有查到文件依据，"
    "不敢乱说\"，然后建议居民拨打12345或到社区居委会、街道办问。绝对禁止编造数字、标准、日期。\n"
    "2. 用大白话讲，像跟邻居大爷大妈聊天，别用官话套话。数字一定要说清楚，可以举个例子帮老人理解。\n"
    "3. 每条关键信息后面用[1][2]这样的编号标出来源编号。\n"
    "4. 回答要简短清楚，适当分点，别啰嗦。\n"
    "5. 问的是地方具体标准、但资料里只有国家层面说法时，要讲明\"具体金额各地不一样，以当地公布为准\"。\n"
    "6. 资料互相冲突时，以发布时间新的为准，并提一句新旧差异。\n"
    "7. 如果消息里给了居民所在地区，优先引用该地区的文件；该地区没有具体标准的，照第5条办。"
)

UNKNOWN_TEXT = (
    "不好意思，这个我这边没有查到文件依据，不敢乱说。\n\n"
    "您可以这样做：\n"
    "1. 拨打12345政务服务便民热线问问；\n"
    "2. 到社区居委会或街道办当面问工作人员。\n\n"
    "等社区把相关的文件放进资料库，我马上就能答。"
)

app = FastAPI(title="社区养老便民助手")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


class ChatIn(BaseModel):
    question: str
    guest: bool = False   # 游客模式:不注册也能问(地区由前端本地保存并随请求带来)
    region: str = ""


class RegisterIn(BaseModel):
    username: str
    password: str
    phone: str = ""
    region: str = ""


class LoginIn(BaseModel):
    username: str
    password: str


class RegionIn(BaseModel):
    region: str


def _set_cookie(resp: Response, token: str):
    resp.set_cookie(COOKIE, token, **COOKIE_OPTS)


def _require_user(request: Request) -> dict:
    user = auth_db.get_user_by_token(request.cookies.get(COOKIE))
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")


# ---------- 账户 ----------

@app.post("/api/register")
def register(inp: RegisterIn, resp: Response):
    username = inp.username.strip()
    password = inp.password
    if not (2 <= len(username) <= 20) or any(ch.isspace() for ch in username):
        raise HTTPException(400, "用户名需 2~20 个字符，不能有空格")
    if len(password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    uid = auth_db.create_user(username, password, inp.phone.strip(), inp.region.strip())
    if uid is None:
        raise HTTPException(400, "这个用户名已经有人用了，换一个吧")
    token = auth_db.new_session(uid)
    _set_cookie(resp, token)
    return {"ok": True, "user": auth_db.get_user_by_token(token)}


@app.post("/api/login")
def login(inp: LoginIn, resp: Response):
    username = inp.username.strip()
    if not auth_db.user_exists(username):
        raise HTTPException(401, {"code": "need_register", "msg": "这个用户名还没注册，请先注册"})
    uid = auth_db.check_login(username, inp.password)
    if uid is None:
        raise HTTPException(401, {"code": "bad_password", "msg": "密码不对，再试试"})
    token = auth_db.new_session(uid)
    _set_cookie(resp, token)
    return {"ok": True, "user": auth_db.get_user_by_token(token)}


@app.post("/api/logout")
def logout(request: Request, resp: Response):
    auth_db.drop_session(request.cookies.get(COOKIE, ""))
    resp.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    return {"user": _require_user(request)}


# ---------- 地区 ----------

@app.get("/api/regions")
def regions():
    wifi_map, builtin = locate.load_regions()
    return {"wifi_map": wifi_map, "builtin": builtin}


@app.get("/api/locate")
def api_locate():
    return locate.detect()


@app.put("/api/region")
def api_region(inp: RegionIn, request: Request):
    user = _require_user(request)
    auth_db.set_region(user["id"], inp.region.strip()[:30])
    return {"ok": True, "region": inp.region.strip()[:30]}


# ---------- 问答 ----------

@app.get("/api/docs")
def api_docs():
    return {"docs": [d.meta() for d in knowledge.docs], "total_chunks": len(knowledge.all_chunks)}


@app.post("/api/reload")
def api_reload():
    knowledge.reload()
    return {"ok": True, "docs": len(knowledge.docs), "chunks": len(knowledge.all_chunks)}


def _hit_sources(hits):
    """命中的片段 -> 给前端的来源标注列表(编号与提示词里一致)。"""
    return [
        {"n": i + 1, "title": c.doc.title, "source": c.doc.source,
         "url": c.doc.url, "date": c.doc.date, "section": c.section,
         "region": c.doc.region, "excerpt": c.text[:120]}
        for i, (_, c) in enumerate(hits)
    ]


@app.post("/api/chat")
def chat(inp: ChatIn, request: Request):
    # 登录用户用账号里存的地区;游客模式(guest=true)不登录也能用,地区随请求带来
    user = auth_db.get_user_by_token(request.cookies.get(COOKIE))
    if user:
        region = user.get("region") or ""
    elif inp.guest:
        region = inp.region.strip()[:30]
    else:
        raise HTTPException(status_code=401, detail="请先登录")

    q = inp.question.strip()[:200]
    if not q:
        return {"mode": "unknown", "answer": "您想问点什么？", "sources": []}

    hits = knowledge.retrieve(q, region=region)
    if not hits:
        # 知识库里查不到 -> 不调用大模型,直接坦白说不知道
        return {"mode": "unknown", "answer": UNKNOWN_TEXT, "sources": []}

    refs = "\n".join(
        f"[{i + 1}] 《{c.doc.title}》\"{c.section}\"一节:{c.text}"
        for i, (_, c) in enumerate(hits)
    )
    region_line = f"居民所在地区：{region}\n" if region else ""
    if client is None:
        return _fallback(hits, "没配 DEEPSEEK_API_KEY")

    try:
        resp = client.chat.completions.create(
            model=MODEL, temperature=0.2, max_tokens=900,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"{region_line}【参考资料】\n{refs}\n\n居民问:{q}\n请按铁规矩回答。"},
            ],
        )
        answer = resp.choices[0].message.content.strip()
    except Exception as e:  # 接口挂了也降级,不能让居民干等
        return _fallback(hits, f"大模型接口暂时连不上({type(e).__name__})")

    return {"mode": "answered", "answer": answer, "sources": _hit_sources(hits)}


def _fallback(hits, reason):
    parts = ["（大模型接口暂时连不上，先把查到的原文给您看：）", ""]
    for i, (_, c) in enumerate(hits):
        parts.append(f"《{c.doc.title}》- {c.section}：{c.text}")
    parts.append("")
    parts.append(f"（原因：{reason}。接口恢复后我就能把这些翻译成大白话。）")
    return {"mode": "fallback", "answer": "\n\n".join(parts), "sources": _hit_sources(hits)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8090")))
