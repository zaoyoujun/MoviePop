import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  getAppPath: () => ipcRenderer.invoke('get-app-path'),
  minimizeWindow: () => ipcRenderer.invoke('window:minimize'),
  toggleMaximizeWindow: () => ipcRenderer.invoke('window:toggle-maximize'),
  closeWindow: () => ipcRenderer.invoke('window:close'),
  isWindowMaximized: () => ipcRenderer.invoke('window:is-maximized'),
  onWindowMaximized: (callback) => {
    const listener = (_event, value) => callback(Boolean(value))
    ipcRenderer.on('window:maximized', listener)
    return () => ipcRenderer.removeListener('window:maximized', listener)
  },
  extractVideoInfo: (url) => ipcRenderer.invoke('online:extract-video', url),
  playVideo: (videoInfo) => ipcRenderer.invoke('online:play-video', videoInfo),
  onVideoClick: (callback) => {
    const listener = (_event, data) => callback(data)
    ipcRenderer.on('online:video-click', listener)
    return () => ipcRenderer.removeListener('online:video-click', listener)
  },
})
