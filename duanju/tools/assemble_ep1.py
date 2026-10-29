# -*- coding: utf-8 -*-
"""第1集合成: 10镜头拼接 + 横转竖(模糊背景) + 配音对齐 -> 成片
用法: python assemble_ep1.py
"""
import os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = r"D:\DevTools\Python\Miniconda3\envs\ai\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
SRC = r"d:/AI_agent/duanju/素材/第1集"
AUD = os.path.join(HERE, "tmp_audio")
TMP = os.path.join(HERE, "tmp_build")
os.makedirs(TMP, exist_ok=True)

# 镜头 -> 配音文件 (s03/s06 无配音)
SHOTS = [("镜01", "s01"), ("镜02", "s02"), ("镜03", None), ("镜04", "s04"),
         ("镜05", "s05"), ("镜06", None), ("镜07", "s07"), ("镜08", "s08"),
         ("镜09", "s09"), ("镜10", "s10")]

def run(args):
    r = subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error"] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("FFMPEG ERROR:", r.stderr[-800:])
        sys.exit(1)

missing = [s for s, _ in SHOTS if not os.path.exists(os.path.join(SRC, s + ".mp4"))]
if missing:
    print("缺少镜头文件:", missing)
    sys.exit(1)

# 1) 每个镜头: 统一24fps -> 竖屏 720x1280
#    竖屏源(比例<=1): 直接放大填满画布(轻微裁边)
#    横屏源(比例>1) : 模糊背景填充 + 居中
import cv2 as _cv2
for i, (shot, _) in enumerate(SHOTS):
    src = os.path.join(SRC, shot + ".mp4")
    dst = os.path.join(TMP, f"v{i}.mp4")
    _v = _cv2.VideoCapture(src)
    _w, _h = int(_v.get(3)), int(_v.get(4))
    _v.release()
    if _h > _w:  # 竖屏源: 填满, 不压扁
        vf = "fps=24,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1"
    else:        # 横屏源: 模糊背景 + 居中
        vf = ("fps=24,split[a][b];"
              "[b]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=20:2[bg];"
              "[a]scale=720:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    run(["-i", src, "-vf", vf,
         "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", dst])
    print(f"{shot} ({_w}x{_h}) 竖屏化完成 {i+1}/10")

# 2) 拼接
concat_file = os.path.join(TMP, "list.txt")
with open(concat_file, "w") as f:
    for i in range(len(SHOTS)):
        f.write(f"file '{os.path.join(TMP, f'v{i}.mp4')}'\n")
run(["-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy",
     os.path.join(TMP, "video.mp4")])

# 3) 配音对齐 + 烧录字幕: 每镜5秒 adelay 混音, subtitles 滤镜烧 ASS
ASS = os.path.join(TMP, "sub-ep1.ass").replace("\\", "/")
ass_filter = (f"subtitles=filename='{ASS.replace(':', '\\:')}'"
              f":fontsdir='C\\:/Windows/Fonts'")
amix_inputs = []
filters = ["[0:v]" + ass_filter + "[vout]"]
for i, (_, audio) in enumerate(SHOTS):
    if audio is None:
        continue
    apath = os.path.join(AUD, audio + ".mp3")
    amix_inputs += ["-i", apath]
    idx = len(filters)
    filters.append(f"[{idx}:a]adelay={i * 5000}|{i * 5000}[a{idx - 1}]")
n_audio = len(amix_inputs) // 2
filters.append("".join(f"[a{i}]" for i in range(n_audio)) +
                f"amix=inputs={n_audio}:normalize=0[aout]")
run(["-i", os.path.join(TMP, "video.mp4")] + amix_inputs +
    ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
     "-c:v", "libx264", "-preset", "fast", "-crf", "20",
     "-c:a", "aac", "-t", "50",
     os.path.join(TMP, "ep1_final.mp4")])

# 4) 拷贝成片 (中文名)
final = os.path.join(SRC, "第1集-成片.mp4")
shutil.copy(os.path.join(TMP, "ep1_final.mp4"), final)
print("成片完成 ->", final)
