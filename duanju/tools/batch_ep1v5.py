# -*- coding: utf-8 -*-
"""第1集 v5: Seedance fast 全片重拍 (11镜 x 4秒, 免费额度内)
临摹《反相之地》结构, 风格统一 3D动画电影风(与定妆图一致)
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"D:/DevTools/Python/Miniconda3/envs/ai/python.exe"
SRC = r"d:/AI_agent/duanju/素材/第1集"
IMG = r"d:/AI_agent/duanju/素材/定妆图"
GEN = os.path.join(HERE, "gen_video_volc.py")

STYLE = "3D动画电影风格，电影感光影，微恐氛围，冷蓝调"

# (名称, 提示词, 参考图 or None)
SHOTS = [
    ("v5-01校园夜", f"{STYLE}，深夜大学校园外景，雨夜，雨丝飘落，宿舍楼灯火零星，地面湿滑反光，镜头缓缓推进", None),
    ("v5-02巨脸", f"{STYLE}，大学宿舍墙上挂着一面镜子，镜面中浮现一张巨大的苍白人脸，五官模糊扭曲，人脸缓缓向镜外贴近", None),
    ("v5-03夜谈", f"{STYLE}，大学宿舍内，一个戴黑框眼镜穿白色卫衣的男生和一个微胖穿红色T恤的男生坐在下铺聊天，暖黄台灯光，轻松日常，镜头缓慢横移", None),
    ("v5-04王照镜", f"{STYLE}，参考图中的微胖男生站在宿舍镜子前嬉皮笑脸地拨弄头发，镜中倒影的动作逐渐与他不同步", "王富贵-1.png"),
    ("v5-05倒影笑", f"{STYLE}，宿舍镜子特写，镜中一个男生的倒影缓缓停住动作，直勾勾盯着镜外，嘴角诡异上扬", None),
    ("v5-06鬼手", f"{STYLE}，一只苍白的手从镜面中缓缓伸出，手指抓向镜外，宿舍灯光闪烁熄灭", None),
    ("v5-07林默惊", f"{STYLE}，参考图中的男生深夜从宿舍下铺惊醒坐起，表情紧张，手机屏幕在黑暗中发出红光", "林默-1.png"),
    ("v5-08规则二", f"{STYLE}，特写，黑暗中一部手机屏幕亮起，红色警示文字弹出，屏幕光映亮周围", None),
    ("v5-09按按钮", f"{STYLE}，参考图中的男生咬着牙用手指用力按向手机屏幕上的金色发光按钮，表情紧张", "林默-1.png"),
    ("v5-10金光", f"{STYLE}，手指按下金色按钮的瞬间，耀眼的金色光芒从手机爆发，照亮整个宿舍，特效镜头", None),
    ("v5-11倒影对笑", f"{STYLE}，参考图中的男生站在镜子前，镜中他的倒影没有跟着他转身，而是直勾勾盯着他，嘴角诡异上扬", "林默-1.png"),
]

ok_list, fail_list = [], []
for name, prompt, ref in SHOTS:
    out = os.path.join(SRC, name + ".mp4")
    if os.path.exists(out) and os.path.getsize(out) > 10000:
        print(name, "已存在, 跳过")
        ok_list.append(name)
        continue
    args = [PY, GEN, prompt, out]
    if ref:
        args.append(os.path.join(IMG, ref))
    args.append("4")
    print("=" * 40)
    print(name)
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    tail = (r.stdout + r.stderr).strip().splitlines()
    print("  ", tail[-1] if tail else r.returncode)
    if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 10000:
        ok_list.append(name)
    else:
        fail_list.append(name)
        # 若因额度/欠费失败, 立即停止, 不再继续烧钱
        if "quota" in (r.stdout + r.stderr).lower() or "Insufficient" in (r.stdout + r.stderr):
            print("检测到额度问题, 立即停止")
            break
        time.sleep(5)

print("\n成功:", ok_list)
print("失败:", fail_list)
