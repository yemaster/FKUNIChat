import { app, BrowserWindow, ipcMain, shell } from "electron";
import { exec, spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sourceRoot = path.resolve(__dirname, "..");
const appRoot = app.getAppPath();
const userDataPath = app.getPath("userData");
const runtimeDataPath = path.join(userDataPath, "runtime");
const serviceRoot = app.isPackaged
  ? path.join(process.resourcesPath, "service")
  : path.join(sourceRoot, "service");
const rendererDistDir = path.join(appRoot, "dist", "renderer");
const iconPath = path.join(appRoot, "resources", "icons", "appIcon.png");
const storePath = path.join(app.getPath("userData"), "electron-store.json");

let mainWindow = null;
let allowAppQuit = false;
let nextProcessId = 1;
let quitAfterCleanup = false;
let cleanupPromise = null;
const spawnedProcesses = new Map();

function mapOsName(platform) {
  if (platform === "win32") {
    return "Windows";
  }

  if (platform === "darwin") {
    return "Darwin";
  }

  if (platform === "linux") {
    return "Linux";
  }

  return platform || "Unknown";
}

function sendToRenderer(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, payload);
  }
}

async function readStore() {
  try {
    const content = await fs.readFile(storePath, "utf-8");
    return JSON.parse(content);
  } catch {
    return {};
  }
}

async function writeStore(data) {
  await fs.mkdir(path.dirname(storePath), { recursive: true });
  await fs.writeFile(storePath, JSON.stringify(data, null, 2), "utf-8");
}

async function ensureRuntimeDataPath() {
  await fs.mkdir(runtimeDataPath, { recursive: true });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 720,
    minWidth: 960,
    minHeight: 640,
    center: true,
    show: false,
    autoHideMenuBar: true,
    icon: iconPath,
    webPreferences: {
      preload: path.join(__dirname, "preload.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("close", (event) => {
    if (allowAppQuit) {
      return;
    }

    event.preventDefault();
    sendToRenderer("window-close");
  });

  const devServerUrl = process.env.ELECTRON_RENDERER_URL;
  if (devServerUrl) {
    mainWindow.loadURL(devServerUrl);
    return;
  }

  mainWindow.loadFile(path.join(rendererDistDir, "index.html"));
}

function createExecResult({ pid = 0, stdOut = "", stdErr = "", exitCode = 0 }) {
  return {
    pid,
    stdOut,
    stdErr,
    exitCode
  };
}

function spawnShellCommand(command, options = {}) {
  return spawn(command, {
    cwd: options.cwd || runtimeDataPath,
    shell: true,
    windowsHide: true,
    detached: false
  });
}

async function killProcessTree(pid) {
  if (!pid) {
    return;
  }

  if (process.platform === "win32") {
    await new Promise((resolve) => {
      exec(`taskkill /PID ${pid} /T /F`, { windowsHide: true }, () => resolve());
    });
    return;
  }

  try {
    process.kill(-pid, "SIGTERM");
  } catch {
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      // Ignore kill failures.
    }
  }
}

async function cleanupSpawnedProcesses() {
  if (cleanupPromise) {
    return cleanupPromise;
  }

  cleanupPromise = (async () => {
    const children = Array.from(spawnedProcesses.values());
    spawnedProcesses.clear();
    await Promise.all(children.map((child) => killProcessTree(child.pid)));
  })();

  try {
    await cleanupPromise;
  } finally {
    cleanupPromise = null;
  }
}

