# -*- coding: utf-8 -*-
"""零成本悬疑音频包: BGM(低音弦乐垫+心跳) 与 音效(嗡鸣/惊吓/玻璃/金色/转场)
纯 numpy 合成, 无版权问题
"""
import numpy as np, wave, os

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_audio")
os.makedirs(OUT, exist_ok=True)

def save(name, data, vol=0.9):
    data = np.clip(data * vol, -1, 1)
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((data * 32767).astype(np.int16).tobytes())
    print("OK", name, f"{len(data)/SR:.1f}s")

def fade(data, sec):
    n = int(SR * sec)
    env = np.ones(len(data))
    env[:n] = np.linspace(0, 1, n)
    env[-n:] = np.linspace(1, 0, n)
    return data * env

# 1) BGM: 悬疑低音弦乐垫 (50秒, 低音drone + 缓慢起伏)
t = np.arange(SR * 50) / SR
drone = (np.sin(2*np.pi*55*t) * 0.5 + np.sin(2*np.pi*110.3*t) * 0.25
         + np.sin(2*np.pi*82.4*t) * 0.2)
lfo = 0.6 + 0.4 * np.sin(2*np.pi*0.07*t) * np.sin(2*np.pi*0.031*t)
save("bgm-50s.wav", fade(drone * lfo, 2), 0.30)

# 2) 心跳 (2秒, 双低音脉冲, 用于镜03/04)
hb = np.zeros(SR * 2)
for s in (0.0, 0.35, 1.0, 1.35):
    i = int(s * SR)
    n = int(0.12 * SR)
    hb[i:i+n] = np.sin(2*np.pi*48*np.arange(n)/SR) * np.exp(-np.arange(n)/n*5)
save("sfx-heartbeat.wav", hb, 0.9)

# 3) 嗡鸣/诡异底噪 (3秒, 用于规则出现时)
tt = np.arange(SR * 3) / SR
hum = np.sin(2*np.pi*220*tt) * 0.4 + np.sin(2*np.pi*222.5*tt) * 0.4
hum *= 0.5 + 0.5*np.sin(2*np.pi*8*tt)
save("sfx-hum.wav", fade(hum, 0.3), 0.5)

# 4) 惊吓stinger (1秒, 高频冲击+噪声, 用于镜03鬼手)
tt2 = np.arange(SR) / SR
noise = np.random.randn(SR)
noise = noise * np.exp(-tt2*6)
sting = np.sin(2*np.pi*880*tt2) * np.exp(-tt2*8) * 0.7 + noise * 0.5
save("sfx-sting.wav", sting, 0.8)

# 5) 玻璃碎裂 (1.2秒, 噪声脉冲簇)
gl = np.zeros(int(SR * 1.2))
rng = np.random.default_rng(7)
for _ in range(60):
    pos = rng.uniform(0, 0.4)
    i = int(pos * SR)
    n = int(rng.uniform(0.005, 0.03) * SR)
    if i + n < len(gl):
        gl[i:i+n] += rng.standard_normal(n) * np.exp(-np.arange(n)/n*4)
save("sfx-glass.wav", gl, 0.7)

# 6) 金色魔法音效 (1.5秒, 上升琶音+闪烁, 用于编辑按钮/金光)
tt3 = np.arange(int(SR * 1.5)) / SR
notes = [523, 659, 784, 1047, 1319]
gold = np.zeros_like(tt3)
for k, f in enumerate(notes):
    st = k * 0.18
    i = int(st * SR)
    n = int(0.5 * SR)
    if i + n < len(tt3):
        gold[i:i+n] += np.sin(2*np.pi*f*tt3[i:i+n]) * np.exp(-np.arange(n)/n*3)
save("sfx-gold.wav", fade(gold, 0.15), 0.5)

# 7) 手机消息提示 (0.3秒, 短促叮)
tt4 = np.arange(int(SR * 0.3)) / SR
ding = np.sin(2*np.pi*1568*tt4) * np.exp(-tt4*14) + np.sin(2*np.pi*2093*tt4) * np.exp(-tt4*18)
save("sfx-ding.wav", ding, 0.6)

# 8) 转场whoosh (0.5秒, 噪声扫频)
tt5 = np.arange(int(SR * 0.5)) / SR
wz = np.random.randn(int(SR * 0.5)) * np.exp(-tt5*9)
wz *= np.sin(2*np.pi*(300 + 1500*tt5)*tt5)
save("sfx-whoosh.wav", fade(wz, 0.1), 0.5)
