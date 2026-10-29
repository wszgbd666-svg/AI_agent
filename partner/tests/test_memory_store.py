"""双层记忆测试:写入、搜索(关键词+双字组合)、删除、默认私有。"""


def test_save_and_list(mem_store):
    mid = mem_store.save_memory("用户喜欢用手机看效果图", "public")
    items = mem_store.list_memories("public")
    assert any(it["id"] == mid and "手机" in it["content"] for it in items)


def test_bad_scope_defaults_private(mem_store):
    mid = mem_store.save_memory("敏感信息测试", "不存在的作用域")
    items = mem_store.list_memories("private")
    assert any(it["id"] == mid for it in items)
    assert not mem_store.list_memories("public")


def test_keyword_search(mem_store):
    mem_store.save_memory("断桥铝系列门窗是我们主推产品", "public")
    hits = mem_store.search_memories("断桥铝")
    assert hits and "断桥铝" in hits[0]["content"]


def test_bigram_search_different_phrasing(mem_store):
    mem_store.save_memory("断桥铝系列门窗是我们主推产品", "public")
    hits = mem_store.search_memories("我们卖什么门窗系列")
    assert any("断桥铝" in h["content"] for h in hits)


def test_search_scope_filter(mem_store):
    mem_store.save_memory("公开的偏好:喜欢蓝色", "public")
    mem_store.save_memory("私有密码:abc123", "private")
    hits = mem_store.search_memories("蓝色", scope="private")
    assert not any("蓝色" in h["content"] for h in hits)
    hits = mem_store.search_memories("蓝色", scope="public")
    assert any("蓝色" in h["content"] for h in hits)


def test_delete_memory(mem_store):
    mid = mem_store.save_memory("要删掉的记忆", "public")
    assert mem_store.delete_memory(mid, "public") is True
    assert mem_store.get_memory(mid, "public") is None
    assert mem_store.delete_memory(mid, "public") is False  # 再删返回 False


def test_delete_rejects_bad_id(mem_store):
    assert mem_store.delete_memory("../../etc/passwd", "public") is False
    assert mem_store.delete_memory("", "public") is False


def test_empty_search(mem_store):
    assert mem_store.search_memories("") == []
    assert mem_store.search_memories("   ") == []