async function autoFetchUstcToken({ requestId, timeoutMs = 180000 }) {
  return new Promise((resolve, reject) => {
    let resolved = false;
    let lastSignature = "";
    let pollTimer = null;
    let timeoutTimer = null;
    let childWindow = null;

    function sendProgress(payload) {
      const signature = JSON.stringify({
        stage: payload?.stage || "",
        status: payload?.status || "",
        href: payload?.href || "",
        isLogin: Boolean(payload?.isLogin),
        hasToken: Boolean(payload?.hasToken || payload?.token),
        tokenLength: Number(payload?.tokenLength || 0),
        message: payload?.message || ""
      });

      if (signature === lastSignature) {
        return;
      }

      lastSignature = signature;
      sendToRenderer("ustc-token-progress", {
        requestId,
        ...payload
      });
    }

    function cleanup() {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }

      if (timeoutTimer) {
        clearTimeout(timeoutTimer);
        timeoutTimer = null;
      }

      if (childWindow && !childWindow.isDestroyed()) {
        childWindow.removeAllListeners();
      }
    }

    async function inspectPage(stage) {
      if (!childWindow || childWindow.isDestroyed()) {
        return;
      }

      try {
        const payload = await childWindow.webContents.executeJavaScript(
          `(() => {
            try {
              const raw = window.localStorage.getItem("ustchat-user-store");
              if (!raw) {
                return {
                  status: "progress",
                  stage: ${JSON.stringify(stage)},
                  href: window.location.href,
                  title: document.title || "",
                  hasStore: false
                };
              }

              const parsed = JSON.parse(raw);
              const state = parsed?.state || {};
              const token = String(state.token || "");

              return {
                status: state.isLogin && token ? "token" : "progress",
                stage: state.isLogin && token ? "captured" : ${JSON.stringify(stage)},
                href: window.location.href,
                title: document.title || "",
                hasStore: true,
                isLogin: Boolean(state.isLogin),
                hasToken: Boolean(token),
                token,
                tokenLength: token.length,
                rawLength: raw.length,
                stateKeys: Object.keys(state)
              };
            } catch (error) {
              return {
                status: "error",
                stage: "inspect_failed",
                href: window.location.href,
                title: document.title || "",
                message: error?.message || String(error || "unknown_error")
              };
            }
          })()`,
          true
        );

        sendProgress(payload);

        if (payload?.status === "token" && String(payload?.token || "").trim()) {
          resolved = true;
          cleanup();
          if (childWindow && !childWindow.isDestroyed()) {
            childWindow.close();
          }
          resolve(String(payload.token).trim());
        }
      } catch (error) {
        sendProgress({
          status: "error",
          stage: "execute_failed",
          href: childWindow.webContents.getURL(),
          message: error?.message || String(error || "unknown_error")
        });
      }
    }

    childWindow = new BrowserWindow({
      width: 1180,
      height: 800,
      minWidth: 980,
      minHeight: 680,
      center: true,
      autoHideMenuBar: true,
      parent: mainWindow || undefined,
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true
      }
    });

    sendProgress({
      status: "progress",
      stage: "window_created"
    });

    childWindow.webContents.on("did-start-loading", () => {
      sendProgress({
        status: "progress",
        stage: "did_start_loading",
        href: childWindow.webContents.getURL()
      });
    });

    childWindow.webContents.on("did-finish-load", () => {
      sendProgress({
        status: "progress",
        stage: "did_finish_load",
        href: childWindow.webContents.getURL(),
        title: childWindow.getTitle()
      });
      void inspectPage("did_finish_load");
    });

    childWindow.webContents.on("did-navigate", (_event, url) => {
      sendProgress({
        status: "progress",
        stage: "did_navigate",
        href: url
      });
      void inspectPage("did_navigate");
    });

    childWindow.webContents.on("did-navigate-in-page", (_event, url) => {
      sendProgress({
        status: "progress",
        stage: "did_navigate_in_page",
        href: url
      });
      void inspectPage("did_navigate_in_page");
    });

    childWindow.on("closed", () => {
      if (resolved) {
        return;
      }

      cleanup();
      reject(new Error("token 获取失败：自动获取窗口已关闭，且未检测到有效 token。"));
    });

    pollTimer = setInterval(() => {
      void inspectPage("poll");
    }, 1000);

    timeoutTimer = setTimeout(() => {
      if (resolved) {
        return;
      }

      cleanup();
      if (childWindow && !childWindow.isDestroyed()) {
        childWindow.close();
      }
      reject(new Error("在规定时间内未获取到 token。"));
    }, Math.max(5000, Number(timeoutMs) || 180000));

    childWindow.loadURL("https://chat.ustc.edu.cn/ustchat/");
  });
}

