# -*- coding: utf-8 -*-
"""第1集 v3 临摹版新镜头批量生成: 分镜图先行 -> 图生视频
新镜头: 群像哄笑(t2v) / 周凯照镜子(sb) / 倒影不动+微笑(sb) / 手机规则二(t2v)
        林默回头(sb) / 镜中倒影对林默笑(sb, 结尾大钩子)
"""
import os, subprocess, sys, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"D:/DevTools/Python/Miniconda3/envs/ai/python.exe"
SRC = r"d:/AI_agent/duanju/素材/第1集"

# (名称, 类型t2v/sb, 分镜图提示词(仅sb), 视频提示词)
SHOTS = [
    ("镜群像", "t2v", None,
     "电影级3D渲染，国漫3D动画电影风格，大学男生宿舍里几个大学生围坐对着亮着红光的手机屏幕满不在乎地哄笑，深夜氛围，暖色台灯光，电影感光影"),
    ("镜周凯", "sb",
     "电影级3D渲染，CGI质感，国漫3D动画电影风格，大学男生宿舍，一个瘦高男大学生不戴眼镜黑色短发穿灰色T恤站在墙上挂着的镜子前，对镜整理头发，身后是上下铺铁架床，深夜暖色台灯光，电影感光影，8K质感",
     "参考图中瘦高的男生对镜整理头发，镜中倒影的动作与他逐渐不同步，诡异氛围，微恐，电影感光影"),
    ("镜倒影", "sb",
     "电影级3D渲染，CGI质感，国漫3D动画电影风格，大学男生宿舍墙上的镜子特写，镜中一个男生的倒影面无表情直勾勾盯着镜外，嘴角缓缓上扬，镜外模糊可见灰色T恤的男生背影，微恐氛围，电影感光影，8K质感",
     "参考图中镜子里倒影的嘴角缓缓上扬，露出诡异的微笑，眼神直勾勾，微恐氛围，电影感光影，特写"),
    ("镜规则二", "t2v", None,
     "电影级3D渲染，国漫3D动画电影风格，特写镜头，黑暗中一部手机屏幕突然亮起，屏幕上显示红色警示文字推送，微恐氛围，电影感光影"),
    ("镜回头", "sb",
     "电影级3D渲染，CGI质感，国漫3D动画电影风格，戴黑框眼镜穿白色连帽卫衣的男生猛地回头，身后大学宿舍走廊空无一人，只有昏暗的灯光，表情惊魂未定，微恐氛围，电影感光影，8K质感",
     "参考图中戴黑框眼镜的男生猛地回头张望，身后空无一人的走廊，灯光闪烁一下，微恐氛围，电影感光影"),
    ("镜倒影笑", "sb",
     "电影级3D渲染，CGI质感，国漫3D动画电影风格，大学宿舍里，戴黑框眼镜穿白色连帽卫衣的男生站在镜子前看着镜子，镜中他的倒影却没有看向镜子而是直直地盯着他，嘴角诡异上扬，微恐氛围，电影感光影，8K质感",
     "参考图中镜子里男生的倒影直勾勾地盯着镜外，嘴角缓缓诡异上扬，微恐氛围，电影感光影"),
]

def run_gen(py_args):
    r = subprocess.run([PY] + py_args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout + r.stderr).strip().splitlines()
    print("  ", out[-1] if out else r.returncode)
    return r.returncode == 0

def t2i(prompt, out_png):
    code = f"""
import sys, time, urllib.request
sys.path.insert(0, r'{HERE}')
from gen_image import load_key, post_json
key = load_key()
r = post_json('https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis',
    {{'model':'wan2.5-t2i-preview','input':{{'prompt':{json.dumps(prompt, ensure_ascii=False)}}},
     'parameters':{{'size':'720*1280','n':1}}}}, key)
task = r['output']['task_id']
for _ in range(40):
    time.sleep(5)
    t = post_json('https://dashscope.aliyuncs.com/api/v1/tasks/'+task, {{}}, key)
    st = t.get('output',{{}}).get('task_status')
    if st=='SUCCEEDED':
        urllib.request.urlretrieve(t['output']['results'][0]['url'], r'{out_png}')
        print('SB OK'); break
    if st in ('FAILED','CANCELED'): print('SB FAIL', t.get('output',{{}}).get('message','')); sys.exit(1)
"""
    return run_gen(["-c", code])

for name, kind, sb_prompt, v_prompt in SHOTS:
    out_v = os.path.join(SRC, name + ".mp4")
    if os.path.exists(out_v) and os.path.getsize(out_v) > 10000:
        print(name, "已存在, 跳过")
        continue
    print("=" * 40)
    print(name, kind)
    ok = False
    for attempt in range(3):
        if kind == "t2v":
            ok = run_gen([os.path.join(HERE, "gen_video.py"), v_prompt, out_v])
        else:
            sb = os.path.join(SRC, name + "-sb.png")
            if not (os.path.exists(sb) and os.path.getsize(sb) > 10000):
                print("  分镜图生成中...")
                t2i(sb_prompt, sb)
                time.sleep(3)
            if os.path.exists(sb) and os.path.getsize(sb) > 10000:
                ok = run_gen([os.path.join(HERE, "gen_video.py"), v_prompt, out_v, sb])
        if ok:
            break
        time.sleep(15)
    print(name, "->", "OK" if ok else "FAILED")
