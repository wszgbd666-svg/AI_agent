/* ============================================================
 * 主程序：应用状态、界面交互、各模块联动
 * ============================================================ */

(function () {
  const STATE_KEY = 'doorwin-state';
  const STATE_VER = '2026-09-29-v3'; // 数据格式版本：升级后旧数据自动作废

  /* ---- 默认状态 ---- */
  const defaultState = {
    styleId: 'win-casement-2',
    w: 1500, h: 1500,
    series: 'aluminum',
    frameColor: '#f2f2ee',
    glass: 'insulated',
    screen: false,
    angle: 0,
    scene: 'indoor',
    view: '3d',
  };

  let state = loadState();
  let lastViewTab = '3d';

  function loadState() {
    try {
      const raw = localStorage.getItem(STATE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        if (saved.__v === STATE_VER) {
          return Object.assign({}, defaultState, saved);
        }
      }
      // 旧版本数据：连带清理降级模式等遗留标记
      localStorage.removeItem('doorwin-nogl');
      localStorage.removeItem('doorwin-3d-attempt');
    } catch (e) { /* ignore */ }
    return Object.assign({}, defaultState);
  }

  let persistTimer = null;
  function persist() {
    clearTimeout(persistTimer);
    persistTimer = setTimeout(() => {
      try {
        state.__v = STATE_VER;
        localStorage.setItem(STATE_KEY, JSON.stringify(state));
      } catch (e) { /* ignore */ }
    }, 400);
  }

  const $ = id => document.getElementById(id);
  const style = () => Models.getStyleById(state.styleId);

  /* ---------- Toast ---------- */
  let toastTimer = null;
  function toast(msg) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2000);
  }

  /* ---------- 款式条 ---------- */
  function renderStyleStrip() {
    const strip = $('style-strip');
    strip.innerHTML = '';
    const all = STYLE_LIBRARY.concat(CUSTOM_STYLES.filter(s => !s._draft));
    all.forEach(s => {
      const chip = document.createElement('button');
      chip.className = 'style-chip' + (s.id === state.styleId ? ' active' : '');
      const isCustom = s.custom;
      chip.textContent = (isCustom ? '✏️ ' : (s.cat === '门' ? '🚪 ' : '🪟 ')) + s.name;
      chip.addEventListener('click', () => {
        state.styleId = s.id;
        const sz = s.size || { w: s.w, h: s.h };
        state.w = sz.w; state.h = sz.h;
        state.angle = 0;
        state.frameThick = s.frameThick || 60;
        applySizeToSliders();
        update();
        renderStyleStrip();
        toast('已切换：' + s.name);
        strip.scrollTo({ left: chip.offsetLeft - strip.clientWidth / 2, behavior: 'smooth' });
      });
      strip.appendChild(chip);
    });
  }

  function bindDesignerEntry() {
    const btn = $('btn-designer');
    if (btn) btn.addEventListener('click', () => Designer.open());
  }

  /* ---------- 尺寸滑杆范围按门/窗调整 ---------- */
  function applySizeToSliders() {
    const isDoor = style().cat === '门';
    const wInput = $('param-width'), hInput = $('param-height');
    wInput.min = isDoor ? 600 : 400; wInput.max = isDoor ? 3600 : 4000;
    hInput.min = isDoor ? 1800 : 400; hInput.max = isDoor ? 3000 : 2400;
    state.w = Math.min(Math.max(state.w, +wInput.min), +wInput.max);
    state.h = Math.min(Math.max(state.h, +hInput.min), +hInput.max);
    wInput.value = state.w; hInput.value = state.h;
    $('width-val').textContent = state.w;
    $('height-val').textContent = state.h;
  }

  /* ---------- 参数面板内容 ---------- */
  function renderSeriesChips() {
    const row = $('series-chips');
    row.innerHTML = '';
    FRAME_SERIES.forEach(sr => {
      const chip = document.createElement('button');
      chip.className = 'chip' + (sr.id === state.series ? ' active' : '');
      chip.textContent = sr.name + ' ¥' + Quote.getPrices().series[sr.id] + '/㎡';
      chip.addEventListener('click', () => {
        state.series = sr.id;
        update(); renderSeriesChips();
      });
      row.appendChild(chip);
    });
  }

  function renderColorSwatches() {
    const row = $('color-swatches');
    row.innerHTML = '';
    FRAME_COLORS.forEach(c => {
      const sw = document.createElement('button');
      sw.className = 'swatch' + (c.hex === state.frameColor ? ' active' : '');
      sw.style.background = c.hex;
      sw.title = c.name;
      sw.addEventListener('click', () => {
        state.frameColor = c.hex;
        $('custom-color').value = c.hex;
        update(); renderColorSwatches();
      });
      row.appendChild(sw);
    });
  }

  function renderGlassChips() {
    const row = $('glass-chips');
    row.innerHTML = '';
    GLASS_TYPES.forEach(g => {
      const chip = document.createElement('button');
      chip.className = 'chip' + (g.id === state.glass ? ' active' : '');
      chip.textContent = g.name + (g.price ? ' +¥' + g.price + '/㎡' : '');
      chip.addEventListener('click', () => {
        state.glass = g.id;
        update(); renderGlassChips();
      });
      row.appendChild(chip);
    });
  }

  function renderSceneChips() {
    const row = $('scene-chips');
    row.innerHTML = '';
    SCENES.forEach(sc => {
      const chip = document.createElement('button');
      chip.className = 'chip' + (sc.id === state.scene ? ' active' : '');
      chip.textContent = sc.name;
      chip.addEventListener('click', () => {
        state.scene = sc.id;
        update(); renderSceneChips(); updateSceneUI();
      });
      row.appendChild(chip);
    });
  }

  function updateSceneUI() {
    $('btn-scene').textContent = state.scene === 'outdoor' ? '🌆' : '🏠';
    $('scene-label').textContent = state.scene === 'outdoor' ? '室外立面' : '室内场景';
  }

  function renderParams() {
    $('param-width').value = state.w;
    $('param-height').value = state.h;
    $('param-angle').value = state.angle;
    $('param-screen').checked = state.screen;
    $('custom-color').value = state.frameColor;
    $('width-val').textContent = state.w;
    $('height-val').textContent = state.h;
    $('angle-val').textContent = state.angle;
    renderSeriesChips();
    renderColorSwatches();
    renderGlassChips();
    renderSceneChips();
  }

  /* ---------- 报价面板 ---------- */
  function renderQuote() {
    const q = Quote.calc(state);
    const tbody = $('quote-table').querySelector('tbody');
    tbody.innerHTML = '';
    q.items.forEach(it => {
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + it.name + '<div class="sub">' + it.detail + '</div></td>' +
        '<td class="num">' + it.qty + '</td>' +
        '<td class="num">¥' + Quote.fmtMoney(it.price) + '</td>' +
        '<td class="num">¥' + Quote.fmtMoney(it.amount) + '</td>';
      tbody.appendChild(tr);
    });
    $('quote-total').textContent = '¥' + Quote.fmtMoney(q.total);
  }

  /* ---------- 价格设置 ---------- */
  function renderSettings() {
    const p = Quote.getPrices();
    const form = $('settings-form');
    form.innerHTML = '';
    const groups = [
      ['型材系列（元/㎡）', 'series', FRAME_SERIES.map(sr => ({ key: sr.id, label: sr.name }))],
      ['玻璃加价（元/㎡）', 'glass', GLASS_TYPES.map(g => ({ key: g.id, label: g.name }))],
      ['零件加价（元/㎡）', 'parts', Object.keys(PART_PRICES).map(k => ({ key: k, label: PART_TYPES[k] ? PART_TYPES[k].name : k }))],
    ];
    groups.forEach(([title, groupKey, entries]) => {
      const gDiv = document.createElement('div');
      gDiv.className = 'setting-group';
      gDiv.textContent = title;
      form.appendChild(gDiv);
      entries.forEach(e => {
        const row = document.createElement('div');
        row.className = 'setting-row';
        row.innerHTML = '<span>' + e.label + '</span>';
        const input = document.createElement('input');
        input.type = 'number';
        input.value = p[groupKey][e.key];
        input.addEventListener('change', () => {
          const v = parseFloat(input.value);
          if (!isNaN(v) && v >= 0) {
            p[groupKey][e.key] = v;
            Quote.setPrices(p);
            toast('已保存价格');
            renderQuote(); renderSeriesChips(); renderGlassChips();
          }
        });
        row.appendChild(input);
        form.appendChild(row);
      });
    });
    const extra = [
      ['screen', '纱窗（元/樘）'],
      ['hardware.window', '窗五金（元/樘）'],
      ['hardware.door', '门五金（元/樘）'],
      ['install', '安装运输（元/樘）'],
    ];
    const gDiv = document.createElement('div');
    gDiv.className = 'setting-group';
    gDiv.textContent = '其他（元/樘）';
    form.appendChild(gDiv);
    extra.forEach(([path, label]) => {
      const row = document.createElement('div');
      row.className = 'setting-row';
      row.innerHTML = '<span>' + label + '</span>';
      const input = document.createElement('input');
      input.type = 'number';
      const [g, k] = path.split('.');
      input.value = g === 'hardware' ? p.hardware[k] : p[g];
      input.addEventListener('change', () => {
        const v = parseFloat(input.value);
        if (!isNaN(v) && v >= 0) {
          if (g === 'hardware') p.hardware[k] = v; else p[g] = v;
          Quote.setPrices(p);
          toast('已保存价格');
          renderQuote();
        }
      });
      row.appendChild(input);
      form.appendChild(row);
    });
  }

  /* ---------- 视图切换 ---------- */
  function setView(view) {
    state.view = view;
    lastViewTab = view;
    const is3d = view === '3d';
    $('view3d').style.display = is3d ? '' : 'none';
    $('view2d').hidden = is3d;
    SceneManager.setActive(is3d);
    if (!is3d) Drawing.setState(state);
    document.querySelectorAll('.tab[data-tab]').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === view));
    persist();
  }

  /* ---------- 抽屉面板 ---------- */
  function openSheet(id) {
    $('params-sheet').classList.toggle('open', id === 'params-sheet');
    $('quote-sheet').classList.toggle('open', id === 'quote-sheet');
    $('settings-sheet').classList.toggle('open', id === 'settings-sheet');
    if (id === 'quote-sheet') renderQuote();
    if (id === 'settings-sheet') renderSettings();
  }
  function closeSheets() {
    $('params-sheet').classList.remove('open');
    $('quote-sheet').classList.remove('open');
    $('settings-sheet').classList.remove('open');
  }

  /* ---------- 核心更新 ---------- */
  function update() {
    $('area-badge').textContent = (state.w * state.h / 1e6).toFixed(2) + ' ㎡';
    $('dims-info').innerHTML =
      '宽 <b>' + state.w + '</b> mm · 高 <b>' + state.h + '</b> mm · ' +
      '型材厚 <b>' + (state.frameThick || 60) + '</b> mm · 墙厚 <b>240</b> mm';
    SceneManager.setState(state);
    Drawing.setState(state);
    renderQuote();
    persist();
  }

  /* ============================================================
   * 自建设计器：零件工具箱拼装 + 参数调整 + 实时预览
   * 草稿以 _draft 标记临时挂到 CUSTOM_STYLES，让 3D/2D/报价引擎
   * 通过 getStyleById 直接看到草稿，实现实时联动预览。
   * ============================================================ */
  const Designer = (function () {
    let draft = null;       // 当前草稿款式
    let prevStyleId = null; // 进入设计器前的款式
    let prevScreen = false; // 进入设计器前的纱窗设置
    let editing = null;     // 正在编辑的格子 {r, c}

    function deepCopy(o) { return JSON.parse(JSON.stringify(o)); }

    function open(loadId) {
      prevStyleId = state.styleId;
      prevScreen = state.screen;
      const base = loadId ? getStyleById(loadId) : getStyleById(state.styleId);
      draft = deepCopy(base);
      draft.id = 'draft-' + Date.now();
      draft.custom = true;
      draft._draft = true;
      if (draft.size) { draft.w = draft.size.w; draft.h = draft.size.h; delete draft.size; }
      if (!draft.frameThick) draft.frameThick = 60;
      if (!draft.cells || !draft.cells.length) {
        draft.rows = 1; draft.cols = 2; draft.cells = [];
        for (let c = 0; c < 2; c++) draft.cells.push({ r: 0, c, type: 'fixed' });
      }
      CUSTOM_STYLES = CUSTOM_STYLES.filter(s => !s._draft);
      CUSTOM_STYLES.push(draft);

      // 主状态切到草稿 → 全链路实时预览
      state.styleId = draft.id;
      state.w = draft.w; state.h = draft.h;
      state.screen = !!draft.screen;
      state.frameThick = draft.frameThick;
      applySizeToSliders();
      update();
      renderStyleStrip();

      editing = null;
      renderAll();
      $('designer-sheet').classList.add('open');
    }

    function close() {
      // 丢弃草稿，恢复之前的款式
      CUSTOM_STYLES = CUSTOM_STYLES.filter(s => s.id !== (draft ? draft.id : ''));
      state.styleId = prevStyleId || STYLE_LIBRARY[0].id;
      const st = getStyleById(state.styleId);
      const sz = st.size || { w: st.w, h: st.h };
      state.w = sz.w; state.h = sz.h;
      state.frameThick = st.frameThick || 60;
      state.screen = prevScreen;
      applySizeToSliders();
      update();
      renderStyleStrip();
      draft = null;
      $('designer-sheet').classList.remove('open');
    }

    /* 当前草稿同步进主状态并刷新预览 */
    function sync() {
      state.styleId = draft.id;
      state.w = draft.w; state.h = draft.h;
      state.screen = !!draft.screen;
      state.frameThick = draft.frameThick;
      applySizeToSliders();
      update();
    }

    /* 调整分格：保留已有格子的设置 */
    function resizeCells(rows, cols) {
      const old = {};
      draft.cells.forEach(c => { old[c.r + '-' + c.c] = c; });
      draft.rows = rows; draft.cols = cols;
      const cells = [];
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          cells.push(old[r + '-' + c] ? deepCopy(old[r + '-' + c]) : { r, c, type: 'fixed' });
        }
      }
      draft.cells = cells;
    }

    function cellAt(r, c) {
      return draft.cells.find(cl => cl.r === r && cl.c === c);
    }

    function renderAll() {
      if (!draft) return;
      $('d-name').value = draft.name || '';
      $('d-width').value = draft.w; $('d-width-val').textContent = draft.w;
      $('d-height').value = draft.h; $('d-height-val').textContent = draft.h;
      $('d-thick').value = draft.frameThick; $('d-thick-val').textContent = draft.frameThick;
      $('d-screen').checked = !!draft.screen;
      $('d-rows-val').textContent = draft.rows;
      $('d-cols-val').textContent = draft.cols;
      renderCatChips();
      renderGrid();
      renderMyList();
    }

    function renderCatChips() {
      const row = $('d-cat-chips');
      row.innerHTML = '';
      ['窗', '门'].forEach(cat => {
        const chip = document.createElement('button');
        chip.className = 'chip' + (draft.cat === cat ? ' active' : '');
        chip.textContent = cat === '门' ? '🚪 门' : '🪟 窗';
        chip.addEventListener('click', () => {
          draft.cat = cat;
          draft.sill = cat === '门' ? 0 : 900;
          sync(); renderCatChips(); renderMyList();
        });
        row.appendChild(chip);
      });
    }

    const CELL_ICONS = {
      fixed: '🪟', casement: '🔓', 'top-hung': '⬆️', 'bottom-hung': '⬇️', 'tilt-turn': '🔀',
      slide: '↔️', fold: '🪗', 'hinge-door': '🚪', 'slide-door': '🚪',
      louver: '🪜', 'sealed-louver': '🧊', grille: '🪈', 'glass-grille': '🔲',
      lattice: '❎', security: '🛡️', solid: '⬛',
    };
    function partShortName(type) {
      const n = (PART_TYPES[type] || {}).name || '固定';
      return n.length > 4 ? n.slice(0, 2) + '…' : n;
    }

    function renderGrid() {
      const grid = $('designer-grid');
      grid.style.gridTemplateColumns = 'repeat(' + draft.cols + ', 1fr)';
      grid.innerHTML = '';
      for (let r = 0; r < draft.rows; r++) {
        for (let c = 0; c < draft.cols; c++) {
          const cell = cellAt(r, c);
          const btn = document.createElement('button');
          btn.className = 'designer-cell' + (editing && editing.r === r && editing.c === c ? ' active' : '');
          btn.innerHTML = '<span class="cell-ico">' + (CELL_ICONS[cell.type] || '🪟') + '</span>' +
            '<span>' + partShortName(cell.type) + '</span>';
          btn.addEventListener('click', () => {
            editing = { r, c };
            renderGrid();
            renderPartEditor();
            $('d-part-section').hidden = false;
            $('d-part-section').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          });
          grid.appendChild(btn);
        }
      }
    }

    function renderPartEditor() {
      if (!editing) return;
      const cell = cellAt(editing.r, editing.c);
      $('d-part-title').textContent = '编辑格子：第' + (editing.r + 1) + '行 第' + (editing.c + 1) + '列';

      // 零件选择（按组）
      const chips = $('d-part-chips');
      chips.innerHTML = '';
      const groups = ['开启', '面板'];
      groups.forEach(g => {
        const label = document.createElement('div');
        label.className = 'part-group-label';
        label.textContent = g === '开启' ? '开启方式' : '面板 / 装饰';
        chips.appendChild(label);
        const wrap = document.createElement('div');
        wrap.className = 'chip-row';
        Object.keys(PART_TYPES).forEach(type => {
          if (PART_TYPES[type].group !== g) return;
          const chip = document.createElement('button');
          chip.className = 'part-chip' + (cell.type === type ? ' active' : '');
          chip.textContent = (CELL_ICONS[type] || '') + ' ' + PART_TYPES[type].name;
          chip.addEventListener('click', () => {
            cell.type = type;
            const def = {};
            PART_TYPES[type].params.forEach(p => { def[p.key] = p.def; });
            cell.params = def;
            sync(); renderGrid(); renderPartEditor();
          });
          wrap.appendChild(chip);
        });
        chips.appendChild(wrap);
      });

      // 参数控件
      const controls = $('d-param-controls');
      controls.innerHTML = '';
      const pdefs = PART_TYPES[cell.type].params;
      if (!pdefs.length) {
        controls.innerHTML = '<p class="settings-tip">该零件没有可调参数</p>';
        return;
      }
      cell.params = cell.params || {};
      pdefs.forEach(pdef => {
        const val = cell.params[pdef.key] !== undefined ? cell.params[pdef.key] : pdef.def;
        if (pdef.type === 'range') {
          const wrap = document.createElement('div');
          wrap.className = 'slider-row';
          const labelText = {
            angle: '叶片角度', spacing: '叶片间距', bladeW: '叶片宽度',
            thick: '型材厚度', count: '数量', foldAngle: '折叠角度',
          }[pdef.key] || pdef.key;
          wrap.innerHTML = '<label>' + labelText + ' <span class="val">' + val + '</span>' +
            (pdef.key === 'spacing' || pdef.key === 'bladeW' || pdef.key === 'thick' ? ' mm' :
             pdef.key === 'angle' || pdef.key === 'foldAngle' ? '°' : '') + '</label>';
          const input = document.createElement('input');
          input.type = 'range';
          input.min = pdef.min; input.max = pdef.max; input.step = pdef.step;
          input.value = val;
          input.addEventListener('input', () => {
            cell.params[pdef.key] = +input.value;
            input.previousElementSibling.querySelector('.val').textContent = input.value;
            sync();
          });
          wrap.appendChild(input);
          controls.appendChild(wrap);
        } else if (pdef.type === 'select') {
          const wrap = document.createElement('div');
          wrap.className = 'chip-row';
          wrap.style.marginBottom = '10px';
          pdef.options.forEach((opt, i) => {
            const chip = document.createElement('button');
            chip.className = 'part-chip' + (val === opt ? ' active' : '');
            chip.textContent = pdef.labels ? pdef.labels[i] : opt;
            chip.addEventListener('click', () => {
              cell.params[pdef.key] = opt;
              sync();
              renderPartEditor();
            });
            wrap.appendChild(chip);
          });
          controls.appendChild(wrap);
        }
      });
    }

    function renderMyList() {
      const list = $('d-mylist');
      list.innerHTML = '';
      const mine = CUSTOM_STYLES.filter(s => !s._draft);
      if (!mine.length) {
        list.innerHTML = '<p class="settings-tip">还没有保存的款式</p>';
        return;
      }
      mine.forEach(s => {
        const row = document.createElement('div');
        row.className = 'mystyle-row';
        row.innerHTML = '<span class="ms-name">✏️ ' + s.name + ' <span class="sub">' +
          (s.w + '×' + s.h + ' · ' + s.rows + '行' + s.cols + '列') + '</span></span>';
        const btns = document.createElement('div');
        btns.className = 'ms-btns';
        const loadBtn = document.createElement('button');
        loadBtn.className = 'ms-btn';
        loadBtn.textContent = '载入';
        loadBtn.addEventListener('click', () => {
          // 以自建款为基础继续编辑
          CUSTOM_STYLES = CUSTOM_STYLES.filter(x => !x._draft);
          draft = deepCopy(s);
          draft._draft = true;
          CUSTOM_STYLES.push(draft);
          editing = null;
          sync(); renderStyleStrip(); renderAll();
          $('d-part-section').hidden = true;
          toast('已载入：' + s.name);
        });
        const delBtn = document.createElement('button');
        delBtn.className = 'ms-btn del';
        delBtn.textContent = '删除';
        delBtn.addEventListener('click', () => {
          if (!confirm('确定删除「' + s.name + '」？')) return;
          removeCustomStyle(s.id);
          if (state.styleId === s.id) {
            state.styleId = STYLE_LIBRARY[0].id;
            state.w = STYLE_LIBRARY[0].size.w; state.h = STYLE_LIBRARY[0].size.h;
            state.frameThick = 60;
            applySizeToSliders();
            update();
          }
          renderStyleStrip(); renderMyList();
          toast('已删除');
        });
        btns.appendChild(loadBtn);
        btns.appendChild(delBtn);
        row.appendChild(btns);
        list.appendChild(row);
      });
    }

    function save() {
      if (!draft) return;
      draft.name = ($('d-name').value || '').trim() || '自建款式';
      draft.custom = true;
      delete draft._draft;
      draft.id = 'custom-' + Date.now();
      draft.sill = draft.cat === '门' ? 0 : 900;
      addCustomStyle(draft);
      state.styleId = draft.id;
      draft = null;
      update();
      renderStyleStrip();
      $('designer-sheet').classList.remove('open');
      toast('✅ 已保存款式，出现在款式条');
    }

    function bind() {
      $('btn-close-designer').addEventListener('click', close);
      $('d-cancel').addEventListener('click', close);
      $('d-save').addEventListener('click', save);
      $('d-part-done').addEventListener('click', () => { $('d-part-section').hidden = true; });
      $('d-name').addEventListener('input', e => { draft.name = e.target.value; });
      $('d-width').addEventListener('input', e => {
        draft.w = +e.target.value;
        $('d-width-val').textContent = draft.w;
        sync(); renderMyList();
      });
      $('d-height').addEventListener('input', e => {
        draft.h = +e.target.value;
        $('d-height-val').textContent = draft.h;
        sync(); renderMyList();
      });
      $('d-thick').addEventListener('input', e => {
        draft.frameThick = +e.target.value;
        $('d-thick-val').textContent = draft.frameThick;
        sync();
      });
      $('d-screen').addEventListener('change', e => {
        draft.screen = e.target.checked;
        sync();
      });
      document.querySelectorAll('.stepper-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const step = btn.dataset.step;
          const dir = +btn.dataset.dir;
          const max = step === 'rows' ? 4 : 4;
          const cur = draft[step];
          const next = Math.min(max, Math.max(1, cur + dir));
          if (next === cur) return;
          resizeCells(step === 'rows' ? next : draft.rows, step === 'cols' ? next : draft.cols);
          if (editing && (editing.r >= draft.rows || editing.c >= draft.cols)) editing = null;
          $('d-rows-val').textContent = draft.rows;
          $('d-cols-val').textContent = draft.cols;
          sync(); renderGrid(); renderMyList();
        });
      });
    }

    return { open, close, bind };
  })();

  /* ---------- 事件绑定 ---------- */
  function bindEvents() {
    // 底部导航
    document.querySelectorAll('.tab[data-tab]').forEach(tab => {
      tab.addEventListener('click', () => {
        const t = tab.dataset.tab;
        if (t === 'params') { openSheet('params-sheet'); return; }
        if (t === 'quote') { openSheet('quote-sheet'); return; }
        closeSheets();
        setView(t);
      });
    });

    $('btn-close-params').addEventListener('click', closeSheets);
    $('btn-close-quote').addEventListener('click', closeSheets);
    $('btn-close-settings').addEventListener('click', closeSheets);
    $('btn-settings').addEventListener('click', () => openSheet('settings-sheet'));

    // 尺寸/角度滑杆
    $('param-width').addEventListener('input', e => {
      state.w = +e.target.value;
      $('width-val').textContent = state.w;
      update();
    });
    $('param-height').addEventListener('input', e => {
      state.h = +e.target.value;
      $('height-val').textContent = state.h;
      update();
    });
    $('param-angle').addEventListener('input', e => {
      state.angle = +e.target.value;
      $('angle-val').textContent = state.angle;
      update();
    });

    // 纱窗
    $('param-screen').addEventListener('change', e => {
      state.screen = e.target.checked;
      update();
    });

    // 自定义颜色
    $('custom-color').addEventListener('input', e => {
      state.frameColor = e.target.value;
      update(); renderColorSwatches();
    });

    // 舞台按钮
    $('btn-scene').addEventListener('click', () => {
      state.scene = state.scene === 'indoor' ? 'outdoor' : 'indoor';
      update(); renderSceneChips(); updateSceneUI();
      toast(state.scene === 'outdoor' ? '已切换：室外立面' : '已切换：室内场景');
    });
    $('btn-reset-view').addEventListener('click', () => {
      SceneManager.requestFit();
      toast('视角已重置');
    });
    $('btn-export').addEventListener('click', () => {
      Export.exportCurrentView(state);
    });

    // 报价按钮
    $('btn-copy-quote').addEventListener('click', () => {
      const text = Quote.toText(state, $('q-customer').value.trim(), $('q-address').value.trim());
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => toast('报价已复制'));
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        toast('报价已复制');
      }
    });
    $('btn-export-quote').addEventListener('click', () => Export.exportQuote(state));
    $('btn-print-quote').addEventListener('click', () => {
      const canvas = Quote.toCanvas(state, $('q-customer').value.trim(), $('q-address').value.trim());
      const win = window.open('', '_blank');
      if (!win) { toast('请允许弹出窗口后重试'); return; }
      win.document.write(
        '<html><head><title>门窗报价单</title></head><body style="margin:0;display:flex;justify-content:center;">' +
        '<img src="' + canvas.toDataURL('image/png') + '" style="max-width:100%" onload="window.print()">' +
        '</body></html>');
      win.document.close();
    });

    // 价格重置
    $('btn-reset-prices').addEventListener('click', () => {
      Quote.reset();
      renderSettings();
      renderQuote(); renderSeriesChips(); renderGlassChips();
      toast('已恢复默认价格');
    });

    // 清除全部数据（恢复出厂）
    if ($('btn-reset-all')) {
      $('btn-reset-all').addEventListener('click', () => {
        if (!confirm('确定清除全部数据（自建款式/价格/设置）并恢复默认？')) return;
        try {
          localStorage.removeItem('doorwin-state');
          localStorage.removeItem('doorwin-styles');
          localStorage.removeItem('doorwin-styles-ver');
          localStorage.removeItem('doorwin-prices');
        } catch (e) { /* ignore */ }
        location.reload();
      });
    }

    // 客户信息变化 → 报价实时
    $('q-customer').addEventListener('input', renderQuote);
    $('q-address').addEventListener('input', renderQuote);

    // 窗口尺寸变化
    window.addEventListener('resize', () => SceneManager.resize());

    Designer.bind();
    bindDesignerEntry();
    Export.bind();
  }

  /* ---------- 启动屏（App 内显示进度，浏览器无效果） ---------- */
  function splash(text, hide) {
    if (window.Android && window.Android.setSplash) {
      window.Android.setSplash(text || '', !!hide);
    }
  }

  /* ---------- 2D 安全模式提示（3D 崩溃自动降级） ---------- */
  function showNoGlNotice(fromCrash) {
    const stage = $('stage');
    if (document.getElementById('nogl-notice')) return;
    const div = document.createElement('div');
    div.id = 'nogl-notice';
    div.style.cssText = 'position:absolute;left:0;top:0;right:0;bottom:0;display:flex;' +
      'flex-direction:column;align-items:center;justify-content:center;color:#fff;' +
      'font-size:14px;text-align:center;padding:30px;z-index:20;line-height:1.9;' +
      'background:radial-gradient(ellipse at 50% 30%, #1b2734 0%, #0f1722 70%)';
    div.innerHTML = '<div style="font-size:44px;margin-bottom:12px">📐</div>' +
      (fromCrash ? '<b>检测到 3D 渲染导致应用异常退出</b><br>已自动切换为 2D 模式，图纸/报价/设计功能不受影响<br><br>' : '') +
      '<b>2D 安全模式</b><br>本设备暂不支持 3D 渲染<br><br>' +
      '<button id="btn-retry-3d" style="padding:10px 26px;border-radius:22px;border:none;' +
      'background:#4ea3ff;color:#fff;font-size:14px;cursor:pointer">🔄 重试 3D</button>';
    stage.appendChild(div);
    document.getElementById('btn-retry-3d').addEventListener('click', function () {
      localStorage.removeItem('doorwin-nogl');
      location.reload();
    });
  }

  /* ---------- 启动 ---------- */
  function boot() {
    loadCustomStyles();
    bindEvents();
    renderStyleStrip();
    renderParams();
    updateSceneUI();
    update();
    splash('页面加载完成');

    // 3D 崩溃自恢复：上次启动在 3D 初始化阶段异常退出 → 本次直接进 2D 模式
    const prevCrash = localStorage.getItem('doorwin-3d-attempt') === '1';
    const noGl = localStorage.getItem('doorwin-nogl') === '1';
    if (prevCrash || noGl) {
      if (prevCrash) {
        localStorage.setItem('doorwin-nogl', '1');
        localStorage.removeItem('doorwin-3d-attempt');
      }
      requestAnimationFrame(() => requestAnimationFrame(() => {
        splash('已进入 2D 安全模式');
        Drawing.init($('view2d'));
        setView('2d');
        showNoGlNotice(!!prevCrash);
        setTimeout(() => splash('', true), 600);
      }));
      return;
    }

    // 等布局完成后初始化 3D（容器需有尺寸）
    requestAnimationFrame(() => requestAnimationFrame(() => {
      splash('正在初始化 3D 引擎…');
      localStorage.setItem('doorwin-3d-attempt', '1'); // 崩溃标记：首帧成功后才清除
      SceneManager.init($('view3d'));
      Drawing.init($('view2d'));
      setView(state.view);
      update();
      // 首帧渲染成功后清除崩溃标记并隐藏启动屏
      requestAnimationFrame(() => requestAnimationFrame(() => {
        localStorage.removeItem('doorwin-3d-attempt');
        splash('', true);
      }));
    }));

    toast('🪟 欢迎使用小贤门窗');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  /* ---------- PWA：注册离线缓存（需 https 或 localhost，局域网 http 下自动跳过；App 内无需） ---------- */
  if ('serviceWorker' in navigator && !window.Android) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').catch(function () { /* 环境不支持则忽略 */ });
    });
  }

  /* ---------- 📱 手机打开：动态生成当前地址二维码 ---------- */
  if (window.Android) $('btn-phone').style.display = 'none'; // App 内无需扫码
  $('btn-phone').addEventListener('click', function () {
    const url = location.protocol + '//' + location.host + '/';
    try {
      const q = qrcode(0, 'M');
      q.addData(url);
      q.make();
      $('phone-qr').innerHTML = q.createSvgTag({ cellSize: 5, margin: 2, scalable: true });
    } catch (e) {
      $('phone-qr').textContent = '二维码生成失败';
    }
    $('phone-url').textContent = url +
      (location.hostname === 'localhost' || location.hostname === '127.0.0.1'
        ? '（当前是电脑本机地址，手机扫不了；请双击 start.bat 启动，让页面以局域网地址打开）'
        : '');
    $('phone-modal').hidden = false;
  });
  $('btn-close-phone').addEventListener('click', function () { $('phone-modal').hidden = true; });
  $('phone-modal').addEventListener('click', function (e) {
    if (e.target.id === 'phone-modal') $('phone-modal').hidden = true;
  });
})();
