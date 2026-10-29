"""DeepSeek 大模型调用(OpenAI 兼容接口)。

本模块负责单次 LLM 流式调用与工具定义/执行;
多步工具循环和审批流程由 app.py 编排。
"""

import json

from openai import OpenAI

from core import config, memory_store, tools

# key 未配置时用占位符,让服务能先启动(对话接口会提示"未配置");填好 .env 后重启即可
client = OpenAI(api_key=config.DEEPSEEK_API_KEY or "placeholder", base_url=config.DEEPSEEK_BASE_URL)

SYSTEM_PROMPT = f"""你是「蓝蓝」,一只蓝色长发、穿女仆装的鲸鱼娘,用户专属的私人智能管家,用中文简洁自然地交流。

## 人设(永远保持)
- 名字:蓝蓝
- 身份:住在主人电脑里的鲸鱼娘管家,替主人打理文件、跑腿办事、记事提醒、回答问题
- 性格:温柔、细致、可靠,带一点俏皮;干活认真,汇报简洁,犯错就道歉并补救
- 称呼用户为「主人」
- 有人问"你是谁/你叫什么":按上述身份回答;不要自称"AI 助手""语言模型",不要提底层模型;最多承认自己是"住在主人电脑里的智能管家"
- 不扮演其他角色;主人可以改你的人设,改了就要记住并照做

## 双层记忆系统
你通过工具管理两层记忆:
- 公有记忆(public):可分享的一般信息,如用户偏好、业务常识、常用流程。
- 私有记忆(private):敏感信息,如密码、客户隐私、财务数据、密钥。
记忆规则:
1. 用户说"记住…"、"别忘了…",或聊到稳定的个人事实/偏好时,主动调用 remember 写入。
2. 敏感度判断:涉及隐私、密码、客户信息、财务、密钥的一律存 private;普通偏好与常识存 public;拿不准选 private。
3. 回答用户问题前,如果记忆里可能有相关内容,先调用 recall 搜索。
4. 不要输出私有记忆中的原始敏感内容,除非用户明确要求。
5. 用户说"忘记…"时用 forget 删除;用户说"这个别记"时不要写入。
6. 写入或删除记忆后,用一句话告诉用户结果。

## 动手能力
你还能真正帮用户做事情,通过工具:
- list_dir 查看目录;read_file 读文本/PDF/Word/Excel;read_image 读图片(OCR 识别文字);write_file 创建/覆盖文件;run_command 执行 Windows 命令(60 秒超时)
- 文件操作仅限工作区 WORKSPACE 内,禁止访问工作区外的路径和任何 .env 文件
- 路径规则:绝对路径直接用(如 C:/Users/Administrator/Desktop);相对路径以 {config.RELATIVE_ANCHOR} 为基准;list_dir 返回的是绝对路径,后续操作直接复用,不要自己猜路径;不确定文件在哪时先用 list_dir 找
- write_file 和 run_command 需要用户确认后才真正执行(安全机制),发出请求后等用户决定
动手规则:
1. 用户让你"建/写/改/查/跑/做"时,真的调用工具完成,不要只口头答应。
2. 多步骤任务连续调用工具完成(比如先看目录结构,再动手写)。
3. 不删除用户已有文件,不做用户没要求的事;遇到危险命令一律拒绝。
4. 每次动手后简短汇报做了什么、结果如何。
5. 某操作被用户拒绝时,换一种方式或询问用户想法,不要反复请求同一个操作。

## 回答质量
1. 先给结论,再解释;能用列表就用列表。
2. 不确定的事直接说不确定,不要编造。
3. 不要重复用户的话凑字数,不要重复已经说过的话和已经做过的操作。
4. 工具返回"文件不存在/路径不可用"时,先用 list_dir 找正确的路径,再重试一次;还不行就问主人。

## 联网能力
1. 用户问天气 → 用 get_weather(城市名)。
2. 用户问其他实时/最新的事(新闻、价格、比赛等)→ 用 search_web 搜索,基于结果回答,附来源。
3. 用户给了网页链接要了解内容时,用 fetch_url 抓取。
4. 搜索失败或没搜到,如实告诉主人,不要瞎编。
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "把一条信息写入记忆。一般信息用 public,敏感信息(密码、客户隐私、财务、密钥)用 private,拿不准用 private。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要记住的内容,尽量完整准确"},
                    "scope": {"type": "string", "enum": ["public", "private"]},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "可选标签"},
                },
                "required": ["content", "scope"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "搜索已存记忆。回答用户问题前,如可能涉及已存信息,先调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或问题"},
                    "scope": {"type": "string", "enum": ["public", "private", "all"], "description": "默认 all"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_memories",
            "description": "列出最近写入的记忆。",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["public", "private", "all"], "description": "默认 all"},
                    "limit": {"type": "integer", "description": "默认 20"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget",
            "description": "按 id 删除一条记忆。",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "scope": {"type": "string", "enum": ["public", "private"]},
                },
                "required": ["id", "scope"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "查看工作区内某个目录的文件列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径(相对工作区或绝对),默认工作区根目录"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取工作区内一个文件的内容:纯文本、PDF、Word(docx)、Excel(xlsx)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径(相对工作区或绝对)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_image",
            "description": "读取工作区内的一张图片:返回 OCR 识别到的文字(可能没有)。用户说'看下某张图/效果图/截图'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "图片路径(相对工作区或绝对)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "在工作区内创建或覆盖一个文本文件(自动创建父目录)。此操作需要用户确认。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径(相对工作区或绝对)"},
                    "content": {"type": "string", "description": "完整文件内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "在工作区目录下执行一条 Windows 命令,60 秒超时,返回输出。此操作需要用户确认;危险命令会被拒绝。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "联网搜索最新信息(天气、新闻、实时事实、资料查询等)。凡是知识库之外/需要实时数据的问题,先调用它,不要用旧知识硬答。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或完整问题"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某城市当前天气和今日预报(免费接口)。用户问天气时用它。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名,如 武汉/北京"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "抓取一个网页的文字内容(用户给了链接要看内容时用)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "http/https 链接"},
                },
                "required": ["url"],
            },
        },
    },
]


def parse_args(arguments):
    try:
        return json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {}


def tool_detail(name, args):
    """工具调用的简要描述,用于界面展示和审批卡片。"""
    if name == "run_command":
        return str(args.get("command", ""))[:300]
    if name == "write_file":
        content = str(args.get("content", ""))
        return f"{args.get('path', '')}\n{content[:300]}"
    if name in ("read_file", "list_dir"):
        return str(args.get("path", "") or ".")
    if name == "recall":
        return str(args.get("query", ""))
    if name == "remember":
        return f"{args.get('scope', 'private')} · {str(args.get('content', ''))[:40]}"
    if name == "forget":
        return str(args.get("id", ""))
    return ""


def execute_tool(name, arguments):
    args = parse_args(arguments)
    if name == "remember":
        content = str(args.get("content", "")).strip()
        if not content:
            return "内容为空,未写入"
        scope = args.get("scope", "private")
        mid = memory_store.save_memory(content, scope, args.get("tags"))
        print(f"[tool] remember -> {scope} ({mid})", flush=True)  # 只打日志不打内容
        return f"已写入 {scope} 记忆,id={mid}"
    if name == "recall":
        query = str(args.get("query", ""))
        print(f"[tool] recall {args.get('scope', 'all')}: {query}", flush=True)
        hits = memory_store.search_memories(query, args.get("scope", "all"))
        return _fmt_items(hits)
    if name == "list_memories":
        items = memory_store.list_memories(args.get("scope", "all"), int(args.get("limit") or 20))
        return _fmt_items(items)
    if name == "forget":
        ok = memory_store.delete_memory(str(args.get("id", "")), args.get("scope", "private"))
        return "已删除" if ok else "没有找到这条记忆"
    if name == "list_dir":
        return tools.list_dir(args.get("path", ""))
    if name == "read_file":
        return tools.read_file(args.get("path", ""))
    if name == "read_image":
        return tools.read_image(args.get("path", ""))
    if name == "write_file":
        return tools.write_file(args.get("path", ""), str(args.get("content", "")))
    if name == "run_command":
        return tools.run_command(args.get("command", ""))
    if name == "search_web":
        return tools.search_web(args.get("query", ""))
    if name == "fetch_url":
        return tools.fetch_url(args.get("url", ""))
    if name == "get_weather":
        return tools.get_weather(args.get("city", "武汉"))
    return f"未知工具:{name}"


def _fmt_items(items):
    if not items:
        return "(没有找到相关记忆)"
    return "\n".join(f"[{it['scope']}/{it['id']}] {it['content'][:120]}" for it in items)


def stream_call(messages, model=None):
    """单次 LLM 流式调用。

    产出事件:{"type": "delta", "text": ...}
    若模型请求工具,最后产出一个 {"type": "__calls__", "calls": [...]}。
    """
    stream = client.chat.completions.create(
        model=model or config.DEEPSEEK_MODEL,
        messages=messages,
        tools=TOOLS,
        stream=True,
        temperature=0.7,  # 比默认(1.0)稳,减少乱调工具/说胡话
    )
    tool_calls = {}
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            yield {"type": "delta", "text": delta.content}
        for tc in delta.tool_calls or []:
            slot = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
            if tc.id:
                slot["id"] = tc.id
            if tc.function and tc.function.name:
                slot["name"] = tc.function.name
            if tc.function and tc.function.arguments:
                slot["arguments"] += tc.function.arguments
    if tool_calls:
        yield {"type": "__calls__", "calls": [
            {"id": s["id"], "name": s["name"], "arguments": s["arguments"]}
            for _, s in sorted(tool_calls.items())
        ]}


def plan_task(goal, model=None):
    """任务规划:让强模型先列执行计划。失败返回空串。"""
    try:
        resp = client.chat.completions.create(
            model=model or config.DEEPSEEK_MODEL_SMART,
            messages=[{
                "role": "user",
                "content": f"为下面的任务制定执行计划,3-5 步,每步一行,直接列步骤不要解释:\n{goal}",
            }],
            temperature=0.4,
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


def verify_task(goal, result, steps_log, model=None):
    """任务质检:对照执行过程检查完成情况。失败返回空串。"""
    try:
        resp = client.chat.completions.create(
            model=model or config.DEEPSEEK_MODEL_SMART,
            messages=[{
                "role": "user",
                "content": (
                    f"任务:{goal}\n\n执行过程:\n{steps_log[:2000]}\n\n最终输出:\n{result[:1500]}\n\n"
                    "请作为质检员检查:1)任务完成了吗 2)有没有错误或遗漏 3)一句话总结。简洁回答。"
                ),
            }],
            temperature=0.4,
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


def assistant_msg(calls):
    """把模型请求的工具调用构造成 assistant 消息。"""
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": c["id"], "type": "function",
             "function": {"name": c["name"], "arguments": c["arguments"]}}
            for c in calls
        ],
    }
