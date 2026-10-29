# -*- coding: utf-8 -*-
"""第1集 v2 电影化合成: 冷开场 + 快节奏 + 推镜 + BGM/音效/配音 全混音
"""
import os, shutil, subprocess, sys, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = r"D:\DevTools\Python\Miniconda3\envs\ai\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
SRC = r"d:/AI_agent/duanju/素材/第1集"
AUD = os.path.join(HERE, "tmp_audio")
TMP = os.path.join(HERE, "tmp_build")
os.makedirs(TMP, exist_ok=True)

# (镜头, 时长, TTS, 冷开场标记)
SEQ = [
    ("镜03", 1.5, None, True),
    ("镜01", 4.0, "s01", False),
    ("镜02", 4.5, "s02", False),
    ("镜03", 4.0, None, False),
    ("镜04", 4.5, "s04", False),
    ("镜05", 4.0, "s05", False),
    ("镜06", 3.5, None, False),
    ("镜07", 4.0, "s07", False),
    ("镜08", 4.0, "s08", False),
    ("镜09", 3.5, "s09", False),
    ("镜10", 4.5, "s10", False),
]
TOTAL = sum(d for _, d, _, _ in SEQ)

# (文件, 起始秒, 音量)
SFX = [
    ("sfx-sting.wav", 0.0, 0.9), ("sfx-ding.wav", 1.8, 0.7),
    ("sfx-hum.wav", 1.8, 0.55), ("sfx-heartbeat.wav", 10.0, 0.9),
    ("sfx-glass.wav", 10.8, 0.8), ("sfx-sting.wav", 11.5, 0.9),
    ("sfx-heartbeat.wav", 14.0, 0.9), ("sfx-heartbeat.wav", 22.5, 0.9),
    ("sfx-gold.wav", 26.0, 0.8), ("sfx-whoosh.wav", 30.0, 0.7),
    ("sfx-ding.wav", 34.0, 0.7), ("sfx-hum.wav", 37.5, 0.55),
    ("sfx-sting.wav", 41.0, 0.8),
]

def run(args):
    r = subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error"] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("FFMPEG ERROR:", r.stderr[-1000:])
        sys.exit(1)

def ms(sec):
    return int(sec * 1000)

# ---- 1) 每镜: 竖屏化 + 推镜 + 裁时长 ----
built = {}
for i, (shot, dur, _, cold) in enumerate(SEQ):
    key = f"{shot}-{dur}"
    if key in built:
        continue
    src = os.path.join(SRC, shot + ".mp4")
    dst = os.path.join(TMP, f"c{i}.mp4")
    v = cv2.VideoCapture(src)
    w, h = int(v.get(3)), int(v.get(4))
    v.release()
    if h > w:
        vf = "fps=24,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1"
    else:
        vf = ("fps=24,split[a][b];"
              "[b]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=20:2[bg];"
              "[a]scale=720:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    n = int(dur * 24)
    zrate = 0.10 if cold else 0.045   # 冷开场快推, 普通镜头缓推
    zoom = (f"zoompan=z='1+{zrate}*on/{n-1}':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={n}:s=720x1280:fps=24")
    run(["-i", src, "-vf", vf + "," + zoom, "-t", str(dur),
         "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", dst])
    built[key] = dst
    print(f"{shot} ({dur}s) 完成 {i+1}/{len(SEQ)}")

# ---- 2) 拼接 ----
concat_file = os.path.join(TMP, "list.txt")
with open(concat_file, "w") as f:
    for i, (shot, dur, _, _) in enumerate(SEQ):
        f.write(f"file '{built[f'{shot}-{dur}']}'\n")
run(["-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy",
     os.path.join(TMP, "video.mp4")])

# ---- 3) 全混音: BGM + 音效 + 配音 ----
offsets = [0.0]
inputs = ["-i", os.path.join(AUD, "bgm-50s.wav")]
filters = ["[1:a]volume=0.30[a1]"]
idx = 2
for fname, off, vol in SFX:
    inputs += ["-i", os.path.join(AUD, fname)]
    filters.append(f"[{idx}:a]adelay={ms(off)}|{ms(off)},volume={vol}[a{idx}]")
    idx += 1
t = 0.0
tts_inputs = {}
for shot, dur, tts, _ in SEQ:
    if tts:
        tts_inputs[tts] = t + 0.3
    t += dur
for tts, off in tts_inputs.items():
    inputs += ["-i", os.path.join(AUD, tts + ".mp3")]
    filters.append(f"[{idx}:a]adelay={ms(off)}|{ms(off)},volume=1.0[a{idx}]")
    idx += 1
mix_in = "".join(f"[a{i}]" for i in range(1, idx))
filters.append(f"{mix_in}amix=inputs={idx-1}:normalize=0,afade=t=out:st={TOTAL-1.2}:d=1.2[aout]")

# 字幕
ASS = os.path.join(TMP, "sub-ep1.ass").replace("\\", "/")
ass_filter = (f"subtitles=filename='{ASS.replace(':', '\\:')}'"
              f":fontsdir='C\\:/Windows/Fonts'")
run(["-i", os.path.join(TMP, "video.mp4")] + inputs +
    ["-filter_complex", f"[0:v]{ass_filter}[vout];" + ";".join(filters),
     "-map", "[vout]", "-map", "[aout]",
     "-c:v", "libx264", "-preset", "fast", "-crf", "20",
     "-c:a", "aac", "-t", str(TOTAL),
     os.path.join(TMP, "ep1_v2.mp4")])

final = os.path.join(SRC, "第1集-成片-v2.mp4")
shutil.copy(os.path.join(TMP, "ep1_v2.mp4"), final)
print(f"成片 v2 完成 -> {final}  总时长 {TOTAL}s")
