/* ============================================================
 * 报价引擎：默认价格（可在设置中修改并保存到本机）、
 * 按当前款式/尺寸自动算价、报价单文本与图片导出
 * ============================================================ */

const DEFAULT_PRICES = {
  series: { aluminum: 780, pvc: 420, 'wood-alu': 1680 },   // 元/㎡
  glass: { clear: 0, insulated: 90, lowe: 150, frosted: 60, coated: 120 }, // 元/㎡加价
  parts: Object.assign({}, PART_PRICES),                    // 零件加价 元/㎡
  screen: 180,            // 纱窗 元/樘
  hardware: { window: 260, door: 380 },  // 五金配件 元/樘
  install: 150,           // 安装运输 元/樘
};

const PRICE_KEY = 'doorwin-prices';

const Quote = (function () {
  let prices = load();

  function load() {
    try {
      const raw = localStorage.getItem(PRICE_KEY);
      if (raw) return Object.assign(deepCopy(DEFAULT_PRICES), JSON.parse(raw));
    } catch (e) { /* ignore */ }
    return deepCopy(DEFAULT_PRICES);
  }
  function deepCopy(o) { return JSON.parse(JSON.stringify(o)); }
  function save() {
    try { localStorage.setItem(PRICE_KEY, JSON.stringify(prices)); } catch (e) { /* ignore */ }
  }
  function getPrices() { return prices; }
  function reset() { prices = deepCopy(DEFAULT_PRICES); save(); }
  function setPrices(newPrices) {
    prices = Object.assign(deepCopy(DEFAULT_PRICES), newPrices);
    save();
  }

  /* 计算报价明细 */
  function calc(state) {
    const style = Models.getStyleById(state.styleId);
    const series = FRAME_SERIES.find(sr => sr.id === state.series) || FRAME_SERIES[0];
    const glass = GLASS_TYPES.find(t => t.id === state.glass) || GLASS_TYPES[0];
    const isDoor = style.cat === '门';
    const area = state.w * state.h / 1e6;

    const items = [];
    items.push({
      name: '主体型材（' + series.name + '）',
      detail: fmtDims(state.w, state.h) + ' = ' + area.toFixed(2) + '㎡ × ¥' + prices.series[series.id],
      qty: area.toFixed(2) + ' ㎡', price: prices.series[series.id], amount: area * prices.series[series.id],
    });
    const gp = prices.glass[glass.id] || 0;
    if (gp > 0) {
      items.push({
        name: '玻璃升级（' + glass.name + '）',
        detail: area.toFixed(2) + '㎡ × ¥' + gp,
        qty: area.toFixed(2) + ' ㎡', price: gp, amount: area * gp,
      });
    }
    // 零件加价：按各格零件类型汇总
    const cellCounts = {};
    style.cells.forEach(cell => {
      const t = cell.type || 'fixed';
      cellCounts[t] = (cellCounts[t] || 0) + 1;
    });
    const totalCells = style.rows * style.cols;
    Object.keys(cellCounts).forEach(t => {
      const pp = (prices.parts || {})[t] || 0;
      if (pp > 0) {
        const partArea = area * cellCounts[t] / totalCells;
        items.push({
          name: (PART_TYPES[t] ? PART_TYPES[t].name : t) + '（' + cellCounts[t] + '格）',
          detail: partArea.toFixed(2) + '㎡ × ¥' + pp,
          qty: partArea.toFixed(2) + ' ㎡', price: pp, amount: partArea * pp,
        });
      }
    });
    items.push({
      name: isDoor ? '门锁五金' : '开窗五金',
      detail: '1 樘 × ¥' + prices.hardware[isDoor ? 'door' : 'window'],
      qty: '1 樘', price: prices.hardware[isDoor ? 'door' : 'window'],
      amount: prices.hardware[isDoor ? 'door' : 'window'],
    });
    if (state.screen && !isDoor) {
      items.push({
        name: '金刚网纱窗', detail: '1 樘 × ¥' + prices.screen,
        qty: '1 樘', price: prices.screen, amount: prices.screen,
      });
    }
    items.push({
      name: '安装运输费', detail: '含打胶 · 1 樘 × ¥' + prices.install,
      qty: '1 樘', price: prices.install, amount: prices.install,
    });

    const total = items.reduce((sum, it) => sum + it.amount, 0);
    return { items, total, area, series, glass, isDoor };
  }

  function fmtDims(w, h) { return w + '×' + h + 'mm'; }

  /* 报价文本（复制用） */
  function toText(state, customer, address) {
    const q = calc(state);
    const style = Models.getStyleById(state.styleId);
    const lines = [
      '【小贤门窗报价单】',
      '型号：' + style.name,
      '洞口尺寸：' + fmtDims(state.w, state.h) + '（面积 ' + q.area.toFixed(2) + '㎡）',
      '玻璃：' + q.glass.name + '｜颜色：' + (FRAME_COLORS.find(c => c.hex === state.frameColor) || { name: '自定义' }).name,
      '-------------------------------',
    ];
    q.items.forEach(it => lines.push(it.name + '：¥' + fmtMoney(it.amount)));
    lines.push('-------------------------------');
    lines.push('合计：¥' + fmtMoney(q.total));
    if (customer) lines.push('客户：' + customer);
    if (address) lines.push('地址：' + address);
    lines.push('日期：' + new Date().toLocaleDateString('zh-CN'));
    return lines.join('\n');
  }

  /* 报价单图片 */
  function toCanvas(state, customer, address) {
    const q = calc(state);
    const style = Models.getStyleById(state.styleId);
    const colorName = (FRAME_COLORS.find(c => c.hex === state.frameColor) || { name: '自定义' }).name;

    const W = 1080;
    const rowH = 46;
    const headH = 210, footH = 150;
    const H = headH + q.items.length * rowH + footH;

    const c = document.createElement('canvas');
    c.width = W; c.height = H;
    const g = c.getContext('2d');
    g.fillStyle = '#ffffff';
    g.fillRect(0, 0, W, H);

    // 头部
    g.fillStyle = '#1e2a38';
    g.fillRect(0, 0, W, headH);
    g.fillStyle = '#ffffff';
    g.font = 'bold 44px "Microsoft YaHei", sans-serif';
    g.fillText('小贤门窗 · 报价单', 48, 78);
    g.font = '22px "Microsoft YaHei", sans-serif';
    g.fillStyle = '#c8d4e2';
    g.fillText('型号：' + style.name, 48, 126);
    g.fillText('洞口尺寸：' + fmtDims(state.w, state.h) + '  面积：' + q.area.toFixed(2) + '㎡', 48, 162);
    g.fillText('玻璃：' + q.glass.name + '　颜色：' + colorName + '　纱窗：' + (state.screen && !q.isDoor ? '配' : '无'), 48, 196);

    // 明细
    const x0 = 48, x1 = 760, x2 = 900, x3 = 1032;
    g.textBaseline = 'middle';
    q.items.forEach((it, i) => {
      const y = headH + i * rowH;
      g.fillStyle = i % 2 ? '#f5f6f8' : '#ffffff';
      g.fillRect(0, y, W, rowH);
      g.fillStyle = '#333';
      g.font = '24px "Microsoft YaHei", sans-serif';
      g.fillText(it.name, x0, y + rowH / 2);
      g.fillStyle = '#888';
      g.font = '19px "Microsoft YaHei", sans-serif';
      g.fillText(it.detail, x0, y + rowH - 13);
      g.fillStyle = '#333';
      g.font = '22px "Microsoft YaHei", sans-serif';
      g.textAlign = 'right';
      g.fillText('¥' + fmtMoney(it.price), x2, y + rowH / 2);
      g.fillText('¥' + fmtMoney(it.amount), x3, y + rowH / 2);
      g.textAlign = 'left';
    });

    // 合计
    const ty = headH + q.items.length * rowH + 20;
    g.fillStyle = '#e8f4ee';
    g.fillRect(0, ty - 8, W, 78);
    g.fillStyle = '#1c8a4c';
    g.font = 'bold 34px "Microsoft YaHei", sans-serif';
    g.textAlign = 'right';
    g.fillText('合计：¥' + fmtMoney(q.total), x3, ty + 32);
    g.textAlign = 'left';

    // 底部
    g.fillStyle = '#999';
    g.font = '20px "Microsoft YaHei", sans-serif';
    g.fillText('客户：' + (customer || '＿＿＿＿＿'), 48, ty + 86);
    g.fillText('地址：' + (address || '＿＿＿＿＿＿＿＿＿＿＿＿'), 48, ty + 118);
    g.textAlign = 'right';
    g.fillText('日期：' + new Date().toLocaleDateString('zh-CN'), x3, ty + 118);
    g.textAlign = 'left';
    g.fillStyle = '#bbb';
    g.font = '16px "Microsoft YaHei", sans-serif';
    g.fillText('本报价由小贤门窗软件自动生成，价格含材料/五金/安装，不含土建修补。', 48, H - 26);

    return c;
  }

  function fmtMoney(n) {
    return Math.round(n).toLocaleString('zh-CN');
  }

  return { calc, toText, toCanvas, getPrices, setPrices, reset, fmtMoney };
})();
