"""工具层测试:safe_path 边界、文件读写、危险命令拦截。"""

from pathlib import Path

from core import config
from core import tools


def test_safe_path_inside_workspace():
    root = config.WORKSPACE_ROOTS[0]
    p = tools.safe_path(str(root / "some" / "file.txt"))
    assert p is not None
    assert p.parent.exists() is False  # 只解析不创建


def test_safe_path_outside_workspace_blocked():
    assert tools.safe_path("C:/Windows/System32/drivers/etc/hosts") is None


def test_safe_path_env_always_blocked():
    root = config.WORKSPACE_ROOTS[0]
    assert tools.safe_path(str(root / ".env")) is None
    assert tools.safe_path(str(root / "sub" / ".ENV")) is None  # 大小写不敏感


def test_safe_path_relative_anchored():
    p = tools.safe_path("随便一个相对路径")
    assert p is not None
    assert str(p).startswith(str(config.RELATIVE_ANCHOR))


def test_write_and_read_roundtrip():
    root = config.WORKSPACE_ROOTS[0]
    f = root / "test_roundtrip.txt"
    try:
        r = tools.write_file(str(f), "你好 Partner")
        assert "已写入" in r
        content = tools.read_file(str(f))
        assert "你好 Partner" in content
    finally:
        f.unlink(missing_ok=True)


def test_read_binary_graceful():
    root = config.WORKSPACE_ROOTS[0]
    f = root / "test_bin.bin"
    try:
        f.write_bytes(b"\x00\x01\x02\xff\xfe")
        r = tools.read_file(str(f))
        assert "二进制" in r or "不适合" in r
    finally:
        f.unlink(missing_ok=True)


def test_run_command_denylist():
    assert "安全策略拒绝" in tools.run_command("rm -rf /")
    assert "安全策略拒绝" in tools.run_command("shutdown /s")
    assert "安全策略拒绝" in tools.run_command("format C:")


def test_run_command_simple():
    r = tools.run_command("echo hello")
    assert "hello" in r


def test_list_dir_absolute_paths():
    root = config.WORKSPACE_ROOTS[0]
    sub = root / "test_list_dir"
    sub.mkdir(exist_ok=True)
    try:
        (sub / "a.txt").write_text("x", encoding="utf-8")
        out = tools.list_dir(str(sub))
        assert "a.txt" in out
        assert str(sub).replace("/", "\\") in out  # 绝对路径
    finally:
        (sub / "a.txt").unlink(missing_ok=True)
        sub.rmdir()
