"""Partner 服务入口:FastAPI 后端 + 手机网页前端。

- 会话持久化:data/sessions.json,每轮结束原子落盘,启动恢复
- 工具循环与审批流程在本文件编排;单次模型调用在 core.llm
- write_file / run_command 需要用户确认:SSE 推 approval 事件,
  前端点允许/拒绝后调 /api/approve 继续
- 后台任务:/api/task 起线程跑完整对话循环,完成可推微信通知(PushPlus)

启动:python app.py(默认 0.0.0.0:8000)
"""

import json
import os
import threading
import time
import urllib.request
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core import config, memory_store, permissions, tools, wecom
from core.llm import (
    SYSTEM_PROMPT, assistant_msg, execute_tool, parse_args, plan_task, stream_call,
    tool_detail, verify_task,
)

app = FastAPI(title="Partner")

# session_id -> {"messages": [...], "steps": int, "pending": {...} | None}
sessions = {}
MAX_SESSIONS = 200
MAX_MESSAGES = 60   # 每个会话保留的消息条数上限(不含 system)
MAX_STEPS = 12      # 每条用户消息最多触发的工具步数

GATED_TOOLS = ("write_file", "run_command")  # 需要用户确认的工具

# 后台任务:task_id -> {id, message, status, result, created, finished}
tasks = {}
MAX_TASKS = 100

SESSION_FILE = config.BASE_DIR / "data" / "sessions.json"
AUDIT_FILE = config.BASE_DIR / "data" / "audit.log"
SCHEDULE_FILE = config.BASE_DIR / "data" / "schedule.json"

# 定时任务:schedule id -> {id, kind: daily|interval, at, minutes, message, allow_write, last_run}
schedules = {}


