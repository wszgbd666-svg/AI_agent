const chatEl = document.getElementById('chat');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const statusEl = document.getElementById('status');
const clearBtn = document.getElementById('clearBtn');

// 生成会话 ID:crypto.randomUUID 只在 HTTPS/localhost 下存在,
// 局域网 HTTP 访问(手机 http://192.168.x.x)会没有它,必须兜底
function newId() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

// 会话 ID 持久化:刷新/重开页面接着上次的聊
let sessionId = localStorage.getItem('partner_sid') || newId();
if (!localStorage.getItem('partner_sid')) localStorage.setItem('partner_sid', sessionId);
let sending = false;

function rememberSid(sid) {
  sessionId = sid;
  localStorage.setItem('partner_sid', sid);
}

// 页面出错时显示红条,方便排查
window.addEventListener('error', (e) => {
  const bar = document.getElementById('errBar');
  if (bar) {
    bar.hidden = false;
    bar.textContent = '页面出错:' + (e.message || '未知错误');
  }
});

// 访问密码:从 URL 或 localStorage 取,拼到所有请求上;有保存的密码就自动跳转
function currentKey() {
  return new URLSearchParams(location.search).get('key') || localStorage.getItem('partner_key') || '';
}
function apiUrl(path) {
  const key = currentKey();
  return path + (key ? (path.includes('?') ? '&' : '?') + 'key=' + encodeURIComponent(key) : '');
}
if (!location.search.includes('key=') && localStorage.getItem('partner_key')) {
  location.replace('/?key=' + encodeURIComponent(localStorage.getItem('partner_key')));
}

const GREETING = '主人好,我是蓝蓝,你的鲸鱼娘管家 🐳\n'
  + '我能陪你聊天、记事,也能帮你做事:查目录、读文件、写文件、跑命令(写和跑需要你点允许)。\n'
  + '比如试试:「帮我在 partner 里建一个 hello.txt,内容写你好」。';

const TOOL_LABELS = {
  list_dir: '📂 查看目录',
  read_file: '📄 读文件',
  write_file: '✏️ 写文件',
  run_command: '⚙️ 执行命令',
  recall: '🔍 搜索记忆',
  remember: '💾 写入记忆',
  forget: '🗑 删除记忆',
  list_memories: '📚 翻看记忆',
};

function addMsg(role, text) {
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + role;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  wrap.appendChild(bubble);
  chatEl.appendChild(wrap);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

function addToolRow(detail) {
  const row = document.createElement('div');
  row.className = 'tool-row';
  row.textContent = detail;
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  return row;
}

function setStatus(text) {
  statusEl.hidden = !text;
  statusEl.textContent = text || '';
}

async function* readStream(res) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const raw = buf.slice(0, i);
      buf = buf.slice(i + 2);
      if (raw.startsWith('data: ')) yield JSON.parse(raw.slice(6));
    }
  }
}

async function handleEvents(events, ref) {
  for await (const ev of events) {
    if (ev.type === 'session') {
      rememberSid(ev.id);
    } else if (ev.type === 'delta') {
      ref.saw = true;
      if (!ref.bubble) ref.bubble = addMsg('assistant', '');
      ref.full += ev.text;
      ref.bubble.textContent = ref.full;
    } else if (ev.type === 'tool') {
      ref.saw = true;
      const label = TOOL_LABELS[ev.name] || ev.name;
      const firstLine = (ev.detail || '').split('\n')[0];
      ref.toolRow = addToolRow(label + (firstLine ? ': ' + firstLine : ''));
    } else if (ev.type === 'tool_result') {
      ref.saw = true;
      if (ref.toolRow && ev.summary) ref.toolRow.textContent += '\n↳ ' + ev.summary;
    } else if (ev.type === 'approval') {
      ref.saw = true;
      ref.pending = true;
      setStatus('等待你的确认…');
      addApprovalCard(ev, ref);
    }
    chatEl.scrollTop = chatEl.scrollHeight;
  }
}

