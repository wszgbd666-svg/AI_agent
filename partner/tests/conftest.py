"""测试全局配置:工作区指向临时目录,避免污染真实数据。"""

import os
import tempfile

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

_tmp = tempfile.mkdtemp(prefix="partner_test_")
os.environ["WORKSPACE_DIRS"] = _tmp.replace("\\", "/")

import pytest


@pytest.fixture
def mem_store(tmp_path, monkeypatch):
    """内存存储测试:隔离目录 + 屏蔽向量层(测试不下载模型)。"""
    import core.memory_store as ms

    monkeypatch.setattr(ms, "SCOPES", {
        "public": tmp_path / "public",
        "private": tmp_path / "private",
    })
    monkeypatch.setattr(ms.vector_memory, "add_memory", lambda *a, **k: False)
    monkeypatch.setattr(ms.vector_memory, "delete_memory", lambda *a, **k: None)
    monkeypatch.setattr(ms.vector_memory, "backfill_all", lambda *a, **k: None)
    monkeypatch.setattr(ms.vector_memory, "search", lambda *a, **k: [])
    return ms
