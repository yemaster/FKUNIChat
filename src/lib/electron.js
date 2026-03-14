const STORAGE_KEY = "fkunichat-console-state";
const RUNTIME_STATE_FILENAME = "fkunichat-runtime-state.json";
const VENV_DIRNAME = "venv";
const REQUIREMENTS_FILE = "requirements.txt";
const DEFAULT_REQUIREMENT_IMPORTS = ["flask", "requests"];

let runtimeInfoPromise = null;

function hasElectronRuntime() {
  return (
    typeof window !== "undefined" &&
    typeof globalThis.electronAPI !== "undefined" &&
    globalThis.electronAPI?.isElectron === true
  );
}

async function getRuntimeInfo() {
  if (!hasElectronRuntime()) {
    return {
      os: "Unknown",
      cwd: "",
      appPath: "",
      tempPath: "",
      appId: "browser-preview",
      appVersion: __APP_VERSION__
    };
  }

  if (!runtimeInfoPromise) {
    runtimeInfoPromise = globalThis.electronAPI.getRuntimeInfo();
  }

  return runtimeInfoPromise;
}

export async function waitForElectronRuntime(timeoutMs = 1600, intervalMs = 50) {
  const deadline = Date.now() + Math.max(0, timeoutMs);

  while (Date.now() <= deadline) {
    if (hasElectronRuntime()) {
      return true;
    }

    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }

  return hasElectronRuntime();
}

function normalizeApiKey(entry, index = 0) {
  const createdAt = Number(entry?.createdAt) || Date.now();
  const id = String(entry?.id || `key-${createdAt}-${index}`);

  return {
    id,
    label: String(entry?.label || `密钥 ${index + 1}`),
    value: String(entry?.value || ""),
    createdAt,
    expiresAt: entry?.expiresAt === null || entry?.expiresAt === undefined ? null : Number(entry.expiresAt),
    maxUsage: entry?.maxUsage === undefined ? -1 : Number(entry.maxUsage),
    usageCount: entry?.usageCount === undefined ? 0 : Number(entry.usageCount)
  };
}

const createDefaultConfig = () => ({
  selectedPage: "setup",
  sidebarCollapsed: false,
  selectedApiKeyId: "default",
  selectedModel: "deepseek-r1",
  listenHost: "127.0.0.1",
  themeColor: "#0ea5e9",
  themeMode: "light",
  setupAcceptedPrivacy: false,
  setupAcceptedServiceTerms: false,
  setupCompleted: false,
  ustcToken: "",
  apiKeys: [
    normalizeApiKey({ id: "default", label: "默认密钥", value: "" })
  ],
  port: "28080"
});

function normalizeConfigPayload(parsed) {
  const defaults = createDefaultConfig();
  const apiKeys =
    Array.isArray(parsed?.apiKeys) && parsed.apiKeys.length > 0
      ? parsed.apiKeys.map((item, index) => normalizeApiKey(item, index))
      : defaults.apiKeys;

  const normalized = {
    ...defaults,
    ...parsed,
    apiKeys
  };

  if (normalized.selectedPage === "about") {
    normalized.selectedPage = "settings";
  }

  if (!["light", "dark", "system"].includes(normalized.themeMode)) {
    normalized.themeMode = defaults.themeMode;
  }

  if (!["127.0.0.1", "0.0.0.0"].includes(normalized.listenHost)) {
    normalized.listenHost = defaults.listenHost;
  }

  return normalized;
}

export function loadConfig() {
  const saved = globalThis.localStorage?.getItem(STORAGE_KEY);

  if (!saved) {
    return createDefaultConfig();
  }

  try {
    return normalizeConfigPayload(JSON.parse(saved));
  } catch {
    return createDefaultConfig();
  }
}

export function saveConfig(config) {
  const serialized = JSON.stringify(config);
  globalThis.localStorage?.setItem(STORAGE_KEY, serialized);

  if (hasElectronRuntime()) {
    void globalThis.electronAPI.storageSet(STORAGE_KEY, serialized).catch(() => {});
  }
}

