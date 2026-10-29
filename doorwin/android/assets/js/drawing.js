/* ============================================================
 * 2D 门窗立面图：按比例绘制分格、开启扇方向、尺寸标注、标题栏
 * 画布固定 1100×780 逻辑像素（×2 输出高清），用于屏幕查看与导出。
 * ============================================================ */

const Drawing = (function () {
  let canvas, ctx, state = null;

  const LW = 1100, LH = 780;   // 逻辑尺寸
  const DPR = 2;               // 输出倍率
  const MARGIN = { left: 110, top: 95, right: 190, bottom: 250 };

  function init(el) {
    canvas = el;
    canvas.width = LW * DPR;
    canvas.height = LH * DPR;
    ctx = canvas.getContext('2d');
    ctx.scale(DPR, DPR);
    draw();
  }

  function setState(s) { state = s; draw(); }

  function draw() {
    if (!state || !ctx) return;
    const style = Models.getStyleById(state.styleId);
    const W = state.w, H = state.h;
    const fw = 60; // 外框可视宽（与 3D 模型一致）

    // 背景
    ctx.clearRect(0, 0, LW, LH);
    ctx.fillStyle = '#fdfdfb';
    ctx.fillRect(0, 0, LW, LH);

    // 比例计算：为标注留出空间
    const availW = LW - MARGIN.left - MARGIN.right;
    const availH = LH - MARGIN.top - MARGIN.bottom;
    const s = Math.min(availW / W, availH / H);
    const ox = MARGIN.left + (availW - W * s) / 2;
    const oy = MARGIN.top + (availH - H * s) / 2;
    const X = mm => ox + mm * s;   // mm → x 坐标
    const Y = mm => oy + mm * s;

    // ---- 墙体：洞口外围填充斜线 ----
    const wallExt = 260; // 墙体向外延伸
    ctx.save();
    ctx.beginPath();
    ctx.rect(X(-wallExt), Y(-wallExt), (W + 2 * wallExt) * s, (H + 2 * wallExt) * s);
    ctx.rect(X(0), Y(0), W * s, H * s);
    ctx.clip('evenodd');
    ctx.strokeStyle = '#c9c2b4';
    ctx.lineWidth = 0.8;
    for (let x = -wallExt; x < W + wallExt + H; x += 16) {
      ctx.beginPath();
      ctx.moveTo(X(x), Y(-wallExt));
      ctx.lineTo(X(x - (H + 2 * wallExt)), Y(H + wallExt));
      ctx.stroke();
    }
    ctx.restore();

    // ---- 洞口轮廓 ----
    ctx.strokeStyle = '#8a8478';
    ctx.lineWidth = 2;
    ctx.strokeRect(X(0), Y(0), W * s, H * s);

    // ---- 外框 ----
    ctx.strokeStyle = '#3d434b';
    ctx.lineWidth = 2.6;
    ctx.strokeRect(X(fw), Y(fw), (W - 2 * fw) * s, (H - 2 * fw) * s);
    // 外框与洞口之间的填充（型材截面）
    ctx.fillStyle = '#e4e0d6';
    ctx.fillRect(X(0), Y(0), W * s, fw * s);
    ctx.fillRect(X(0), Y(H - fw), W * s, fw * s);
    ctx.fillRect(X(0), Y(fw), fw * s, (H - 2 * fw) * s);
    ctx.fillRect(X(W - fw), Y(fw), fw * s, (H - 2 * fw) * s);

    // ---- 分格梃料 ----
    ctx.fillStyle = '#3d434b';
    const innerW = W - 2 * fw, innerH = H - 2 * fw;
    const cw = innerW / style.cols, ch = innerH / style.rows;
    for (let c = 1; c < style.cols; c++) {
      ctx.fillRect(X(fw + c * cw) - 1.5 * s, Y(fw), 3 * s, innerH * s);
    }
    for (let r = 1; r < style.rows; r++) {
      ctx.fillRect(X(fw), Y(fw + r * ch) - 1.5 * s, innerW * s, 3 * s);
    }

    // ---- 每格扇 ----
    const glassMat = GLASS_TYPES.find(t => t.id === state.glass) || GLASS_TYPES[0];
    style.cells.forEach(cell => {
      const cx0 = fw + cell.c * cw, cy0 = fw + cell.r * ch;
      const rect = { x0: cx0, y0: cy0, w: cw, h: ch };
      drawCell(rect, cell, style, glassMat, s, X, Y);
    });

    // ---- 尺寸标注 ----
    drawDims(W, H, style, s, X, Y);

    // ---- 标题栏 ----
    drawTitleBlock(style, W, H, glassMat);
  }

  /* ---- 零件参数取值（与 3D 一致） ---- */
  function cellSpec2(cell) {
    const type = cell.type || 'fixed';
    const def = {};
    (PART_TYPES[type] ? PART_TYPES[type].params : []).forEach(p => { def[p.key] = p.def; });
    const params = Object.assign(def, cell.params || {});
    if (cell.hinge !== undefined) params.hinge = cell.hinge;
    return { type, params };
  }

  /* ---- 单格绘制 ---- */
  function drawCell(rect, cell, style, glassMat, s, X, Y) {
    const { x0, y0, w, h } = rect;
    const sw = 45; // 扇料宽
    const { type, params } = cellSpec2(cell);
    const hasGlass = ['fixed', 'casement', 'top-hung', 'bottom-hung', 'tilt-turn', 'slide',
      'hinge-door', 'slide-door', 'sealed-louver', 'grille', 'glass-grille'].indexOf(type) >= 0;

    // 玻璃填充
    if (hasGlass) {
      ctx.fillStyle = '#dcebf3';
      ctx.fillRect(X(x0 + sw), Y(y0 + sw), (w - 2 * sw) * s, (h - 2 * sw) * s);
    }

    switch (type) {
      case 'fixed': {
        ctx.strokeStyle = '#3d434b';
        ctx.lineWidth = 1.6;
        ctx.strokeRect(X(x0 + sw), Y(y0 + sw), (w - 2 * sw) * s, (h - 2 * sw) * s);
        break;
      }
      case 'casement':
      case 'tilt-turn':
      case 'hinge-door': {
        const isDoor = type === 'hinge-door';
        ctx.strokeStyle = '#3d434b';
        ctx.lineWidth = 1.6;
        ctx.strokeRect(X(x0 + sw / 2), Y(y0 + sw / 2), (w - sw) * s, (h - sw) * s);
        if (isDoor) {
          ctx.fillStyle = '#3d434b';
          ctx.fillRect(X(x0 + sw), Y(y0 + h - sw - 300), (w - 2 * sw) * s, 300 * s);
        }
        const left = params.hinge !== 'right';
        const hx = X(left ? x0 + sw / 2 : x0 + w - sw / 2);
        const hy = Y(y0 + h - (isDoor ? sw : sw * 0.5));
        const r = (w - sw) * s;
        ctx.strokeStyle = '#4ea3ff';
        ctx.lineWidth = 1.6;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        if (left) ctx.arc(hx, hy, r, -Math.PI / 2, 0);
        else ctx.arc(hx, hy, r, Math.PI, Math.PI * 1.5);
        ctx.stroke();
        ctx.setLineDash([]);
        const lineEnd = { x: X(left ? x0 + w : x0), y: hy - r };
        ctx.beginPath();
        ctx.moveTo(hx, hy);
        ctx.lineTo(lineEnd.x, lineEnd.y);
        ctx.strokeStyle = '#4ea3ff';
        ctx.stroke();
        const triX = left ? hx + r - 14 : hx - r + 14;
        ctx.fillStyle = '#4ea3ff';
        ctx.beginPath();
        ctx.moveTo(triX, hy - 14);
        ctx.lineTo(triX, hy - 2);
        ctx.lineTo(triX - 10 * (left ? 1 : -1), hy - 8);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = '#3d434b';
        if (isDoor) {
          const hhx = left ? x0 + w - 30 : x0 + 30;
          ctx.fillRect(X(hhx - 4), Y(y0 + h - 950), 8 * s, 90 * s);
        } else {
          const hhx = left ? x0 + w - 26 : x0 + 26;
          ctx.fillRect(X(hhx - 5), Y(y0 + h * 0.62), 10 * s, 70 * s);
        }
        break;
      }
      case 'top-hung':
      case 'bottom-hung': {
        const isTop = type === 'top-hung';
        ctx.strokeStyle = '#3d434b';
        ctx.lineWidth = 1.6;
        ctx.strokeRect(X(x0 + sw / 2), Y(y0 + sw / 2), (w - sw) * s, (h - sw) * s);
        // 铰链边 + 开启弧线
        const hx = X(x0 + w / 2);
        const hy = isTop ? Y(y0 + sw / 2) : Y(y0 + h - sw / 2);
        const r = (h - sw) * s;
        ctx.strokeStyle = '#4ea3ff';
        ctx.lineWidth = 1.6;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        if (isTop) ctx.arc(hx, hy, r, Math.PI / 2, Math.PI / 2 + 0.55);
        else ctx.arc(hx, hy, r, -Math.PI / 2, -Math.PI / 2 - 0.55);
        ctx.stroke();
        ctx.setLineDash([]);
        const ex = X(x0 + w / 2 + (isTop ? -1 : 1) * 10);
        const ey = isTop ? hy - r : hy + r;
        ctx.beginPath();
        ctx.moveTo(hx, hy);
        ctx.lineTo(ex, ey);
        ctx.strokeStyle = '#4ea3ff';
        ctx.stroke();
        break;
      }
      case 'slide':
      case 'slide-door': {
        const isDoor = type === 'slide-door';
        const overlap = 40;
        const half = w / 2 + overlap;
        ctx.strokeStyle = '#3d434b';
        ctx.lineWidth = 1.4;
        ctx.strokeRect(X(x0 + w - half), Y(y0 + sw / 2), (half - sw) * s, (h - sw) * s);
        ctx.lineWidth = 1.8;
        ctx.strokeRect(X(x0 + sw / 2), Y(y0 + sw / 2), (half - sw) * s, (h - sw) * s);
        ctx.fillStyle = 'rgba(61,67,75,0.12)';
        ctx.fillRect(X(x0 + w - half - overlap), Y(y0 + sw / 2), overlap * 2 * s, (h - sw) * s);
        if (isDoor) {
          ctx.fillStyle = '#3d434b';
          ctx.fillRect(X(x0 + sw), Y(y0 + h - sw - 260), (half - sw) * s, 260 * s);
        }
        ctx.fillStyle = '#4ea3ff';
        ctx.strokeStyle = '#4ea3ff';
        ctx.lineWidth = 1.4;
        const ay = Y(y0 + h / 2);
        drawArrow(X(x0 + half * 0.45), ay, X(x0 + half * 0.7), ay);
        drawArrow(X(x0 + w - half * 0.45), ay, X(x0 + w - half * 0.7), ay);
        break;
      }
      case 'fold': {
        const n = params.panels || 4;
        const pw = w / n;
        ctx.strokeStyle = '#3d434b';
        ctx.lineWidth = 1.5;
        for (let i = 0; i < n; i++) {
          ctx.strokeRect(X(x0 + i * pw + sw / 4), Y(y0 + sw / 2), (pw - sw / 2) * s, (h - sw) * s);
        }
        // 折叠示意（锯齿线）
        ctx.strokeStyle = '#4ea3ff';
        ctx.lineWidth = 1.4;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        const fy = Y(y0 + h / 2);
        ctx.moveTo(X(x0 + sw), fy);
        for (let i = 1; i < n; i++) {
          ctx.lineTo(X(x0 + i * pw), fy + (i % 2 ? -1 : 1) * 12);
        }
        ctx.stroke();
        ctx.setLineDash([]);
        break;
      }
      case 'louver': {
        const spacing = params.spacing || 70;
        const inset = sw + 14;
        const count = Math.max(2, Math.floor((h - 2 * inset) / spacing));
        const startY = y0 + h / 2 - (count - 1) * spacing / 2;
        ctx.strokeStyle = '#3d434b';
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        for (let i = 0; i < count; i++) {
          const by = Y(startY + i * spacing);
          ctx.moveTo(X(x0 + inset), by);
          ctx.lineTo(X(x0 + w - inset), by);
        }
        ctx.stroke();
        break;
      }
      case 'sealed-louver': {
        ctx.strokeStyle = '#3d434b';
        ctx.lineWidth = 1.6;
        ctx.strokeRect(X(x0 + sw), Y(y0 + sw), (w - 2 * sw) * s, (h - 2 * sw) * s);
        const spacing = params.spacing || 50;
        const count = Math.max(2, Math.floor((h - 2 * sw) / spacing));
        const startY = y0 + h / 2 - (count - 1) * spacing / 2;
        ctx.strokeStyle = '#8fa8b8';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        for (let i = 0; i < count; i++) {
          const by = Y(startY + i * spacing);
          ctx.moveTo(X(x0 + sw + 8), by);
          ctx.lineTo(X(x0 + w - sw - 8), by);
        }
        ctx.stroke();
        break;
      }
      case 'grille':
      case 'glass-grille': {
        const thick = params.thick || 25;
        const count = params.count || 4;
        const dir = params.dir || 'v';
        const inset = sw + 10;
        const innerW = w - 2 * inset, innerH = h - 2 * inset;
        ctx.strokeStyle = '#3d434b';
        ctx.lineWidth = Math.max(1.2, thick * s * 0.6);
        ctx.beginPath();
        if (dir === 'v' || dir === 'grid') {
          for (let i = 1; i <= count; i++) {
            const x = X(x0 + inset + i * (innerW / (count + 1)));
            ctx.moveTo(x, Y(y0 + inset));
            ctx.lineTo(x, Y(y0 + h - inset));
          }
        }
        if (dir === 'h' || dir === 'grid') {
          for (let i = 1; i <= count; i++) {
            const y = Y(y0 + inset + i * (innerH / (count + 1)));
            ctx.moveTo(X(x0 + inset), y);
            ctx.lineTo(X(x0 + w - inset), y);
          }
        }
        if (dir === 'diamond') {
          ctx.save();
          ctx.beginPath();
          ctx.rect(X(x0 + inset), Y(y0 + inset), innerW * s, innerH * s);
          ctx.clip();
          const step = (innerW + innerH) / (count + 1);
          ctx.translate(X(x0 + w / 2), Y(y0 + h / 2));
          for (let i = 1; i <= count; i++) {
            const off = (i / (count + 1) - 0.5) * step * s;
            [-1, 1].forEach(sgn => {
              ctx.moveTo(-innerW * s / 2 - off * 0.2, sgn * (innerH * s / 2 - 0));
              ctx.lineTo(innerW * s / 2 - off * 0.2, -sgn * innerH * s / 2);
            });
          }
          ctx.stroke();
          ctx.restore();
        }
        ctx.stroke();
        break;
      }
      case 'lattice': {
        const thick = params.thick || 22;
        const pattern = params.pattern || 'jing';
        ctx.strokeStyle = '#3d434b';
        ctx.lineWidth = Math.max(1.5, thick * s * 0.6);
        ctx.beginPath();
        if (pattern === 'jing' || pattern === 'cross') {
          ctx.moveTo(X(x0 + w / 2), Y(y0 + sw));
          ctx.lineTo(X(x0 + w / 2), Y(y0 + h - sw));
          ctx.moveTo(X(x0 + sw), Y(y0 + h / 2));
          ctx.lineTo(X(x0 + w - sw), Y(y0 + h / 2));
        } else if (pattern === 'diamond') {
          ctx.moveTo(X(x0 + sw), Y(y0 + sw));
          ctx.lineTo(X(x0 + w - sw), Y(y0 + h - sw));
          ctx.moveTo(X(x0 + w - sw), Y(y0 + sw));
          ctx.lineTo(X(x0 + sw), Y(y0 + h - sw));
        }
        ctx.stroke();
        break;
      }
      case 'security': {
        const count = params.count || 9;
        const inset = 30;
        const innerW = w - 2 * inset, innerH = h - 2 * inset;
        ctx.strokeStyle = '#8b99a6';
        ctx.lineWidth = 1.4;
        ctx.strokeRect(X(x0 + inset), Y(y0 + inset), innerW * s, innerH * s);
        ctx.beginPath();
        for (let i = 1; i <= count; i++) {
          const x = X(x0 + inset + i * (innerW / (count + 1)));
          ctx.moveTo(x, Y(y0 + inset));
          ctx.lineTo(x, Y(y0 + h - inset));
        }
        const rows = Math.max(2, Math.round(innerH / 500));
        for (let i = 1; i <= rows; i++) {
          const y = Y(y0 + inset + i * (innerH / (rows + 1)));
          ctx.moveTo(X(x0 + inset), y);
          ctx.lineTo(X(x0 + w - inset), y);
        }
        ctx.stroke();
        break;
      }
      case 'solid': {
        ctx.fillStyle = '#4a4f55';
        ctx.fillRect(X(x0 + sw / 2), Y(y0 + sw / 2), (w - sw) * s, (h - sw) * s);
        break;
      }
    }

    // 零件名称标注
    const partName = (PART_TYPES[type] || {}).name || '固定';
    ctx.fillStyle = '#7a94a8';
    ctx.font = '11px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(hasGlass ? glassMat.name : partName, X(x0 + w / 2), Y(y0 + h * 0.5));
    ctx.fillStyle = '#98a2ad';
    ctx.font = '10px "Microsoft YaHei", sans-serif';
    ctx.fillText(partName, X(x0 + w / 2), Y(y0 + h * 0.62));
  }

  function drawArrow(x1, y, x2, y2) {
    ctx.beginPath();
    ctx.moveTo(x1, y);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    const dx = x2 - x1, dy = y2 - y;
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len;
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - ux * 8 - uy * 4, y2 - uy * 8 + ux * 4);
    ctx.lineTo(x2 - ux * 8 + uy * 4, y2 - uy * 8 - ux * 4);
    ctx.closePath();
    ctx.fill();
  }

  /* ---- 尺寸标注（建筑斜线起止符） ---- */
  function drawDims(W, H, style, s, X, Y) {
    ctx.fillStyle = '#333';
    ctx.strokeStyle = '#444';
    ctx.font = '12px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineWidth = 1;

    const dimY1 = Y(H) + 55, dimY2 = Y(H) + 88; // 总宽、分格两条标注线
    // 总宽
    dimLine(X(0), X(W), dimY1);
    label((W) + ' mm', (X(0) + X(W)) / 2, dimY1 - 13);
    // 分格宽
    if (style.cols > 1) {
      const fw = 60, cw = (W - 2 * fw) / style.cols;
      dimLine(X(0), X(W), dimY2);
      for (let c = 0; c < style.cols; c++) {
        const x1 = X(fw + c * cw), x2 = X(fw + (c + 1) * cw);
        tick(x1, dimY2); tick(x2, dimY2);
        label(cw + '', (x1 + x2) / 2, dimY2 - 13);
      }
      label('分格宽度 mm', (X(0) + X(W)) / 2, dimY2 + 13);
    }

    // 总高（右侧）
    const dimX1 = X(W) + 55, dimX2 = X(W) + 88;
    vDimLine(Y(0), Y(H), dimX1);
    vLabel(H + ' mm', dimX1 - 13, (Y(0) + Y(H)) / 2);
    // 分格高
    if (style.rows > 1) {
      const fw = 60, ch = (H - 2 * fw) / style.rows;
      vDimLine(Y(0), Y(H), dimX2);
      for (let r = 0; r < style.rows; r++) {
        const y1 = Y(fw + r * ch), y2 = Y(fw + (r + 1) * ch);
        tickX(dimX2, y1); tickX(dimX2, y2);
        vLabel(ch + '', dimX2 - 13, (y1 + y2) / 2);
      }
    }

    function dimLine(x1, x2, y) {
      ctx.beginPath(); ctx.moveTo(x1, y); ctx.lineTo(x2, y); ctx.stroke();
      // 尺寸界线
      ctx.beginPath();
      ctx.moveTo(x1, y + 6); ctx.lineTo(x1, y - (y - Y(0)) + Y(0)); ctx.stroke();
      ctx.moveTo(x2, y + 6); ctx.lineTo(x2, y - (y - Y(0)) + Y(0)); ctx.stroke();
      tick(x1, y); tick(x2, y);
    }
    function tick(x, y) {
      ctx.beginPath();
      ctx.moveTo(x - 7, y); ctx.lineTo(x + 7, y);
      ctx.stroke();
    }
    function label(t, x, y) {
      ctx.fillStyle = '#fff';
      ctx.fillRect(x - ctx.measureText(t).width / 2 - 5, y - 9, ctx.measureText(t).width + 10, 18);
      ctx.fillStyle = '#333';
      ctx.fillText(t, x, y);
    }
    function vDimLine(y1, y2, x) {
      ctx.beginPath(); ctx.moveTo(x, y1); ctx.lineTo(x, y2); ctx.stroke();
      tickX(x, y1); tickX(x, y2);
    }
    function tickX(x, y) {
      ctx.beginPath();
      ctx.moveTo(x, y - 7); ctx.lineTo(x, y + 7);
      ctx.stroke();
    }
    function vLabel(t, x, y) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(-Math.PI / 2);
      ctx.fillStyle = '#fff';
      ctx.fillRect(-ctx.measureText(t).width / 2 - 5, -9, ctx.measureText(t).width + 10, 18);
      ctx.fillStyle = '#333';
      ctx.textAlign = 'center';
      ctx.fillText(t, 0, 0);
      ctx.restore();
    }

    // 洞口线（外沿到标注线的引出线）
    ctx.beginPath();
    ctx.moveTo(X(0), Y(0)); ctx.lineTo(X(0) - 30, Y(0)); ctx.stroke();
    ctx.moveTo(X(W), Y(0)); ctx.lineTo(X(W) + 30, Y(0)); ctx.stroke();
  }

  /* ---- 标题栏 ---- */
  function drawTitleBlock(style, W, H, glassMat) {
    const series = FRAME_SERIES.find(sr => sr.id === state.series) || FRAME_SERIES[0];
    const colorName = (FRAME_COLORS.find(c => c.hex === state.frameColor) || { name: '自定义' }).name;
    const area = (W * H / 1e6).toFixed(2);

    const rows = [
      ['型号', style.name],
      ['洞口尺寸', W + ' × ' + H + ' mm'],
      ['型材厚度', (state.frameThick || 60) + ' mm'],
      ['面积', area + ' ㎡'],
      ['玻璃', glassMat.name],
      ['型材', series.name + ' / ' + colorName],
      ['日期', new Date().toLocaleDateString('zh-CN')],
    ];
    const bw = 340, bh = rows.length * 26 + 10;
    const bx = LW - bw - 16, by = LH - bh - 14;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(bx, by, bw, bh);
    ctx.strokeStyle = '#444';
    ctx.lineWidth = 1.4;
    ctx.strokeRect(bx, by, bw, bh);

    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    const rowH = bh / rows.length;
    rows.forEach((row, i) => {
      const ry = by + i * rowH;
      ctx.fillStyle = '#f2f0ea';
      ctx.fillRect(bx, ry, 78, rowH);
      ctx.strokeStyle = '#999';
      ctx.lineWidth = 0.8;
      ctx.strokeRect(bx, ry, 78, rowH);
      ctx.fillStyle = '#444';
      ctx.font = '11px "Microsoft YaHei", sans-serif';
      ctx.fillText(row[0], bx + 10, ry + rowH / 2);
      ctx.fillStyle = '#222';
      ctx.font = '600 11.5px "Microsoft YaHei", sans-serif';
      ctx.fillText(row[1], bx + 90, ry + rowH / 2);
    });

    // 图名
    ctx.fillStyle = '#333';
    ctx.font = '600 15px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('小贤门窗 · ' + style.name + ' 立面图', 16, 28);

    // 比例
    const s = Math.min((LW - MARGIN.left - MARGIN.right) / W, (LH - MARGIN.top - MARGIN.bottom) / H);
    const nice = Math.max(5, Math.round(1 / s / 5) * 5);
    ctx.fillStyle = '#888';
    ctx.font = '11px "Microsoft YaHei", sans-serif';
    ctx.fillText('比例 1:' + nice, 16, 48);
  }

  /* 导出高清 PNG */
  function exportPNG() {
    return canvas.toDataURL('image/png');
  }

  return { init, setState, exportPNG };
})();
