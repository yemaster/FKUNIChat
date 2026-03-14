import { spawn } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function getLocalElectronPackage() {
  try {
    return require("electron/package.json");
  } catch (error) {
    throw new Error(`未找到本地 Electron 依赖，请先执行 npm install。${error?.message ? ` (${error.message})` : ""}`);
  }
}

export function launchLocalElectron({
  args = ["."],
  cwd = process.cwd(),
  env = {}
} = {}) {
  const electronBinary = require("electron");
  const electronPackage = getLocalElectronPackage();

  console.log(`[electron] using local electron ${electronPackage.version} on node ${process.version}`);

  const child = spawn(electronBinary, args, {
    cwd,
    stdio: "inherit",
    shell: false,
    env: {
      ...process.env,
      ...env
    }
  });

  child.on("error", (error) => {
    console.error(`[electron] failed to start local electron: ${error?.message || String(error)}`);
  });

  return child;
}

export function exitWithChildCode(child) {
  const shutdown = (signal) => {
    if (!child.killed) {
      child.kill(signal);
    }
  };

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));

  child.on("exit", (code, signal) => {
    if (code === null) {
      console.error(`[electron] exited with signal ${signal || "unknown"}`);
      process.exit(1);
      return;
    }

    process.exit(code);
  });
}
