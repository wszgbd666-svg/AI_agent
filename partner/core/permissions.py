"""细粒度权限策略:在"全部确认"之上加规则层。

规则示例:
- 路径规则(write_file):「D:/notes」+ 允许 → 该目录下写文件免确认
- 命令规则(run_command):「git status」+ 允许 → 该命令免确认
- 任何规则 + 禁止 → 直接拦下,连审批都不弹

判定优先级:禁止 > 允许 > 询问(默认)。
"""

import json
import uuid

from core import config

PERM_FILE = config.BASE_DIR / "data" / "permissions.json"

# 规则列表:[{id, target: "path"|"command", value, action: "allow"|"deny"}]
rules = []


def load():
    global rules
    if PERM_FILE.exists():
        try:
            rules = json.loads(PERM_FILE.read_text(encoding="utf-8"))
        except Exception:
            rules = []


def save():
    try:
        PERM_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PERM_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")
        tmp.replace(PERM_FILE)
    except Exception:
        pass


def add_rule(target, value, action):
    if target not in ("path", "command") or action not in ("allow", "deny"):
        return None
    rule = {"id": uuid.uuid4().hex[:10], "target": target,
            "value": str(value).strip(), "action": action}
    if not rule["value"]:
        return None
    rules.append(rule)
    save()
    return rule


def delete_rule(rid):
    global rules
    rules = [r for r in rules if r["id"] != rid]
    save()


def list_rules():
    return list(rules)


def _norm(s):
    return s.replace("/", "\\").lower()


def check_tool(name, args):
    """返回 ask / allow / deny。"""
    if name == "write_file":
        v = _norm(str(args.get("path", "")))
        matched = [(r, _norm(r["value"])) for r in rules
                   if r["target"] == "path" and v.startswith(_norm(r["value"]))]
    elif name == "run_command":
        v = _norm(str(args.get("command", "")))
        matched = [(r, _norm(r["value"])) for r in rules
                   if r["target"] == "command" and _norm(r["value"]) in v]
    else:
        return "ask"
    for r, _ in matched:
        if r["action"] == "deny":
            return "deny"
    for r, _ in matched:
        if r["action"] == "allow":
            return "allow"
    return "ask"
