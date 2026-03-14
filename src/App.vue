<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import Toast from "primevue/toast";
import SidebarNav from "./components/SidebarNav.vue";
import {
  buildCreateProjectVenvCommand,
  buildBundledServiceCommand,
  buildInstallProjectDependenciesCommand,
  checkUstcToken,
  exitApp,
  getAppVersion,
  fetchUstcTokenWithWebview,
  getEnvironmentLabel,
  getRunningProcesses,
  hydrateConfig,
  initElectronRuntime,
  inspectInitialization,
  isElectronRuntimeAvailable,
  isPortAvailable,
  loadConfig,
  openExternalUrl,
  probeLocalService,
  saveConfig,
  syncRuntimeState,
  stopService,
  startService,
  waitForElectronRuntime
} from "./lib/electron";
import { applyThemeSettings } from "./lib/theme";

const HomeView = defineAsyncComponent(() => import("./views/HomeView.vue"));
const ChatTestView = defineAsyncComponent(() => import("./views/ChatTestView.vue"));
const ApiKeysView = defineAsyncComponent(() => import("./views/ApiKeysView.vue"));
const LogsView = defineAsyncComponent(() => import("./views/LogsView.vue"));
const SetupView = defineAsyncComponent(() => import("./views/SetupView.vue"));
const HelpView = defineAsyncComponent(() => import("./views/HelpView.vue"));
const PrivacyView = defineAsyncComponent(() => import("./views/PrivacyView.vue"));
const ServiceTermsView = defineAsyncComponent(() => import("./views/ServiceTermsView.vue"));
const SettingsView = defineAsyncComponent(() => import("./views/SettingsView.vue"));

const toast = useToast();
const titleCompact = ref(false);
const isNarrow = ref(false);
const mobileDrawerOpen = ref(false);
const appLogs = ref([]);
const serviceLogs = ref([]);
const appVersion = ref(__APP_VERSION__);
const helpNavigation = ref({ anchor: "", token: 0 });
let mediaQuery = null;
let mediaHandler = null;
let systemThemeQuery = null;
let systemThemeHandler = null;
const setupProcessState = {
  id: null,
  action: "",
  resolve: null,
  reject: null
};
const setupLogState = {
  "create-venv": { lines: [], buffer: "" },
  "install-dependencies": { lines: [], buffer: "" }
};

const config = reactive(loadConfig());
const SETUP_ALLOWED_PAGES = new Set(["setup", "settings", "privacy", "service-terms"]);

const serviceState = reactive({
  running: false,
  id: null,
  pid: null,
  command: "",
  port: "",
  startedAt: null,
  error: "",
  pendingAction: ""
});
const tokenState = reactive({
  valid: false,
  checked: false,
  pendingAction: "",
  error: ""
});
const initializationState = reactive({
  loaded: false,
  checking: false,
  pendingAction: "",
  error: "",
  pythonAvailable: false,
  pythonVersion: "",
  pythonCommand: "",
  pythonExecutable: "",
  systemPythonAvailable: false,
  venvReady: false,
  venvPython: "",
  venvVersion: "",
  venvDirectory: "",
  venvLogs: [],
  requirementsPath: "",
  dependenciesInstalled: false,
  missingDependencies: [],
  dependencyLogs: []
});

const isElectron = ref(isElectronRuntimeAvailable());
const initializationReady = computed(() =>
  !isElectron.value || (
    initializationState.pythonAvailable &&
    initializationState.venvReady &&
    initializationState.dependenciesInstalled &&
    config.setupAcceptedPrivacy &&
    config.setupAcceptedServiceTerms
  )
);
const initializationLocked = computed(() => isElectron.value && !config.setupCompleted);
const pageTitle = computed(() =>
  config.selectedPage === "setup"
    ? "初始化"
    : config.selectedPage === "logs"
      ? "运行日志"
      : config.selectedPage === "chat-test"
        ? "聊天测试"
      : config.selectedPage === "api-keys"
        ? "API 密钥管理"
        : config.selectedPage === "help"
          ? "帮助"
        : config.selectedPage === "privacy"
          ? "FKUNIChat 隐私条款"
        : config.selectedPage === "service-terms"
          ? "FKUNIChat 服务协议"
        : config.selectedPage === "settings"
          ? "设置"
          : "FKUNIChat 控制中心"
);