function addApprovalCard(ev, ref) {
  const card = document.createElement('div');
  card.className = 'approval-card';
  const title = document.createElement('div');
  title.className = 'approval-title';
  title.textContent = 'Partner 请求执行:' + (TOOL_LABELS[ev.name] || ev.name);
  const detail = document.createElement('pre');
  detail.className = 'approval-detail';
  detail.textContent = ev.detail || '';
  const actions = document.createElement('div');
  actions.className = 'approval-actions';
  const okBtn = document.createElement('button');
  okBtn.textContent = '允许';
  okBtn.className = 'approve-ok';
  const noBtn = document.createElement('button');
  noBtn.textContent = '拒绝';
  noBtn.className = 'approve-no';
  actions.append(okBtn, noBtn);
  card.append(title, detail, actions);
  chatEl.appendChild(card);
  chatEl.scrollTop = chatEl.scrollHeight;

  const decide = (approved) => {
    card.remove();
    ref.pending = false;
    approve(ev.request_id, approved);
  };
  okBtn.addEventListener('click', () => decide(true));
  noBtn.addEventListener('click', () => decide(false));
}

async function approve(requestId, approved) {
  sending = true;
  setStatus(approved ? '执行中…' : '已拒绝,Partner 正在调整…');
  const ref = { bubble: null, full: '', toolRow: null, saw: false, pending: false };
  try {
    const res = await fetch(apiUrl('/api/approve'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, request_id: requestId, approved }),
    });
    if (!res.ok) {
      addMsg('assistant', '审批失败(' + res.status + '),可能已过期');
      return;
    }
    await handleEvents(readStream(res), ref);
    if (ref.bubble) addSpeakButton(ref.bubble, ref.full);
  } catch (e) {
    addMsg('assistant', '网络出错了:' + e.message);
  } finally {
    if (!ref.pending) setStatus('');
    sending = false;
    input.focus();
  }
}

async function sendText(text) {
  sending = true;
  document.getElementById('chips').hidden = true;
  addMsg('user', text);
  const ref = { bubble: null, full: '', toolRow: null, saw: false, pending: false };
  setStatus('思考中…');
  try {
    const res = await fetch(apiUrl('/api/chat'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });
    if (!res.ok) {
      addMsg('assistant', '出错了(' + res.status + ')');
      return;
    }
    await handleEvents(readStream(res), ref);
    if (!ref.saw) addMsg('assistant', '(没有回复)');
    if (ref.bubble) addSpeakButton(ref.bubble, ref.full);
  } catch (e) {
    addMsg('assistant', '网络出错了:' + e.message);
  } finally {
    if (!ref.pending) setStatus('');
    sending = false;
    input.focus();
  }
}

async function send() {
  const text = input.value.trim();
  if (!text || sending) return;
  input.value = '';
  await sendText(text);
}

// ---- 语音输入 + 朗读回复 ----
const micBtn = document.getElementById('micBtn');
let rec = null;
let listening = false;

let micWatchdog = null;

function micReset() {
  listening = false;
  micBtn.style.background = '';
  setStatus('');
  clearTimeout(micWatchdog);
  micWatchdog = null;
}

function startVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    addMsg('assistant', '这个浏览器不支持语音输入,换 Chrome/Edge 试试');
    return;
  }
  if (listening) {
    // 再点一次:强制停止
    try { rec.abort(); } catch (e) {}
    micReset();
    return;
  }
  rec = new SR();
  rec.lang = 'zh-CN';
  rec.continuous = false;
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  listening = true;
  micBtn.style.background = '#e5534b';
  setStatus('🎤 正在听,请说话…');
  rec.onresult = (e) => {
    const text = e.results[0][0].transcript;
    micReset();
    input.value = text;
    send();
  };
  rec.onerror = (e) => {
    micReset();
    if (e.error === 'not-allowed') {
      addMsg('assistant', '麦克风权限被拒绝了,请在浏览器/系统设置里允许本站使用麦克风');
    } else if (e.error === 'no-speech') {
      addMsg('assistant', '没听到声音,再点一次 🎤 试试');
    } else if (e.error !== 'aborted') {
      addMsg('assistant', '语音识别出错了(' + e.error + ')。国内网络下浏览器语音可能不稳,可以先打字~');
    }
  };
  rec.onend = () => micReset();
  // 看门狗:8 秒没结果就强制复位,防止卡在"正在听"状态
  micWatchdog = setTimeout(() => {
    try { rec.abort(); } catch (e) {}
    micReset();
    addMsg('assistant', '语音超时了。国内网络下浏览器语音经常连不上服务器,建议先打字~');
  }, 8000);
  try { rec.start(); } catch (e) { micReset(); }
}
micBtn.addEventListener('click', startVoice);

