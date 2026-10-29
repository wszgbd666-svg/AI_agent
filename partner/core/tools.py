"""文件与命令工具:让 Partner 能真正动手做事。

所有文件操作限制在工作区(WORKSPACE_DIR)内;禁止读写任何 .env;
危险命令直接拒绝。write_file / run_command 是否需要用户确认由 app.py 的审批流程控制。
"""

import base64
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from core import config

MAX_READ_BYTES = 50 * 1024
MAX_EXTRACT = 50 * 1024   # 文档/图片抽取文字的上限
MAX_OUTPUT = 4000
COMMAND_TIMEOUT = 60

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
DOC_TEXT_EXTS = {".pdf": "PDF", ".docx": "Word", ".xlsx": "Excel", ".xlsm": "Excel"}

# 危险命令拒绝列表(小写子串匹配)
DENY_COMMANDS = [
    "format ", "shutdown", "diskpart", "reg delete", "rm -rf",
    "rd /s", "del /f /s", "del /s /q", "taskkill /f", "rmdir /s",
]


def safe_path(path_str):
    """把模型给的路径解析到工作区白名单内;越界、访问 .env 等非法路径返回 None。"""
    raw = str(path_str or "").strip().strip('"')
    if not raw:
        return None
    # Linux 上拒绝 Windows 盘符路径(如 D:/xxx),避免被当成普通相对路径建出怪目录
    if os.name != "nt" and re.match(r"^[A-Za-z]:", raw):
        return None
    p = __import__("pathlib").Path(raw)
    if not p.is_absolute():
        p = config.RELATIVE_ANCHOR / p  # 相对路径锚定到项目目录
    try:
        resolved = p.resolve()
    except OSError:
        return None
    in_roots = any(
        resolved == r.resolve() or r.resolve() in resolved.parents
        for r in config.WORKSPACE_ROOTS
    )
    if not in_roots:
        return None
    if any(part.lower() == ".env" for part in resolved.parts):
        return None  # .env 含密钥,禁止读写
    return resolved


def _path_error(path_str):
    """生成友好的路径错误信息。"""
    raw = str(path_str or "").strip().strip('"')
    if os.name != "nt" and re.match(r"^[A-Za-z]:", raw):
        return ("这是 Linux 服务器,没有 Windows 盘符路径(D 盘/C 盘都不存在)。"
                "文件都放在服务器的工作区 /root/partner 下,请用那里的路径。")
    return f"路径不可用:{path_str}(工作区外或路径非法)"


def list_dir(path_str=""):
    p = safe_path(path_str)
    if p is None or not p.is_dir():
        return _path_error(path_str)
    rows = []
    for child in sorted(p.iterdir(), key=lambda c: c.name):
        try:
            size = child.stat().st_size
        except OSError:
            size = 0
        # 返回绝对路径,模型后续 read/write 直接用,不用猜
        if child.is_dir():
            rows.append(f"DIR  {child}\\")
        else:
            rows.append(f"FILE {child} ({size}B)")
    return "\n".join(rows) or "(空目录)"


def read_file(path_str):
    p = safe_path(path_str)
    if p is None or not p.is_file():
        return _path_error(path_str)
    ext = p.suffix.lower()
    if ext in DOC_TEXT_EXTS:
        return _extract_document(p, ext)
    try:
        data = p.read_bytes()
        if len(data) > MAX_READ_BYTES:
            data = data[:MAX_READ_BYTES]
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return "(二进制文件,不适合直接读)"
    except OSError as e:
        return f"读取失败:{e}"


def write_file(path_str, content):
    p = safe_path(path_str)
    if p is None:
        return _path_error(path_str)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(content), encoding="utf-8")
        return f"已写入 {p}({len(str(content))} 字符)"
    except OSError as e:
        return f"写入失败:{e}"


def run_command(command):
    cmd = str(command or "").strip()
    if not cmd:
        return "命令为空"
    low = cmd.lower()
    for bad in DENY_COMMANDS:
        if bad in low:
            return f"命令被安全策略拒绝(包含危险片段:{bad.strip()})"
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=str(config.RELATIVE_ANCHOR),
            capture_output=True, timeout=COMMAND_TIMEOUT,
        )
        out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
        if len(out) > MAX_OUTPUT:
            out = out[:MAX_OUTPUT] + "\n...(输出过长已截断)"
        return (out.strip() or "(无输出)") + f"\n[退出码 {proc.returncode}]"
    except subprocess.TimeoutExpired:
        return f"命令超时(>{COMMAND_TIMEOUT}s),已终止"
    except OSError as e:
        return f"执行失败:{e}"


