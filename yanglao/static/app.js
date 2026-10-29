/* 社区养老便民助手 - 前端逻辑:登录注册、地区识别/选择、对话、朗读、来源标注、字号调节 */
(function () {
  "use strict";

  const chatEl = document.getElementById("chat");
  const input = document.getElementById("input");
  const sendBtn = document.getElementById("send");
  const docList = document.getElementById("doc-list");
  const suggestEl = document.getElementById("suggest");

  /* ---------- 公共请求 ---------- */
  async function api(url, opts) {
    const resp = await fetch(url, opts);
    let data = null;
    try { data = await resp.json(); } catch (e) { /* 非 JSON 响应 */ }
    if (resp.status === 401) {
      // 带业务码的 401(如登录密码错)由调用方处理;纯"未登录"才弹登录页
      if (data && data.detail && typeof data.detail === "object" && data.detail.code) {
        const err = new Error(data.detail.msg || "登录失败");
        err.code = data.detail.code;
        throw err;
      }
      showAuth("请先登录");
      throw new Error("未登录");
    }
    if (!resp.ok) {
      let msg = "请求失败(" + resp.status + ")";
      if (data && data.detail) {
        msg = typeof data.detail === "string" ? data.detail : (data.detail.msg || msg);
      }
      throw new Error(msg);
    }
    return data;
  }

  /* ---------- 登录/注册(两个独立页面,互带跳转) ---------- */
  const authScreen = document.getElementById("auth-screen");
  const authLoginCard = document.getElementById("auth-login");
  const authRegisterCard = document.getElementById("auth-register");
  const formLogin = document.getElementById("form-login");
  const formRegister = document.getElementById("form-register");
  const authLocate = document.getElementById("auth-locate");

  function showAuth(msg) {
    authScreen.classList.remove("hidden");
    showLoginCard();
    const el = document.getElementById("login-error");
    if (msg && el) el.textContent = msg;
  }
  function hideAuth() { authScreen.classList.add("hidden"); }
  function showLoginCard() {
    authLoginCard.classList.remove("hidden");
    authRegisterCard.classList.add("hidden");
  }
  function showRegCard(prefillName) {
    authLoginCard.classList.add("hidden");
    authRegisterCard.classList.remove("hidden");
    if (prefillName) {
      document.getElementById("reg-username").value = prefillName;
      document.getElementById("reg-error").textContent =
        "「" + prefillName + "」还没注册，注册一个账号就能用了";
      document.getElementById("reg-password").focus();
    }
  }

  document.getElementById("goto-register").addEventListener("click", () => {
    document.getElementById("login-error").textContent = "";
    showRegCard();
  });
  document.getElementById("goto-login").addEventListener("click", () => {
    document.getElementById("reg-error").textContent = "";
    showLoginCard();
  });

  formLogin.addEventListener("submit", async e => {
    e.preventDefault();
    document.getElementById("login-error").textContent = "";
    const username = document.getElementById("login-username").value.trim();
    try {
      await api("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          password: document.getElementById("login-password").value,
        }),
      });
      await initSession();
    } catch (err) {
      if (err.code === "need_register") {
        // 没注册就去登录:提示需要注册,并直接带到注册页(用户名已填好)
        showRegCard(username);
      } else if (err.message !== "未登录") {
        document.getElementById("login-error").textContent = err.message;
      }
    }
  });

  formRegister.addEventListener("submit", async e => {
    e.preventDefault();
    const errEl = document.getElementById("reg-error");
    errEl.textContent = "";
    const pwd = document.getElementById("reg-password").value;
    const pwd2 = document.getElementById("reg-password2").value;
    if (pwd !== pwd2) { errEl.textContent = "两次输入的密码不一样"; return; }
    try {
      const region = document.getElementById("reg-region").value.trim();
      await api("/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: document.getElementById("reg-username").value.trim(),
          phone: document.getElementById("reg-phone").value.trim(),
          password: pwd,
          region,
        }),
      });
      document.getElementById("reg-region").value = "";
      await initSession();
    } catch (err) {
      if (err.message !== "未登录") errEl.textContent = err.message;
    }
  });

  /* ---------- 会话与头部信息(登录用户 / 游客两种模式) ---------- */
  let me = null;
  let isGuest = false;

  async function initSession() {
    // 用裸 fetch:401 时不要 api() 的弹登录副作用,由这里统一决定
    try {
      const resp = await fetch("/api/me");
      if (resp.ok) {
        const data = await resp.json();
        me = data.user;
        isGuest = false;
        try { localStorage.removeItem("yl_guest"); } catch (e) {}
        hideAuth();
        renderHeader();
        renderRegion(me.region || "");
        return;
      }
    } catch (e) { /* 网络问题,下面按游客/登录页处理 */ }

    try {
      if (localStorage.getItem("yl_guest") === "1") {
        isGuest = true;
        me = null;
        hideAuth();
        renderHeader();
        renderRegion(localStorage.getItem("yl_guest_region") || "");
        return;
      }
    } catch (e) {}
    showAuth();
  }

  function renderHeader() {
    document.getElementById("user-chip").textContent = isGuest ? "👤 游客" : ("👤 " + (me ? me.username : ""));
    document.getElementById("logout-btn").textContent = isGuest ? "登录" : "退出";
  }

  // 游客点"不用注册,直接使用"
  document.getElementById("guest-btn").addEventListener("click", () => {
    try { localStorage.setItem("yl_guest", "1"); } catch (e) {}
    isGuest = true;
    me = null;
    hideAuth();
    renderHeader();
    renderRegion(localStorage.getItem("yl_guest_region") || "");
  });

  // 头部按钮:游客是"登录",登录用户是"退出"
  document.getElementById("logout-btn").addEventListener("click", async () => {
    if (isGuest) {
      try { localStorage.removeItem("yl_guest"); } catch (e) {}
      isGuest = false;
      me = null;
      renderHeader();
      renderRegion("");
      showAuth();
      return;
    }
    try { await fetch("/api/logout", { method: "POST" }); } catch (e) {}
    me = null;
    isGuest = false;
    renderHeader();
    renderRegion("");
    showAuth();
  });

  function renderRegion(region) {
    document.getElementById("region-text").textContent = region || "选择地区";
  }
  function currentRegion() {
    if (me) return me.region || "";
    try { return localStorage.getItem("yl_guest_region") || ""; } catch (e) { return ""; }
  }

  /* ---------- 地区:检测 + 选择 ---------- */
  const regionModal = document.getElementById("region-modal");
  const regionInput = document.getElementById("region-input");
  const regionList = document.getElementById("region-list");
  const regionDetect = document.getElementById("region-detect");
  let detectResult = null;
  let allRegions = [];

  fetch("/api/regions").then(r => r.json()).then(data => {
    allRegions = data.builtin.slice();
    Object.values(data.wifi_map || {}).forEach(v => { if (!allRegions.includes(v)) allRegions.push(v); });
    regionList.innerHTML = allRegions.map(s => '<option value="' + s.replace(/"/g, "") + '">').join("");
  }).catch(() => {});

  fetch("/api/locate").then(r => r.json()).then(d => {
    detectResult = d;
    const lines = [];
    if (d.wifi) lines.push("📶 检测到 WiFi：" + d.wifi);
    if (d.region) {
      lines.push((d.source === "wifi" ? "📍 按 WiFi 判断您在：" : "📍 按网络 IP 判断您在：") + d.region);
      lines.push('<button id="use-detect" class="pill pill-btn">就用这个地区</button>');
    } else if (d.wifi) {
      lines.push("该 WiFi 还没配置地区映射，可联系管理员在 regions.json 里加上，或手动选择。");
    } else {
      lines.push("没检测到 WiFi 也没查到网络位置，请手动选择地区。");
    }
    authLocate.innerHTML = lines.join("<br>");
    const btn = document.getElementById("use-detect");
    if (btn) btn.addEventListener("click", () => {
      // 还没登录:把检测到的地区带进注册表,一起去注册
      document.getElementById("reg-region").value = d.region;
      showRegCard();
    });
  }).catch(() => {});

  function openRegionModal() {
    regionInput.value = currentRegion();
    regionDetect.innerHTML = detectResult && detectResult.region
      ? "系统检测到：<b>" + detectResult.region + "</b>（" + (detectResult.source === "wifi" ? "WiFi判断" : "网络IP判断") + "）"
      : "";
    regionModal.classList.remove("hidden");
    regionInput.focus();
  }

  document.getElementById("region-chip").addEventListener("click", openRegionModal);
  document.getElementById("region-cancel").addEventListener("click", () => regionModal.classList.add("hidden"));
  document.getElementById("region-save").addEventListener("click", async () => {
    const region = regionInput.value.trim();
    if (!region) { regionInput.focus(); return; }
    try {
      if (isGuest) {
        // 游客:地区存浏览器本地,提问时随请求带去
        try { localStorage.setItem("yl_guest_region", region); } catch (e) {}
      } else {
        await api("/api/region", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ region }),
        });
        if (me) me.region = region;
      }
      renderRegion(region);
      regionModal.classList.add("hidden");
    } catch (e) { /* 错误提示交给 api() 弹的登录页或静默 */ }
  });

  /* ---------- 朗读(Web Speech API) ---------- */
  let zhVoices = [];
  function loadVoices() {
    zhVoices = (window.speechSynthesis ? speechSynthesis.getVoices() : [])
      .filter(v => v.lang && v.lang.toLowerCase().startsWith("zh"));
  }
  if (window.speechSynthesis) {
    loadVoices();
    speechSynthesis.onvoiceschanged = loadVoices;
  }
  function pickVoice() {
    return zhVoices.find(v => /xiaoxiao|yunxi|yunjian|huihui/i.test(v.name)) || zhVoices[0] || null;
  }
  function speak(btn, text) {
    if (!window.speechSynthesis) {
      alert("当前浏览器不支持朗读功能，建议使用 Edge 或 Chrome 浏览器。");
      return;
    }
    if (speechSynthesis.speaking && btn.classList.contains("on")) {
      speechSynthesis.cancel();
      return;
    }
    speechSynthesis.cancel();
    const clean = text
      .replace(/\[\d+\]/g, "")   // 去掉来源编号
      .replace(/\*\*/g, "")
      .replace(/[#>*`-]/g, "");
    const u = new SpeechSynthesisUtterance(clean);
    u.lang = "zh-CN";
    u.rate = 1.0;
    const v = pickVoice();
    if (v) u.voice = v;
    u.onend = () => { btn.classList.remove("on"); btn.textContent = "🔊 朗读"; };
    u.onerror = () => { btn.classList.remove("on"); btn.textContent = "🔊 朗读"; };
    speechSynthesis.speak(u);
    btn.classList.add("on");
    btn.textContent = "⏹ 停止";
  }
  function addSpeakBtn(bubble, text) {
    const btn = document.createElement("button");
    btn.className = "speak-btn";
    btn.textContent = "🔊 朗读";
    btn.title = "把回答读出来";
    btn.addEventListener("click", () => speak(btn, text));
    bubble.appendChild(btn);
  }

  /* ---------- 极简 Markdown 渲染(先转义再处理,安全) ---------- */
  function inline(s) {
    return s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }
  function md(text) {
    const esc = String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const lines = esc.split("\n");
    let html = "", list = null;
    for (const line of lines) {
      if (/^[-*]\s+/.test(line)) {
        if (list !== "ul") { html += "<ul>"; list = "ul"; }
        html += "<li>" + inline(line.replace(/^[-*]\s+/, "")) + "</li>";
        continue;
      }
      if (/^\d+[.、]\s*/.test(line)) {
        if (list !== "ol") { html += "<ol>"; list = "ol"; }
        html += "<li>" + inline(line.replace(/^\d+[.、]\s*/, "")) + "</li>";
        continue;
      }
      if (list) { html += "</" + list + ">"; list = null; }
      if (/^#{1,3}\s/.test(line)) {
        html += "<h4>" + inline(line.replace(/^#{1,3}\s/, "")) + "</h4>";
        continue;
      }
      if (line.trim() === "") continue;
      html += "<p>" + inline(line) + "</p>";
    }
    if (list) html += "</" + list + ">";
    return html || "<p>…</p>";
  }

  /* ---------- 来源标签 ---------- */
  function sourcesHtml(sources) {
    if (!sources || !sources.length) return "";
    const chips = sources.map(s => {
      const label = s.title.length > 14 ? s.title.slice(0, 14) + "…" : s.title;
      return `<a class="src-chip" href="${s.url}" target="_blank" rel="noopener" title="${s.source}｜${s.section}｜${s.date}">
        <span class="n">${s.n}</span>${label}</a>`;
    }).join("");
    return `<div class="sources"><div class="src-label">📎 回答依据（点击可查看原文）：</div>${chips}</div>`;
  }

  /* ---------- 消息渲染 ---------- */
  function addMsg(role, kind, text, sources) {
    const div = document.createElement("div");
    div.className = "msg " + role + (kind ? " " + kind : "");
    div.innerHTML =
      '<div class="avatar">' + (role === "user" ? "🙋" : "🤝") + "</div>" +
      '<div class="bubble">' + md(text) + sourcesHtml(sources) + "</div>";
    chatEl.appendChild(div);
    const bubble = div.querySelector(".bubble");
    addSpeakBtn(bubble, text);  // 用户气泡也加,方便重听自己问的啥
    chatEl.scrollTop = chatEl.scrollHeight;
    return div;
  }

  function addTyping() {
    const div = document.createElement("div");
    div.className = "msg bot typing";
    div.innerHTML = '<div class="avatar">🤝</div><div class="bubble"></div>';
    chatEl.appendChild(div);
    chatEl.scrollTop = chatEl.scrollHeight;
    return div;
  }

  const MODE_TAG = {
    unknown: '<span class="mode-tag unknown">⚠ 资料库里没有相关文件，如实告知</span>',
    fallback: '<span class="mode-tag fallback">ℹ 接口降级，以下为资料原文</span>',
  };

  /* ---------- 提问 ---------- */
  async function ask(question) {
    question = question.trim();
    if (!question || sendBtn.disabled) return;
    sendBtn.disabled = true;
    suggestEl.style.display = "none";
    addMsg("user", "", question);
    const typing = addTyping();

    try {
      const data = await api("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, guest: isGuest, region: currentRegion() }),
      });
      typing.remove();
      const tag = MODE_TAG[data.mode] || "";
      addMsg("bot", data.mode, tag + data.answer, data.sources);
    } catch (err) {
      typing.remove();
      if (err.message !== "未登录") {
        addMsg("bot", "unknown", MODE_TAG.unknown + "网络出问题了，没连上服务。请检查服务是否已启动（运行 start.bat）。");
      }
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  /* ---------- 事件 ---------- */
  sendBtn.addEventListener("click", () => { ask(input.value); input.value = ""; });
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      ask(input.value);
      input.value = "";
    }
  });
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
  });
  suggestEl.addEventListener("click", e => {
    if (e.target.classList.contains("chip")) ask(e.target.textContent);
  });
  document.getElementById("clear-btn").addEventListener("click", () => {
    chatEl.querySelectorAll(".msg:not(.welcome)").forEach(n => n.remove());
    suggestEl.style.display = "";
  });

  /* 字号:html 上切 class f1~f4 */
  const FONT_STEPS = ["f1", "f2", "f3", "f4"];
  let fontIdx = 1;
  function applyFont() {
    document.documentElement.className = FONT_STEPS[fontIdx];
    try { localStorage.setItem("yl_font", String(fontIdx)); } catch (e) {}
  }
  document.getElementById("font-down").addEventListener("click", () => {
    fontIdx = Math.max(0, fontIdx - 1); applyFont();
  });
  document.getElementById("font-up").addEventListener("click", () => {
    fontIdx = Math.min(FONT_STEPS.length - 1, fontIdx + 1); applyFont();
  });
  try { fontIdx = Math.min(FONT_STEPS.length - 1, Math.max(0, +localStorage.getItem("yl_font") || 1)); } catch (e) {}
  applyFont();

  /* ---------- 资料库列表 ---------- */
  fetch("/api/docs").then(r => r.json()).then(data => {
    docList.innerHTML = data.docs.map(d =>
      '<li><a class="doc-title" href="' + d.url + '" target="_blank" rel="noopener" title="' + d.source + '">' +
      "📄 " + d.title + " ↗</a>" +
      (d.region ? '<span class="doc-region">适用：' + d.region + "</span>" : "") +
      '<div class="doc-meta">' + d.source + (d.date ? "｜" + d.date : "") + "</div></li>"
    ).join("") || '<li class="doc-loading">资料库为空，请把政策文件放进 docs 文件夹。</li>';
  }).catch(() => {
    docList.innerHTML = '<li class="doc-loading">资料库读取失败。</li>';
  });

  /* ---------- 启动 ---------- */
  initSession();
})();
