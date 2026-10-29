// 小蕾米桌面宠物:透明置顶小窗,读 ~/.codex/pets/xiaolemi 的 Codex 精灵图
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const os = require('os');

let win = null;

// 点击穿透切换:默认整窗穿透,鼠标移到宠物身体上才恢复交互
ipcMain.on('set-interactive', (_e, on) => {
  if (win && !win.isDestroyed()) {
    win.setIgnoreMouseEvents(!on, { forward: true });
  }
});

// 实时调整窗口尺寸(配合右键菜单放大/缩小)
ipcMain.on('resize', (_e, w, h) => {
  if (win && !win.isDestroyed()) {
    const { screen } = require('electron');
    const wa = screen.getPrimaryDisplay().workArea;
    win.setMinimumSize(w, h);
    win.setMaximumSize(w, h);
    win.setContentSize(w, h);
    // 保持右下角锚定
    win.setPosition(wa.x + wa.width - w - 60, wa.y + wa.height - h - 60);
  }
});

ipcMain.on('quit', () => app.quit());

const SCALE = 0.9;              // 用户要求:再缩小一倍
const W = Math.round(192 * SCALE);
const H = Math.round(208 * SCALE);
const PET_DIR = path.join(os.homedir(), '.codex', 'pets', 'xiaolemi');

app.whenReady().then(() => {
  const { screen } = require('electron');
  const wa = screen.getPrimaryDisplay().workArea;

  win = new BrowserWindow({
    width: W,
    height: H,
    x: wa.x + wa.width - W - 60,
    y: wa.y + wa.height - H - 60,
    useContentSize: true,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    webPreferences: {
      webSecurity: false,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });
  win.setAlwaysOnTop(true, 'screen-saver');
  // 锁定尺寸,防止被撑大
  win.setMinimumSize(W, H);
  win.setMaximumSize(W, H);
  win.setSize(W, H, false);
  win.setContentSize(W, H);
  // 默认整窗点击穿透(透明区域不挡下层应用)
  win.webContents.on('did-finish-load', () => {
    win.setIgnoreMouseEvents(true, { forward: true });
  });
  win.loadFile('index.html', { query: { pet: PET_DIR } });

  win.on('closed', () => app.quit());
});

app.on('window-all-closed', () => app.quit());
