# 社区养老便民助手

帮社区居民查养老政策的问答助手。回答**只依据 docs/ 文件夹里收录的政策文件**，用大白话讲解（不说官话），每条信息标注来源编号并可点击查看原文；文件里查不到的，直接回答"不知道"，绝不瞎编。每条回答都有"朗读"按钮（浏览器语音合成，建议用 Edge/Chrome）。

## 启动

双击 `start.bat`（用 conda 的 ai 环境，和 partner 项目一致），浏览器自动打开 http://localhost:8090

依赖在 `D:\DevTools\Python\Miniconda3\envs\ai` 环境里已装好；换机器的话 `pip install -r requirements.txt`。

## 账号与地区

- **注册/登录**：首次使用先注册（用户名+密码，手机号选填），账号存本地 SQLite（`data.db`，自动创建，密码加盐哈希不存明文）。登录状态存在浏览器 Cookie 里，30 天有效。不登录不能提问。
- **地区识别**：优先读本机 WiFi 名称（`netsh wlan show interfaces`），命中 `regions.json` 里 `wifi_map` 的映射就自动识别为对应地区；映射没配或没连 WiFi 时，按服务器出口 IP 反查城市（ip-api.com，有 1 小时缓存；国内网络下可能不通，属正常）。把社区的 WiFi 名称配进 `wifi_map` 即可自动识别，例如：`"居委会WiFi": "示例社区"`。
- **手动选择**：登录后点右上角"📍 地区"随时可改，地区跟着账号存。选了地区后，回答会优先引用该地区的文件（文件头部加 `region: 湖北省` 标注适用地区），并会在提示里告诉模型居民所在地区。

## 回答是怎么来的

1. 居民提问 → 在 docs/ 里做关键词检索（按居民所在地区对当地文件加权），找出最相关的几段原文。
2. **一段都找不到** → 不调大模型，直接答"这个我这边没有查到文件依据，不敢乱说"。
3. 找得到 → 把原文连同来源编号一起交给 DeepSeek，只许依据原文用大白话回答，并给每条关键信息标 `[1][2]` 编号。
4. 前端把编号渲染成来源标签，点击跳转到官方原文页面；答案尾部列出本次回答依据的文件。

## 怎么放进自己社区的文件

把社区的官方文件转成 `docs/` 文件夹里的 `.md`（Markdown）文件即可，然后点页面右上角"清空对话"旁边不用管——服务每次回答都会读最新文件；也可以用 `POST /api/reload` 强制重扫。

格式（开头一段元信息，正文用 `## 小节` 分节）：

```markdown
---
title: XX社区高龄津贴发放办法
source: XX社区居委会（2026年X号文件）
url: https://官方发布链接
date: 2026-01-01
---

## 发放标准
80周岁以上老人每月XX元……

## 怎么申请
带身份证到居委会……
```

支持 txt/docx/pdf 的话，先用工具转成 md 或纯文本（标题行用 `## ` 开头效果最好）。

## 接口

| 接口 | 说明 |
| --- | --- |
| `POST /api/register` | 注册 `{username, password, phone?, region?}`，成功即登录并种 Cookie |
| `POST /api/login` / `POST /api/logout` | 登录 / 退出 |
| `GET /api/me` | 当前登录用户（未登录返回 401） |
| `GET /api/locate` | 地区检测结果（WiFi 名称 + 映射/IP 反查） |
| `GET /api/regions` | 地区映射与内置地区列表 |
| `PUT /api/region` | 修改当前用户地区 `{region}`（需登录） |
| `POST /api/chat` | 入参 `{"question":"..."}`，返回 `{mode, answer, sources}`；mode 有 answered / unknown / fallback 三种；**需登录** |
| `GET /api/docs` | 资料库清单 |
| `POST /api/reload` | 重新扫描 docs 文件夹 |

## 注意事项

- DeepSeek 密钥复用 `D:\AI_agent\.env` 里的 `DEEPSEEK_API_KEY`。
- 检索打分的阈值在 `knowledge.py` 的 `retrieve()` 里（`threshold=0.22`）：调高 → 更保守（更多"不知道"），调低 → 更容易回答。
- 知识库当前收录的 6 份文件来自政府公开网站（检索于 2026-10-29），政策会更新，请定期核对原文；社区文件到位后，优先以社区文件为准。