function maskTokenForLog(token) {
  const value = String(token || "").trim();
  if (!value) {
    return "--";
  }

  if (value.length <= 12) {
    return `${value.slice(0, 4)}${"*".repeat(Math.max(4, value.length - 4))}`;
  }

  return `${value.slice(0, 6)}${"*".repeat(Math.max(6, value.length - 10))}${value.slice(-4)}`;
}

function pushToast(severity, summary, detail) {
  toast.add({
    severity,
    summary,
    detail,
    life: 2600
  });
}

function appendLog(source, level, message) {
  const text = String(message ?? "").trim();
  if (!text) {
    return;
  }

  appLogs.value = [
    ...appLogs.value,
    {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
      source,
      level,
      message: text
    }
  ].slice(-300);
}

function appendServiceLog(level, message) {
  const text = String(message ?? "").trim();
  if (!text) {
    return;
  }

  serviceLogs.value = [
    ...serviceLogs.value,
    {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
      source: "service",
      level,
      message: text
    }
  ].slice(-300);
}

function clearAppLogs() {
  appLogs.value = [];
}

function clearServiceLogs() {
  serviceLogs.value = [];
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function resetServiceState(error = "") {
  serviceState.running = false;
  serviceState.id = null;
  serviceState.pid = null;
  serviceState.command = "";
  serviceState.port = "";
  serviceState.startedAt = null;
  serviceState.error = error;
  serviceState.pendingAction = "";
}

function hasServiceId(value) {
  return value !== null && value !== undefined;
}

function applyInitializationInspection(result) {
  initializationState.loaded = true;
  initializationState.pythonAvailable = Boolean(result?.pythonAvailable);
  initializationState.pythonVersion = String(result?.pythonVersion || "");
  initializationState.pythonCommand = String(result?.pythonCommand || "");
  initializationState.pythonExecutable = String(result?.pythonExecutable || "");
  initializationState.systemPythonAvailable = Boolean(result?.systemPythonAvailable);
  initializationState.venvReady = Boolean(result?.venvReady);
  initializationState.venvPython = String(result?.venvPython || "");
  initializationState.venvVersion = String(result?.venvVersion || "");
  initializationState.venvDirectory = String(result?.venvDirectory || "");
  initializationState.requirementsPath = String(result?.requirementsPath || "");
  initializationState.dependenciesInstalled = Boolean(result?.dependenciesInstalled);
  initializationState.missingDependencies = Array.isArray(result?.missingDependencies)
    ? result.missingDependencies.map((item) => String(item))
    : [];
}

function normalizeSetupLogLines(lines) {
  const source = Array.isArray(lines)
    ? lines
    : String(lines || "").split(/\r?\n/);

  return source
    .map((line) => String(line || "").trim())
    .filter(Boolean);
}

function getSetupLogKey(action) {
  if (action === "create-venv") {
    return "venvLogs";
  }

  if (action === "install-dependencies") {
    return "dependencyLogs";
  }

  return "";
}

function getSetupLogMessage(action) {
  return action === "create-venv" ? "创建 venv" : "安装依赖";
}

function syncSetupLogView(action) {
  const logKey = getSetupLogKey(action);
  const state = setupLogState[action];

  if (!logKey || !state) {
    return;
  }

  initializationState[logKey] = normalizeSetupLogLines([
    ...state.lines,
    state.buffer
  ]);
}

function clearSetupLogState(action) {
  const state = setupLogState[action];
  const logKey = getSetupLogKey(action);

  if (!state || !logKey) {
    return;
  }

  state.lines = [];
  state.buffer = "";
  initializationState[logKey] = [];
}

function appendSetupLogChunk(action, chunk) {
  const state = setupLogState[action];

  if (!state) {
    return;
  }

  const source = `${state.buffer}${String(chunk || "").replace(/\u0000/g, "")}`;
  const lines = source.split(/\r?\n/);
  state.buffer = lines.pop() || "";

  const nextLines = lines
    .map((line) => String(line || "").trim())
    .filter(Boolean);

  if (nextLines.length > 0) {
    state.lines = [...state.lines, ...nextLines];
  }

  syncSetupLogView(action);
}

function flushSetupLogBuffer(action) {
  const state = setupLogState[action];

  if (!state) {
    return;
  }

  const tail = String(state.buffer || "").trim();
  if (tail) {
    state.lines = [...state.lines, tail];
  }
  state.buffer = "";
  syncSetupLogView(action);
}

function resetSetupProcessState() {
  setupProcessState.id = null;
  setupProcessState.action = "";
  setupProcessState.resolve = null;
  setupProcessState.reject = null;
}

function buildSetupProcessError(action, exitCode) {
  const logKey = getSetupLogKey(action);
  const lines = logKey ? normalizeSetupLogLines(initializationState[logKey]).slice(-3) : [];
  const summary = getSetupLogMessage(action);

  if (lines.length > 0) {
    return `${summary}失败：${lines.join(" | ")}`;
  }

  return `${summary}失败${Number.isFinite(exitCode) ? `，exitCode=${exitCode}` : ""}`;
}

function syncInitializationGate() {
  if (!isElectron.value) {
    if (!config.setupCompleted) {
      config.setupCompleted = true;
    }

    if (config.selectedPage === "setup") {
      config.selectedPage = "home";
    }
    return;
  }

  if (config.setupCompleted && initializationState.loaded && !initializationReady.value) {
    config.setupCompleted = false;
  }

  if (!config.setupCompleted && !SETUP_ALLOWED_PAGES.has(config.selectedPage)) {
    config.selectedPage = "setup";
  }
}

async function refreshInitializationStatus(force = false) {
  if (!isElectron.value) {
    syncInitializationGate();
    return;
  }

  if (initializationState.pendingAction && initializationState.pendingAction !== "refresh") {
    return;
  }

  initializationState.checking = true;
  if (!initializationState.pendingAction) {
    initializationState.pendingAction = "refresh";
  }

  try {
    const result = await inspectInitialization(force);
    applyInitializationInspection(result);
    initializationState.error = "";
    appendLog(
      "frontend",
      "info",
      `初始化检查: python=${result.pythonAvailable ? "ready" : "missing"}, venv=${result.venvReady ? "ready" : "missing"}, deps=${result.dependenciesInstalled ? "ready" : "missing"}`
    );
  } catch (error) {
    applyInitializationInspection({
      pythonAvailable: false,
      pythonVersion: "",
      pythonCommand: "",
      pythonExecutable: "",
      systemPythonAvailable: false,
      venvReady: false,
      venvPython: initializationState.venvPython,
      venvVersion: "",
      venvDirectory: initializationState.venvDirectory,
      requirementsPath: initializationState.requirementsPath,
      dependenciesInstalled: false,
      missingDependencies: []
    });
    initializationState.error = error.message || String(error);
    appendLog("frontend", "error", `初始化检查失败: ${initializationState.error}`);
  } finally {
    if (initializationState.pendingAction === "refresh") {
      initializationState.pendingAction = "";
    }
    initializationState.checking = false;
    syncInitializationGate();
  }
}

async function handleCreateVenv() {
  if (initializationState.pendingAction) {
    return;
  }

  try {
    initializationState.pendingAction = "create-venv";
    initializationState.checking = true;
    initializationState.error = "";
    clearSetupLogState("create-venv");
    appendLog("frontend", "info", "开始创建项目 venv");
    const { command, cwd } = await buildCreateProjectVenvCommand();
    const spawned = await startService(command, cwd);
    setupProcessState.id = spawned.id;
    setupProcessState.action = "create-venv";
    const inspection = await new Promise((resolve, reject) => {
      setupProcessState.resolve = resolve;
      setupProcessState.reject = reject;
    });
    applyInitializationInspection(inspection);
    appendLog("frontend", "info", `venv 已创建: ${inspection.venvDirectory || "venv"}`);
    pushToast("success", "初始化", "venv 已创建");
  } catch (error) {
    if (initializationState.venvLogs.length === 0) {
      initializationState.venvLogs = normalizeSetupLogLines(error.message || error);
    }
    initializationState.error = error.message || String(error);
    appendLog("frontend", "error", `创建 venv 失败: ${initializationState.error}`);
    pushToast("error", "创建失败", initializationState.error);
  } finally {
    resetSetupProcessState();
    initializationState.pendingAction = "";
    initializationState.checking = false;
    syncInitializationGate();
  }
}

async function handleInstallDependencies() {
  if (initializationState.pendingAction) {
    return;
  }

  try {
    initializationState.pendingAction = "install-dependencies";
    initializationState.checking = true;
    initializationState.error = "";
    clearSetupLogState("install-dependencies");
    appendLog("frontend", "info", "开始安装 Python 依赖");
    const { command, cwd } = await buildInstallProjectDependenciesCommand();
    const spawned = await startService(command, cwd);
    setupProcessState.id = spawned.id;
    setupProcessState.action = "install-dependencies";
    const inspection = await new Promise((resolve, reject) => {
      setupProcessState.resolve = resolve;
      setupProcessState.reject = reject;
    });
    applyInitializationInspection(inspection);
    appendLog("frontend", "info", "Python 依赖安装完成");
    pushToast("success", "初始化", "依赖已安装");
  } catch (error) {
    if (initializationState.dependencyLogs.length === 0) {
      initializationState.dependencyLogs = normalizeSetupLogLines(error.message || error);
    }
    initializationState.error = error.message || String(error);
    appendLog("frontend", "error", `安装依赖失败: ${initializationState.error}`);
    pushToast("error", "安装失败", initializationState.error);
  } finally {
    resetSetupProcessState();
    initializationState.pendingAction = "";
    initializationState.checking = false;
    syncInitializationGate();
  }
}

async function openPythonDownloadPage() {
  try {
    await openExternalUrl("https://www.python.org/downloads/");
  } catch (error) {
    appendLog("frontend", "error", `打开 Python 下载页失败: ${error.message || error}`);
    pushToast("error", "打开失败", error.message || String(error));
  }
}

async function completeInitialization() {
  if (!initializationReady.value) {
    pushToast("warn", "未完成", "请先完成初始化步骤");
    return;
  }

  config.setupCompleted = true;
  config.selectedPage = "home";
  appendLog("frontend", "info", "初始化已完成");
  pushToast("success", "初始化完成", "可以开始使用");
  await refreshTokenStatus();
}

async function handleWindowClose() {
  appendLog("frontend", "info", "收到窗口关闭请求");

  if (hasServiceId(serviceState.id)) {
    try {
      appendLog("frontend", "info", `关闭前终止服务，spawnId=${serviceState.id}`);
      await stopService(serviceState.id, serviceState.pid);
    } catch (error) {
      appendLog("frontend", "warn", `关闭前终止服务失败: ${error.message || error}`);
    }
  }

  await exitApp();
}

watch(
  config,
  (value) => {
    saveConfig(value);
    void syncRuntimeState(value);
  },
  { deep: true }
);

watch(
  [
    () => isElectron.value,
    () => config.setupCompleted,
    () => config.setupAcceptedPrivacy,
    () => config.setupAcceptedServiceTerms,
    () => initializationState.loaded,
    () => initializationState.pythonAvailable,
    () => initializationState.venvReady,
    () => initializationState.dependenciesInstalled,
    () => config.selectedPage
  ],
  () => {
    syncInitializationGate();
  },
  { immediate: true }
);

watch(
  () => config.ustcToken,
  (nextValue, previousValue) => {
    if (nextValue === previousValue) {
      return;
    }

    tokenState.valid = false;
    tokenState.checked = false;
    tokenState.pendingAction = "";
    tokenState.error = "";
  }
);

watch(
  () => [config.themeColor, config.themeMode],
  () => {
    applyThemeSettings({
      themeColor: config.themeColor,
      themeMode: config.themeMode,
      prefersDark: Boolean(systemThemeQuery?.matches)
    });
  },
  { immediate: true }
);

function handleSpawnedProcess(event) {
  const detail = event?.detail;

  if (!detail) {
    return;
  }

  if (detail.id === setupProcessState.id) {
    const action = setupProcessState.action;

    if ((detail.action === "stdOut" || detail.action === "stdErr") && typeof detail.data === "string" && detail.data) {
      appendSetupLogChunk(action, detail.data);
      return;
    }

    if (detail.action === "exit") {
      const exitCode = Number(detail.data);
      const resolve = setupProcessState.resolve;
      const reject = setupProcessState.reject;

      flushSetupLogBuffer(action);
      resetSetupProcessState();

      if (!resolve || !reject) {
        return;
      }

      if (Number.isFinite(exitCode) && exitCode === 0) {
        void inspectInitialization(true)
          .then(resolve)
          .catch(reject);
      } else {
        reject(new Error(buildSetupProcessError(action, exitCode)));
      }
    }
    return;
  }

  if (detail.id !== serviceState.id) {
    return;
  }

  if (detail.action === "stdOut" && typeof detail.data === "string" && detail.data.trim()) {
    appendServiceLog("info", detail.data);
  }

  if (detail.action === "exit") {
    const exitCode = Number(detail.data);
    appendServiceLog(exitCode > 0 ? "error" : "info", `进程退出，exitCode=${Number.isFinite(exitCode) ? exitCode : "unknown"}`);
    resetServiceState(exitCode > 0 ? `进程异常退出 (${exitCode})` : "");
    return;
  }

  if (detail.action === "stdErr" && typeof detail.data === "string" && detail.data.trim()) {
    serviceState.error = detail.data.trim();
    appendServiceLog("error", detail.data);
  }
}

function addApiKey(payload) {
  const id = `key-${Date.now()}`;
  config.apiKeys = [...config.apiKeys, { id, ...payload }];
  config.selectedApiKeyId = id;
}

function removeApiKey(id) {
  config.apiKeys = config.apiKeys.filter((item) => item.id !== id);
  if (!config.apiKeys.some((item) => item.id === config.selectedApiKeyId)) {
    config.selectedApiKeyId = config.apiKeys[0]?.id || "";
  }
}

async function refreshTokenStatus(showToast = false) {
  if (isElectron.value && !config.setupCompleted) {
    tokenState.valid = false;
    tokenState.checked = false;
    tokenState.pendingAction = "";
    tokenState.error = "";
    return false;
  }

  if (!config.ustcToken) {
    tokenState.valid = false;
    tokenState.checked = true;
    tokenState.error = "";
    appendLog("frontend", "warn", "未配置 USTChat Token");
    return false;
  }

  try {
    tokenState.pendingAction = "check";
    appendLog("frontend", "info", `开始校验 USTChat Token: ${maskTokenForLog(config.ustcToken)} (length=${String(config.ustcToken).length})`);
    const result = await checkUstcToken(config.ustcToken);
    tokenState.valid = Boolean(result.valid);
    tokenState.checked = true;
    tokenState.error = tokenState.valid ? "" : String(result.reason || "invalid_token");
    appendLog(
      "frontend",
      tokenState.valid ? "info" : "warn",
      `USTChat Token 校验结果: ${tokenState.valid ? "可用" : "无效"}, reason=${result.reason || "unknown"}, status=${result.statusCode ?? "none"}, contentType=${result.contentType || "none"}`
    );
    if (result.bodyPreview) {
      appendLog("frontend", "info", `USTChat Token 校验响应摘要: ${result.bodyPreview}`);
    }
    if (showToast) {
      pushToast("secondary", "Token", tokenState.valid ? "Token 可用" : "Token 无效");
    }
    return tokenState.valid;
  } catch (error) {
    tokenState.valid = false;
    tokenState.checked = true;
    tokenState.error = error.message;
    appendLog("frontend", "error", `Token 校验失败: ${error.message}`);
    if (showToast) {
      pushToast("error", "Token 校验失败", error.message);
    }
    return false;
  } finally {
    tokenState.pendingAction = "";
  }
}

async function openUstcPage() {
  try {
    appendLog("frontend", "info", "打开 USTChat 页面，需手动登录并复制 Token");
    await openExternalUrl("https://chat.ustc.edu.cn/ustchat/");
  } catch (error) {
    appendLog("frontend", "error", `打开 USTC 页面失败: ${error.message}`);
    pushToast("error", "打开页面失败", error.message);
  }
}

async function autoFetchUstcToken() {
  try {
    appendLog("frontend", "info", "开始自动获取 USTChat Token");
    tokenState.pendingAction = "auto-fetch";
    const token = await fetchUstcTokenWithWebview({
      onProgress(payload) {
        const stage = String(payload?.stage || "unknown");
        const href = payload?.href ? `, href=${payload.href}` : "";
        const title = payload?.title ? `, title=${payload.title}` : "";
        const isLogin = payload?.isLogin !== undefined ? `, isLogin=${Boolean(payload.isLogin)}` : "";
        const hasToken = payload?.hasToken !== undefined ? `, hasToken=${Boolean(payload.hasToken)}` : "";
        const tokenLength = payload?.tokenLength ? `, tokenLength=${payload.tokenLength}` : "";
        const message = payload?.message ? `, message=${payload.message}` : "";
        const rawLength = payload?.rawLength ? `, rawLength=${payload.rawLength}` : "";
        const stateKeys = Array.isArray(payload?.stateKeys) && payload.stateKeys.length > 0
          ? `, stateKeys=${payload.stateKeys.join("|")}`
          : "";
        const detail = payload?.detail ? `, detail=${JSON.stringify(payload.detail)}` : "";
        appendLog(
          "frontend",
          payload?.status === "error" ? "error" : "info",
          `自动获取进度: stage=${stage}${href}${title}${isLogin}${hasToken}${tokenLength}${rawLength}${stateKeys}${message}${detail}`
        );
      }
    });
    config.ustcToken = token;
    appendLog("frontend", "info", `自动获取到 USTChat Token: ${maskTokenForLog(token)}`);
    pushToast("success", "Token", "已获取到 token，正在校验");
    await refreshTokenStatus(true);
  } catch (error) {
    appendLog("frontend", "error", `自动获取 token 失败: ${error.message || error}`);
    pushToast("error", "自动获取失败", error.message || String(error));
  } finally {
    if (tokenState.pendingAction === "auto-fetch") {
      tokenState.pendingAction = "";
    }
  }
}

async function waitForServiceReady(port, spawnId) {
  let lastError = "";

  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      const health = await probeLocalService(port);
      appendLog("frontend", "info", `健康检查通过: ${JSON.stringify(health)}`);
      return health;
    } catch (error) {
      lastError = error.message;
      appendLog("frontend", "warn", `健康检查未通过(${attempt + 1}/12): ${error.message}`);
    }

    try {
      const processes = await getRunningProcesses();
      const current = processes.find((item) => item.id === spawnId);
      if (!current) {
        throw new Error("服务进程已退出");
      }
      if (current.pid && !serviceState.pid) {
        serviceState.pid = current.pid;
      }
    } catch (error) {
      throw new Error(error.message || lastError || "服务进程不存在");
    }

    await sleep(500);
  }

  throw new Error(lastError || "服务未在预期时间内启动");
}

