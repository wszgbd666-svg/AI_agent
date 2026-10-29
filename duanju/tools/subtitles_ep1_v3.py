# -*- coding: utf-8 -*-
"""第1集 v3 字幕: 零旁白, 纯规则+台词 (临摹爆款: 不解释, 让观众自己推理)"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tmp_build", "sub-ep1-v3.ass")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dialogue,微软雅黑,40,&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,2,1,2,40,40,150,1
Style: Rule,微软雅黑,46,&H003030FF,&H003030FF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,3,2,8,60,60,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

LINES = [
    (1.5, 3.0, "Rule", "【今日规则】零点后，不要照镜子。"),
    (3.0, 5.5, "Dialogue", "周凯：垃圾短信吧？谁信这个啊。"),
    (5.5, 8.0, "Dialogue", "周凯：照个镜子还能死啊？"),
    (15.5, 17.5, "Rule", "规则二：听见有人叫你的名字，不要回头。"),
    (22.5, 25.0, "Dialogue", "林默：规则二……修订。"),
    (30.0, 32.5, "Dialogue", "王富贵：大半夜的你站那干嘛呢？"),
    (32.5, 34.5, "Rule", "存在感 -1"),
    (43.5, 46.0, "Rule", "规则三：今夜零点，全校师生请到操场集合。"),
]

def ts(sec):
    h, m = int(sec // 3600), int(sec % 3600 // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HEADER)
    for st, en, style, text in LINES:
        f.write(f"Dialogue: 0,{ts(st)},{ts(en)},{style},,0,0,0,,{text}\n")
print("ASS ->", OUT)
