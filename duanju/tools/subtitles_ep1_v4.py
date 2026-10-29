# -*- coding: utf-8 -*-
"""第1集 v4 字幕: 临摹《反相之地》播报式字幕系统
- 播报/规则 = 底部白色 "– xxx"(仿广播) + 顶部红色警示
- 台词 = 底部白色带人名
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tmp_build", "sub-ep1-v4.ass")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dialogue,微软雅黑,40,&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,2,1,2,40,40,150,1
Style: Rule,微软雅黑,46,&H003030FF,&H003030FF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,3,2,8,60,60,60,1
Style: Notice,微软雅黑,32,&H0000B4FF,&H0000B4FF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,2,1,8,60,60,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# (开始, 结束, 样式, 文本)
LINES = [
    (0, 4.5, "Notice", "【观影提示】本片内容纯属虚构，内含惊悚元素"),
    (0.5, 3, "Rule", "– 各位同学请注意：今晚零点起，请勿照镜子。"),
    (5, 6.8, "Dialogue", "王富贵：照个镜子还能死啊？"),
    (6.8, 9, "Dialogue", "林默：别瞎试，规则说得很清楚。"),
    (16.5, 19, "Rule", "– 规则二：听见有人叫你的名字，不要回头。"),
    (24, 26.5, "Dialogue", "林默：规则二……修订。"),
    (31.5, 34, "Dialogue", "王富贵：大半夜的你站那干嘛呢？"),
    (34, 36, "Rule", "存在感 -1"),
    (41.5, 44, "Rule", "– 规则三：今夜零点，全校师生请到操场集合。"),
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
