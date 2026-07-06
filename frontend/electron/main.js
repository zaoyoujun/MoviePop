import { app, BrowserWindow, ipcMain, Menu } from 'electron'
import { existsSync } from 'fs'
import { join, dirname } from 'path'
import { spawn, spawnSync } from 'child_process'
import { fileURLToPath } from 'url'
import http from 'http'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

let mainWindow
let backendProcess

const BACKEND_PORT = process.env.MOVIEPOP_BACKEND_PORT || '18987'

const getIconPath = () => {
  const packagedIcon = join(process.resourcesPath, 'icon.ico')
  const fallbackIcon = join(__dirname, '..', 'build-resources', 'icon.ico')
  if (app.isPackaged && existsSync(packagedIcon)) return packagedIcon
  return fallbackIcon
}

const getBackendPath = () => (
  app.isPackaged
    ? join(process.resourcesPath, 'backend', 'MoviePopBackend.exe')
    : join(__dirname, '..', 'backend-dist', 'MoviePopBackend.exe')
)

const getBackendDataDir = () => {
  if (app.isPackaged) {
    const portableDir =
      process.env.PORTABLE_EXECUTABLE_DIR ||
      (process.env.PORTABLE_EXECUTABLE_FILE ? dirname(process.env.PORTABLE_EXECUTABLE_FILE) : '')

    if (portableDir) {
      return join(portableDir, 'MoviePopData', 'backend')
    }
  }

  return join(__dirname, '..', 'MoviePopData', 'backend')
}

const startBackend = () => {
  if (backendProcess) return

  const backendPath = getBackendPath()
  if (!existsSync(backendPath)) {
    console.warn(`MoviePop backend executable not found: ${backendPath}`)
    return
  }

  const backendDataDir = getBackendDataDir()

  backendProcess = spawn(backendPath, [], {
    cwd: dirname(backendPath),
    windowsHide: true,
    stdio: 'ignore',
    env: {
      ...process.env,
      MOVIEPOP_BACKEND_PORT: BACKEND_PORT,
      MOVIEPOP_BACKEND_BASE_DIR: backendDataDir
    }
  })

  backendProcess.unref()

  backendProcess.on('exit', () => {
    backendProcess = null
  })
}

const waitForBackend = (timeoutMs = 120000) => new Promise((resolve) => {
  const startedAt = Date.now()

  const check = () => {
    const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/api/movies/home?limit=1`, (res) => {
      res.resume()
      resolve(true)
    })

    req.on('error', () => {
      if (Date.now() - startedAt >= timeoutMs) {
        resolve(false)
        return
      }
      setTimeout(check, 500)
    })

    req.setTimeout(2000, () => {
      req.destroy()
    })
  }

  check()
})

const stopBackend = () => {
  if (backendProcess?.pid) {
    spawnSync('taskkill', ['/PID', String(backendProcess.pid), '/T', '/F'], { windowsHide: true })
    backendProcess = null
  }

  if (app.isPackaged) {
    spawnSync('taskkill', ['/IM', 'MoviePopBackend.exe', '/T', '/F'], { windowsHide: true })
  }
}

const createWindow = () => {
  const iconPath = getIconPath()

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 720,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    autoHideMenuBar: true,
    backgroundColor: '#030506',
    icon: iconPath,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: join(__dirname, 'preload.cjs'),
    },
  })

  if (app.isPackaged) {
    const indexPath = join(__dirname, '..', 'dist', 'renderer', 'index.html')
    mainWindow.loadFile(indexPath)
  } else {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL || 'http://localhost:5173')
    mainWindow.webContents.openDevTools()
  }

  mainWindow.on('maximize', () => {
    mainWindow.webContents.send('window:maximized', true)
  })

  mainWindow.on('unmaximize', () => {
    mainWindow.webContents.send('window:maximized', false)
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null)
  startBackend()
  if (app.isPackaged) {
    await waitForBackend()
  }
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('before-quit', () => {
  stopBackend()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

ipcMain.handle('get-app-path', () => {
  return app.getAppPath()
})

ipcMain.handle('window:minimize', () => {
  if (mainWindow) mainWindow.minimize()
})

ipcMain.handle('window:toggle-maximize', () => {
  if (!mainWindow) return false
  if (mainWindow.isMaximized()) {
    mainWindow.unmaximize()
    return false
  } else {
    mainWindow.maximize()
    return true
  }
})

ipcMain.handle('window:close', () => {
  if (mainWindow) mainWindow.close()
})

ipcMain.handle('window:is-maximized', () => {
  return mainWindow ? mainWindow.isMaximized() : false
})