ipcMain.handle("runtime:get-info", async () => ({
  os: mapOsName(process.platform),
  platform: process.platform,
  cwd: runtimeDataPath,
  appPath: appRoot,
  sourcePath: sourceRoot,
  servicePath: serviceRoot,
  dataPath: runtimeDataPath,
  isPackaged: app.isPackaged,
  tempPath: app.getPath("temp"),
  userDataPath,
  appId: app.getName(),
  appVersion: app.getVersion()
}));

ipcMain.handle("storage:get", async (_event, key) => {
  const store = await readStore();
  return store[key] ?? "";
});

ipcMain.handle("storage:set", async (_event, key, value) => {
  const store = await readStore();
  store[key] = value;
  await writeStore(store);
  return true;
});

ipcMain.handle("fs:path-exists", async (_event, filePath) => {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
});
ipcMain.handle("fs:read-file", async (_event, filePath) => fs.readFile(filePath, "utf-8"));
ipcMain.handle("fs:write-file", async (_event, filePath, data) => {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, data, "utf-8");
  return true;
});

ipcMain.handle("os:exec-command", async (_event, command, options = {}) => {
  if (options.background) {
    const child = spawn(command, {
      cwd: options.cwd || runtimeDataPath,
      shell: true,
      detached: true,
      windowsHide: true,
      stdio: "ignore"
    });
    child.unref();
    return createExecResult({ pid: child.pid, exitCode: 0 });
  }

  return new Promise((resolve) => {
    const child = exec(command, {
      cwd: options.cwd || runtimeDataPath,
      windowsHide: true,
      maxBuffer: 16 * 1024 * 1024
    }, (error, stdout, stderr) => {
      resolve(
        createExecResult({
          pid: child.pid || 0,
          stdOut: stdout || "",
          stdErr: stderr || "",
          exitCode: typeof error?.code === "number" ? error.code : 0
        })
      );
    });
  });
});

ipcMain.handle("os:spawn-process", async (_event, command, options = {}) => {
  const child = spawnShellCommand(command, options);
  const id = nextProcessId;
  nextProcessId += 1;

  spawnedProcesses.set(id, child);

  child.stdout?.on("data", (data) => {
    sendToRenderer("spawned-process", {
      id,
      action: "stdOut",
      data: data.toString()
    });
  });

  child.stderr?.on("data", (data) => {
    sendToRenderer("spawned-process", {
      id,
      action: "stdErr",
      data: data.toString()
    });
  });

  child.on("exit", (code) => {
    spawnedProcesses.delete(id);
    sendToRenderer("spawned-process", {
      id,
      action: "exit",
      data: code ?? 0
    });
  });

  return {
    id,
    pid: child.pid || 0
  };
});

ipcMain.handle("os:get-spawned-processes", async () =>
  Array.from(spawnedProcesses.entries()).map(([id, child]) => ({
    id,
    pid: child.pid || 0
  }))
);

ipcMain.handle("os:update-spawned-process", async (_event, id, action) => {
  const child = spawnedProcesses.get(id);
  if (!child) {
    return false;
  }

  if (action === "exit") {
    await killProcessTree(child.pid);
  }

  return true;
});

ipcMain.handle("os:open-external", async (_event, url) => {
  await shell.openExternal(url);
  return true;
});

ipcMain.handle("app:exit", async () => {
  allowAppQuit = true;
  app.quit();
  return true;
});

ipcMain.handle("ustc:auto-fetch-token", async (_event, payload) => autoFetchUstcToken(payload || {}));

app.whenReady().then(() => {
  void ensureRuntimeDataPath().catch(() => {});
  createMainWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on("before-quit", (event) => {
  if (quitAfterCleanup) {
    allowAppQuit = true;
    return;
  }

  event.preventDefault();
  allowAppQuit = true;

  void cleanupSpawnedProcesses().finally(() => {
    quitAfterCleanup = true;
    app.quit();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