export async function hydrateConfig(targetConfig) {
  if (!hasElectronRuntime()) {
    return false;
  }

  try {
    const saved = await globalThis.electronAPI.storageGet(STORAGE_KEY);
    if (!saved) {
      return false;
    }

    const normalized = normalizeConfigPayload(JSON.parse(saved));
    Object.assign(targetConfig, normalized);
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(normalized));
    return true;
  } catch {
    return false;
  }
}

function normalizePath(value) {
  const input = String(value || "");
  if (!input) {
    return "";
  }

  if (globalThis.electronAPI?.platform === "win32") {
    return input.replace(/\//g, "\\");
  }

  return input.replace(/\\/g, "/");
}

function joinPath(basePath, targetPath) {
  if (!basePath) {
    return normalizePath(targetPath);
  }

  const isWindows = globalThis.electronAPI?.platform === "win32";
  const separator = basePath.endsWith("\\") || basePath.endsWith("/") ? "" : isWindows ? "\\" : "/";
  return `${normalizePath(basePath)}${separator}${normalizePath(targetPath)}`;
}

function quoteForShell(value) {
  const input = String(value ?? "");

  if (globalThis.electronAPI?.platform === "win32") {
    return `"${input.replace(/"/g, '\\"')}"`;
  }

  return `'${input.replace(/'/g, `'\\''`)}'`;
}

function quotePythonSnippet(value) {
  const input = String(value ?? "");

  if (globalThis.electronAPI?.platform === "win32") {
    return `"${input.replace(/"/g, '""')}"`;
  }

  return `'${input.replace(/'/g, `'\\''`)}'`;
}

async function runCommand(command, options = {}) {
  if (!hasElectronRuntime()) {
    throw new Error("当前不在桌面运行时中，无法调用本地命令。");
  }

  return globalThis.electronAPI.execCommand(command, options);
}

async function pathExists(filePath) {
  if (!hasElectronRuntime()) {
    return false;
  }

  try {
    return await globalThis.electronAPI.pathExists(filePath);
  } catch {
    return false;
  }
}

function buildPortCheckCommand(port) {
  const safePort = Number(port);

  if (!Number.isInteger(safePort) || safePort < 1 || safePort > 65535) {
    throw new Error("端口号不合法。");
  }

  if (globalThis.electronAPI?.platform === "win32") {
    return `cmd /C netstat -ano | findstr LISTENING | findstr :${safePort}`;
  }

  return `sh -lc "lsof -iTCP:${safePort} -sTCP:LISTEN -P -n >/dev/null 2>&1 || ss -ltn '( sport = :${safePort} )' 2>/dev/null | tail -n +2 | grep -q . || netstat -an 2>/dev/null | grep -E 'LISTEN|LISTENING' | grep -q '[\\.:]${safePort}[[:space:]]'"`;
}

function buildKillProcessCommand(pid) {
  const safePid = Number(pid);

  if (!Number.isInteger(safePid) || safePid < 1) {
    throw new Error("进程 PID 不合法。");
  }

  if (globalThis.electronAPI?.platform === "win32") {
    return `cmd /C taskkill /PID ${safePid} /T /F`;
  }

  return `sh -lc "pkill -TERM -P ${safePid} >/dev/null 2>&1 || true; for child in $(pgrep -P ${safePid} 2>/dev/null); do kill -TERM \"$child\" >/dev/null 2>&1 || true; done; kill -TERM ${safePid} >/dev/null 2>&1 || true"`;
}

export async function isPortAvailable(port) {
  if (!hasElectronRuntime()) {
    return true;
  }

  const result = await runCommand(buildPortCheckCommand(port));
  return result.exitCode !== 0;
}

let systemPythonInfoPromise = null;
let requirementImportsPromise = null;
let venvPythonInfoPromise = null;

async function getProjectPythonPaths() {
  const runtimeInfo = await getRuntimeInfo();
  const dataPath = runtimeInfo.dataPath || runtimeInfo.userDataPath || runtimeInfo.appPath;
  const servicePath = runtimeInfo.servicePath || joinPath(runtimeInfo.appPath, "service");
  const venvDir = joinPath(dataPath, VENV_DIRNAME);
  const venvPython = globalThis.electronAPI?.platform === "win32"
    ? joinPath(dataPath, `${VENV_DIRNAME}/Scripts/python.exe`)
    : joinPath(dataPath, `${VENV_DIRNAME}/bin/python`);

  return {
    appPath: runtimeInfo.appPath,
    dataPath,
    servicePath,
    venvDir,
    venvPython,
    requirementsPath: joinPath(servicePath, REQUIREMENTS_FILE)
  };
}

async function getRequirementImports(force = false) {
  if (!hasElectronRuntime()) {
    return [...DEFAULT_REQUIREMENT_IMPORTS];
  }

  if (force) {
    requirementImportsPromise = null;
  }

  if (!requirementImportsPromise) {
    requirementImportsPromise = (async () => {
      try {
        const { requirementsPath } = await getProjectPythonPaths();
        const content = await globalThis.electronAPI.readFile(requirementsPath);
        return parseRequirementImports(content);
      } catch {
        return [...DEFAULT_REQUIREMENT_IMPORTS];
      }
    })();
  }

  return requirementImportsPromise;
}

async function detectSystemPython(force = false) {
  if (!hasElectronRuntime()) {
    return {
      available: true,
      command: navigator.platform?.startsWith("Win") ? "python" : "python3",
      version: "",
      executable: ""
    };
  }

  if (force) {
    systemPythonInfoPromise = null;
  }

  if (!systemPythonInfoPromise) {
    systemPythonInfoPromise = (async () => {
      const candidates = globalThis.electronAPI?.platform === "win32"
        ? ["python", "py -3"]
        : ["python3", "python"];

      for (const command of candidates) {
        const versionResult = await runCommand(`${command} --version`);
        if (Number(versionResult?.exitCode || 0) !== 0) {
          continue;
        }

        const executableResult = await runCommand(
          `${command} -c ${quotePythonSnippet("import sys; print(sys.executable)")}`
        );
        const versionLine = extractCommandLines(versionResult)[0] || "";
        const executableLine = extractCommandLines(executableResult)[0] || "";

        return {
          available: true,
          command,
          version: versionLine.replace(/^Python\s+/i, ""),
          executable: executableLine
        };
      }

      return {
        available: false,
        command: "",
        version: "",
        executable: ""
      };
    })();
  }

  return systemPythonInfoPromise;
}

async function detectVenvPython(force = false) {
  if (!hasElectronRuntime()) {
    return {
      available: true,
      path: navigator.platform?.startsWith("Win") ? "python" : "python3",
      version: ""
    };
  }

  if (force) {
    venvPythonInfoPromise = null;
  }

  if (!venvPythonInfoPromise) {
    venvPythonInfoPromise = (async () => {
      const { venvDir, venvPython } = await getProjectPythonPaths();
      const markerPath = joinPath(venvDir, "pyvenv.cfg");
      const markerExists = await pathExists(markerPath);

      if (!markerExists) {
        return {
          available: false,
          path: venvPython,
          version: ""
        };
      }

      const versionResult = await runCommand(`${quoteForShell(venvPython)} --version`);
      if (Number(versionResult?.exitCode || 0) !== 0) {
        return {
          available: false,
          path: venvPython,
          version: ""
        };
      }

      const versionLine = extractCommandLines(versionResult)[0] || "";
      return {
        available: true,
        path: venvPython,
        version: versionLine.replace(/^Python\s+/i, "")
      };
    })();
  }

  return venvPythonInfoPromise;
}

async function ensureVenvPythonPath() {
  const venvPython = await detectVenvPython();
  if (venvPython.available) {
    return venvPython.path;
  }

  throw new Error("项目尚未完成初始化，请先创建 venv 并安装依赖。");
}

async function buildPythonCommand(scriptPath, args = []) {
  const launcher = await ensureVenvPythonPath();
  return `${quoteForShell(launcher)} -X utf8 ${quoteForShell(scriptPath)} ${args.map((item) => quoteForShell(item)).join(" ")}`.trim();
}

export async function inspectInitialization(force = false) {
  if (!hasElectronRuntime()) {
    return {
      supported: false,
      pythonAvailable: true,
      pythonVersion: "",
      pythonCommand: "",
      pythonExecutable: "",
      systemPythonAvailable: true,
      venvReady: true,
      venvPython: "",
      venvVersion: "",
      venvDirectory: "",
      requirementsPath: "",
      dependenciesInstalled: true,
      missingDependencies: []
    };
  }

  const [systemPython, venvPython, imports, paths] = await Promise.all([
    detectSystemPython(force),
    detectVenvPython(force),
    getRequirementImports(force),
    getProjectPythonPaths()
  ]);

  let dependenciesInstalled = false;
  let missingDependencies = [...imports];

  if (venvPython.available) {
    const importList = imports.map((item) => `'${item.replace(/'/g, "\\'")}'`).join(", ");
    const dependencyResult = await runCommand(
      `${quoteForShell(venvPython.path)} -X utf8 -c ${quotePythonSnippet(
        `import importlib.util, json; modules=[${importList}]; missing=[name for name in modules if importlib.util.find_spec(name) is None]; print(json.dumps({"installed": not missing, "missing": missing}))`
      )}`,
      { cwd: paths.dataPath }
    );

    if (Number(dependencyResult?.exitCode || 0) === 0) {
      try {
        const parsed = parseJsonOutput(dependencyResult);
        dependenciesInstalled = Boolean(parsed.installed);
        missingDependencies = Array.isArray(parsed.missing) ? parsed.missing.map((item) => String(item)) : [];
      } catch {
        dependenciesInstalled = false;
        missingDependencies = [...imports];
      }
    }
  }

  return {
    supported: true,
    pythonAvailable: Boolean(systemPython.available || venvPython.available),
    pythonVersion: systemPython.version || venvPython.version || "",
    pythonCommand: systemPython.command || (venvPython.available ? venvPython.path : ""),
    pythonExecutable: systemPython.executable || venvPython.path || "",
    systemPythonAvailable: Boolean(systemPython.available),
    venvReady: Boolean(venvPython.available),
    venvPython: paths.venvPython,
    venvVersion: venvPython.version || "",
    venvDirectory: paths.venvDir,
    requirementsPath: paths.requirementsPath,
    dependenciesInstalled,
    missingDependencies
  };
}

