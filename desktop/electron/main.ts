import { app, BrowserWindow } from 'electron';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const devUrl = process.env.VITE_DEV_SERVER_URL || 'http://127.0.0.1:7777';
const apiUrl = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
let backend: ChildProcess | null = null;

function startBackend() {
  if (backend) return;
  const env = { ...process.env };
  let command: string;
  let args: string[];
  let cwd: string;
  if (app.isPackaged) {
    cwd = process.resourcesPath;
    command = path.join(process.resourcesPath, 'prebuilt', process.platform === 'win32' ? 'crossborder-backend.exe' : 'crossborder-backend');
    if (!fs.existsSync(command)) throw new Error(`Packaged backend not found: ${command}`);
    args = [];
    env.CROSSBORDER_COWORK_BASE_DIR = process.resourcesPath;
    env.CROSSBORDER_COWORK_RUNTIME_DIR = app.getPath('userData');
  } else {
    cwd = path.resolve(__dirname, '../..');
    command = process.env.CROSSBORDER_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
    args = ['-m', 'crossborder_cowork.app'];
    env.CROSSBORDER_COWORK_BASE_DIR = cwd;
  }
  backend = spawn(command, args, {
    cwd,
    env,
    windowsHide: true,
    stdio: app.isPackaged ? 'ignore' : 'inherit',
  });
  backend.once('exit', () => { backend = null; });
}

async function waitForBackend() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`${apiUrl}/health`);
      if (response.ok) return;
    } catch {
      // The packaged backend may need several seconds to unpack on first launch.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}

function createWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1080,
    minHeight: 680,
    backgroundColor: '#f4f1eb',
    webPreferences: { preload: path.join(__dirname, 'preload.mjs') },
  });
  if (!app.isPackaged) void window.loadURL(devUrl);
  else void window.loadFile(path.join(__dirname, '../dist/index.html'));
}

app.whenReady().then(async () => {
  startBackend();
  await waitForBackend();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('before-quit', () => {
  backend?.kill();
  backend = null;
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