# ---------- 文档抽取 ----------

def _extract_document(p, ext):
    try:
        if ext == ".pdf":
            text = _extract_pdf(p)
        elif ext == ".docx":
            text = _extract_docx(p)
        else:
            text = _extract_xlsx(p)
        if not text.strip():
            return "(文档里没有可提取的文字)"
        if len(text) > MAX_EXTRACT:
            text = text[:MAX_EXTRACT] + "\n...(内容过长已截断)"
        return text
    except ImportError:
        return "(缺少解析库,读不了这个格式)"
    except Exception as e:
        return f"解析失败:{e}"


def _extract_pdf(p):
    from pypdf import PdfReader
    reader = PdfReader(str(p))
    pages = []
    for i, page in enumerate(reader.pages[:50]):
        t = page.extract_text() or ""
        if t.strip():
            pages.append(f"--- 第{i + 1}页 ---\n{t}")
    return "\n\n".join(pages)


def _extract_docx(p):
    import docx
    d = docx.Document(str(p))
    return "\n".join(par.text for par in d.paragraphs if par.text.strip())


def _extract_xlsx(p):
    from openpyxl import load_workbook
    wb = load_workbook(str(p), read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets[:5]:
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            if any(cells):
                rows.append(" | ".join(cells))
            if len(rows) >= 200:
                rows.append("...(行数过多已截断)")
                break
        parts.append(f"--- 工作表:{ws.title} ---\n" + "\n".join(rows))
    return "\n\n".join(parts)


# ---------- 图片:OCR + 本地视觉模型 ----------

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


def _ocr(image_path):
    """图片文字识别。

    - Linux:优先 Tesseract(chi_sim 中文)
    - Windows:系统自带 OCR(结果写临时文件避免控制台编码问题)
    """
    if os.name != "nt":
        try:
            r = subprocess.run(
                ["tesseract", str(image_path), "stdout", "-l", "chi_sim+eng"],
                capture_output=True, timeout=60,
            )
            if r.returncode == 0:
                return r.stdout.decode("utf-8", errors="replace").strip()
        except (OSError, subprocess.SubprocessError):
            pass
        return ""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_path = f.name
    try:
        # 注意:必须用原生反斜杠路径,WinRT GetFileFromPathAsync 不认正斜杠
        script = _PS_OCR.replace("__IMAGE_PATH__", str(Path(image_path))) \
                        .replace("__OUT_PATH__", str(Path(out_path)))
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, timeout=60,
        )
        return Path(out_path).read_text(encoding="utf-8-sig").strip()
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass


