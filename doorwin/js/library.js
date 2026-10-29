/* ============================================================
 * 门窗款式库：每种款式 = 分格布局(rows×cols) + 每格开启方式 + 默认尺寸
 * 类型说明：
 *   fixed      固定扇（不可开启，只有玻璃）
 *   casement   平开扇（hinge: left/right 铰链位置，可开启角度旋转）
 *   slide      推拉窗扇（两扇前后错位左右推拉）
 *   hinge-door 平开门扇（hinge: left/right）
 *   slide-door 推拉门扇（落地玻璃门扇）
 * 单位：mm
 * ============================================================ */

const STYLE_LIBRARY = [
  // ---------- 窗户 ----------
  { id: 'win-casement-1', name: '平开窗 · 单扇', cat: '窗', size: { w: 800, h: 1200 }, sill: 900,
    rows: 1, cols: 1,
    cells: [{ r: 0, c: 0, type: 'casement', hinge: 'left' }] },
  { id: 'win-casement-2', name: '平开窗 · 双扇', cat: '窗', size: { w: 1500, h: 1500 }, sill: 900,
    rows: 1, cols: 2,
    cells: [{ r: 0, c: 0, type: 'casement', hinge: 'left' },
            { r: 0, c: 1, type: 'casement', hinge: 'right' }] },
  { id: 'win-casement-3', name: '平开窗 · 三扇', cat: '窗', size: { w: 2100, h: 1500 }, sill: 900,
    rows: 1, cols: 3,
    cells: [{ r: 0, c: 0, type: 'casement', hinge: 'left' },
            { r: 0, c: 1, type: 'fixed' },
            { r: 0, c: 2, type: 'casement', hinge: 'right' }] },
  { id: 'win-casement-fixed', name: '平开窗 · 一固一开', cat: '窗', size: { w: 1500, h: 1500 }, sill: 900,
    rows: 1, cols: 2,
    cells: [{ r: 0, c: 0, type: 'fixed' },
            { r: 0, c: 1, type: 'casement', hinge: 'right' }] },
  { id: 'win-slide-2', name: '推拉窗 · 双轨', cat: '窗', size: { w: 1800, h: 1500 }, sill: 900,
    rows: 1, cols: 2,
    cells: [{ r: 0, c: 0, type: 'slide' }, { r: 0, c: 1, type: 'slide' }] },
  { id: 'win-slide-3', name: '推拉窗 · 三轨', cat: '窗', size: { w: 2400, h: 1500 }, sill: 900,
    rows: 1, cols: 3,
    cells: [{ r: 0, c: 0, type: 'slide' }, { r: 0, c: 1, type: 'slide' }, { r: 0, c: 2, type: 'slide' }] },
  { id: 'win-toplight', name: '上亮推拉窗', cat: '窗', size: { w: 1800, h: 1800 }, sill: 900,
    rows: 2, cols: 2,
    cells: [{ r: 0, c: 0, type: 'fixed' }, { r: 0, c: 1, type: 'fixed' },
            { r: 1, c: 0, type: 'slide' }, { r: 1, c: 1, type: 'slide' }] },
  { id: 'win-fixed', name: '观景固定窗', cat: '窗', size: { w: 1800, h: 1500 }, sill: 900,
    rows: 1, cols: 1,
    cells: [{ r: 0, c: 0, type: 'fixed' }] },

  // ---------- 门 ----------
  { id: 'door-single', name: '平开门 · 单扇', cat: '门', size: { w: 900, h: 2100 }, sill: 0,
    rows: 1, cols: 1, doorPanel: 'glass',
    cells: [{ r: 0, c: 0, type: 'hinge-door', hinge: 'left' }] },
  { id: 'door-double', name: '平开门 · 双扇', cat: '门', size: { w: 1500, h: 2100 }, sill: 0,
    rows: 1, cols: 2, doorPanel: 'glass',
    cells: [{ r: 0, c: 0, type: 'hinge-door', hinge: 'left' },
            { r: 0, c: 1, type: 'hinge-door', hinge: 'right' }] },
  { id: 'door-slide-2', name: '推拉门 · 双轨', cat: '门', size: { w: 1800, h: 2300 }, sill: 0,
    rows: 1, cols: 2, doorPanel: 'glass',
    cells: [{ r: 0, c: 0, type: 'slide-door' }, { r: 0, c: 1, type: 'slide-door' }] },
  { id: 'door-slide-3', name: '推拉门 · 三轨', cat: '门', size: { w: 2400, h: 2300 }, sill: 0,
    rows: 1, cols: 3, doorPanel: 'glass',
    cells: [{ r: 0, c: 0, type: 'slide-door' }, { r: 0, c: 1, type: 'slide-door' }, { r: 0, c: 2, type: 'slide-door' }] },
];

