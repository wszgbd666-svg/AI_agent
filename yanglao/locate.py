# -*- coding: utf-8 -*-
"""地区识别:优先读本机 WiFi 名称(Windows netsh),命中 regions.json 里的映射;
映射没配或没连 WiFi 时,按服务器出口 IP 反查城市(ip-api.com 免费接口,有缓存)。

wifi 名称 -> 地区的映射配置在 regions.json 的 wifi_map 里,社区把自家 WiFi 配进去即可。
"""
import json
import os
import re
import subprocess
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
REGIONS_PATH = os.path.join(BASE, "regions.json")


def load_regions():
    with open(REGIONS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("wifi_map", {}), data.get("builtin", [])


def get_wifi_ssid():
    """读当前连接的 WiFi 名称;失败或没有 WiFi 返回 None。"""
    try:
        out = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=5,
            encoding="gbk", errors="ignore",
        ).stdout
    except Exception:
        return None
    for m in re.finditer(r"^\s*SSID\s*:\s*(.+)$", out, re.M):
        name = m.group(1).strip()
        if name:
            return name
    return None


_ip_cache = {"t": 0.0, "region": None}


def get_ip_region():
    """按服务器出口 IP 反查省市(1小时缓存);失败返回 None。"""
    now = time.time()
    if now - _ip_cache["t"] < 3600:
        return _ip_cache["region"]
    _ip_cache["t"] = now
    try:
        with urllib.request.urlopen("http://ip-api.com/json/?lang=zh-CN", timeout=4) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("status") == "success":
            region = (data.get("regionName") or "") + (data.get("city") or "")
            _ip_cache["region"] = region or None
            return _ip_cache["region"]
    except Exception:
        pass
    _ip_cache["region"] = None
    return None


def detect():
    """返回 {"source": "wifi"|"ip"|None, "region": str|None, "wifi": str|None}。"""
    wifi_map, _ = load_regions()
    ssid = get_wifi_ssid()
    if ssid:
        for key, region in wifi_map.items():
            if ssid.lower() == key.lower() or key.lower() in ssid.lower():
                return {"source": "wifi", "region": region, "wifi": ssid}
        # 有 WiFi 但没配映射:把名称带回去,再试 IP
        ip_region = get_ip_region()
        return {"source": "ip" if ip_region else None,
                "region": ip_region, "wifi": ssid}
    ip_region = get_ip_region()
    if ip_region:
        return {"source": "ip", "region": ip_region, "wifi": None}
    return {"source": None, "region": None, "wifi": None}
