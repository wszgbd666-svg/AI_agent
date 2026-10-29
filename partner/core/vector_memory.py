"""向量记忆:语义检索层。

Embedding 优先级:
1. 云端:阿里云百炼 DashScope(需要 .env 里配 DASHCOPE_API_KEY,OpenAI 兼容接口)
2. 本地:sentence-transformers text2vec-base-chinese(家电脑用,hf-mirror)
两者都不可用 → 自动禁用,回退关键词搜索(不影响其他功能)。
"""

import json
import os
import threading
import urllib.request

from core import config

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

_collection = None
_init_lock = threading.Lock()
_failed = False


def _cloud_embed(texts):
    """DashScope text-embedding(OpenAI 兼容),返回向量列表。"""
    key = os.getenv("DASHCOPE_API_KEY", "").strip()
    model = os.getenv("DASHCOPE_EMBED_MODEL", "text-embedding-v3")
    body = json.dumps({
        "model": model,
        "input": texts,
        "encoding_format": "float",
    }).encode()
    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    return [item["embedding"] for item in data["data"]]


class _CloudEF:
    def name(self):
        return "dashscope-text-embedding-v3"

    def __call__(self, input):
        texts = input if isinstance(input, list) else [input]
        return _cloud_embed(texts)


def _get_collection():
    """懒加载 Chroma 集合;失败返回 None(关键词搜索兜底)。"""
    global _collection, _failed
    if _failed:
        return None
    if _collection is not None:
        return _collection
    with _init_lock:
        if _collection is not None or _failed:
            return _collection
        try:
            import chromadb
            from chromadb.config import Settings

            client = chromadb.PersistentClient(
                path=str(config.BASE_DIR.parent / "chroma_db"),
                settings=Settings(anonymized_telemetry=False),
            )
            if os.getenv("DASHCOPE_API_KEY", "").strip():
                ef = _CloudEF()
                print("[vector_memory] 使用云端 embedding (DashScope)", flush=True)
            else:
                from chromadb.utils import embedding_functions
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="shibing624/text2vec-base-chinese"
                )
                print("[vector_memory] 使用本地 embedding (text2vec)", flush=True)
            _collection = client.get_or_create_collection(
                name="partner_memories", embedding_function=ef,
            )
            return _collection
        except Exception as e:
            print(f"[vector_memory] 初始化失败,回退关键词搜索: {e}", flush=True)
            _failed = True
            return None


def add_memory(mid, content, scope):
    col = _get_collection()
    if col is None:
        return False
    try:
        col.upsert(documents=[content], ids=[mid], metadatas=[{"scope": scope}])
        return True
    except Exception:
        return False


def search(query, scope="all", limit=5):
    """语义搜索,返回 [{id, content, scope, meta}]。"""
    col = _get_collection()
    if col is None:
        return []
    try:
        where = None if scope == "all" else {"scope": scope}
        res = col.query(query_texts=[query], n_results=limit, where=where)
        hits = []
        docs = res.get("documents") or [[]]
        metas = res.get("metadatas") or [[]]
        ids = res.get("ids") or [[]]
        for i, mid in enumerate(ids[0]):
            hits.append({
                "id": mid,
                "content": (docs[0][i] if i < len(docs[0]) else ""),
                "meta": str((metas[0][i] if i < len(metas[0]) else {}) or {}),
                "scope": (metas[0][i] or {}).get("scope", "") if metas and metas[0] else "",
            })
        return hits
    except Exception:
        return []


def delete_memory(mid):
    col = _get_collection()
    if col is None:
        return
    try:
        col.delete(ids=[mid])
    except Exception:
        pass


def backfill_all(memories):
    """把已有的 md 记忆批量灌入向量库(首次启用时,幂等)。"""
    col = _get_collection()
    if col is None:
        return
    try:
        existing = set(col.get().get("ids", []))
        docs, ids, metas = [], [], []
        for it in memories:
            if it["id"] in existing:
                continue
            ids.append(it["id"])
            docs.append(it["content"])
            metas.append({"scope": it["scope"]})
        if ids:
            col.upsert(documents=docs, ids=ids, metadatas=metas)
            print(f"[vector_memory] 回填 {len(ids)} 条历史记忆", flush=True)
    except Exception as e:
        print(f"[vector_memory] 回填失败: {e}", flush=True)