def vision_describe(image_path, timeout=90):
    """描述画面:优先 DashScope qwen3-vl(云端,需要 DASHCOPE_API_KEY);
    否则回退本地 Ollama(VISION_MODEL)。都不可用返回 None。"""
    dash_key = os.getenv("DASHCOPE_API_KEY", "").strip()
    if dash_key:
        try:
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            ext = Path(image_path).suffix.lstrip(".") or "png"
            payload = json.dumps({
                "model": os.getenv("DASHCOPE_VL_MODEL", "qwen3-vl-plus"),
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/{ext};base64,{b64}"}},
                        {"type": "text", "text": "请用中文详细描述这张图片的内容。"},
                    ],
                }],
            }).encode()
            req = urllib.request.Request(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {dash_key}"},
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode())
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[vision] DashScope 视觉失败: {e}", flush=True)
    model = os.getenv("VISION_MODEL", "").strip()
    if not model:
        return None
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        body = json.dumps({
            "model": model,
            "prompt": "用中文简短描述这张图片的内容。",
            "images": [b64],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=body, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()).get("response", "").strip() or None
    except Exception:
        return None


def _bocha_search(query):
    """博查搜索 API(可靠首选)。失败返回 None。"""
    key = os.getenv("BOCHA_API_KEY", "").strip()
    if not key:
        return None
    try:
        payload = json.dumps({"query": str(query), "summary": True}).encode()
        req = urllib.request.Request(
            "https://api.bocha.cn/v1/web-search",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        pages = (((data.get("data") or {}).get("webPages") or {}).get("value") or [])
        lines = []
        for p in pages[:8]:
            title = p.get("name") or p.get("title") or ""
            url = p.get("url") or p.get("displayUrl") or ""
            summary = p.get("summary") or p.get("snippet") or ""
            lines.append(f"- {title}\n  {url}\n  {summary[:150]}")
        return "\n\n".join(lines) if lines else None
    except Exception:
        return None


def search_web(query):
    """联网搜索:博查 → 自建 SearXNG → DashScope 三级回退。"""
    import urllib.parse

    # 1) 博查
    bocha = _bocha_search(query)
    if bocha:
        return bocha
    # 2) SearXNG
    searx = os.getenv("SEARXNG_URL", "http://127.0.0.1:8088").rstrip("/")
    try:
        url = f"{searx}/search?q={urllib.parse.quote(str(query))}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        results = data.get("results", [])
        if not results:
            return "(搜索无结果)"
        lines = []
        for item in results[:8]:
            title = re.sub(r"<[^>]+>", "", str(item.get("title", ""))).strip()
            content = re.sub(r"<[^>]+>", "", str(item.get("content", ""))).strip()
            lines.append(f"- {title}\n  {item.get('url', '')}\n  {content[:150]}")
        return "\n\n".join(lines)
    except Exception as e:
        return _dashscope_search(query, e)


def _dashscope_search(query, searx_error):
    """回退方案:DashScope enable_search(部分账号未开通时返回提示)。"""
    key = os.getenv("DASHCOPE_API_KEY", "").strip()
    if not key:
        return "(联网搜索不可用:未配置 SEARXNG_URL 且没有 DASHCOPE_API_KEY)"
    try:
        payload = json.dumps({
            "model": os.getenv("DASHCOPE_SEARCH_MODEL", "qwen-plus"),
            "messages": [{"role": "user", "content": str(query).strip()}],
            "enable_search": True,
        }).encode()
        req = urllib.request.Request(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        content = data["choices"][0]["message"]["content"]
        if "search_info" not in data:
            return "(联网搜索未生效,请如实告诉主人暂时查不了。)"
        refs = [x.get("title") or x.get("url") or ""
                for x in (data.get("search_info") or {}).get("search_results", [])[:5]]
        refs = [x for x in refs if x]
        if refs:
            content += "\n\n参考来源:\n" + "\n".join(f"- {x}" for x in refs)
        return content.strip()
    except Exception as e:
        return f"搜索失败(自建搜索:{searx_error};回退:{e})"


def get_weather(city="武汉"):
    """查询城市天气(wttr.in 免费接口,免注册)。"""
    try:
        import urllib.parse
        url = f"http://wttr.in/{urllib.parse.quote(city)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        cur = data["current_condition"][0]
        today = data["weather"][0]
        lines = [
            f"{city}当前: {cur.get('weatherDesc', [{}])[0].get('value', '')} {cur.get('temp_C', '?')}°C",
            f"体感 {cur.get('FeelsLikeC', '?')}°C,湿度 {cur.get('humidity', '?')}%,风速 {cur.get('windspeedKmph', '?')}km/h",
            f"今日: {today.get('mintempC', '?')}~{today.get('maxtempC', '?')}°C",
        ]
        for h in today.get("hourly", [])[::4]:
            lines.append(f"{h['time'][-3:]} {h.get('weatherDesc', [{}])[0].get('value', '')} {h.get('tempC', '?')}°C")
        return "\n".join(lines[:10])
    except Exception as e:
        return f"天气获取失败:{e}"


def fetch_url(url):
    """抓取网页文字内容(限 http/https,截取前 4000 字)。"""
    if not re.match(r"^https?://", str(url or "").strip()):
        return "只支持 http/https 链接"
    try:
        req = urllib.request.Request(str(url).strip(), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read(200000).decode("utf-8", errors="replace")
        text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:4000] or "(网页为空)"
    except Exception as e:
        return f"抓取失败:{e}"


def read_image(path_str):
    """读图片:OCR 识别文字 + (配置了视觉模型时)画面描述。"""
    p = safe_path(path_str)
    if p is None or not p.is_file():
        return _path_error(path_str)
    if p.suffix.lower() not in IMAGE_EXTS:
        return f"不是图片文件:{p.suffix}"
    parts = []
    try:
        ocr = _ocr(str(p))
        parts.append("[OCR识别到的文字]\n" + ocr if ocr.strip() else "[OCR] 图中没有识别到文字")
    except Exception as e:
        parts.append(f"[OCR 失败]{e}")
    desc = vision_describe(str(p))
    if desc:
        parts.append("[画面描述]\n" + desc)
    return "\n\n".join(parts)
