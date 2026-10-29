"""企业微信集成:蓝蓝 → 企业微信主动推送(任务完成、定时提醒等)。

双向聊天需要内网穿透(回调 URL),暂未启用;本模块先实现发送侧。
"""

import json
import os
import threading
import time
import urllib.request

# 缓存 access_token(2 小时有效,提前 5 分钟刷新)
_token = None
_token_expire = 0
_lock = threading.Lock()


def configured():
    return bool(
        os.getenv("WECOM_CORP_ID", "").strip()
        and os.getenv("WECOM_AGENT_ID", "").strip()
        and os.getenv("WECOM_SECRET", "").strip()
    )


def _get_token():
    global _token, _token_expire
    with _lock:
        if _token and time.time() < _token_expire:
            return _token
        corp = os.getenv("WECOM_CORP_ID", "").strip()
        secret = os.getenv("WECOM_SECRET", "").strip()
        url = (f"https://qyapi.weixin.qq.com/cgi-bin/gettoken"
               f"?corpid={corp}&corpsecret={secret}")
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        if data.get("errcode") != 0:
            raise RuntimeError(f"gettoken 失败: {data}")
        _token = data["access_token"]
        _token_expire = time.time() + data.get("expires_in", 7200) - 300
        return _token


def send_text(text, touser="@all"):
    """给企业微信用户发文本消息(默认发给全体可见成员)。

    touser: 企业微信用户 ID(通讯录里看),或 "@all"。
    """
    if not configured():
        return False
    try:
        token = _get_token()
        agent = os.getenv("WECOM_AGENT_ID", "").strip()
        body = json.dumps({
            "touser": touser,
            "msgtype": "text",
            "agentid": int(agent),
            "text": {"content": text[:2000]},
        }).encode()
        req = urllib.request.Request(
            f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}",
            data=body, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if data.get("errcode") != 0:
            print(f"[wecom] 发送失败: {data}", flush=True)
            return False
        return True
    except Exception as e:
        print(f"[wecom] 发送异常: {e}", flush=True)
        return False


def notify(title, content):
    """统一的主动通知:企业微信(已配置时)+ PushPlus(已配置时)。"""
    if configured():
        send_text(f"【{title}】\n{content[:1500]}")
    # PushPlus 走 app.py 里的 notify_pushplus,避免循环导入,这里只负责企业微信
