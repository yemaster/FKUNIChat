import path from "node:path";
import { fileURLToPath } from "node:url";
import { exitWithChildCode, launchLocalElectron } from "./local-electron.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");

const electron = launchLocalElectron({
  cwd: projectRoot
});

exitWithChildCode(electron);
