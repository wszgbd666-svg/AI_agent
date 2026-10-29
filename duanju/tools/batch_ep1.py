# -*- coding: utf-8 -*-
"""第1集批量生成: 按 shots-ep1.json 逐个调用 gen_video.py, 失败重试2次"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"D:/DevTools/Python/Miniconda3/envs/ai/python.exe"
SHOTS = json.load(open(os.path.join(HERE, "shots-ep1.json"), encoding="utf-8"))
OUT_DIR = r"d:/AI_agent/duanju/素材/第1集"
IMG_DIR = r"d:/AI_agent/duanju/素材/定妆图"
done, failed = [], []

for name, cfg in SHOTS.items():
    ref = None
    if cfg.get("ref"):
        ref = os.path.join(IMG_DIR, cfg["ref"] + "-1.png")
    out = os.path.join(OUT_DIR, name + ".mp4")
    if os.path.exists(out) and os.path.getsize(out) > 10000:
        print(f"{name} 已存在, 跳过")
        done.append(name)
        continue
    ok = False
    for attempt in range(3):
        cmd = [PY, os.path.join(HERE, "gen_video.py"), cfg["prompt"], out]
        if ref:
            cmd.append(ref)
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        tail = (r.stdout + r.stderr).strip().splitlines()
        print(f"[{name} 第{attempt+1}次]", tail[-1] if tail else r.returncode)
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 10000:
            ok = True
            break
        time.sleep(10)  # 被绿网拦截/限流时等一下再试
    (done if ok else failed).append(name)

print("\n完成:", done)
print("失败:", failed)
