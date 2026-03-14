import { contextBridge, ipcRenderer } from "electron";

const windowCloseListeners = new Set();
const spawnedProcessListeners = new Set();
const ustcTokenProgressListeners = new Set();

ipcRenderer.on("window-close", () => {
  for (const listener of windowCloseListeners) {
    listener();
  }
});

ipcRenderer.on("spawned-process", (_event, detail) => {
  for (const listener of spawnedProcessListeners) {
    listener(detail);
  }
});

ipcRenderer.on("ustc-token-progress", (_event, detail) => {
  for (const listener of ustcTokenProgressListeners) {
    listener(detail);
  }
});

contextBridge.exposeInMainWorld("electronAPI", {
  isElectron: true,
  platform: process.platform,
  env: {
    os:
      process.platform === "win32"
        ? "Windows"
        : process.platform === "darwin"
          ? "Darwin"
          : process.platform === "linux"
            ? "Linux"
            : process.platform
  },
  getRuntimeInfo: () => ipcRenderer.invoke("runtime:get-info"),
  storageGet: (key) => ipcRenderer.invoke("storage:get", key),
  storageSet: (key, value) => ipcRenderer.invoke("storage:set", key, value),
  pathExists: (filePath) => ipcRenderer.invoke("fs:path-exists", filePath),
  readFile: (filePath) => ipcRenderer.invoke("fs:read-file", filePath),
  writeFile: (filePath, data) => ipcRenderer.invoke("fs:write-file", filePath, data),
  execCommand: (command, options) => ipcRenderer.invoke("os:exec-command", command, options),
  spawnProcess: (command, options) => ipcRenderer.invoke("os:spawn-process", command, options),
  getSpawnedProcesses: () => ipcRenderer.invoke("os:get-spawned-processes"),
  updateSpawnedProcess: (id, action) => ipcRenderer.invoke("os:update-spawned-process", id, action),
  openExternal: (url) => ipcRenderer.invoke("os:open-external", url),
  autoFetchUstcToken: (payload) => ipcRenderer.invoke("ustc:auto-fetch-token", payload),
  exitApp: () => ipcRenderer.invoke("app:exit"),
  onWindowClose(listener) {
    windowCloseListeners.add(listener);
    return () => windowCloseListeners.delete(listener);
  },
  onSpawnedProcess(listener) {
    spawnedProcessListeners.add(listener);
    return () => spawnedProcessListeners.delete(listener);
  },
  onUstcTokenProgress(listener) {
    ustcTokenProgressListeners.add(listener);
    return () => ustcTokenProgressListeners.delete(listener);
  }
});
