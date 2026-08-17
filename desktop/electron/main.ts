import { app, BrowserWindow } from 'electron';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createServer } from 'node:net';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const devUrl = process.env.VITE_DEV_SERVER_URL || 'http://127.0.0.1:7777';
let backend: ChildProcess | null = null;
let runtimeApiUrl = '';

async function availablePort(): Promise<number> {
  return await new Promise((resolve, reject) => {
    const server = createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      const port = typeof address === 'object' && address ? address.port : 0;
      server.close((error) => error ? reject(error) : resolve(port));
    });
  });
}

function startBackend(port: number) {
  if (backend) return;
  const env = { ...process.env };
  env.CROSSBORDER_COWORK_HOST = '127.0.0.1';
  env.CROSSBORDER_COWORK_PORT = String(port);
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

function stopBackend() {
  if (!backend) return;
  const pid = backend.pid;
  if (pid && process.platform === 'win32') {
    const killer = spawn('taskkill', ['/pid', String(pid), '/t', '/f'], { windowsHide: true, stdio: 'ignore' });
    killer.unref();
  } else {
    backend.kill();
  }
  backend = null;
}

async function waitForBackend(apiUrl: string) {
  let lastError = '后端没有响应。';
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`${apiUrl}/health`);
      if (response.ok) {
        const health = await response.json() as Record<string, unknown>;
        if (health.app_id === 'crossborder-catalog-cowork' && health.protocol_name === 'agentteams' && health.protocol_version === 1) return;
        lastError = '后端身份或事件协议版本不匹配。';
      }
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(lastError);
}

function createWindow(apiUrl: string) {
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1080,
    minHeight: 680,
    backgroundColor: '#f4f1eb',
    webPreferences: { preload: path.join(__dirname, 'preload.mjs') },
  });
  if (!app.isPackaged) {
    const url = new URL(devUrl);
    url.searchParams.set('apiBaseUrl', apiUrl);
    void window.loadURL(url.toString());
  } else {
    void window.loadFile(path.join(__dirname, '../dist/index.html'), { query: { apiBaseUrl: apiUrl } });
  }
}

function createStartupFailureWindow(message: string) {
  const window = new BrowserWindow({ width: 720, height: 480, backgroundColor: '#f7f8fa' });
  const html = `<main style="font-family:system-ui;padding:48px;color:#172033"><h1>应用启动失败</h1><p>${message.replace(/[<>&]/g, '')}</p><p>请关闭其他旧版本应用后重试。</p></main>`;
  void window.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
}

app.whenReady().then(async () => {
  try {
    const port = await availablePort();
    const apiUrl = `http://127.0.0.1:${port}`;
    startBackend(port);
    await waitForBackend(apiUrl);
    runtimeApiUrl = apiUrl;
    createWindow(apiUrl);
  } catch (error) {
    createStartupFailureWindow(error instanceof Error ? error.message : String(error));
  }
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0 && runtimeApiUrl) createWindow(runtimeApiUrl);
  });
});

app.on('before-quit', () => {
  stopBackend();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
