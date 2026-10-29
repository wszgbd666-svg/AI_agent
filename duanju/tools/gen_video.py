# -*- coding: utf-8 -*-
"""通义万相 视频生成器 (文生视频/图生视频)
用法: python gen_video.py <提示词文件或直接提示词> <输出路径> [参考图路径,可选]
"""
import os, sys, json, time, urllib.request, urllib.error, base64

ENV_PATH = r"D:/AI_agent/partner/.env"
T2V_API = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
I2V_API = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
TASK_API = "https://dashscope.aliyuncs.com/api/v1/tasks/"
T2V_MODELS = ["wan2.5-t2v-preview", "wan2.2-t2v-plus", "wan2.1-t2v-plus"]
I2V_MODELS = ["wan2.5-i2v-preview", "wan2.2-i2v-plus", "wan2.1-i2v-plus"]
PARAMS = [{"resolution": "720P", "duration": 5},
          {"resolution": "480P", "duration": 5},
          {"resolution": "720P", "duration": 3}]


def load_key():
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DASHCOPE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("未找到 DASHCOPE_API_KEY")


def post_json(url, payload, key):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json",
                                          "X-DashScope-Async": "enable"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    prompt_src, out_path = sys.argv[1], sys.argv[2]
    ref_img = sys.argv[3] if len(sys.argv) > 3 else None
    if os.path.isfile(prompt_src):
        prompt = open(prompt_src, encoding="utf-8").read().strip()
    else:
        prompt = prompt_src
    key = load_key()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    models = I2V_MODELS if ref_img else T2V_MODELS
    for model in models:
        for params in PARAMS:
            inp = {"prompt": prompt}
            if ref_img:
                inp["img_url"] = "data:image/png;base64," + base64.b64encode(
                    open(ref_img, "rb").read()).decode()
            try:
                r = post_json(T2V_API, {"model": model, "input": inp,
                                        "parameters": params}, key)
                task_id = r["output"]["task_id"]
                print(f"已提交 model={model} {params} task={task_id}")
            except urllib.error.HTTPError as e:
                print(f"model={model} {params} 提交失败: {e.code} "
                      f"{e.read().decode('utf-8', 'ignore')[:150]}")
                continue

            for _ in range(60):  # 视频生成较慢, 最多轮询5分钟
                time.sleep(6)
                try:
                    t = post_json(TASK_API + task_id, {}, key)
                except urllib.error.HTTPError as e:
                    print(f"  轮询失败 {e.code}")
                    continue
                st = t.get("output", {}).get("task_status")
                if st == "SUCCEEDED":
                    url = t["output"]["video_url"]
                    urllib.request.urlretrieve(url, out_path)
                    print(f"完成 -> {out_path} (model={model})")
                    return
                if st in ("FAILED", "CANCELED"):
                    print(f"{st}: {t.get('output', {}).get('message', '')[:200]}")
                    break
            else:
                print("超时, 换下一个参数组合")
    print("所有参数组合都失败了")


if __name__ == "__main__":
    main()