def audit_log(kind, detail):
    """行动审计:记录每次工具执行/审批/任务,写到 data/audit.log。"""
    try:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"time": time.strftime("%m-%d %H:%M:%S"), "kind": kind, "detail": str(detail)[:200]},
                          ensure_ascii=False)
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_schedules():
    if SCHEDULE_FILE.exists():
        try:
            schedules.update(json.loads(SCHEDULE_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass


def save_schedules():
    try:
        SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = SCHEDULE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(schedules, ensure_ascii=False), encoding="utf-8")
        tmp.replace(SCHEDULE_FILE)
    except Exception:
        pass

LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Partner · 访问验证</title>
<style>
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0f1115;color:#e8eaf0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.box{background:#171a21;padding:28px 24px;border-radius:14px;width:min(320px,86vw);text-align:center}
h1{font-size:20px;margin:0 0 6px}
p{color:#8b93a7;font-size:13px;margin:0 0 16px}
input{width:100%;box-sizing:border-box;background:#232936;border:1px solid #2a3040;border-radius:10px;padding:12px 14px;font-size:16px;color:#e8eaf0;outline:none;margin-bottom:12px}
button{width:100%;background:#2f6fed;border:none;border-radius:10px;padding:12px;font-size:15px;color:#fff}
</style></head><body><div class="box">
<h1>Partner</h1><p>输入访问密码(在电脑 partner/.env 的 ACCESS_KEY 一行)</p>
<input id="k" type="password" placeholder="访问密码" autocomplete="off">
<button onclick="go()">进入</button>
</div><script>
function go(){var v=document.getElementById('k').value.trim();if(!v)return;localStorage.setItem('partner_key',v);location.href='/?key='+encodeURIComponent(v)}
document.getElementById('k').addEventListener('keydown',function(e){if(e.key==='Enter')go()});
</script></body></html>"""


@app.middleware("http")
async def guard(request, call_next):
    """访问密码校验 + 前端文件不缓存。"""
    if config.ACCESS_KEY:
        key = request.query_params.get("key") or request.headers.get("x-access-key")
        ok = key == config.ACCESS_KEY
        if request.url.path.startswith("/api/") and not ok:
            return JSONResponse({"detail": "需要访问密钥"}, status_code=401)
        if request.url.path == "/" and not ok:
            return HTMLResponse(LOGIN_HTML, status_code=401)
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store"
    return response


def sse(event):
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""


class ApproveRequest(BaseModel):
    session_id: str
    request_id: str
    approved: bool


class TaskRequest(BaseModel):
    message: str
    session_id: str = ""
    allow_write: bool = False


@app.get("/")
def index():
    return FileResponse(config.BASE_DIR / "static" / "index.html")


# ---------- 会话持久化 ----------

def load_sessions():
    """启动时恢复历史会话(重启/刷新不丢上下文)。"""
    if not SESSION_FILE.exists():
        return
    try:
        raw = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        for k, v in raw.items():
            if isinstance(v, dict) and isinstance(v.get("messages"), list):
                sessions[k] = {
                    "messages": repair_session(v["messages"]), "steps": 0, "pending": None,
                    "updated": v.get("updated", ""),
                }
        print(f"[sessions] 已恢复 {len(sessions)} 个会话", flush=True)
    except Exception as e:
        print(f"[sessions] 恢复失败: {e}", flush=True)


def save_sessions():
    """每轮对话结束后落盘(原子写)。"""
    try:
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = SESSION_FILE.with_suffix(".json.tmp")
        now = time.strftime("%m-%d %H:%M")
        trimmed = {
            k: {"messages": (v["messages"][:1] + v["messages"][-(MAX_MESSAGES):]),
                "updated": now}
            for k, v in sessions.items()
        }
        for v in sessions.values():
            v["updated"] = now
        tmp.write_text(json.dumps(trimmed, ensure_ascii=False), encoding="utf-8")
        tmp.replace(SESSION_FILE)
    except Exception as e:
        print(f"[sessions] 保存失败: {e}", flush=True)


def repair_session(messages):
    """修复悬空的 tool_calls:给缺响应的工具调用补"已取消"应答。

    场景:审批卡片未处理就发新消息/会话持久化后中断——
    没有 tool 消息跟随的 assistant(tool_calls) 会导致 API 400,必须补齐。
    """
    out = []
    i = 0
    while i < len(messages):
        m = messages[i]
        out.append(m)
        if m.get("role") == "assistant" and m.get("tool_calls"):
            ids = [tc["id"] for tc in m["tool_calls"]]
            answered = set()
            j = i + 1
            while j < len(messages) and messages[j].get("role") == "tool":
                out.append(messages[j])  # 关键:保留已有的 tool 消息,不能丢
                answered.add(messages[j].get("tool_call_id"))
                j += 1
            for tid in ids:
                if tid not in answered:
                    out.append({
                        "role": "tool", "tool_call_id": tid,
                        "content": "此操作未完成(会话中断),已自动取消。",
                    })
            i = j
        else:
            i += 1
    return out


def get_session(sid):
    sid = str(sid or "").strip()
    if sid and sid in sessions:
        return sid, sessions[sid]
    if len(sessions) >= MAX_SESSIONS:
        sessions.pop(next(iter(sessions)))
    # 采用客户端传的会话 ID;没传才生成
    new_id = sid[:64] if sid else uuid.uuid4().hex
    sessions[new_id] = {
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
        "steps": 0,
        "pending": None,
        "updated": time.strftime("%m-%d %H:%M"),
    }
    return new_id, sessions[new_id]


def tool_msg(call, content):
    return {"role": "tool", "tool_call_id": call["id"], "content": content}


def _dump_message_trace(messages):
    """API 报错时把消息结构写日志(不含正文),方便定位悬空 tool_calls。"""
    try:
        trace = []
        for m in messages[-16:]:
            role = m.get("role")
            if role == "assistant" and m.get("tool_calls"):
                ids = [tc.get("id", "?") for tc in m["tool_calls"]]
                trace.append(f"assistant(tool_calls={ids})")
            elif role == "tool":
                trace.append(f"tool(id={m.get('tool_call_id', '?')})")
            else:
                trace.append(role)
        print(f"[trace] {' | '.join(trace)}", flush=True)
    except Exception:
        pass


# ---------- 工具循环(事件字典,网页流与后台线程共用) ----------

def run_one(session, call):
    """执行一个工具调用,产出 UI 事件,并把结果追加进会话消息。"""
    args = parse_args(call["arguments"])
    detail = tool_detail(call["name"], args)
    audit_log("tool", f"{call['name']}: {detail}")
    yield {"type": "tool", "name": call["name"], "detail": detail}
    result = execute_tool(call["name"], call["arguments"])
    yield {"type": "tool_result", "summary": (result or "").strip().splitlines()[0][:100]}
    session["messages"].append(tool_msg(call, result))


def process_rest(sid):
    """处理 pending 里剩余的调用:再遇需确认的就发起审批,否则直接执行。"""
    session = sessions[sid]
    pending = session["pending"]
    call = pending["rest"][0]
    pending["rest"] = pending["rest"][1:]
    if call["name"] in GATED_TOOLS:
        pending["request_id"] = uuid.uuid4().hex
        pending["current"] = call
        yield {"type": "approval", "request_id": pending["request_id"],
               "name": call["name"],
               "detail": tool_detail(call["name"], parse_args(call["arguments"]))}
        return
    yield from run_one(session, call)
    if pending["rest"]:
        yield from process_rest(sid)
    else:
        session["pending"] = None
        yield from run_loop(sid)


def run_loop(sid, gate_handler=None, model=None):
    """主循环:调模型 → 有工具调用就执行(需确认的走审批或 gate_handler 自动裁决)。

    model:指定模型(后台任务传 config.DEEPSEEK_MODEL_SMART,聊天默认 chat)。
    """
    session = sessions[sid]
    while session["steps"] < MAX_STEPS:
        # 每轮调用模型前都体检一次,防任何来源的悬空 tool_calls 毒化
        session["messages"] = repair_session(session["messages"])
        calls = None
        try:
            for ev in stream_call(session["messages"], model=model):
                if ev["type"] == "__calls__":
                    calls = ev["calls"]
                else:
                    yield ev
        except Exception as e:
            _dump_message_trace(session["messages"])
            raise
        if not calls:
            return
        session["steps"] += 1
        session["messages"].append(assistant_msg(calls))
        idx = next((i for i, c in enumerate(calls) if c["name"] in GATED_TOOLS), len(calls))
        for c in calls[:idx]:
            yield from run_one(session, c)
        if idx == len(calls):
            continue  # 全是只读调用,继续循环
        if gate_handler:
            # 后台任务:自动裁决,不打断
            for c in calls[idx:]:
                decision = gate_handler(c)
                if decision is True:
                    yield from run_one(session, c)
                else:
                    session["messages"].append(tool_msg(c, decision))
                    yield {"type": "tool_result", "summary": "(后台任务权限不足,已拒绝)"}
            continue
        # 交互模式:先按权限策略分流(规则放行 → 直接执行;规则拦截 → 拒绝;其余 → 审批)
        gated = calls[idx:]
        exec_now, ask_later = [], []
        for c in gated:
            decision = permissions.check_tool(c["name"], parse_args(c["arguments"]))
            if decision == "allow":
                exec_now.append(c)
            elif decision == "deny":
                session["messages"].append(
                    tool_msg(c, "权限策略禁止此操作,请换一种方式或询问主人。"))
                audit_log("permission", f"规则拦截 {c['name']}")
                yield {"type": "tool_result", "summary": "(权限策略已拦截)"}
            else:
                ask_later.append(c)
        for c in exec_now:
            audit_log("permission", f"规则放行 {c['name']}")
            yield from run_one(session, c)
        if not ask_later:
            continue
        pending = {"request_id": "", "current": None, "rest": ask_later}
        session["pending"] = pending
        call = pending["rest"][0]
        pending["rest"] = pending["rest"][1:]
        pending["request_id"] = uuid.uuid4().hex
        pending["current"] = call
        yield {"type": "approval", "request_id": pending["request_id"],
               "name": call["name"],
               "detail": tool_detail(call["name"], parse_args(call["arguments"]))}
        return
    yield {"type": "delta", "text": "(步骤有点多,先到这。你可以继续说下一步)"}


# ---------- 通知 ----------

def notify_pushplus(title, content):
    """微信推送(需在 .env 配 PUSHPLUS_TOKEN);失败仅记日志。"""
    token = os.getenv("PUSHPLUS_TOKEN", "").strip()
    if not token:
        return
    try:
        req = urllib.request.Request(
            "http://www.pushplus.plus/send",
            data=json.dumps({"token": token, "title": title,
                             "content": content[:800]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[notify] 微信推送失败: {e}", flush=True)


# ---------- 接口 ----------

@app.post("/api/chat")
def api_chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")
    if not config.DEEPSEEK_API_KEY:
        return StreamingResponse(
            iter([
                sse({"type": "delta", "text": "未配置 DEEPSEEK_API_KEY,请在 partner/.env 中填写。"}),
                sse({"type": "done"}),
            ]),
            media_type="text/event-stream",
        )
    sid, session = get_session(req.session_id)
    # 体检:修复悬空工具调用(未处理的审批),防止 API 400 中毒
    session["messages"] = repair_session(session["messages"])
    session["messages"].append({"role": "user", "content": req.message.strip()})
    session["steps"] = 0
    session["pending"] = None
    if len(session["messages"]) > MAX_MESSAGES + 1:
        session["messages"] = session["messages"][:1] + session["messages"][-MAX_MESSAGES:]

    def gen():
        yield sse({"type": "session", "id": sid})
        try:
            for ev in run_loop(sid):
                yield sse(ev)
        except Exception as e:
            yield sse({"type": "delta", "text": f"\n(出错了:{e})"})
        finally:
            save_sessions()
        yield sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/approve")
def api_approve(req: ApproveRequest):
    session = sessions.get(req.session_id.strip())
    pending = session["pending"] if session else None
    if not pending or pending["request_id"] != req.request_id.strip():
        raise HTTPException(404, "审批请求不存在或已过期")
    sid = req.session_id.strip()
    call = pending["current"]
    pending["current"] = None

    def gen():
        try:
            if req.approved:
                audit_log("approve", f"允许 {call['name']}")
                for ev in run_one(session, call):
                    yield sse(ev)
            else:
                audit_log("approve", f"拒绝 {call['name']}")
                session["messages"].append(
                    tool_msg(call, "用户拒绝了此操作,请换一种方式或询问用户想法。"))
                yield sse({"type": "tool_result", "summary": "你已拒绝此操作"})
            if pending["rest"]:
                for ev in process_rest(sid):
                    yield sse(ev)
            else:
                session["pending"] = None
                for ev in run_loop(sid):
                    yield sse(ev)
        finally:
            save_sessions()
        yield sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")


def _bg_gate(allow_write):
    def gate(call):
        decision = permissions.check_tool(call["name"], parse_args(call["arguments"]))
        if decision == "allow":
            return True
        if decision == "deny":
            return "权限策略禁止此操作,请换一种方式或询问主人。"
        if allow_write:
            return True
        return ("主人在忙,这个后台任务不允许执行 {}。请改用只读方式(查看/统计/规划)完成,"
                "或把结论告诉主人,不要反复请求执行。").format(call["name"])
    return gate


def _spawn_task(message, allow_write, sid=""):
    """起后台任务线程:计划(强模型)→ 执行(工具循环)→ 质检(强模型)。"""
    sid, session = get_session(sid)
    tid = uuid.uuid4().hex[:12]
    task = {
        "id": tid,
        "message": message.strip(),
        "status": "running",
        "result": "",
        "created": time.strftime("%m-%d %H:%M"),
        "finished": "",
    }
    tasks[tid] = task
    if len(tasks) > MAX_TASKS:
        for old in sorted(tasks, key=lambda k: tasks[k]["created"])[:len(tasks) - MAX_TASKS]:
            tasks.pop(old, None)
    audit_log("task", f"开始后台任务: {message[:80]}")

    def worker():
        try:
            # 体检:修复悬空工具调用
            session["messages"] = repair_session(session["messages"])
            # 阶段一:计划
            plan = plan_task(task["message"], config.DEEPSEEK_MODEL_SMART)
            task["plan"] = plan
            # 阶段二:执行
            session["messages"].append({"role": "user", "content": task["message"]})
            session["steps"] = 0
            session["pending"] = None
            parts = []
            steps_log = []
            for ev in run_loop(sid, gate_handler=_bg_gate(allow_write),
                               model=config.DEEPSEEK_MODEL_SMART):
                if ev["type"] == "delta":
                    parts.append(ev.get("text", ""))
                elif ev["type"] == "tool":
                    steps_log.append(f"调用 {ev.get('name')}: {str(ev.get('detail', ''))[:60]}")
                elif ev["type"] == "tool_result":
                    steps_log.append(f"  → {str(ev.get('summary', ''))[:80]}")
            result = "".join(parts).strip() or "(无文字输出)"
            # 阶段三:质检
            report = verify_task(task["message"], result, "\n".join(steps_log),
                                 config.DEEPSEEK_MODEL_SMART)
            task["result"] = (
                (f"📋 计划:\n{plan}\n\n" if plan else "") +
                f"📝 执行结果:\n{result}\n\n" +
                (f"✅ 质检报告:\n{report}" if report else "")
            )
            task["status"] = "done"
        except Exception as e:
            task["status"] = "failed"
            task["result"] = f"出错:{e}"
        task["finished"] = time.strftime("%m-%d %H:%M")
        save_sessions()
        audit_log("task", f"任务结束 {tid}: {task['status']}")
        notify_pushplus(
            f"蓝蓝:任务完成",
            f"{task['message'][:60]}\n\n{task['result'][:500]}",
        )
        wecom.notify("蓝蓝:任务完成", f"{task['message'][:60]}\n\n{task['result'][:500]}")
        print(f"[task] {tid} -> {task['status']}", flush=True)

    threading.Thread(target=worker, daemon=True).start()
    return {"ok": True, "task_id": tid, "session_id": sid}


@app.post("/api/task")
def api_task(req: TaskRequest):
    """后台任务:计划-执行-质检三阶段。"""
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")
    return _spawn_task(req.message, req.allow_write, req.session_id)


@app.get("/api/tasks")
def api_tasks():
    return sorted(tasks.values(), key=lambda t: t["created"], reverse=True)


class ScheduleRequest(BaseModel):
    kind: str = "daily"      # daily(每天 HH:MM)或 interval(每 N 分钟)
    at: str = ""             # daily 用:"HH:MM"
    minutes: int = 0         # interval 用
    message: str
    allow_write: bool = False


@app.get("/api/schedule")
def api_schedule():
    return sorted(schedules.values(), key=lambda x: x.get("id", ""))


@app.post("/api/schedule")
def api_schedule_add(req: ScheduleRequest):
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")
    item = {
        "id": uuid.uuid4().hex[:10],
        "kind": req.kind,
        "at": req.at.strip(),
        "minutes": max(1, int(req.minutes or 0)),
        "message": req.message.strip(),
        "allow_write": req.allow_write,
        "last_run": "",
        "created": time.strftime("%m-%d %H:%M"),
    }
    schedules[item["id"]] = item
    save_schedules()
    audit_log("schedule", f"新建定时任务({item['kind']} {item['at'] or str(item['minutes']) + '分钟'}): {item['message'][:50]}")
    return {"ok": True, "id": item["id"]}


@app.delete("/api/schedule/{sid}")
def api_schedule_del(sid: str):
    if sid in schedules:
        schedules.pop(sid)
        save_schedules()
        audit_log("schedule", f"删除定时任务 {sid}")
    return {"ok": True}


def scheduler_loop():
    """调度线程:每 30 秒检查一次到期的定时任务。"""
    while True:
        time.sleep(30)
        try:
            now = time.localtime()
            cur_hm = time.strftime("%H:%M")
            for item in list(schedules.values()):
                due = False
                if item["kind"] == "daily":
                    due = item["at"] == cur_hm and item.get("last_run", "")[:5] != cur_hm
                elif item["kind"] == "interval":
                    last = item.get("last_run", "")
                    if last:
                        lt = time.strptime(last, "%m-%d %H:%M")
                        due = (time.time() - time.mktime(lt)) >= item["minutes"] * 60
                    else:
                        due = True
                if due:
                    item["last_run"] = time.strftime("%m-%d %H:%M")
                    save_schedules()
                    _spawn_task(item["message"], item["allow_write"])
                    print(f"[schedule] 触发: {item['message'][:40]}", flush=True)
        except Exception as e:
            print(f"[schedule] 检查出错: {e}", flush=True)


class PermissionRequest(BaseModel):
    target: str   # path | command
    value: str
    action: str   # allow | deny


@app.get("/api/permissions")
def api_permissions():
    return permissions.list_rules()


@app.post("/api/permissions")
def api_permissions_add(req: PermissionRequest):
    rule = permissions.add_rule(req.target, req.value, req.action)
    if not rule:
        raise HTTPException(400, "参数不对(target=path/command, action=allow/deny)")
    audit_log("permission", f"新增规则 {req.target} {req.value} → {req.action}")
    return {"ok": True, "rule": rule}


@app.delete("/api/permissions/{rid}")
def api_permissions_del(rid: str):
    permissions.delete_rule(rid)
    audit_log("permission", f"删除规则 {rid}")
    return {"ok": True}


class SyncUploadRequest(BaseModel):
    memories: list = Field(default_factory=list)


@app.get("/api/sync/memories")
def api_sync_list():
    """记忆同步:返回本机全部记忆(双层),供对端拉取。"""
    return [{"id": it["id"], "scope": it["scope"], "content": it["content"], "meta": it["meta"]}
            for it in memory_store.list_memories("all", 5000)]


@app.post("/api/sync/memories")
def api_sync_upload(req: SyncUploadRequest):
    """记忆同步:接收对端推来的新记忆(按原 id 导入,已存在的跳过)。"""
    added = 0
    for m in req.memories:
        if isinstance(m, dict) and m.get("id") and m.get("scope"):
            if memory_store.save_memory_with_id(
                    m["id"], str(m.get("content", "")), m["scope"], str(m.get("meta", ""))):
                added += 1
    if added:
        print(f"[sync] 导入 {added} 条对端记忆", flush=True)
    return {"ok": True, "added": added}


def memory_sync_loop():
    """记忆同步线程(仅配置了 SYNC_SERVER_URL 的一端跑):每 30 秒与中枢对账。"""
    import urllib.parse
    import urllib.request

    url = os.getenv("SYNC_SERVER_URL", "").strip().rstrip("/")
    if not url:
        return
    while True:
        time.sleep(30)
        try:
            # 用对端口令:SYNC_KEY 配置服务器那套的 ACCESS_KEY
            key = os.getenv("SYNC_KEY", config.ACCESS_KEY).strip()
            # 1) 拉取中枢记忆
            req = urllib.request.Request(
                f"{url}/api/sync/memories?key={urllib.parse.quote(key)}")
            with urllib.request.urlopen(req, timeout=20) as r:
                remote = json.loads(r.read().decode())
            local = memory_store.list_memories("all", 5000)
            local_ids = {it["id"] for it in local}
            for m in remote:
                if m.get("id") not in local_ids:
                    memory_store.save_memory_with_id(
                        m["id"], str(m.get("content", "")), m.get("scope", "public"),
                        str(m.get("meta", "")))
            # 2) 推送本地独有记忆
            remote_ids = {m.get("id") for m in remote}
            to_push = [{"id": it["id"], "scope": it["scope"],
                        "content": it["content"], "meta": it["meta"]}
                       for it in local if it["id"] not in remote_ids]
            if to_push:
                payload = json.dumps({"memories": to_push}).encode()
                req2 = urllib.request.Request(
                    f"{url}/api/sync/memories?key={urllib.parse.quote(key)}",
                    data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req2, timeout=20) as r2:
                    r2.read()
        except Exception as e:
            print(f"[sync] 同步失败: {e}", flush=True)


@app.get("/api/audit")
def api_audit(limit: int = 100):
    """行动审计:返回最近的工具执行/审批/任务记录。"""
    try:
        if not AUDIT_FILE.exists():
            return []
        lines = AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
        out = []
        for line in reversed(lines[-limit:]):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
    except Exception:
        return []


@app.get("/api/sessions")
def api_sessions():
    """聊天记录列表:标题(首条用户消息)+ 时间 + 条数。"""
    out = []
    for sid, s in sessions.items():
        title = ""
        for m in s["messages"]:
            if m.get("role") == "user":
                title = m.get("content", "").strip()[:30]
                break
        out.append({
            "id": sid,
            "title": title or "(空会话)",
            "updated": s.get("updated", ""),
            "count": sum(1 for m in s["messages"] if m.get("role") == "user"),
        })
    out.sort(key=lambda x: x["updated"], reverse=True)
    return out[:50]


@app.get("/api/session/{sid}/messages")
def api_session_messages(sid: str):
    """返回某会话的聊天内容(user/assistant 文本消息)。"""
    s = sessions.get(sid)
    if not s:
        raise HTTPException(404, "会话不存在")
    return [
        {"role": m["role"], "content": m.get("content")}
        for m in s["messages"]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """上传图片(手机拍照/相册),返回 OCR 文字与画面描述。"""
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "图片太大(>10MB)")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in tools.IMAGE_EXTS:
        raise HTTPException(400, "只支持图片文件(png/jpg/bmp/gif/webp)")
    uploads = config.BASE_DIR / "uploads"
    uploads.mkdir(exist_ok=True)
    name = f"up_{uuid.uuid4().hex}{ext}"
    (uploads / name).write_bytes(data)
    return {"ok": True, "file": name, "text": tools.read_image(str(uploads / name))}


@app.get("/api/memories")
def api_memories(scope: str = "all", limit: int = 50):
    return memory_store.list_memories(scope, limit)


@app.delete("/api/memories/{scope}/{mid}")
def api_delete_memory(scope: str, mid: str):
    if scope not in ("public", "private"):
        raise HTTPException(400, "scope 必须是 public 或 private")
    return {"ok": memory_store.delete_memory(mid, scope)}


app.mount("/static", StaticFiles(directory=config.BASE_DIR / "static"), name="static")

# 启动时恢复历史会话(必须在路由注册之后、服务启动之前调用)
load_sessions()
load_schedules()
permissions.load()


if __name__ == "__main__":
    import uvicorn

    threading.Thread(target=scheduler_loop, daemon=True).start()
    threading.Thread(target=memory_sync_loop, daemon=True).start()
    # HOST 可配置:服务器上设 HOST=127.0.0.1 只监听本机(有 run_command/write_file,不暴露公网)
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8000")))