/* ---------- 型材系列（价格元/㎡，可在设置中修改） ---------- */
const FRAME_SERIES = [
  { id: 'aluminum', name: '断桥铝', price: 780, colorHint: '#d9d9d4' },
  { id: 'pvc', name: '塑钢', price: 420, colorHint: '#f2f2ee' },
  { id: 'wood-alu', name: '铝包木', price: 1680, colorHint: '#8a5a2b' },
];

/* ---------- 颜色 ---------- */
const FRAME_COLORS = [
  { name: '白色', hex: '#f2f2ee' },
  { name: '香槟金', hex: '#d6b98c' },
  { name: '银灰', hex: '#9aa0a6' },
  { name: '深灰', hex: '#4b5056' },
  { name: '咖啡棕', hex: '#6e4a2e' },
  { name: '黑色', hex: '#2e2e2e' },
  { name: '木纹棕', hex: '#8a5a2b' },
];

/* ---------- 玻璃（price 元/㎡ 加价） ---------- */
const GLASS_TYPES = [
  { id: 'clear', name: '单层白玻', opacity: 0.22, roughness: 0.06, tint: '#ffffff', price: 0 },
  { id: 'insulated', name: '中空白玻', opacity: 0.32, roughness: 0.06, tint: '#eef5ee', price: 90 },
  { id: 'lowe', name: 'LOW-E中空', opacity: 0.40, roughness: 0.08, tint: '#cfe0ea', price: 150 },
  { id: 'frosted', name: '磨砂玻璃', opacity: 0.42, roughness: 0.70, tint: '#ffffff', price: 60 },
  { id: 'coated', name: '镀膜玻璃', opacity: 0.40, roughness: 0.10, tint: '#b8ccd9', price: 120 },
];

/* ---------- 场景 ---------- */
const SCENES = [
  { id: 'indoor', name: '🏠 室内', icon: '🏠' },
  { id: 'outdoor', name: '🌆 室外', icon: '🌆' },
];

/* ============================================================
 * 零件库（自定义设计用）：每种零件 = 名称 + 可调参数定义
 * params: key 参数键 | type: range/select | min/max/step | options
 * 参数由用户在自定义设计器中调整，存进款式的 cells 里
 * ============================================================ */
