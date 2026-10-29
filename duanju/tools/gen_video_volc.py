# -*- coding: utf-8 -*-
"""火山方舟 Seedance 视频生成器 (文生/图生视频)
用法: python gen_video_volc.py <提示词> <输出路径> [参考图路径,可选] [时长秒=5]
密钥从 .volc_key 读取
"""
import os, sys, json, time, base64, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(HERE, ".volc_key")
TASK_API = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
# Seedance 2.0 系列模型 (从 /api/v3/models 实测确认的准确 ID)
# 注意: 免费额度只有 fast/mini 档, pro 档直接扣余额! 默认走 fast, pro 需显式传 --pro
MODELS_T2V = ["doubao-seedance-2-0-fast-260128", "doubao-seedance-2-0-mini-260615"]
MODELS_T2V_PRO = ["doubao-seedance-2-0-260128"]
MODELS_I2V = ["doubao-seedance-2-0-fast-260128", "doubao-seedance-2-0-mini-260615"]


def load_key():
    if not os.path.exists(KEY_FILE):
        raise SystemExit(f"未找到密钥文件 {KEY_FILE}")
    return open(KEY_FILE, encoding="utf-8").read().strip()


def post_json(url, payload, key):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    use_pro = "--pro" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--pro"]
    if len(args) < 2:
        raise SystemExit("用法: gen_video_volc.py <提示词> <输出> [参考图] [时长] [--pro]")
    prompt, out_path = args[0], args[1]
    ref_img = args[2] if len(args) > 2 else None
    dur = int(args[3]) if len(args) > 3 else 5
    key = load_key()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    content = [{"type": "text", "text": prompt}]
    if ref_img:
        b64 = base64.b64encode(open(ref_img, "rb").read()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    if use_pro:
        models = MODELS_T2V_PRO
    else:
        models = MODELS_I2V if ref_img else MODELS_T2V
    for model in models:
        try:
            r = post_json(TASK_API, {"model": model, "content": content,
                                     "duration": dur, "resolution": "720p"}, key)
            task_id = r.get("id") or r.get("task_id")
            print(f"已提交 model={model} task={task_id}")
        except urllib.error.HTTPError as e:
            print(f"model={model} 提交失败: {e.code} {e.read().decode('utf-8','ignore')[:200]}")
            continue

        for _ in range(60):
            time.sleep(6)
            try:
                t = post_json(TASK_API + "/" + task_id + f"?model={model}", {}, key)
            except urllib.error.HTTPError as e:
                print(f"  轮询失败 {e.code} {e.read().decode('utf-8','ignore')[:150]}")
                continue
            status = t.get("status")
            if status in ("succeeded", "Succeeded"):
                url = t.get("content", {}).get("video_url", "")
                urllib.request.urlretrieve(url, out_path)
                print(f"完成 -> {out_path} (model={model})")
                return
            if status in ("failed", "Failed", "cancelled"):
                print(f"{status}: {json.dumps(t, ensure_ascii=False)[:200]}")
                break
        else:
            print("超时, 换下一个模型")
    print("所有模型都失败了")


if __name__ == "__main__":
    main()