async function launchService() {
  if (isElectron.value && !config.setupCompleted) {
    appendLog("frontend", "warn", "启动失败，初始化未完成");
    pushToast("warn", "未初始化", "请先完成初始化");
    config.selectedPage = "setup";
    return;
  }

  const port = Number(config.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    appendLog("frontend", "warn", `启动失败，非法端口: ${config.port}`);
    pushToast("warn", "参数错误", "请输入合法端口");
    return;
  }

  const tokenValid = await refreshTokenStatus();
  if (!tokenValid) {
    appendLog("frontend", "warn", "启动失败，USTChat Token 无效");
    pushToast("warn", "Token 无效", "请先获取可用的 USTChat Token");
    return;
  }

  try {
    serviceState.pendingAction = "start";
    clearServiceLogs();
    const available = await isPortAvailable(port);
    if (!available) {
      serviceState.pendingAction = "";
      appendLog("frontend", "warn", `启动失败，端口 ${port} 已被占用`);
      pushToast("warn", "端口占用", `${port} 已被占用`);
      return;
    }

    const { command, cwd } = await buildBundledServiceCommand(port, config);
    appendLog("frontend", "info", `准备启动服务: ${command}`);
    if (cwd) {
      appendLog("frontend", "info", `服务工作目录: ${cwd}`);
    }

    const spawned = await startService(command, cwd);
    serviceState.id = spawned.id;
    serviceState.pid = spawned.pid || null;
    serviceState.command = command;
    serviceState.port = String(port);
    appendLog("frontend", "info", `进程已触发，spawnId=${spawned.id}, pid=${spawned.pid || "unknown"}`);

    await waitForServiceReady(String(port), spawned.id);

    serviceState.running = true;
    serviceState.startedAt = Date.now();
    serviceState.error = "";
    serviceState.pendingAction = "";
    appendLog("frontend", "info", `服务已就绪，spawnId=${spawned.id}, pid=${serviceState.pid || "unknown"}`);
    pushToast("success", "已启动", serviceState.pid ? `PID ${serviceState.pid}` : "服务已就绪");
  } catch (error) {
    appendLog("frontend", "error", `启动失败: ${error.message}`);
    resetServiceState(error.message);
    pushToast("error", "启动失败", error.message);
  }
}

