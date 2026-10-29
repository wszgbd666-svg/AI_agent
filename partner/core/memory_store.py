"""双层记忆存储:公有(可分享)与私有(敏感)。

每条记忆是一个独立的 markdown 文件,目录下有自动生成的 MEMORY.md 索引。
memory/private/ 已被 .gitignore 忽略,绝不提交到 git。
"""

import re
import secrets
from datetime import datetime

from core import vector_memory
from core.config import PRIVATE_MEMORY_DIR, PUBLIC_MEMORY_DIR

SCOPES = {
    "public": PUBLIC_MEMORY_DIR,
    "private": PRIVATE_MEMORY_DIR,
}

HEADER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
ID_PATTERN = re.compile(r"^m\d{8}_\d{6}_[0-9a-f]{6}$")


def _ensure_dirs():
    for d in SCOPES.values():
        d.mkdir(parents=True, exist_ok=True)


def _new_id():
    return f"m{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}"


def save_memory(content, scope, tags=None):
    """写入一条记忆,返回记忆 id。scope 非法时默认 private(更安全)。"""
    if scope not in SCOPES:
        scope = "private"
    _ensure_dirs()
    mid = _new_id()
    tags_line = f"tags: [{', '.join(tags)}]" if tags else "tags: []"
    created = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = f"---\n{tags_line}\ncreated: {created}\n---\n\n{content.strip()}\n"
    (SCOPES[scope] / f"{mid}.md").write_text(text, encoding="utf-8")
    _rebuild_index(scope)
    vector_memory.add_memory(mid, content.strip(), scope)  # 向量索引,失败不影响主流程
    return mid


def save_memory_with_id(mid, content, scope, meta=""):
    """按指定 id 写入记忆(记忆同步导入用,保持两边 id 一致)。已存在则跳过。"""
    if scope not in SCOPES or not ID_PATTERN.match(mid or ""):
        return False
    _ensure_dirs()
    path = SCOPES[scope] / f"{mid}.md"
    if path.exists():
        return False
    header = meta.strip() or "tags: []\ncreated: " + datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(f"---\n{header}\n---\n\n{content.strip()}\n", encoding="utf-8")
    _rebuild_index(scope)
    vector_memory.add_memory(mid, content.strip(), scope)
    return True


def _parse_file(path):
    text = path.read_text(encoding="utf-8")
    m = HEADER_RE.match(text)
    if m:
        return m.group(1), text[m.end():].strip()
    return "", text.strip()


def _load_all(scope):
    _ensure_dirs()
    items = []
    for f in sorted(SCOPES[scope].glob("*.md")):
        if not ID_PATTERN.match(f.stem):
            continue
        meta, body = _parse_file(f)
        items.append({"id": f.stem, "meta": meta, "content": body})
    return items


def list_memories(scope="all", limit=20):
    scopes = ["public", "private"] if scope == "all" else ([scope] if scope in SCOPES else [])
    items = []
    for s in scopes:
        items.extend({**it, "scope": s} for it in _load_all(s))
    items.sort(key=lambda x: x["id"], reverse=True)
    return items[:limit]


def search_memories(query, scope="all", limit=5):
    """混合搜索:向量语义搜索优先,关键词结果补充(按 id 去重)。"""
    q = str(query).strip()
    if not q:
        return []
    result = []
    seen = set()

    def add(it):
        if it["id"] not in seen:
            seen.add(it["id"])
            result.append(it)

    # 0) 惰性回填:把启用向量前的历史记忆灌进向量库(幂等)
    vector_memory.backfill_all(list_memories("all", 1000))

    # 1) 向量语义搜索(换种说法也能命中)
    for hit in vector_memory.search(q, scope, limit):
        full = get_memory(hit["id"], hit["scope"])
        add(full or hit)

    # 2) 关键词搜索兜底/补充
    low = q.lower()
    frags = [low] + _fragments(low)
    scored = []
    for it in list_memories(scope, 1000):
        hay = (it["content"] + "\n" + it["meta"]).lower()
        hits = [f for f in frags if f in hay]
        if hits:
            score = 999 if low in hay else len(set(hits))
            scored.append((score, it))
    scored.sort(key=lambda x: -x[0])
    for _, it in scored:
        add(it)
        if len(result) >= limit:
            break
    return result[:limit]


_STOPWORDS = set("的了吗呢吧啊呀哦我你他她它你们我们什么怎么为什么哪如何这个那个这些那些是有关于说过之前现在可以帮请")


def _fragments(q):
    """把查询拆成可匹配的片段:去停用词后的词语 + 相邻二字组合(中文换说法也能命中)。"""
    frags = []
    for w in re.split(r"[\s,。.!?;:、'\"()]+", q):
        w = "".join(ch for ch in w if ch not in _STOPWORDS)
        if len(w) >= 2:
            frags.append(w)
            frags.extend(w[i:i + 2] for i in range(len(w) - 1))
    return [f for f in frags if f]


def get_memory(mid, scope):
    if scope not in SCOPES:
        return None
    path = SCOPES[scope] / f"{mid}.md"
    if not path.exists():
        return None
    meta, body = _parse_file(path)
    return {"id": mid, "scope": scope, "meta": meta, "content": body}


def delete_memory(mid, scope):
    if scope not in SCOPES or not ID_PATTERN.match(mid or ""):
        return False
    path = SCOPES[scope] / f"{mid}.md"
    if not path.exists():
        return False
    path.unlink()
    _rebuild_index(scope)
    vector_memory.delete_memory(mid)
    return True


def _rebuild_index(scope):
    lines = ["# 记忆索引\n"]
    for it in sorted(_load_all(scope), key=lambda x: x["id"]):
        first = it["content"].splitlines()[0][:40] if it["content"] else ""
        lines.append(f"- [{first}]({it['id']}.md)")
    (SCOPES[scope] / "MEMORY.md").write_text("\n".join(lines), encoding="utf-8")
