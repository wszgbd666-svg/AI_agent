"""权限规则测试:匹配、优先级、增删。"""

from core import permissions


def setup_function():
    permissions.rules = []


def test_default_ask():
    assert permissions.check_tool("write_file", {"path": "D:/any/x.txt"}) == "ask"
    assert permissions.check_tool("run_command", {"command": "dir"}) == "ask"
    assert permissions.check_tool("read_file", {"path": "x"}) == "ask"


def test_path_allow():
    permissions.add_rule("path", "D:/notes", "allow")
    assert permissions.check_tool("write_file", {"path": "D:/notes/日记.md"}) == "allow"
    # 前缀之外仍要问
    assert permissions.check_tool("write_file", {"path": "D:/other/x.txt"}) == "ask"


def test_path_deny_priority_over_allow():
    permissions.add_rule("path", "D:/", "allow")
    permissions.add_rule("path", "D:/Windows秘密", "deny")
    assert permissions.check_tool("write_file", {"path": "D:/notes/x.txt"}) == "allow"
    assert permissions.check_tool("write_file", {"path": "D:/Windows秘密/x.txt"}) == "deny"


def test_command_substring():
    permissions.add_rule("command", "git status", "allow")
    assert permissions.check_tool("run_command", {"command": "git status --short"}) == "allow"
    assert permissions.check_tool("run_command", {"command": "git push"}) == "ask"


def test_add_delete_rule():
    r = permissions.add_rule("path", "D:/temp", "deny")
    assert r is not None
    assert any(x["id"] == r["id"] for x in permissions.list_rules())
    permissions.delete_rule(r["id"])
    assert not any(x["id"] == r["id"] for x in permissions.list_rules())


def test_add_rule_invalid():
    assert permissions.add_rule("bogus", "x", "allow") is None
    assert permissions.add_rule("path", "", "allow") is None
    assert permissions.add_rule("path", "x", "maybe") is None