function addSpeakButton(bubble, text) {
  if (!('speechSynthesis' in window) || !text) return;
  const btn = document.createElement('button');
  btn.className = 'speak-btn';
  btn.textContent = '🔊';
  btn.title = '朗读';
  btn.addEventListener('click', () => {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'zh-CN';
    u.rate = 1.05;
    window.speechSynthesis.speak(u);
  });
  bubble.parentElement.appendChild(btn);
}

// ---- 发图片:上传 → OCR 识别 → 带着识别结果发给 Partner ----
const imgBtn = document.getElementById('imgBtn');
const filePicker = document.getElementById('filePicker');

function addUploadedImage(blobUrl) {
  const wrap = document.createElement('div');
  wrap.className = 'msg user';
  const img = document.createElement('img');
  img.src = blobUrl;
  img.className = 'uploaded-img';
  wrap.appendChild(img);
  chatEl.appendChild(wrap);
  chatEl.scrollTop = chatEl.scrollHeight;
}

imgBtn.addEventListener('click', () => filePicker.click());

filePicker.addEventListener('change', async () => {
  const f = filePicker.files[0];
  filePicker.value = '';
  if (!f || sending) return;
  const blobUrl = URL.createObjectURL(f);
  addUploadedImage(blobUrl);
  setStatus('正在识别图片…');
  try {
    const fd = new FormData();
    fd.append('file', f);
    const res = await fetch(apiUrl('/api/upload'), { method: 'POST', body: fd });
    const r = await res.json();
    if (!res.ok || !r.ok) {
      addMsg('assistant', '图片识别失败:' + (r.detail || res.status));
      return;
    }
    const note = input.value.trim();
    input.value = '';
    const msg = (note ? note + '\n\n' : '') + '[用户发来一张图片]\n' + r.text;
    await sendText(msg);
  } catch (e) {
    addMsg('assistant', '网络出错了:' + e.message);
  } finally {
    URL.revokeObjectURL(blobUrl);
    setStatus('');
  }
});

sendBtn.addEventListener('click', send);
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.isComposing) {
    e.preventDefault();
    send();
  }
});

// 快捷提问:点击直接发送
document.querySelectorAll('.chip').forEach((c) => {
  c.addEventListener('click', () => {
    input.value = c.textContent;
    send();
  });
});

clearBtn.addEventListener('click', () => {
  rememberSid(newId());
  sending = false;
  setStatus('');
  chatEl.innerHTML = '';
  addMsg('assistant', GREETING);
});

// ---- 记忆面板 ----
const memBtn = document.getElementById('memBtn');
const memClose = document.getElementById('memClose');
const memPanel = document.getElementById('memPanel');
const memList = document.getElementById('memList');
const tabs = document.querySelectorAll('.tabs button');
let curScope = 'all';

async function loadMemories() {
  const res = await fetch(apiUrl('/api/memories?scope=' + curScope));
  const items = await res.json();
  memList.innerHTML = '';
  if (!items.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = '还没有记忆。聊天时说「记住…」,我就会记下来。';
    memList.appendChild(li);
    return;
  }
  for (const it of items) {
    const li = document.createElement('li');
    const content = document.createElement('div');
    content.className = 'memo-content';
    content.textContent = it.content;
    const meta = document.createElement('div');
    meta.className = 'meta';
    const badge = document.createElement('span');
    badge.className = 'badge ' + it.scope;
    badge.textContent = it.scope === 'public' ? '公有' : '私有';
    const del = document.createElement('button');
    del.textContent = '删除';
    del.addEventListener('click', async () => {
      await fetch(apiUrl('/api/memories/' + it.scope + '/' + it.id), { method: 'DELETE' });
      loadMemories();
    });
    meta.append(badge, del);
    li.append(content, meta);
    memList.appendChild(li);
  }
}

// ---- 权限规则 ----
const permSection = document.getElementById('permSection');
const permList = document.getElementById('permList');