export async function createProjectVenv() {
  const { command, cwd } = await buildCreateProjectVenvCommand();
  const result = await runCommand(command, { cwd });
  ensureSuccessfulCommand(result, "创建 venv 失败");
  venvPythonInfoPromise = null;
  return {
    inspection: await inspectInitialization(true),
    logLines: collectRecentLogLines(result)
  };
}

export async function buildCreateProjectVenvCommand() {
  const systemPython = await detectSystemPython(true);
  if (!systemPython.available) {
    throw new Error("未找到可用的 Python，请先安装 Python。");
  }

  const { appPath, dataPath, venvDir } = await getProjectPythonPaths();
  return {
    command: `${systemPython.command} -m venv ${quoteForShell(venvDir)}`,
    cwd: dataPath || appPath
  };
}

export async function installProjectDependencies() {
  const { command, cwd } = await buildInstallProjectDependenciesCommand();
  const result = await runCommand(command, { cwd });
  ensureSuccessfulCommand(result, "安装依赖失败");
  return {
    inspection: await inspectInitialization(true),
    logLines: collectRecentLogLines(result)
  };
}

export async function buildInstallProjectDependenciesCommand() {
  const { appPath, dataPath, requirementsPath } = await getProjectPythonPaths();
  const venvPython = await ensureVenvPythonPath();
  return {
    command: `${quoteForShell(venvPython)} -m pip install -r ${quoteForShell(requirementsPath)}`,
    cwd: dataPath || appPath
  };
}

