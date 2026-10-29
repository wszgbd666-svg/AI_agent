# -*- coding: utf-8 -*-
"""通义万相 文生图 - 定妆图生成器
用法: python gen_image.py <角色名> <输出路径>
提示词从 prompts.json 读取(按角色名)
"""
import os, sys, json, time, base64, urllib.request, urllib.error

ENV_PATH = r"D:/AI_agent/partner/.env"
API = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
TASK_API = "https://dashscope.aliyuncs.com/api/v1/tasks/"
MODELS = ["wan2.5-t2i-preview", "wan2.2-t2i-plus", "wanx2.1-t2i-turbo"]  # 依次尝试
SIZES = ["720*1280", "1024*1024"]              # 先竖版, 不行再方版


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
    role, out_path = sys.argv[1], sys.argv[2]
    prompts = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts.json"),
                             encoding="utf-8"))
    prompt = prompts[role]
    key = load_key()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    for model in MODELS:
        for size in SIZES:
            try:
                r = post_json(API, {"model": model, "input": {"prompt": prompt},
                                    "parameters": {"size": size, "n": 1}}, key)
                task_id = r["output"]["task_id"]
                print(f"[{role}] 已提交 model={model} size={size} task={task_id}")
            except urllib.error.HTTPError as e:
                print(f"[{role}] model={model} size={size} 提交失败: {e.code} {e.read().decode('utf-8')[:200]}")
                continue

            # 轮询结果
            for _ in range(40):
                time.sleep(5)
                try:
                    t = post_json(TASK_API + task_id, {}, key)
                except urllib.error.HTTPError as e:
                    print(f"  轮询失败 {e.code}")
                    continue
                st = t.get("output", {}).get("task_status")
                if st == "SUCCEEDED":
                    url = t["output"]["results"][0]["url"]
                    urllib.request.urlretrieve(url, out_path)
                    print(f"[{role}] 完成 -> {out_path} (model={model})")
                    return
                if st in ("FAILED", "CANCELED"):
                    print(f"[{role}] {st}: {t.get('output', {}).get('message', '')[:200]}")
                    break
            else:
                print(f"[{role}] 超时未完成, 换下一个参数组合")
    print(f"[{role}] 所有参数组合都失败了")


if __name__ == "__main__":
    main()