async function loadPerms() {
  const res = await fetch(apiUrl('/api/permissions'));
  const rules = await res.json();
  permList.innerHTML = '';
  if (!rules.length) {
    const li = document.createElement('li');
    li.style.color = 'var(--muted)';
    li.textContent = '还没有规则。加上规则后:匹配的写文件/命令免确认或直接禁止。';
    permList.appendChild(li);
    return;
  }
  for (const r of rules) {
    const li = document.createElement('li');
    const txt = document.createElement('div');
    txt.className = 'p-text';
    txt.textContent = (r.target === 'path' ? '📁 路径: ' : '⌨ 命令: ') + r.value;
    const badge = document.createElement('span');
    badge.className = 'p-badge ' + r.action;
    badge.textContent = r.action === 'allow' ? '免确认' : '禁止';
    const del = document.createElement('button');
    del.textContent = '删除';
    del.addEventListener('click', async () => {
      await fetch(apiUrl('/api/permissions/' + r.id), { method: 'DELETE' });
      loadPerms();
    });
    li.append(txt, badge, del);
    permList.appendChild(li);
  }
}

document.getElementById('permAdd').addEventListener('click', async () => {
  const target = document.getElementById('permTarget').value;
  const value = document.getElementById('permValue').value.trim();
  const action = document.getElementById('permAction').value;
  if (!value) return;
  await fetch(apiUrl('/api/permissions'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target, value, action }),
  });
  document.getElementById('permValue').value = '';
  loadPerms();
});

tabs.forEach((b) => b.addEventListener('click', () => {
  tabs.forEach((x) => x.classList.remove('active'));
  b.classList.add('active');
  curScope = b.dataset.scope;
  if (curScope === 'perm') {
    memList.hidden = true;
    permSection.hidden = false;
    loadPerms();
  } else {
    memList.hidden = false;
    permSection.hidden = true;
    loadMemories();
  }
}));

memBtn.addEventListener('click', () => {
  memPanel.hidden = false;
  loadMemories();
});
memClose.addEventListener('click', () => { memPanel.hidden = true; });

// ---- 后台任务中心 ----
const taskBtn = document.getElementById('taskBtn');
const taskPanel = document.getElementById('taskPanel');
const taskClose = document.getElementById('taskClose');
const taskList = document.getElementById('taskList');
const newTaskBtn = document.getElementById('newTaskBtn');
const taskModal = document.getElementById('taskModal');
const taskMsg = document.getElementById('taskMsg');
const taskAllowWrite = document.getElementById('taskAllowWrite');
const taskStart = document.getElementById('taskStart');
const taskCancel = document.getElementById('taskCancel');
const taskX = document.getElementById('taskX');

let taskPoll = null;
let lastStatuses = {};
let lastItemsJson = '';

async function loadTasks() {
  const res = await fetch(apiUrl('/api/tasks'));
  const items = await res.json();
  // 数据没变就不重绘,避免滚动位置被重置回顶部
  const json = JSON.stringify(items);
  if (json === lastItemsJson) return;
  lastItemsJson = json;
  const keepScroll = taskList.scrollTop;
  taskList.innerHTML = '';
  if (!items.length) {
    const li = document.createElement('li');
    li.textContent = '还没有后台任务。点「＋新建」把大活交给蓝蓝慢慢干。';
    taskList.appendChild(li);
    return;
  }
  for (const t of items) {
    if (lastStatuses[t.id] === 'running' && t.status !== 'running') {
      // 任务刚完成:振动 + 提示音
      try { if (navigator.vibrate) navigator.vibrate(300); } catch (e) {}
      try {
        const ac = new (window.AudioContext || window.webkitAudioContext)();
        const o = ac.createOscillator(); const g = ac.createGain();
        o.connect(g); g.connect(ac.destination);
        g.gain.value = 0.08; o.frequency.value = 880;
        o.start(); o.stop(ac.currentTime + 0.35);
      } catch (e) {}
    }
    lastStatuses[t.id] = t.status;
    const li = document.createElement('li');
    const msg = document.createElement('div');
    msg.className = 't-msg';
    msg.textContent = t.message;
    const meta = document.createElement('div');
    meta.className = 't-meta';
    const badge = document.createElement('span');
    badge.className = 't-badge ' + t.status;
    badge.textContent = { running: '执行中…', done: '已完成', failed: '失败' }[t.status] || t.status;
    meta.append(badge, document.createTextNode(t.created + (t.finished ? ' → ' + t.finished : '')));
    li.append(msg, meta);
    if (t.result) {
      const r = document.createElement('div');
      r.className = 't-result';
      r.textContent = t.result.slice(0, 150) + (t.result.length > 150 ? '…(点击查看全文)' : '');
      li.appendChild(r);
    }
    // 点任务卡片看完整结果
    li.addEventListener('click', () => {
      document.getElementById('taskDetailTitle').textContent = t.message;
      document.getElementById('taskDetailResult').textContent =
        '状态: ' + ({ running: '执行中…', done: '已完成', failed: '失败' }[t.status] || t.status) +
        '\n时间: ' + t.created + (t.finished ? ' → ' + t.finished : '') +
        '\n\n' + (t.result || '(还没有结果)');
      document.getElementById('taskDetailModal').hidden = false;
    });
    taskList.appendChild(li);
  }
  taskList.scrollTop = keepScroll;
}

