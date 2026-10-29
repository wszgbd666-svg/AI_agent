# -*- coding: utf-8 -*-
"""第1集 v4 临摹《反相之地》版新镜头: 写实电影质感, 分镜图先行
新增: 校园雨夜空镜(t2v) / 镜中巨型人脸(sb) / 宿舍夜谈日常(sb) /
      王富贵照镜子(sb) / 王富贵被拖向镜子(sb)
"""
import os, subprocess, sys, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"D:/DevTools/Python/Miniconda3/envs/ai/python.exe"
SRC = r"d:/AI_agent/duanju/素材/第1集"

STYLE = "写实电影质感，真人比例，电影级光影，冷蓝调，微恐氛围"

SHOTS = [
    ("镜校园夜", "t2v", None,
     f"{STYLE}，深夜大学校园外景，雨夜，雨丝飘落，宿舍楼群灯火零星，地面湿滑反光，广角镜头，电影感运镜"),
    ("镜巨脸", "sb",
     f"{STYLE}，大学宿舍昏暗的墙上挂着一面镜子，镜面中浮现一张巨大的苍白人脸，五官模糊扭曲，几乎撑满整个镜面，诡异压迫感，电影感光影，8K质感",
     "参考图中镜子里巨大的苍白人脸缓缓向镜面外贴近，五官扭曲流动，诡异压迫感，微恐，电影感光影"),
    ("镜夜谈", "sb",
     f"写实电影质感，大学宿舍，一个戴黑框眼镜穿白色卫衣的男生和一个微胖穿红色T恤的男生并排坐在下铺聊天，面前摊着零食，暖黄台灯光，轻松日常氛围，电影感光影，8K质感",
     "参考图中两个男生在宿舍聊天，微胖男生边说边笑，戴眼镜的男生无奈摇头，暖黄灯光，日常轻松氛围，电影感光影"),
    ("镜王照镜", "sb",
     f"{STYLE}，大学宿舍，微胖穿红色T恤的男生站在墙上的镜子前，嬉皮笑脸地对着镜子拨弄头发，身后是上下铺铁架床，暖黄灯光，电影感光影，8K质感",
     "参考图中微胖红T恤男生对镜拨弄头发，嬉皮笑脸，镜中倒影的动作却越来越不同步，诡异氛围，微恐，电影感光影"),
    ("镜王拖拽", "sb",
     f"{STYLE}，大学宿舍，微胖穿红色T恤的男生被一只从镜子中伸出的苍白的手抓住衣领往镜面里拖，男生惊恐挣扎，身体向后仰，微恐氛围，电影感光影，8K质感，无血腥",
     "参考图中微胖红T恤男生被镜中伸出的苍白手臂拖向镜面，惊恐挣扎，画面动态感强，微恐，电影感光影"),
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