async function terminateService() {
  if (!hasServiceId(serviceState.id) || serviceState.pendingAction) {
    return;
  }

  const runningPid = serviceState.pid;

  try {
    serviceState.pendingAction = "stop";
    appendLog("frontend", "info", `准备终止服务，spawnId=${serviceState.id}, pid=${runningPid || "unknown"}`);
    await stopService(serviceState.id, runningPid);
    resetServiceState();
    appendLog("frontend", "info", "服务已终止");
    pushToast("secondary", "已终止", runningPid ? `PID ${runningPid} 已终止` : "服务已终止");
  } catch (error) {
    serviceState.pendingAction = "";
    appendLog("frontend", "error", `终止失败: ${error.message}`);
    pushToast("error", "终止失败", error.message);
  }
}

const activeView = computed(() => {
  if (config.selectedPage === "setup") {
    return SetupView;
  }

  if (config.selectedPage === "api-keys") {
    return ApiKeysView;
  }

  if (config.selectedPage === "chat-test") {
    return ChatTestView;
  }

  if (config.selectedPage === "logs") {
    return LogsView;
  }

  if (config.selectedPage === "help") {
    return HelpView;
  }

  if (config.selectedPage === "privacy") {
    return PrivacyView;
  }

  if (config.selectedPage === "service-terms") {
    return ServiceTermsView;
  }

  if (config.selectedPage === "settings") {
    return SettingsView;
  }

  return HomeView;
});