const taskDetailModal = document.getElementById('taskDetailModal');
document.getElementById('taskDetailX').addEventListener('click', () => { taskDetailModal.hidden = true; });
taskDetailModal.addEventListener('click', (e) => {
  if (e.target === taskDetailModal) taskDetailModal.hidden = true;
});

// ---- 定时任务 ----
const newSchedBtn = document.getElementById('newSchedBtn');
const schedModal = document.getElementById('schedModal');
const schedMsg = document.getElementById('schedMsg');
const schedKind = document.getElementById('schedKind');
const schedAt = document.getElementById('schedAt');
const schedUnit = document.getElementById('schedUnit');
const schedAllowWrite = document.getElementById('schedAllowWrite');
const schedStart = document.getElementById('schedStart');
const schedCancel = document.getElementById('schedCancel');
const schedX = document.getElementById('schedX');
const schedList = document.getElementById('schedList');
const auditList = document.getElementById('auditList');

async function loadScheds() {
  const res = await fetch(apiUrl('/api/schedule'));
  const items = await res.json();
  schedList.innerHTML = '';
  if (!items.length) {
    const li = document.createElement('li');
    li.textContent = '没有定时任务。';
    li.style.color = 'var(--muted)';
    schedList.appendChild(li);
    return;
  }
  for (const it of items) {
    const li = document.createElement('li');
    const txt = document.createElement('div');
    txt.className = 's-text';
    txt.textContent = (it.kind === 'daily' ? '每天 ' + it.at + ' 点 · ' : '每 ' + it.minutes + ' 分钟 · ')
      + it.message + (it.last_run ? '(上次 ' + it.last_run + ')' : '(还没跑过)');
    const del = document.createElement('button');
    del.className = 's-del';
    del.textContent = '删除';
    del.addEventListener('click', async () => {
      await fetch(apiUrl('/api/schedule/' + it.id), { method: 'DELETE' });
      loadScheds();
    });
    li.append(txt, del);
    schedList.appendChild(li);
  }
}

async function loadAudit() {
  const res = await fetch(apiUrl('/api/audit?limit=30'));
  const items = await res.json();
  auditList.innerHTML = '';
  if (!items.length) {
    const li = document.createElement('li');
    li.textContent = '(暂无记录)';
    auditList.appendChild(li);
    return;
  }
  for (const a of items) {
    const li = document.createElement('li');
    const b = document.createElement('b');
    b.textContent = '[' + a.time + '] ' + a.kind + ' ';
    li.append(b, document.createTextNode(a.detail));
    auditList.appendChild(li);
  }
}

function refreshPanels() {
  loadTasks();
  loadScheds();
  loadAudit();
}

newSchedBtn.addEventListener('click', () => {
  schedModal.hidden = false;
  schedMsg.value = '';
  schedKind.value = 'daily';
  schedAt.value = '';
  schedUnit.textContent = '点';
});
schedKind.addEventListener('change', () => {
  schedAt.placeholder = schedKind.value === 'daily' ? '09:00' : '分钟数';
  schedUnit.textContent = schedKind.value === 'daily' ? '点' : '分钟';
});
schedCancel.addEventListener('click', () => { schedModal.hidden = true; });
schedX.addEventListener('click', () => { schedModal.hidden = true; });
schedModal.addEventListener('click', (e) => {
  if (e.target === schedModal) schedModal.hidden = true;
});
schedStart.addEventListener('click', async () => {
  const text = schedMsg.value.trim();
  if (!text) return;
  const kind = schedKind.value;
  const at = schedAt.value.trim();
  if (kind === 'daily' && !/^\d{1,2}:\d{2}$/.test(at)) {
    addMsg('assistant', '时间格式不对,写成像 09:00 这样');
    return;
  }
  if (kind === 'interval' && !/^\d+$/.test(at)) {
    addMsg('assistant', '间隔要写数字(分钟)');
    return;
  }
  schedModal.hidden = true;
  try {
    await fetch(apiUrl('/api/schedule'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind,
        at: kind === 'daily' ? at : '',
        minutes: kind === 'interval' ? parseInt(at) : 0,
        message: text,
        allow_write: schedAllowWrite.checked,
      }),
    });
    taskPanel.hidden = false;
    refreshPanels();
    addMsg('assistant', '定时任务安排好了~ 到点我会自己干,结果在任务中心(⏳)里。');
  } catch (e) {
    addMsg('assistant', '网络出错了:' + e.message);
  }
});

