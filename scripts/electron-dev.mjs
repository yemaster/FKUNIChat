import { spawn } from "node:child_process";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { exitWithChildCode, launchLocalElectron } from "./local-electron.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const vitePort = 5173;

function waitForVite(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;

  return new Promise((resolve, reject) => {
    function tryConnect() {
      const request = http.get(url, (response) => {
        response.resume();
        resolve();
      });

      request.on("error", () => {
        if (Date.now() > deadline) {
          reject(new Error("等待 Vite 开发服务器超时。"));
          return;
        }

        setTimeout(tryConnect, 300);
      });
    }

    tryConnect();
  });
}

const vite = spawn(/^win/.test(process.platform) ? "npm.cmd" : "npm", ["run", "dev"], {
  cwd: projectRoot,
  stdio: "inherit",
  shell: false
});

const shutdown = () => {
  if (!vite.killed) {
    vite.kill();
  }
};

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

await waitForVite(`http://127.0.0.1:${vitePort}`);

const electron = launchLocalElectron({
  cwd: projectRoot,
  env: {
    ELECTRON_RENDERER_URL: `http://127.0.0.1:${vitePort}`
  }
});

electron.on("exit", () => {
  shutdown();
});

exitWithChildCode(electron);
