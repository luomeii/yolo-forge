/**
 * YOLO-Forge SP — Electron Main Process Entry
 *
 * Architecture follows Codex CLI / Claude Code patterns:
 * - Main process owns agent loop, tool execution, file system access
 * - Renderer process is pure UI (React)
 * - IPC bridge for structured communication
 * - Python worker subprocess for YOLO compute operations
 */

import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron';
import path from 'path';
import { registerIpcHandlers } from './ipc/handlers';
import { AgentOrchestrator } from './agent/orchestrator';
import { PythonWorkerManager } from './workers/python-manager';
import { Store } from './store';

let mainWindow: BrowserWindow | null = null;
let agentOrchestrator: AgentOrchestrator | null = null;
let pythonManager: PythonWorkerManager | null = null;
let store: Store | null = null;

const isDev = !app.isPackaged;

async function createWindow() {
  // Initialize persistent store
  store = new Store();
  await store.init();

  // Initialize Python worker manager
  pythonManager = new PythonWorkerManager();
  await pythonManager.start();

  // Forward Python worker events to renderer
  pythonManager.on('trainProgress', (progress: any) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('yolo:trainProgress', progress);
    }
  });
  pythonManager.on('trainComplete', (result: any) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('yolo:trainComplete', result);
    }
  });

  // Initialize Agent Orchestrator
  agentOrchestrator = new AgentOrchestrator(store, pythonManager);

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: 'YOLO-Forge SP',
    backgroundColor: '#F9FBF7',
    ...(process.platform === 'darwin' ? { titleBarStyle: 'hiddenInset' as const, trafficLightPosition: { x: 16, y: 16 } } : {}),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: false,  // Allow file:// URLs for Reviewer image loading
      allowRunningInsecureContent: true,
    },
  });

  // Register all IPC handlers
  registerIpcHandlers(mainWindow, agentOrchestrator, pythonManager, store);

  // Load the app
  if (isDev) {
    await mainWindow.loadURL('http://localhost:5173');
    // DevTools: press Ctrl+Shift+I (Win/Linux) or Cmd+Option+I (Mac) to open
    // mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    await mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
    agentOrchestrator?.dispose();
    pythonManager?.stop();
  });

  // Security: prevent new window creation
  mainWindow.webContents.setWindowOpenHandler(() => {
    return { action: 'deny' };
  });

  // Open external links in system browser
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (url !== mainWindow!.webContents.getURL()) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  agentOrchestrator?.dispose();
  pythonManager?.stop();
});