taskBtn.addEventListener('click', () => {
  taskPanel.hidden = false;
  refreshPanels();
  clearInterval(taskPoll);
  taskPoll = setInterval(refreshPanels, 4000);
});
taskClose.addEventListener('click', () => {
  taskPanel.hidden = true;
  clearInterval(taskPoll);
});
newTaskBtn.addEventListener('click', () => {
  taskModal.hidden = false;
  taskMsg.value = '';
  taskAllowWrite.checked = false;
});
taskCancel.addEventListener('click', () => { taskModal.hidden = true; });
taskX.addEventListener('click', () => { taskModal.hidden = true; });
// 点弹窗外面也能关
taskModal.addEventListener('click', (e) => {
  if (e.target === taskModal) taskModal.hidden = true;
});
taskStart.addEventListener('click', async () => {
  const text = taskMsg.value.trim();
  if (!text) return;
  taskModal.hidden = true;
  try {
    const res = await fetch(apiUrl('/api/task'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: sessionId, allow_write: taskAllowWrite.checked }),
    });
    const r = await res.json();
    if (r.ok) {
      taskPanel.hidden = false;
      loadTasks();
      clearInterval(taskPoll);
      taskPoll = setInterval(loadTasks, 4000);
      addMsg('assistant', '收到~ 我把「' + text.slice(0, 30) + (text.length > 30 ? '…' : '') + '」放到后台慢慢做,做完了在任务中心(⏳)看结果。');
    }
  } catch (e) {
    addMsg('assistant', '网络出错了:' + e.message);
  }
});

// ---- 聊天记录 ----
const histBtn = document.getElementById('histBtn');
const histPanel = document.getElementById('histPanel');
const histClose = document.getElementById('histClose');
const histList = document.getElementById('histList');

async function loadHistory() {
  const res = await fetch(apiUrl('/api/sessions'));
  const items = await res.json();
  histList.innerHTML = '';
  if (!items.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = '还没有聊天记录。';
    histList.appendChild(li);
    return;
  }
  for (const it of items) {
    const li = document.createElement('li');
    li.className = 'hist-item';
    const title = document.createElement('div');
    title.className = 'hist-title';
    title.textContent = it.title;
    const meta = document.createElement('div');
    meta.className = 'hist-meta';
    meta.textContent = it.updated + ' · ' + it.count + ' 条消息' + (it.id === sessionId ? ' · 当前' : '');
    li.append(title, meta);
    li.addEventListener('click', async () => {
      histPanel.hidden = true;
      rememberSid(it.id);
      chatEl.innerHTML = '';
      setStatus('加载聊天记录…');
      try {
        const r = await fetch(apiUrl('/api/session/' + it.id + '/messages'));
        const msgs = await r.json();
        if (!msgs.length) {
          addMsg('assistant', GREETING);
        }
        for (const m of msgs) {
          addMsg(m.role === 'user' ? 'user' : 'assistant', m.content);
        }
      } catch (e) {
        addMsg('assistant', '加载失败:' + e.message);
      }
      setStatus('');
    });
    histList.appendChild(li);
  }
}

histBtn.addEventListener('click', () => {
  histPanel.hidden = false;
  loadHistory();
});
histClose.addEventListener('click', () => { histPanel.hidden = true; });

// ---- 启动:有上次的会话就恢复显示,否则问候 ----
(async function initChat() {
  try {
    const res = await fetch(apiUrl('/api/session/' + sessionId + '/messages'));
    if (res.ok) {
      const msgs = await res.json();
      if (msgs.length) {
        for (const m of msgs) {
          addMsg(m.role === 'user' ? 'user' : 'assistant', m.content);
        }
        return;
      }
    }
  } catch (e) { /* 忽略,走问候 */ }
  addMsg('assistant', GREETING);
})();
