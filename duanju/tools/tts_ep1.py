# -*- coding: utf-8 -*-
"""第1集配音生成 (edge-tts 免费)
角色音色: 旁白=Yunjian低沉 / 林默=Yunxi青年 / 王富贵=Yunyang圆润
"""
import asyncio, edge_tts, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tmp_audio")
os.makedirs(OUT, exist_ok=True)

LINES = [
    ("s01", "zh-CN-YunjianNeural", "规则降临的那天，没有人当回事。"),
    ("s02", "zh-CN-YunyangNeural", "照个镜子还能死啊？"),
    ("s04", "zh-CN-YunyangNeural", "林默……过来帮我一把……"),
    ("s05", "zh-CN-YunjianNeural", "别人的规则簿只有遵守，他的，多了一个按钮。"),
    ("s07", "zh-CN-YunxiNeural", "规则二……修订。"),
    ("s08", "zh-CN-YunyangNeural", "大半夜的你站那干嘛呢？"),
    ("s09", "zh-CN-YunjianNeural", "每改一条规则，就扣一点存在感。"),
    ("s10", "zh-CN-YunjianNeural", "真正的怪谈，才刚开始。"),
]

async def gen():
    for name, voice, text in LINES:
        out = os.path.join(OUT, name + ".mp3")
        await edge_tts.Communicate(text, voice, rate="+10%").save(out)
        print("OK", name, text[:12])

asyncio.run(gen())
