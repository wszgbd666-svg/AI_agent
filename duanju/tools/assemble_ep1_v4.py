# -*- coding: utf-8 -*-
"""第1集 v4 临摹《反相之地》版合成: 48秒/20切点
结构: 雨夜播报 -> 镜中巨脸奇观 -> 宿舍夜谈日常 -> 王富贵遇险 -> 林默改写救回 -> 反差 -> 倒影笑钩子
"""
import os, shutil, subprocess, sys, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = r"D:\DevTools\Python\Miniconda3\envs\ai\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
SRC = r"d:/AI_agent/duanju/素材/第1集"
AUD = os.path.join(HERE, "tmp_audio")
TMP = os.path.join(HERE, "tmp_build")
os.makedirs(TMP, exist_ok=True)

# (镜头, 时长, TTS, 冷开场, 起始偏移秒)
SEQ = [
    ("镜校园夜", 3.0, None, False, 0.0),
    ("镜巨脸", 2.0, None, True, 0.0),
    ("镜夜谈", 4.0, "v4-lin1", False, 0.0),
    ("镜王照镜", 2.5, "s02", False, 0.0),
    ("镜倒影", 3.0, None, False, 0.0),
    ("镜03", 2.0, None, False, 0.5),
    ("镜04", 2.5, None, False, 0.0),
    ("镜04", 2.5, "s04", False, 1.5),
    ("镜05", 2.5, None, False, 0.0),
    ("镜06", 2.5, "s07", False, 0.0),
    ("镜07", 2.5, None, False, 0.0),
    ("镜回头", 2.5, None, False, 0.0),
    ("镜08", 2.5, "s08", False, 0.0),
    ("镜09", 2.0, None, False, 0.0),
    ("镜10", 3.0, None, False, 0.0),
    ("镜倒影笑", 2.5, None, False, 0.0),
    ("黑", 2.5, None, False, 0.0),
    ("黑", 2.0, None, False, 0.0),
]
TOTAL = sum(d for _, d, _, _, _ in SEQ)

SFX = [
    ("sfx-hum.wav", 0.0, 0.5), ("sfx-sting.wav", 3.0, 0.9),
    ("sfx-heartbeat.wav", 9.0, 0.85), ("sfx-heartbeat.wav", 11.5, 0.9),
    ("sfx-glass.wav", 14.5, 0.85), ("sfx-sting.wav", 14.5, 0.9),
    ("sfx-ding.wav", 16.5, 0.7), ("sfx-heartbeat.wav", 19.0, 0.85),
    ("sfx-heartbeat.wav", 24.0, 0.85),
    ("sfx-gold.wav", 26.5, 0.8), ("sfx-whoosh.wav", 31.5, 0.7),
    ("sfx-ding.wav", 34.0, 0.7), ("sfx-hum.wav", 36.0, 0.55),
    ("sfx-sting.wav", 39.0, 0.9), ("sfx-hum.wav", 41.5, 0.5),
    ("sfx-sting.wav", 44.0, 0.8),
]

def run(args):
    r = subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error"] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("FFMPEG ERROR:", r.stderr[-1000:])
        sys.exit(1)

def ms(sec):
    return int(sec * 1000)

# ---- 1) 每镜 ----
built = {}
for i, (shot, dur, _, cold, seek) in enumerate(SEQ):
    key = f"{shot}-{dur}-{seek}"
    if key in built:
        continue
    dst = os.path.join(TMP, f"c{i}.mp4")
    if shot == "黑":
        run(["-f", "lavfi", "-i", f"color=c=black:s=720x1280:r=24:d={dur}",
             "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", dst])
    else:
        src = os.path.join(SRC, shot + ".mp4")
        if not os.path.exists(src):
            print("缺少镜头:", src)
            sys.exit(1)
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
        zrate = 0.10 if cold else 0.05
        zoom = (f"zoompan=z='1+{zrate}*on/{n-1}':x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':d={n}:s=720x1280:fps=24")
        run(["-ss", str(seek), "-i", src, "-vf", vf + "," + zoom, "-t", str(dur),
             "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", dst])
    built[key] = dst
    print(f"{shot} ({dur}s) 完成 {i+1}/{len(SEQ)}")

# ---- 2) 拼接 ----
concat_file = os.path.join(TMP, "list.txt")
with open(concat_file, "w") as f:
    for shot, dur, _, _, seek in SEQ:
        f.write(f"file '{built[f'{shot}-{dur}-{seek}']}'\n")
run(["-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy",
     os.path.join(TMP, "video.mp4")])

# ---- 3) 混音 ----
inputs = ["-i", os.path.join(AUD, "bgm-50s.wav")]
filters = ["[1:a]volume=0.26[a1]"]
idx = 2
for fname, off, vol in SFX:
    inputs += ["-i", os.path.join(AUD, fname)]
    filters.append(f"[{idx}:a]adelay={ms(off)}|{ms(off)},volume={vol}[a{idx}]")
    idx += 1
t = 0.0
tts_off = {}
for shot, dur, tts, _, _ in SEQ:
    if tts:
        tts_off[tts] = t + 0.2
    t += dur
for tts, off in tts_off.items():
    inputs += ["-i", os.path.join(AUD, tts + ".mp3")]
    filters.append(f"[{idx}:a]adelay={ms(off)}|{ms(off)},volume=1.0[a{idx}]")
    idx += 1
mix_in = "".join(f"[a{i}]" for i in range(1, idx))
filters.append(f"{mix_in}amix=inputs={idx-1}:normalize=0,afade=t=out:st={TOTAL-1.0}:d=1.0[aout]")

ASS = os.path.join(TMP, "sub-ep1-v4.ass").replace("\\", "/")
ass_filter = (f"subtitles=filename='{ASS.replace(':', '\\:')}'"
              f":fontsdir='C\\:/Windows/Fonts'")
run(["-i", os.path.join(TMP, "video.mp4")] + inputs +
    ["-filter_complex", f"[0:v]{ass_filter}[vout];" + ";".join(filters),
     "-map", "[vout]", "-map", "[aout]",
     "-c:v", "libx264", "-preset", "fast", "-crf", "20",
     "-c:a", "aac", "-t", str(TOTAL),
     os.path.join(TMP, "ep1_v4.mp4")])

final = os.path.join(SRC, "第1集-成片-v4.mp4")
shutil.copy(os.path.join(TMP, "ep1_v4.mp4"), final)
print(f"成片 v4 完成 -> {final}  总时长 {TOTAL}s")
