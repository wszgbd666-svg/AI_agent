# -*- coding: utf-8 -*-
"""知识库:加载 docs/*.md,按标题切块,用字符一元组+二元组重叠打分检索。零第三方依赖。

文件格式(每份 .md 开头):
    ---
    title: 文件标题
    source: 发文单位+文号
    url: 官方链接
    date: 2023-05-21
    fetched: 2026-10-29
    ---
    正文,用 "## 小节标题" 分节。
"""
import os
import re

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

# 查询词里过滤掉的常见口语虚词(只在打分时过滤,不影响正文)
STOP = set("的了吗呢啊呀哦嗯吧这那是就都也了会可以请问一下我想要知道多少什么是怎么")
META_RE = re.compile(r"^([a-z_]+):\s*(.+)$", re.I)


def _norm(s):
    """只保留中文、字母、数字。"""
    out = []
    for ch in s.lower():
        if "一" <= ch <= "鿿" or ch.isalnum():
            out.append(ch)
    return "".join(out)


def _tokens(s):
    """一元组 + 二元组集合。"""
    s = _norm(s)
    toks = set(s)
    for i in range(len(s) - 1):
        toks.add(s[i:i + 2])
    return toks


class Chunk:
    __slots__ = ("doc", "section", "text", "toks")

    def __init__(self, doc, section, text):
        self.doc = doc
        self.section = section
        self.text = text
        # 文件标题+小节标题并入正文一起打分:问"养老金"能命中整份养老金文件,问"高龄津贴"能命中该节
        self.toks = _tokens(doc.title + section + text)


class Doc:
    def __init__(self, path):
        raw = open(path, encoding="utf-8").read()
        meta, body = {}, raw
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) == 3:
                for line in parts[1].strip().splitlines():
                    m = META_RE.match(line.strip())
                    if m:
                        meta[m.group(1)] = m.group(2).strip()
                body = parts[2]
        self.title = meta.get("title", os.path.basename(path))
        self.source = meta.get("source", "")
        self.url = meta.get("url", "")
        self.date = meta.get("date", "")
        self.fetched = meta.get("fetched", "")
        # 可选:该文件适用的地区(如"湖北省"),留空 = 全国通用
        self.region = meta.get("region", "")
        self.chunks = self._chunk(body)

    def meta(self):
        return {
            "title": self.title, "source": self.source, "url": self.url,
            "date": self.date, "fetched": self.fetched,
            "region": self.region, "chunks": len(self.chunks),
        }

    def _chunk(self, body):
        chunks, sec, buf = [], "正文", []
        for line in body.splitlines():
            line = line.rstrip()
            if line.startswith("## "):
                self._flush(chunks, sec, buf)
                sec, buf = line[3:].strip(), []
            elif line.strip():
                buf.append(line.strip())
        self._flush(chunks, sec, buf)
        return chunks

    def _flush(self, chunks, sec, buf):
        if not buf:
            return
        for piece in self._split("。".join(buf), 380):
            chunks.append(Chunk(self, sec, piece))

    @staticmethod
    def _split(text, limit):
        if len(text) <= limit:
            return [text]
        out, cur = [], ""
        for sen in re.split(r"(?<=[。！？])", text):
            if not sen:
                continue
            if len(cur) + len(sen) > limit and cur:
                out.append(cur)
                cur = ""
            cur += sen
        if cur:
            out.append(cur)
        return out or [text]


def reload():
    """重新扫描 docs 目录(用户放进新文件后调用 /api/reload 即可生效)。"""
    global docs, all_chunks
    docs = []
    for name in sorted(os.listdir(DOCS_DIR)):
        if name.endswith(".md"):
            docs.append(Doc(os.path.join(DOCS_DIR, name)))
    all_chunks = [c for d in docs for c in d.chunks]


def _region_norm(s):
    """去掉省市等后缀,方便"湖北省"和"湖北武汉市"互相匹配。"""
    return re.sub(r"[省市区县自治特别行政区壮族回族维吾尔]", "", s or "")


def retrieve(query, region=None, top_k=5, threshold=0.30, max_chars=2600):
    """返回 [(score, chunk)];空列表表示知识库里没有相关内容。
    region:居民所在地区,命中该地区文件的片段分数 ×1.6 加权(全国通用文件不加不扣)。"""
    q = _norm(query)
    qtoks = {t for t in _tokens(q) if len(t) > 1 or t not in STOP}
    if not qtoks:
        return []
    rn = _region_norm(region)
    scored = []
    for c in all_chunks:
        hit = len(qtoks & c.toks)
        if hit >= 2:
            score = hit / len(qtoks)
            if c.doc.region and rn:
                dn = _region_norm(c.doc.region)
                if dn in rn or rn in dn:
                    score *= 1.6
            if score >= threshold:
                scored.append((score, c))
    scored.sort(key=lambda t: -t[0])
    picked, seen, total = [], set(), 0
    for score, c in scored:
        key = (c.doc.title, c.section)
        if key in seen:
            continue
        seen.add(key)
        if total + len(c.text) > max_chars:
            continue
        total += len(c.text)
        picked.append((score, c))
        if len(picked) >= top_k:
            break
    return picked


docs = []
all_chunks = []
reload()
