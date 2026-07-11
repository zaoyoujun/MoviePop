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

const APP_ROOT = join(__dirname, '..')

function isVideoUrl(url) {
  return url.includes('/v/') || 
         url.includes('/p/') || 
         url.includes('/video/') || 
         url.includes('/play/') ||
         url.includes('.mp4') || 
         url.includes('.m3u8') ||
         url.includes('.flv') ||
         url.includes('.ts')
}

const BACKEND_PORT = process.env.MOVIEPOP_BACKEND_PORT || '18987'
const BACKEND_PORT_ARGUMENT = `--moviepop-backend-port=${BACKEND_PORT}`
const TEST_MODE = ['1', 'true'].includes(String(process.env.MOVIEPOP_TEST_MODE || '').toLowerCase())
const TEST_MODE_ARGUMENT = `--moviepop-test-mode=${TEST_MODE ? '1' : '0'}`

const getIconPath = () => {
  const packagedIcon = join(process.resourcesPath, 'icon.ico')
  const fallbackIcon = join(__dirname, '..', 'public', 'moviepop.ico')
  if (app.isPackaged && existsSync(packagedIcon)) return packagedIcon
  return fallbackIcon
}

const getBackendLaunch = () => {
  if (app.isPackaged) {
    return {
      command: join(process.resourcesPath, 'backend', 'MoviePopBackend.exe'),
      args: [],
      cwd: join(process.resourcesPath, 'backend'),
    }
  }

  // 开发模式始终运行源码后端。即使工作区已有构建产物，也不能启动旧的
  // backend-dist/MoviePopBackend.exe，否则后端源码改动不会在开发时生效。
  const virtualEnvPython = join(APP_ROOT, '.venv', 'Scripts', 'python.exe')
  return {
    command: process.env.MOVIEPOP_PYTHON || (existsSync(virtualEnvPython) ? virtualEnvPython : 'python'),
    args: ['backend/run.py'],
    cwd: APP_ROOT,
  }
}

const getBackendDataDir = () => {
  if (app.isPackaged) {
    const portableDir =
      process.env.PORTABLE_EXECUTABLE_DIR ||
      (process.env.PORTABLE_EXECUTABLE_FILE ? dirname(process.env.PORTABLE_EXECUTABLE_FILE) : '')

    if (portableDir) {
      return join(portableDir, 'MoviePopData', 'backend')
    }

    // 安装版与便携版都把数据放在可执行文件同级，便于用户把程序和资料
    // 一起迁移到任意磁盘，而不是写入系统用户目录。
    return join(dirname(process.execPath), 'MoviePopData', 'backend')
  }

  return join(APP_ROOT, 'MoviePopData', 'backend')
}

const startBackend = () => {
  if (backendProcess) return true

  const launch = getBackendLaunch()
  if (app.isPackaged && !existsSync(launch.command)) {
    console.warn(`MoviePop backend executable not found: ${launch.command}`)
    return false
  }

  const backendDataDir = getBackendDataDir()

  backendProcess = spawn(launch.command, launch.args, {
    cwd: launch.cwd,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      MOVIEPOP_BACKEND_PORT: BACKEND_PORT,
      MOVIEPOP_BACKEND_BASE_DIR: backendDataDir
    }
  })

  backendProcess.unref()

  forwardBackendOutput(backendProcess.stdout, console.log)
  forwardBackendOutput(backendProcess.stderr, console.error)

  backendProcess.on('exit', () => {
    backendProcess = null
  })

  backendProcess.on('error', (error) => {
    console.error(`MoviePop backend failed to start: ${error.message}`)
    backendProcess = null
  })

  return true
}

function forwardBackendOutput(stream, log) {
  if (!stream) return
  let pending = ''
  stream.setEncoding('utf8')
  stream.on('data', (chunk) => {
    pending += chunk
    const lines = pending.split(/\r?\n/)
    pending = lines.pop() || ''
    lines.filter(Boolean).forEach((line) => log(`[MoviePop backend] ${line}`))
  })
  stream.on('end', () => {
    if (pending) log(`[MoviePop backend] ${pending}`)
  })
}

const waitForBackend = (timeoutMs = 30000) => new Promise((resolve) => {
  const startedAt = Date.now()

  const check = () => {
    const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/api/health`, (res) => {
      res.resume()
      if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
        resolve(true)
      } else if (Date.now() - startedAt >= timeoutMs) {
        resolve(false)
      } else {
        setTimeout(check, 500)
      }
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
      additionalArguments: [BACKEND_PORT_ARGUMENT, TEST_MODE_ARGUMENT],
    },
  })

  if (app.isPackaged) {
    const indexPath = join(APP_ROOT, 'dist', 'renderer', 'index.html')
    mainWindow.loadFile(indexPath)
  } else {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL || 'http://localhost:5173')
    mainWindow.webContents.openDevTools()
  }

  mainWindow.webContents.on('new-window', (event, url) => {
    event.preventDefault()
    
    if (isVideoUrl(url)) {
      mainWindow.webContents.send('online:video-click', { url })
    } else {
      mainWindow.loadURL(url)
    }
  })

  mainWindow.webContents.on('will-navigate', (event, url) => {
    const parsedUrl = new URL(url)
    const allowedHosts = ['localhost', '127.0.0.1']
    
    if (!allowedHosts.includes(parsedUrl.hostname)) {
      if (isVideoUrl(url)) {
        event.preventDefault()
        mainWindow.webContents.send('online:video-click', { url })
      } else {
        event.preventDefault()
        mainWindow.loadURL(url)
      }
    }
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isVideoUrl(url)) {
      mainWindow.webContents.send('online:video-click', { url })
      return { action: 'deny' }
    }
    return {
      action: 'allow',
      overrideBrowserWindowOptions: {
        frame: true,
        parent: mainWindow,
        modal: true,
        width: 1200,
        height: 800,
        webPreferences: {
          nodeIntegration: false,
          contextIsolation: true,
          preload: join(__dirname, 'preload.cjs'),
          additionalArguments: [BACKEND_PORT_ARGUMENT, TEST_MODE_ARGUMENT],
        },
      },
    }
  })

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
  const backendStarted = startBackend()
  if (backendStarted) {
    const backendReady = await waitForBackend()
    if (!backendReady) {
      console.warn(`MoviePop backend did not become ready on port ${BACKEND_PORT}`)
    }
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

ipcMain.handle('online:extract-video', async (_event, url) => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/online/browse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
    return await response.json()
  } catch (error) {
    return { error: error.message }
  }
})

ipcMain.handle('online:play-video', (_event, videoInfo) => {
  if (mainWindow) {
    mainWindow.webContents.send('online:play-video', videoInfo)
  }
  return { success: true }
})
