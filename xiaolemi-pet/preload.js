// 预加载:向渲染进程暴露接口
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('petApi', {
  setInteractive: (on) => ipcRenderer.send('set-interactive', !!on),
  resize: (w, h) => ipcRenderer.send('resize', w, h),
  quit: () => ipcRenderer.send('quit'),
});