const PART_TYPES = {
  /* ---- 开启方式 ---- */
  fixed:       { name: '固定玻璃', group: '开启', params: [] },
  casement:    { name: '平开扇', group: '开启', params: [
    { key: 'hinge', type: 'select', options: ['left', 'right'], labels: ['左开', '右开'], def: 'left' }] },
  'top-hung':    { name: '上悬扇', group: '开启', params: [] },
  'bottom-hung': { name: '下悬扇', group: '开启', params: [] },
  'tilt-turn':   { name: '内开内倒', group: '开启', params: [] },
  slide:       { name: '推拉扇', group: '开启', params: [] },
  fold:        { name: '折叠扇', group: '开启', params: [
    { key: 'panels', type: 'select', options: [2, 4], labels: ['2扇', '4扇'], def: 4 },
    { key: 'foldAngle', type: 'range', min: 10, max: 60, step: 5, def: 30 }] },
  'hinge-door':  { name: '平开门扇', group: '开启', params: [
    { key: 'hinge', type: 'select', options: ['left', 'right'], labels: ['左开', '右开'], def: 'left' }] },
  'slide-door':  { name: '推拉门扇', group: '开启', params: [] },

  /* ---- 面板 / 装饰 ---- */
  louver:        { name: '百叶', group: '面板', params: [
    { key: 'angle', type: 'range', min: -60, max: 60, step: 5, def: 35 },
    { key: 'spacing', type: 'range', min: 40, max: 140, step: 10, def: 70 },
    { key: 'bladeW', type: 'range', min: 40, max: 120, step: 10, def: 70 }] },
  'sealed-louver': { name: '中空百叶', group: '面板', params: [
    { key: 'angle', type: 'range', min: -60, max: 60, step: 5, def: 35 },
    { key: 'spacing', type: 'range', min: 30, max: 100, step: 5, def: 50 }] },
  grille:        { name: '格栅', group: '面板', params: [
    { key: 'dir', type: 'select', options: ['v', 'h', 'grid', 'diamond'], labels: ['竖格', '横格', '田字', '菱形'], def: 'v' },
    { key: 'count', type: 'range', min: 2, max: 10, step: 1, def: 4 },
    { key: 'thick', type: 'range', min: 15, max: 60, step: 5, def: 25 }] },
  'glass-grille': { name: '玻璃+格栅', group: '面板', params: [
    { key: 'dir', type: 'select', options: ['v', 'h', 'grid', 'diamond'], labels: ['竖格', '横格', '田字', '菱形'], def: 'grid' },
    { key: 'count', type: 'range', min: 1, max: 8, step: 1, def: 3 },
    { key: 'thick', type: 'range', min: 10, max: 40, step: 2, def: 18 }] },
  lattice:       { name: '花格', group: '面板', params: [
    { key: 'pattern', type: 'select', options: ['jing', 'diamond', 'cross'], labels: ['井字', '菱形', '十字'], def: 'jing' },
    { key: 'thick', type: 'range', min: 15, max: 60, step: 5, def: 22 }] },
  security:      { name: '防盗网', group: '面板', params: [
    { key: 'count', type: 'range', min: 4, max: 18, step: 1, def: 9 },
    { key: 'thick', type: 'range', min: 6, max: 20, step: 2, def: 10 }] },
  solid:         { name: '实板', group: '面板', params: [] },
};

/* 各零件的报价加价（元/㎡，可在设置中修改） */
const PART_PRICES = {
  louver: 180, 'sealed-louver': 260, grille: 120, 'glass-grille': 90,
  lattice: 100, security: 150, fold: 220, 'tilt-turn': 160, 'top-hung': 80, 'bottom-hung': 80,
};

/* ============================================================
 * 自建款式：存 localStorage（doorwin-styles）
 * ============================================================ */
const CUSTOM_KEY = 'doorwin-styles';
const CUSTOM_VER_KEY = 'doorwin-styles-ver';
const CUSTOM_DATA_VER = '2026-09-29-v3'; // 数据格式版本：升级后旧数据自动作废
let CUSTOM_STYLES = [];

function loadCustomStyles() {
  try {
    const ver = localStorage.getItem(CUSTOM_VER_KEY);
    const raw = localStorage.getItem(CUSTOM_KEY);
    if (raw && ver === CUSTOM_DATA_VER) {
      CUSTOM_STYLES = JSON.parse(raw);
    } else {
      CUSTOM_STYLES = []; // 旧版本数据：清空重来
      saveCustomStyles();
    }
  } catch (e) { CUSTOM_STYLES = []; }
  return CUSTOM_STYLES;
}
function saveCustomStyles() {
  try {
    localStorage.setItem(CUSTOM_KEY, JSON.stringify(CUSTOM_STYLES));
    localStorage.setItem(CUSTOM_VER_KEY, CUSTOM_DATA_VER);
  } catch (e) { /* ignore */ }
}
function addCustomStyle(style) {
  CUSTOM_STYLES = CUSTOM_STYLES.filter(s => s.id !== style.id);
  CUSTOM_STYLES.push(style);
  saveCustomStyles();
}
function removeCustomStyle(id) {
  CUSTOM_STYLES = CUSTOM_STYLES.filter(s => s.id !== id);
  saveCustomStyles();
}
function getStyleById(id) {
  return STYLE_LIBRARY.find(s => s.id === id) ||
         CUSTOM_STYLES.find(s => s.id === id) ||
         STYLE_LIBRARY[0];
}
