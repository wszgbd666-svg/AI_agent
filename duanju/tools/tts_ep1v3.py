# -*- coding: utf-8 -*-
"""第1集 v3 新配音: 周凯(受害者)台词, 用少年音 Yunxia 区别于林默"""
import asyncio, edge_tts, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tmp_audio")
os.makedirs(OUT, exist_ok=True)

LINES = [
    ("v3-zhou1", "zh-CN-YunxiaNeural", "垃圾短信吧？谁信这个啊。"),
    ("v3-zhou2", "zh-CN-YunxiaNeural", "照个镜子还能死啊？"),
]

async def gen():
    for name, voice, text in LINES:
        await edge_tts.Communicate(text, voice, rate="+5%").save(
            os.path.join(OUT, name + ".mp3"))
        print("OK", name, text)

asyncio.run(gen())
