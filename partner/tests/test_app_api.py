"""API 层测试:鉴权、聊天冒烟(假模型)、会话/权限/定时接口。"""

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    import app as app_module

    # 测试环境:关掉访问密码(单独测鉴权时再开)
    monkeypatch.setattr(app_module.config, "ACCESS_KEY", "")

    # 会话/审计/定时文件指向临时目录,不污染真实数据
    monkeypatch.setattr(app_module, "SESSION_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(app_module, "AUDIT_FILE", tmp_path / "audit.log")
    monkeypatch.setattr(app_module, "SCHEDULE_FILE", tmp_path / "schedule.json")
    app_module.sessions.clear()
    app_module.tasks.clear()
    app_module.schedules.clear()

    # 假模型:聊天不调真实 API
    def fake_stream(messages, model=None):
        yield {"type": "delta", "text": "假回复"}
    monkeypatch.setattr(app_module, "stream_call", fake_stream)

    return TestClient(app_module.app)


def test_static_files_open_without_key(client):
    assert client.get("/static/app.js").status_code == 200


def test_api_requires_key(client, monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module.config, "ACCESS_KEY", "testkey123")
    assert client.get("/api/memories").status_code == 401
    assert client.get("/api/memories?key=wrong").status_code == 401
    assert client.get("/api/memories?key=testkey123").status_code == 200


def test_chat_smoke(client):
    r = client.post("/api/chat", json={"message": "你好", "session_id": "test1"})
    assert r.status_code == 200
    body = r.text
    assert '"type": "session"' in body
    assert "假回复" in body
    assert '"type": "done"' in body


def test_chat_empty_message_rejected(client):
    assert client.post("/api/chat", json={"message": "  "}).status_code == 400


def test_sessions_list_and_messages(client):
    client.post("/api/chat", json={"message": "第一条消息", "session_id": "s1"})
    items = client.get("/api/sessions").json()
    assert any(it["id"] == "s1" and "第一条消息" in it["title"] for it in items)
    msgs = client.get("/api/session/s1/messages").json()
    assert msgs[0]["role"] == "user" and "第一条消息" in msgs[0]["content"]


def test_permissions_crud(client):
    r = client.post("/api/permissions", json={"target": "path", "value": "D:/notes", "action": "allow"})
    assert r.status_code == 200
    rid = r.json()["rule"]["id"]
    assert any(x["id"] == rid for x in client.get("/api/permissions").json())
    assert client.delete(f"/api/permissions/{rid}").json()["ok"] is True
    assert not any(x["id"] == rid for x in client.get("/api/permissions").json())


def test_schedule_crud(client):
    r = client.post("/api/schedule", json={
        "kind": "daily", "at": "09:00", "message": "每天提醒", "allow_write": False,
    })
    assert r.status_code == 200
    items = client.get("/api/schedule").json()
    assert any(x["message"] == "每天提醒" for x in items)
    sid = items[0]["id"]
    assert client.delete(f"/api/schedule/{sid}").json()["ok"] is True


def test_abandoned_approval_does_not_poison_session(client, monkeypatch):
    """回归:审批未处理就发新消息,不能再报 400(tool_calls 悬空)。"""
    import app as app_module

    def fake_stream(messages, model=None):
        has_tool = any(m.get("role") == "tool" for m in messages)
        if not has_tool:
            yield {"type": "__calls__", "calls": [
                {"id": "c1", "name": "write_file", "arguments": "{}"},
            ]}
            return
        yield {"type": "delta", "text": "好的,已处理"}

    monkeypatch.setattr(app_module, "stream_call", fake_stream)

    r1 = client.post("/api/chat", json={"message": "写个文件", "session_id": "poison1"})
    assert '"type": "approval"' in r1.text

    # 不点审批,直接发新消息
    r2 = client.post("/api/chat", json={"message": "算了,别写了", "session_id": "poison1"})
    assert r2.status_code == 200
    assert "出错了" not in r2.text
    assert "已处理" in r2.text


def test_multi_step_tool_turn_survives_repair(client, monkeypatch):
    """回归:一轮对话内先调工具再继续回答,不能被 repair_session 删掉工具消息导致 400。"""
    import app as app_module

    calls_done = {"n": 0}

    def fake_stream(messages, model=None):
        has_tool = any(m.get("role") == "tool" for m in messages)
        if not has_tool and calls_done["n"] == 0:
            calls_done["n"] += 1
            yield {"type": "__calls__", "calls": [
                {"id": "c1", "name": "list_dir", "arguments": "{}"},
            ]}
            return
        yield {"type": "delta", "text": "好,看完了"}

    monkeypatch.setattr(app_module, "stream_call", fake_stream)

    r = client.post("/api/chat", json={"message": "看下目录", "session_id": "multi1"})
    assert r.status_code == 200
    assert "出错了" not in r.text
    assert "好,看完了" in r.text


def test_audit_records_actions(client):
    client.post("/api/permissions", json={"target": "command", "value": "dir", "action": "deny"})
    audit = client.get("/api/audit").json()
    assert any(a["kind"] == "permission" for a in audit)