function handleViewportMode() {
  const nextNarrow = Boolean(mediaQuery?.matches);
  isNarrow.value = nextNarrow;
  if (nextNarrow) {
    mobileDrawerOpen.value = false;
  }
}

function handleContentScroll(event) {
  const scrollTop = event?.target?.scrollTop || 0;
  const compactThreshold = 28;
  const expandThreshold = 8;

  if (!titleCompact.value && scrollTop >= compactThreshold) {
    titleCompact.value = true;
    return;
  }

  if (titleCompact.value && scrollTop <= expandThreshold) {
    titleCompact.value = false;
  }
}

function handleSidebarToggle() {
  if (isNarrow.value) {
    mobileDrawerOpen.value = !mobileDrawerOpen.value;
    return;
  }

  config.sidebarCollapsed = !config.sidebarCollapsed;
}

function handleNavigate(target) {
  let nextPage = "home";
  let nextAnchor = "";

  if (typeof target === "string") {
    nextPage = target;
  } else if (target && typeof target === "object") {
    nextPage = String(target.page || "home");
    nextAnchor = String(target.anchor || "");
  }

  if (initializationLocked.value && !SETUP_ALLOWED_PAGES.has(nextPage)) {
    nextPage = "setup";
    nextAnchor = "";
  }

  config.selectedPage = nextPage;
  helpNavigation.value = {
    anchor: nextAnchor,
    token: nextAnchor ? Date.now() : 0
  };

  if (isNarrow.value) {
    mobileDrawerOpen.value = false;
  }
}