function parseJsonOutput(result) {
  const lines = `${result?.stdOut || ""}\n${result?.stdErr || ""}`
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try {
      return JSON.parse(lines[index]);
    } catch {
      // Ignore non-JSON lines.
    }
  }

  const rawOutput = `${result?.stdErr || ""}\n${result?.stdOut || ""}`.trim();
  if (rawOutput) {
    throw new Error(rawOutput);
  }

  throw new Error("本地命令未返回可解析输出。");
}

function ensureSuccessfulCommand(result, fallbackMessage) {
  if (Number(result?.exitCode || 0) === 0) {
    return;
  }

  const rawOutput = `${result?.stdErr || ""}\n${result?.stdOut || ""}`.trim();
  throw new Error(rawOutput || fallbackMessage);
}

function extractCommandLines(result) {
  return `${result?.stdOut || ""}\n${result?.stdErr || ""}`
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function collectRecentLogLines(result, limit = 3) {
  return extractCommandLines(result).slice(-Math.max(1, Number(limit) || 3));
}

function parseRequirementImports(content) {
  const entries = String(content || "")
    .split(/\r?\n/)
    .map((line) => line.split("#")[0].trim())
    .filter(Boolean)
    .map((line) => line.replace(/\[.*?\]/g, "").split(/[<>=!~]/)[0].trim())
    .filter(Boolean)
    .map((line) => line.replace(/-/g, "_"));

  return entries.length > 0 ? entries : [...DEFAULT_REQUIREMENT_IMPORTS];
}

let runtimeStatePathPromise = null;

async function getRuntimeStatePath() {
  if (!hasElectronRuntime()) {
    return "";
  }

  if (!runtimeStatePathPromise) {
    runtimeStatePathPromise = getRuntimeInfo().then((runtimeInfo) => {
      const basePath = runtimeInfo.dataPath || runtimeInfo.userDataPath || runtimeInfo.tempPath;
      return joinPath(basePath, RUNTIME_STATE_FILENAME);
    });
  }

  return runtimeStatePathPromise;
}

async function readRuntimeStateFile(statePath) {
  if (!(await pathExists(statePath))) {
    return { ustcToken: "", apiKeys: [] };
  }

  try {
    const payload = await globalThis.electronAPI.readFile(statePath);
    return JSON.parse(payload);
  } catch {
    return { ustcToken: "", apiKeys: [] };
  }
}

export async function syncRuntimeState(config) {
  if (!hasElectronRuntime()) {
    return "";
  }

  const statePath = await getRuntimeStatePath();
  const previous = await readRuntimeStateFile(statePath);
  const previousUsageMap = new Map(
    (previous.apiKeys || []).map((item) => [String(item.id), Number(item.usageCount) || 0])
  );

  const runtimeState = {
    ustcToken: String(config.ustcToken || ""),
    apiKeys: (config.apiKeys || []).map((item) => ({
      ...item,
      usageCount: Math.max(Number(item.usageCount) || 0, previousUsageMap.get(String(item.id)) || 0)
    }))
  };

  await globalThis.electronAPI.writeFile(statePath, JSON.stringify(runtimeState, null, 2));
  return statePath;
}

export async function checkUstcToken(token) {
  if (!token) {
    return { valid: false, reason: "missing_token", statusCode: null, contentType: "", bodyPreview: "" };
  }

  const runtimeReady = hasElectronRuntime() || await waitForElectronRuntime();
  if (!runtimeReady) {
    return {
      valid: false,
      reason: "browser_preview",
      statusCode: null,
      contentType: "",
      bodyPreview: "当前为浏览器预览环境，未执行本地 token 校验。"
    };
  }

  const runtimeInfo = await getRuntimeInfo();
  const servicePath = runtimeInfo.servicePath || joinPath(runtimeInfo.appPath, "service");
  const dataPath = runtimeInfo.dataPath || runtimeInfo.userDataPath || runtimeInfo.appPath;
  const command = await buildPythonCommand(joinPath(servicePath, "ustc_token_helper.py"), ["check", "--token", String(token)]);
  const result = await runCommand(command, { cwd: dataPath });
  ensureSuccessfulCommand(result, "Token 校验命令执行失败");
  const parsed = parseJsonOutput(result);

  if (!parsed.ok) {
    throw new Error(parsed.error || "Token 校验失败");
  }

  return {
    valid: Boolean(parsed.valid),
    reason: String(parsed.reason || ""),
    statusCode: parsed.statusCode ?? null,
    contentType: String(parsed.contentType || ""),
    bodyPreview: String(parsed.bodyPreview || "")
  };
}

export async function buildBundledServiceCommand(port, config) {
  const runtimeInfo = await getRuntimeInfo();
  const statePath = await syncRuntimeState(config);
  const servicePath = runtimeInfo.servicePath || joinPath(runtimeInfo.appPath, "service");
  const dataPath = runtimeInfo.dataPath || runtimeInfo.userDataPath || runtimeInfo.appPath;
  const listenHost = ["127.0.0.1", "0.0.0.0"].includes(String(config?.listenHost || ""))
    ? String(config.listenHost)
    : "127.0.0.1";
  const command = await buildPythonCommand(joinPath(servicePath, "ustc_service.py"), [
    "--port",
    String(port),
    "--host",
    listenHost,
    "--state-file",
    statePath
  ]);

  return {
    command,
    cwd: dataPath,
    statePath
  };
}

export async function probeLocalService(port) {
  const response = await fetch(`http://127.0.0.1:${port}/health`, {
    method: "GET",
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`健康检查失败: HTTP ${response.status}`);
  }

  return response.json().catch(() => ({}));
}

export async function openExternalUrl(url) {
  if (hasElectronRuntime()) {
    return globalThis.electronAPI.openExternal(url);
  }

  globalThis.open?.(url, "_blank", "noopener,noreferrer");
}

export async function fetchUstcTokenWithWebview(options = {}) {
  const normalizedOptions =
    typeof options === "number"
      ? { timeoutMs: options }
      : options || {};
  const timeoutMs = Number(normalizedOptions.timeoutMs || 180000);
  const onProgress =
    typeof normalizedOptions.onProgress === "function"
      ? normalizedOptions.onProgress
      : null;

  if (!hasElectronRuntime()) {
    throw new Error("自动获取仅支持 Electron 桌面环境。");
  }

  const requestId = `ustc-token-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const unsubscribe = globalThis.electronAPI.onUstcTokenProgress((payload) => {
    if (payload?.requestId !== requestId) {
      return;
    }

    onProgress?.(payload);
  });

  try {
    return await globalThis.electronAPI.autoFetchUstcToken({
      requestId,
      timeoutMs
    });
  } finally {
    unsubscribe?.();
  }
}

export async function startService(command, cwd) {
  if (!hasElectronRuntime()) {
    return {
      id: Date.now(),
      pid: 0
    };
  }

  return globalThis.electronAPI.spawnProcess(command, { cwd });
}

export async function getRunningProcesses() {
  if (!hasElectronRuntime()) {
    return [];
  }

  return globalThis.electronAPI.getSpawnedProcesses();
}

export async function stopService(id, pid = null) {
  if ((id === null || id === undefined) && (pid === null || pid === undefined)) {
    return;
  }

  if (!hasElectronRuntime()) {
    return;
  }

  let lastError = null;

  if (pid) {
    try {
      const result = await runCommand(buildKillProcessCommand(pid));
      if (Number(result?.exitCode || 0) === 0) {
        return;
      }

      lastError = new Error(`${result?.stdErr || result?.stdOut || "终止进程失败"}`.trim());
    } catch (error) {
      lastError = error;
    }
  }

  if (id !== null && id !== undefined) {
    try {
      await globalThis.electronAPI.updateSpawnedProcess(id, "exit");
      return;
    } catch (error) {
      lastError = error;
    }
  }

  if (lastError) {
    throw lastError;
  }
}

export function initElectronRuntime({ onWindowClose, onSpawnedProcess } = {}) {
  if (!hasElectronRuntime()) {
    return;
  }

  if (onWindowClose) {
    globalThis.electronAPI.onWindowClose(onWindowClose);
  }

  if (onSpawnedProcess) {
    globalThis.electronAPI.onSpawnedProcess((detail) => {
      onSpawnedProcess({ detail });
    });
  }
}

export function exitApp() {
  if (hasElectronRuntime()) {
    return globalThis.electronAPI.exitApp();
  }

  return Promise.resolve();
}

export function getEnvironmentLabel() {
  if (!hasElectronRuntime()) {
    return "浏览器预览";
  }

  const osName = globalThis.electronAPI?.env?.os || "Unknown";
  return `Electron / ${osName}`;
}

export async function getAppVersion() {
  const runtimeInfo = await getRuntimeInfo();
  return String(runtimeInfo?.appVersion || __APP_VERSION__);
}

export function isElectronRuntimeAvailable() {
  return hasElectronRuntime();
}
