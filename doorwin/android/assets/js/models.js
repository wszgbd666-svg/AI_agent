/* ============================================================
 * 参数化门窗 3D 模型生成器（零件化架构）
 * 每个格子（cell）按零件类型(type)+参数(params)程序化生成几何体。
 * 内置款式与自建款式使用同一套零件渲染器。
 * 输入单位 mm，Three.js 场景单位 m。
 * ============================================================ */

const M = 0.001; // mm → m

/* 型材截面尺寸（mm），frameW 随用户设置的型材厚度动态调整 */
const PROFILE = {
  frameW: 60,    // 外框可视宽度
  frameD: 70,    // 外框深度
  sashW: 45,     // 扇料可视宽度
  sashD: 52,     // 扇料深度
  glassT: 8,     // 玻璃厚度
};

const Models = (function () {
  const matCache = {};

  /* 型材厚度联动：扇料 = 外框的 75% */
  function setProfile(frameThick) {
    PROFILE.frameW = frameThick || 60;
    PROFILE.sashW = Math.round(PROFILE.frameW * 0.75);
  }

  function getFrameMaterial(hex) {
    const key = 'frame:' + hex;
    if (!matCache[key]) {
      matCache[key] = new THREE.MeshStandardMaterial({
        color: hex, metalness: 0.35, roughness: 0.45, side: THREE.DoubleSide,
      });
    }
    return matCache[key];
  }

  function getGlassMaterial(glassId) {
    const g = GLASS_TYPES.find(t => t.id === glassId) || GLASS_TYPES[0];
    const key = 'glass:' + g.id;
    if (!matCache[key]) {
      matCache[key] = new THREE.MeshStandardMaterial({
        color: g.tint, transparent: true, opacity: g.opacity,
        roughness: g.roughness, metalness: 0.1,
        side: THREE.DoubleSide, depthWrite: false,
      });
    }
    return matCache[key];
  }

  function getMetalMaterial() {
    if (!matCache['metal']) {
      matCache['metal'] = new THREE.MeshStandardMaterial({
        color: '#c7ccd2', metalness: 0.85, roughness: 0.35, side: THREE.DoubleSide,
      });
    }
    return matCache['metal'];
  }

  /* 便捷创建盒子（mm 输入） */
  function box(parent, cx, cy, cz, sx, sy, sz, mat, shadow) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(sx * M, sy * M, sz * M), mat);
    m.position.set(cx * M, cy * M, cz * M);
    m.castShadow = !!shadow;
    m.receiveShadow = !!shadow;
    parent.add(m);
    return m;
  }

  /* ---- 零件参数：默认值 + 用户值合并 ---- */
  function cellSpec(cell) {
    const type = cell.type || 'fixed';
    const def = {};
    (PART_TYPES[type] ? PART_TYPES[type].params : []).forEach(p => { def[p.key] = p.def; });
    const params = Object.assign(def, cell.params || {});
    if (cell.hinge !== undefined) params.hinge = cell.hinge;
    return { type, params };
  }

  /* ---- 外框：上下左右四根 ---- */
  function addFrame(group, W, H, frameMat) {
    const fw = PROFILE.frameW, d = PROFILE.frameD;
    const hw = W / 2, hh = H / 2;
    box(group, -hw + fw / 2, 0, 0, fw, H, d, frameMat, true);
    box(group, hw - fw / 2, 0, 0, fw, H, d, frameMat, true);
    box(group, 0, hh - fw / 2, 0, W, fw, d, frameMat, true);
    box(group, 0, -hh + fw / 2, 0, W, fw, d, frameMat, true);
  }

  /* ---- 分格梃料：中梃(竖) / 横梃(横) ---- */
  function addGrid(group, W, H, style, frameMat) {
    const fw = PROFILE.frameW, d = PROFILE.frameD;
    const innerW = W - 2 * fw, innerH = H - 2 * fw;
    const x0 = -W / 2 + fw, y0 = -H / 2 + fw;
    for (let c = 1; c < style.cols; c++) {
      box(group, x0 + c * (innerW / style.cols), 0, 0, fw, innerH, d, frameMat, true);
    }
    for (let r = 1; r < style.rows; r++) {
      box(group, 0, y0 + r * (innerH / style.rows), 0, innerW, fw, d, frameMat, true);
    }
  }

  /* ---- 计算每格矩形（mm，中心坐标） ---- */
  function cellRects(style, w, h) {
    const fw = PROFILE.frameW;
    const innerW = w - 2 * fw, innerH = h - 2 * fw;
    const cw = innerW / style.cols, ch = innerH / style.rows;
    const x0 = -w / 2 + fw, y0 = -h / 2 + fw;
    const rects = {};
    style.cells.forEach(cell => {
      rects[cell.r + '-' + cell.c] = {
        x0: x0 + cell.c * cw, y0: y0 + cell.r * ch,
        cx: x0 + cell.c * cw + cw / 2, cy: y0 + cell.r * ch + ch / 2,
        w: cw, h: ch, cell,
      };
    });
    return rects;
  }

  /* ---- 玻璃面板（rect 中心坐标版） ---- */
  function glassPane(parent, cx, cy, w, h, z, glassMat, depth) {
    box(parent, cx, cy, z || 0, w, h, depth || PROFILE.glassT, glassMat, true);
  }

  /* ---- 固定扇 ---- */
  function buildFixed(parent, rect, glassMat) {
    const margin = 30;
    glassPane(parent, rect.cx, rect.cy, rect.w - 2 * margin, rect.h - 2 * margin, 0, glassMat);
  }

  /* ---- 平开扇（铰链旋转组，可门可窗） ---- */
  function buildCasement(parent, rect, state, frameMat, glassMat, isDoor, hingeMode) {
    const angle = (state.angle || 0) * Math.PI / 180;
    const sw = PROFILE.sashW, sd = PROFILE.sashD;
    const cw = rect.w, ch = rect.h;

    const g = new THREE.Group();
    g.position.set(rect.x0 * M, (rect.y0 + rect.h / 2) * M, 0);

    // 扇料：左右梃 + 上下梃
    box(g, sw / 2, 0, 0, sw, ch, sd, frameMat, true);
    box(g, cw - sw / 2, 0, 0, sw, ch, sd, frameMat, true);
    box(g, cw / 2, ch / 2 - sw / 2, 0, cw, sw, sd, frameMat, true);
    box(g, cw / 2, -ch / 2 + sw / 2, 0, cw, sw, sd, frameMat, true);

    // 玻璃（门：下方留挡板位置）
    let glassTop = ch / 2 - sw * 1.6, glassBottom = -ch / 2 + sw * 1.6;
    if (isDoor) glassBottom = -ch / 2 + sw * 1.6 + 300; // 门下方 300mm 挡板
    glassPane(g, cw / 2, (glassTop + glassBottom) / 2, cw - sw * 2 - 14, glassTop - glassBottom, 0, glassMat);

    // 门挡板
    if (isDoor) box(g, cw / 2, -ch / 2 + sw / 2 + 150, 0, cw, 300, sd, frameMat, true);

    // 执手
    if (isDoor) {
      const hy = -ch / 2 + 1050; // 门把手离地 1050mm
      box(g, cw - 24, hy, sd / 2 + 10, 8, 16, 22, frameMat, true);
      box(g, cw - 86, hy, sd / 2 + 14, 150, 10, 10, frameMat, true);
    } else {
      const hy = -ch / 4;
      box(g, cw - 20, hy, sd / 2 + 10, 10, 110, 20, frameMat, true);
    }

    // 铰链：left 组原点即左边缘；right 用镜像
    if (hingeMode === 'right') g.scale.x = -1;
    g.rotation.y = angle; // 正值向室外开启
    parent.add(g);
  }

  /* ---- 上悬扇（铰链在上边缘，底部外开） ---- */
  function buildTopHung(parent, rect, state, frameMat, glassMat) {
    const angle = (state.angle || 15) * Math.PI / 180;
    const sw = PROFILE.sashW, sd = PROFILE.sashD;
    const cw = rect.w, ch = rect.h;
    const g = new THREE.Group();
    g.position.set((rect.x0 + rect.w / 2) * M, (rect.y0 + rect.h) * M, 0);
    // 扇料（y 从 0 到 -ch）
    box(g, 0, -sw / 2, 0, cw, sw, sd, frameMat, true);
    box(g, 0, -ch + sw / 2, 0, cw, sw, sd, frameMat, true);
    box(g, -cw / 2 + sw / 2, -ch / 2, 0, sw, ch, sd, frameMat, true);
    box(g, cw / 2 - sw / 2, -ch / 2, 0, sw, ch, sd, frameMat, true);
    glassPane(g, 0, -ch / 2, cw - sw * 2 - 14, ch - sw * 2 - 14, 0, glassMat);
    box(g, 0, -ch / 2, sd / 2 + 10, 10, 110, 20, frameMat, true);
    g.rotation.x = angle;
    parent.add(g);
  }

  /* ---- 下悬扇（铰链在下边缘，顶部外开） ---- */
  function buildBottomHung(parent, rect, state, frameMat, glassMat) {
    const angle = (state.angle || 15) * Math.PI / 180;
    const sw = PROFILE.sashW, sd = PROFILE.sashD;
    const cw = rect.w, ch = rect.h;
    const g = new THREE.Group();
    g.position.set((rect.x0 + rect.w / 2) * M, rect.y0 * M, 0);
    box(g, 0, sw / 2, 0, cw, sw, sd, frameMat, true);
    box(g, 0, ch - sw / 2, 0, cw, sw, sd, frameMat, true);
    box(g, -cw / 2 + sw / 2, ch / 2, 0, sw, ch, sd, frameMat, true);
    box(g, cw / 2 - sw / 2, ch / 2, 0, sw, ch, sd, frameMat, true);
    glassPane(g, 0, ch / 2, cw - sw * 2 - 14, ch - sw * 2 - 14, 0, glassMat);
    box(g, 0, ch / 2, sd / 2 + 10, 10, 110, 20, frameMat, true);
    g.rotation.x = -angle;
    parent.add(g);
  }

  /* ---- 推拉扇（前后错位两扇） ---- */
  function buildSlide(parent, rect, state, frameMat, glassMat, isDoor) {
    const sw = (isDoor ? 55 : 38), sd = (isDoor ? 46 : 42);
    const cw = rect.w, ch = rect.h;
    const half = cw / 2 + 40; // 每扇宽（含搭接量）
    const cx0 = rect.cx;

    [-1, 1].forEach(side => {
      const z = side * (sd / 2 + 4);
      const xOff = side * 22;
      const g = new THREE.Group();
      g.position.set((cx0 + xOff) * M, rect.cy * M, z * M);

      box(g, sw / 2, 0, 0, sw, ch, sd, frameMat, true);
      box(g, half - sw / 2, 0, 0, sw, ch, sd, frameMat, true);
      box(g, half / 2, ch / 2 - sw / 2, 0, half, sw, sd, frameMat, true);
      box(g, half / 2, -ch / 2 + sw / 2, 0, half, sw, sd, frameMat, true);

      let glassTop = ch / 2 - sw * 1.8, glassBottom = -ch / 2 + sw * 1.8;
      if (isDoor) glassBottom = -ch / 2 + sw * 1.8 + 260;
      glassPane(g, half / 2, (glassTop + glassBottom) / 2, half - sw * 2 - 12, glassTop - glassBottom, 0, glassMat);

      if (isDoor) {
        box(g, half / 2, -ch / 2 + sw / 2 + 130, 0, half, 260, sd, frameMat, true);
        box(g, half - sw / 2 - 30, -ch / 2 + 1050, sd / 2 + 8, 14, 260, 26, frameMat, true);
      } else {
        box(g, half - sw / 2, -ch / 2 + sw + 110, sd / 2 + 6, 18, 14, 12, frameMat, true);
      }
      parent.add(g);
    });
  }

  /* ---- 折叠扇（2/4 扇手风琴式折叠） ---- */
  function buildFold(parent, rect, state, frameMat, glassMat) {
    const n = 4; // 默认 4 扇（params.panels 可选 2/4）
    const sw = PROFILE.sashW, sd = PROFILE.sashD;
    const pw = rect.w / n, ch = rect.h;
    const foldAng = 25 * Math.PI / 180;
    for (let i = 0; i < n; i++) {
      const g = new THREE.Group();
      g.position.set((rect.x0 + i * pw) * M, rect.cy * M, 0);
      box(g, sw / 2, 0, 0, sw, ch, sd, frameMat, true);
      box(g, pw - sw / 2, 0, 0, sw, ch, sd, frameMat, true);
      box(g, pw / 2, ch / 2 - sw / 2, 0, pw, sw, sd, frameMat, true);
      box(g, pw / 2, -ch / 2 + sw / 2, 0, pw, sw, sd, frameMat, true);
      glassPane(g, pw / 2, 0, pw - sw * 2 - 12, ch - sw * 2 - 14, 0, glassMat);
      g.rotation.y = -foldAng * i; // 逐扇折叠
      parent.add(g);
    }
  }

  /* ---- 百叶（水平叶片，角度可调） ---- */
  function buildLouver(parent, rect, params, frameMat, isSealed) {
    const sw = PROFILE.sashW, sd = PROFILE.sashD;
    const cw = rect.w, ch = rect.h;
    const angle = ((params.angle !== undefined ? params.angle : 35) || 0) * Math.PI / 180;
    const spacing = params.spacing || 70;
    const bladeW = isSealed ? 45 : (params.bladeW || 70);
    const bladeT = isSealed ? 2 : 3;
    const inset = sw + 14;
    const bladeLen = cw - 2 * inset;
    const bladeCount = Math.max(2, Math.floor((ch - 2 * inset) / spacing));

    if (!isSealed) {
      // 外框式百叶：四边扇料
      box(parent, rect.cx, rect.cy - ch / 2 + sw / 2, 0, cw, sw, sd, frameMat, true);
      box(parent, rect.cx, rect.cy + ch / 2 - sw / 2, 0, cw, sw, sd, frameMat, true);
      box(parent, rect.cx - cw / 2 + sw / 2, rect.cy, 0, sw, ch, sd, frameMat, true);
      box(parent, rect.cx + cw / 2 - sw / 2, rect.cy, 0, sw, ch, sd, frameMat, true);
    }
    const startY = rect.cy - (bladeCount - 1) * spacing / 2;
    for (let i = 0; i < bladeCount; i++) {
      const b = box(parent, rect.cx, startY + i * spacing, 0, bladeLen, bladeT, bladeW, frameMat, true);
      b.rotation.x = angle;
    }
  }

  /* ---- 中空百叶：玻璃夹层内叶片 ---- */
  function buildSealedLouver(parent, rect, params, frameMat, glassMat) {
    const sw = PROFILE.sashW;
    glassPane(parent, rect.cx, rect.cy, rect.w - 2 * sw, rect.h - 2 * sw, 0, glassMat);
    buildLouver(parent, rect, params, frameMat, true);
  }

  /* ---- 格栅（可带玻璃）：竖/横/田字/菱形 ---- */
  function buildGrille(parent, rect, params, frameMat, glassMat, withGlass) {
    const cw = rect.w, ch = rect.h;
    const thick = params.thick || 25;
    const count = params.count || 4;
    const dir = params.dir || 'v';
    const sw = PROFILE.sashW;
    const z = 6;

    if (withGlass) glassPane(parent, rect.cx, rect.cy, cw - 2 * sw, ch - 2 * sw, 0, glassMat);

    const inset = sw + 10;
    const innerW = cw - 2 * inset, innerH = ch - 2 * inset;

    if (dir === 'v' || dir === 'grid') {
      for (let i = 1; i <= count; i++) {
        const x = rect.cx - innerW / 2 + i * (innerW / (count + 1));
        box(parent, x, rect.cy, z, thick, innerH, thick, frameMat, true);
      }
    }
    if (dir === 'h' || dir === 'grid') {
      for (let i = 1; i <= count; i++) {
        const y = rect.cy - innerH / 2 + i * (innerH / (count + 1));
        box(parent, rect.cx, y, z, innerW, thick, thick, frameMat, true);
      }
    }
    if (dir === 'diamond') {
      const len = Math.hypot(innerW, innerH) * 0.72;
      for (let i = 1; i <= count; i++) {
        const t = i / (count + 1) - 0.5;
        const off = t * (innerW + innerH) * 0.5;
        [-1, 1].forEach(s => {
          const b = box(parent, rect.cx + off * 0.2, rect.cy, z, len, thick, thick, frameMat, true);
          b.rotation.z = s * Math.PI / 4;
        });
      }
    }
  }

  /* ---- 花格（无玻璃装饰格）：井字/菱形/十字 ---- */
  function buildLattice(parent, rect, params, frameMat) {
    const cw = rect.w, ch = rect.h;
    const thick = params.thick || 22;
    const pattern = params.pattern || 'jing';
    const sw = PROFILE.sashW;
    const inset = sw + 6;
    const innerW = cw - 2 * inset, innerH = ch - 2 * inset;
    const z = 4;

    if (pattern === 'jing') {
      box(parent, rect.cx, rect.cy, z, thick, innerH, thick, frameMat, true);
      box(parent, rect.cx, rect.cy, z, innerW, thick, thick, frameMat, true);
    } else if (pattern === 'cross') {
      box(parent, rect.cx, rect.cy, z, thick, innerH, thick, frameMat, true);
      box(parent, rect.cx, rect.cy, z, innerW, thick, thick, frameMat, true);
    } else if (pattern === 'diamond') {
      const len = Math.hypot(innerW, innerH) * 0.8;
      [-1, 1].forEach(s => {
        const b = box(parent, rect.cx, rect.cy, z, len, thick, thick, frameMat, true);
        b.rotation.z = s * Math.PI / 4;
      });
    }
  }

  /* ---- 防盗网（不锈钢圆管） ---- */
  function buildSecurity(parent, rect, params) {
    const metal = getMetalMaterial();
    const cw = rect.w, ch = rect.h;
    const count = params.count || 9;
    const r = (params.thick || 10) / 2;
    const inset = 30;
    const z = 40; // 装在外侧
    const innerW = cw - 2 * inset, innerH = ch - 2 * inset;

    // 边框
    const frameT = 12;
    const tube = (cx, cy, len, horiz) => {
      const geo = horiz ? new THREE.CylinderGeometry(r + 2, r + 2, len, 10) : new THREE.CylinderGeometry(r + 2, r + 2, len, 10);
      const m = new THREE.Mesh(geo, metal);
      m.position.set(cx * M, cy * M, z * M);
      if (horiz) m.rotation.z = Math.PI / 2;
      m.castShadow = true;
      parent.add(m);
      return m;
    };
    tube(rect.cx - innerW / 2, rect.cy, innerH, true);
    tube(rect.cx + innerW / 2, rect.cy, innerH, true);
    tube(rect.cx, rect.cy - innerH / 2, innerW, false);
    tube(rect.cx, rect.cy + innerH / 2, innerW, false);
    // 竖管
    for (let i = 1; i <= count; i++) {
      const x = rect.cx - innerW / 2 + i * (innerW / (count + 1));
      tube(x, rect.cy, innerH, true);
    }
    // 横管
    const rows = Math.max(2, Math.round(innerH / 500));
    for (let i = 1; i <= rows; i++) {
      const y = rect.cy - innerH / 2 + i * (innerH / (rows + 1));
      tube(rect.cx, y, innerW, false);
    }
  }

  /* ---- 实板 ---- */
  function buildSolid(parent, rect, frameMat) {
    box(parent, rect.cx, rect.cy, 0, rect.w - 12, rect.h - 12, PROFILE.sashD, frameMat, true);
  }

  /* ---- 纱窗 ---- */
  function buildScreen(group, W, H) {
    if (!matCache['screen']) {
      matCache['screen'] = new THREE.MeshStandardMaterial({
        color: '#3a3f45', transparent: true, opacity: 0.38, roughness: 0.9,
        side: THREE.DoubleSide, depthWrite: false,
      });
    }
    const fw = PROFILE.frameW;
    box(group, 0, 0, (PROFILE.frameD / 2 + 14), W - 2 * fw, H - 2 * fw, 2, matCache['screen'], false);
  }

  /* ---- 单格渲染分发 ---- */
  function buildCell(parent, rect, state, frameMat, glassMat) {
    const { type, params } = cellSpec(rect.cell);
    switch (type) {
      case 'fixed':
        buildFixed(parent, rect, glassMat);
        break;
      case 'casement':
        buildCasement(parent, rect, state, frameMat, glassMat, false, params.hinge);
        break;
      case 'tilt-turn': // 内开内倒：简化为平开展示
        buildCasement(parent, rect, state, frameMat, glassMat, false, params.hinge || 'left');
        break;
      case 'hinge-door':
        buildCasement(parent, rect, state, frameMat, glassMat, true, params.hinge);
        break;
      case 'top-hung':
        buildTopHung(parent, rect, state, frameMat, glassMat);
        break;
      case 'bottom-hung':
        buildBottomHung(parent, rect, state, frameMat, glassMat);
        break;
      case 'slide':
        buildSlide(parent, rect, state, frameMat, glassMat, false);
        break;
      case 'slide-door':
        buildSlide(parent, rect, state, frameMat, glassMat, true);
        break;
      case 'fold':
        buildFold(parent, rect, state, frameMat, glassMat);
        break;
      case 'louver':
        buildLouver(parent, rect, params, frameMat, false);
        break;
      case 'sealed-louver':
        buildSealedLouver(parent, rect, params, frameMat, glassMat);
        break;
      case 'grille':
        buildGrille(parent, rect, params, frameMat, glassMat, true);
        break;
      case 'glass-grille':
        buildGrille(parent, rect, params, frameMat, glassMat, true);
        break;
      case 'lattice':
        buildLattice(parent, rect, params, frameMat);
        break;
      case 'security':
        buildSecurity(parent, rect, params);
        break;
      case 'solid':
        buildSolid(parent, rect, frameMat);
        break;
      default:
        buildFixed(parent, rect, glassMat);
    }
  }

  /* ---- 总入口：生成完整门窗 ---- */
  function buildProduct(state) {
    setProfile(state.frameThick);
    const group = new THREE.Group();
    const style = getStyleById(state.styleId);
    const W = state.w, H = state.h;
    const frameMat = getFrameMaterial(state.frameColor);
    const glassMat = getGlassMaterial(state.glass);

    addFrame(group, W, H, frameMat);
    addGrid(group, W, H, style, frameMat);

    const rects = cellRects(style, W, H);
    style.cells.forEach(cell => {
      buildCell(group, rects[cell.r + '-' + cell.c], state, frameMat, glassMat);
    });

    if (state.screen && style.cat === '窗') buildScreen(group, W, H);
    return group;
  }

  return { buildProduct, getStyleById };
})();
