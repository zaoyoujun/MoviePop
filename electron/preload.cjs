const { contextBridge, ipcRenderer } = require('electron')

const portArgument = process.argv.find((argument) => argument.startsWith('--moviepop-backend-port='))
const configuredBackendPort = portArgument?.split('=', 2)[1]
const backendPort = /^(?:[1-9]\d{0,3}|[1-5]\d{4}|6(?:[0-4]\d{3}|5(?:[0-4]\d{2}|5(?:[0-2]\d|3[0-5]))))$/.test(configuredBackendPort || '')
  ? configuredBackendPort
  : '18987'

contextBridge.exposeInMainWorld('electronAPI', {
  getBackendPort: () => backendPort,
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