onMounted(() => {
  appendLog("frontend", "info", "应用已加载");
  mediaQuery = window.matchMedia("(max-width: 720px)");
  mediaHandler = () => handleViewportMode();
  systemThemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
  systemThemeHandler = () => {
    applyThemeSettings({
      themeColor: config.themeColor,
      themeMode: config.themeMode,
      prefersDark: Boolean(systemThemeQuery?.matches)
    });
  };
  handleViewportMode();
  void (async () => {
    isElectron.value = await waitForElectronRuntime();
    appendLog("frontend", "info", `运行环境检测: ${isElectron.value ? "Electron" : "浏览器预览"}`);
    appVersion.value = await getAppVersion();
    if (isElectron.value) {
      initElectronRuntime({
        onWindowClose: () => handleWindowClose(),
        onSpawnedProcess: handleSpawnedProcess
      });
      appendLog("frontend", "info", "Electron 本地 API 已初始化");
    }
    const hydrated = await hydrateConfig(config);
    if (hydrated) {
      appendLog("frontend", "info", `已从 Electron 本地存储恢复配置，token=${maskTokenForLog(config.ustcToken)}`);
    }
    if (isElectron.value && !config.setupCompleted) {
      config.selectedPage = "setup";
    }
    await refreshInitializationStatus(true);
    applyThemeSettings({
      themeColor: config.themeColor,
      themeMode: config.themeMode,
      prefersDark: Boolean(systemThemeQuery?.matches)
    });
    if (!isElectron.value || config.setupCompleted) {
      await refreshTokenStatus();
    } else {
      appendLog("frontend", "info", "初始化未完成，已跳过 Token 校验");
    }
  })();

  window.addEventListener("error", handleWindowError);
  window.addEventListener("unhandledrejection", handleUnhandledRejection);

  if (typeof mediaQuery.addEventListener === "function") {
    mediaQuery.addEventListener("change", mediaHandler);
  } else {
    mediaQuery.addListener(mediaHandler);
  }

  if (typeof systemThemeQuery.addEventListener === "function") {
    systemThemeQuery.addEventListener("change", systemThemeHandler);
  } else {
    systemThemeQuery.addListener(systemThemeHandler);
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("error", handleWindowError);
  window.removeEventListener("unhandledrejection", handleUnhandledRejection);
  if (!mediaQuery || !mediaHandler) {
    return;
  }

  if (typeof mediaQuery.removeEventListener === "function") {
    mediaQuery.removeEventListener("change", mediaHandler);
  } else {
    mediaQuery.removeListener(mediaHandler);
  }

  if (systemThemeQuery && systemThemeHandler) {
    if (typeof systemThemeQuery.removeEventListener === "function") {
      systemThemeQuery.removeEventListener("change", systemThemeHandler);
    } else {
      systemThemeQuery.removeListener(systemThemeHandler);
    }
  }
});

function handleWindowError(event) {
  appendLog("frontend", "error", event?.error?.stack || event?.message || "未知前端异常");
}

function handleUnhandledRejection(event) {
  const reason = event?.reason;
  appendLog("frontend", "error", reason?.stack || reason?.message || String(reason || "未知 Promise 异常"));
}
</script>

<template>
  <div class="app-shell">
    <Toast position="bottom-right" />

    <div v-if="isNarrow && mobileDrawerOpen" class="sidebar-backdrop" @click="mobileDrawerOpen = false" />

    <SidebarNav
      :collapsed="isNarrow ? false : config.sidebarCollapsed"
      :mobile="isNarrow"
      :open="mobileDrawerOpen"
      :active-page="config.selectedPage"
      :limited-mode="initializationLocked"
      @toggle="handleSidebarToggle"
      @navigate="handleNavigate"
    />

    <main class="content-shell" @scroll.passive="handleContentScroll">
      <section class="topbar" :class="{ 'topbar--compact': titleCompact }">
        <Button
          v-if="isNarrow"
          icon="pi pi-bars"
          severity="secondary"
          text
          rounded
          class="mobile-menu-button"
          @click="mobileDrawerOpen = true"
        />
        <div class="page-title">{{ pageTitle }}</div>
      </section>

      <Transition name="view-swap" mode="out-in">
        <KeepAlive>
          <component
            :is="activeView"
            :key="config.selectedPage"
            :model-value="config"
            :service-state="serviceState"
            :token-state="tokenState"
            :initialization-state="initializationState"
            :initialization-ready="initializationReady"
            :app-logs="appLogs"
            :service-logs="serviceLogs"
            :environment-label="getEnvironmentLabel()"
            :app-version="appVersion"
            :help-anchor="helpNavigation.anchor"
            :help-anchor-token="helpNavigation.token"
            @update:model-value="Object.assign(config, $event)"
            @auto-fetch-token="autoFetchUstcToken"
            @open-ustc="openUstcPage"
            @clear-app-logs="clearAppLogs"
            @clear-service-logs="clearServiceLogs"
            @refresh-initialization="refreshInitializationStatus(true)"
            @open-python-download="openPythonDownloadPage"
            @create-venv="handleCreateVenv"
            @install-dependencies="handleInstallDependencies"
            @complete-initialization="completeInitialization"
            @start-service="launchService"
            @stop-service="terminateService"
            @create-api-key="addApiKey"
            @remove-api-key="removeApiKey"
            @navigate="handleNavigate"
          />
        </KeepAlive>
      </Transition>
    </main>
  </div>
</template>
