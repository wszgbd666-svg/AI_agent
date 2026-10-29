"""图片识别 MCP 插件:给 Claude Code 提供"看图"能力。

工具:
- ocr_image(path)    :Windows 自带 OCR,提取图中文字(免费)
- describe_image(path):通义千问视觉模型(qwen-vl),描述画面内容(用 DashScope key)

用法:截图/图片保存到磁盘 → 告诉 Claude 文件路径 → 它调用这两个工具。
"""

import base64
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# 复用 partner/.env 里的 DASHCOPE_API_KEY
load_dotenv(r"D:\AI_agent\partner\.env")

mcp = FastMCP("vision")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}

_PS_OCR = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}
$path = '__IMAGE_PATH__'; $out = '__OUT_PATH__'
$storageFile = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
$stream = Await ($storageFile.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($engine -eq $null) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US')) }
if ($engine -eq $null) { Set-Content -Path $out -Value 'OCR-ENGINE-UNAVAILABLE' -Encoding utf8; exit }
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$lines = $result.Lines | ForEach-Object { $_.Text }
Set-Content -Path $out -Value ($lines -join "`n") -Encoding utf8
"""


def _check_path(path_str):
    p = Path(str(path_str).strip().strip('"'))
    if not p.is_file():
        raise ValueError(f"文件不存在: {p}")
    if p.suffix.lower() not in IMAGE_EXTS:
        raise ValueError(f"不是图片文件: {p.suffix}")
    return p


@mcp.tool()
def ocr_image(path: str) -> str:
    """识别图片中的文字(Windows 自带 OCR,中文可用)。适合截图、带文字的图片。"""
    p = _check_path(path)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_path = f.name
    try:
        script = _PS_OCR.replace("__IMAGE_PATH__", str(p)) \
                        .replace("__OUT_PATH__", str(Path(out_path)))
        subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       capture_output=True, timeout=60)
        text = Path(out_path).read_text(encoding="utf-8-sig").strip()
        return text if text else "(图中没有识别到文字)"
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass


@mcp.tool()
def describe_image(path: str) -> str:
    """描述图片画面内容(通义千问 qwen-vl 视觉模型,需要 DASHCOPE_API_KEY)。
    适合"这图画的是什么/颜色/布局"这类问题,不只是文字。"""
    p = _check_path(path)
    key = os.getenv("DASHCOPE_API_KEY", "").strip()
    if not key:
        return "(未配置 DASHCOPE_API_KEY,无法调用视觉模型)"
    b64 = base64.b64encode(p.read_bytes()).decode()
    payload = {
        "model": os.getenv("DASHCOPE_VL_MODEL", "qwen3-vl-plus"),
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/{p.suffix.lstrip('.')};base64,{b64}"}},
                {"type": "text", "text": "请用中文详细描述这张图片的内容。"},
            ],
        }],
    }
    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]


if __name__ == "__main__":
    mcp.run()
