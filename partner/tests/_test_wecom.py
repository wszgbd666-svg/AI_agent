import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import urllib.request

import core.config  # 先加载 .env

corp = os.getenv("WECOM_CORP_ID", "").strip()
secret = os.getenv("WECOM_SECRET", "").strip()
url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corp}&corpsecret={secret}"
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read().decode())
    print("errcode:", data.get("errcode"), "errmsg:", data.get("errmsg"))
    if data.get("errcode") == 0:
        token = data["access_token"]
        agent = os.getenv("WECOM_AGENT_ID", "").strip()
        body = json.dumps({
            "touser": "@all",
            "msgtype": "text",
            "agentid": int(agent),
            "text": {"content": "主人好,我是蓝蓝~ 企业微信推送已接通!"},
        }).encode()
        req = urllib.request.Request(
            f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}",
            data=body, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r2:
            d2 = json.loads(r2.read().decode())
        print("send errcode:", d2.get("errcode"), "errmsg:", d2.get("errmsg"))
except Exception as e:
    print("异常:", e)
