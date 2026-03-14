<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import Button from "primevue/button";
import Card from "primevue/card";
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";
import Select from "primevue/select";
import ToggleSwitch from "primevue/toggleswitch";
import TabPanel from "primevue/tabpanel";
import TabView from "primevue/tabview";
import { useToast } from "primevue/usetoast";

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  },
  serviceState: {
    type: Object,
    required: true
  },
  tokenState: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(["update:model-value", "start-service", "stop-service", "navigate", "open-ustc", "auto-fetch-token"]);
const toast = useToast();
const now = ref(Date.now());
const apiUsageTabIndex = ref(0);
const tokenDraft = ref("");
const tokenEditing = ref(false);
let timerId = null;
const modelOptions = [
  { label: "Deepseek-r1", value: "deepseek-r1", name: "Deepseek r1", reasoning: true },
  { label: "Deepseek-v3", value: "deepseek-v3", name: "Deepseek v3", reasoning: false }
];

onMounted(() => {
  timerId = window.setInterval(() => {
    now.value = Date.now();
  }, 1000);
});

onBeforeUnmount(() => {
  if (timerId) {
    window.clearInterval(timerId);
  }
});

watch(
  () => props.modelValue.ustcToken,
  (value) => {
    if (!tokenEditing.value) {
      tokenDraft.value = String(value || "");
    }
  },
  { immediate: true }
);

watch(
  () => props.tokenState.valid,
  (valid) => {
    if (valid) {
      tokenEditing.value = false;
      tokenDraft.value = String(props.modelValue.ustcToken || "");
    }
  }
);

const latestApiKeys = computed(() => [...props.modelValue.apiKeys].slice(-5).reverse());
const apiKeyOptions = computed(() =>
  props.modelValue.apiKeys.map((item) => ({
    label: item.label,
    value: item.id
  }))
);
const portModel = computed({
  get() {
    const value = Number(props.modelValue.port);
    return Number.isInteger(value) && value > 0 ? value : null;
  },
  set(value) {
    emit("update:model-value", {
      port: value === null || value === undefined || value === "" ? "" : String(value)
    });
  }
});
const listenHostModel = computed({
  get() {
    return props.modelValue.listenHost === "0.0.0.0";
  },
  set(value) {
    emit("update:model-value", {
      listenHost: value ? "0.0.0.0" : "127.0.0.1"
    });
  }
});
const selectedModel = computed({
  get() {
    return props.modelValue.selectedModel || "deepseek-r1";
  },
  set(value) {
    emit("update:model-value", {
      selectedModel: value || "deepseek-r1"
    });
  }
});
const selectedApiKeyId = computed({
  get() {
    return props.modelValue.selectedApiKeyId || props.modelValue.apiKeys[0]?.id || "";
  },
  set(value) {
    emit("update:model-value", {
      selectedApiKeyId: value || props.modelValue.apiKeys[0]?.id || ""
    });
  }
});
const serviceBusy = computed(() => Boolean(props.serviceState.pendingAction));
const selectedModelMeta = computed(
  () => modelOptions.find((item) => item.value === selectedModel.value) || modelOptions[0]
);
const selectedApiKey = computed(
  () => props.modelValue.apiKeys.find((item) => item.id === selectedApiKeyId.value) || props.modelValue.apiKeys[0] || null
);
const activePort = computed(() => props.serviceState.port || props.modelValue.port || "5000");
const serviceBaseUrl = computed(() => `http://localhost:${activePort.value}/v1`);
const claudeBaseUrl = computed(() => `http://localhost:${activePort.value}`);
const openAiPythonCode = computed(
  () => `from openai import OpenAI

client = OpenAI(
    base_url="${serviceBaseUrl.value}",
    api_key="${selectedApiKey.value?.value || ""}"
)

response = client.chat.completions.create(
    model="${selectedModel.value}",
    messages=[
        {"role": "user", "content": "你好"}
    ]
)

print(response.choices[0].message.content)`
);
const claudeEnvCode = computed(
  () => `ANTHROPIC_BASE_URL=${claudeBaseUrl.value}
ANTHROPIC_AUTH_TOKEN=${selectedApiKey.value?.value || ""}
ANTHROPIC_MODEL=${selectedModel.value}`
);
const openClawConfig = computed(() =>
  JSON.stringify(
    {
      models: {
        providers: {
          USTC: {
            baseUrl: serviceBaseUrl.value,
            apiKey: selectedApiKey.value?.value || "",
            api: "openai-completions",
            models: [
              {
                id: selectedModel.value,
                name: `USTC ${selectedModelMeta.value.name}`,
                api: "openai-completions",
                reasoning: selectedModelMeta.value.reasoning,
                input: ["text"],
                cost: {
                  input: 0,
                  output: 0,
                  cacheRead: 0,
                  cacheWrite: 0
                },
                contextWindow: 200000,
                maxTokens: 8192
              }
            ]
          }
        }
      }
    },
    null,
    2
  )
);

const statusMeta = computed(() => {
  if (props.serviceState.running) {
    return { icon: "pi pi-play-circle", text: "运行中", className: "running" };
  }

  if (props.serviceState.pendingAction === "start") {
    return { icon: "pi pi-spin pi-spinner", text: "启动中", className: "pending" };
  }

  if (props.serviceState.error) {
    return { icon: "pi pi-exclamation-circle", text: "异常", className: "error" };
  }

  return { icon: "pi pi-minus-circle", text: "未启动", className: "idle" };
});

const formattedUptime = computed(() => {
  if (!props.serviceState.running || !props.serviceState.startedAt) {
    return "--";
  }

  const elapsedSeconds = Math.max(0, Math.floor((now.value - props.serviceState.startedAt) / 1000));
  const hours = Math.floor(elapsedSeconds / 3600);
  const minutes = Math.floor((elapsedSeconds % 3600) / 60);
  const seconds = elapsedSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }

  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }

  return `${seconds}s`;
});
const tokenStatusLabel = computed(() => {
  if (props.tokenState.pendingAction === "check") {
    return "校验中";
  }

  if (props.tokenState.valid) {
    return "可用";
  }

  if (props.tokenState.checked) {
    return "无效";
  }

  return "未校验";
});

function maskKey(value) {
  const text = String(value || "");

  if (!text) {
    return "-----";
  }

  if (text.length <= 5) {
    return `${text}${"*".repeat(5)}`;
  }

  return `${text.slice(0, 5)}${"*".repeat(Math.max(4, text.length - 5))}`;
}

function maskToken(value) {
  const text = String(value || "").trim();

  if (!text) {
    return "";
  }

  if (text.length <= 8) {
    return `${text.slice(0, 2)}${"*".repeat(Math.max(4, text.length - 2))}`;
  }

  return `${text.slice(0, 4)}${"*".repeat(Math.max(6, text.length - 8))}${text.slice(-4)}`;
}

const displayedToken = computed(() => {
  if (props.tokenState.valid && !tokenEditing.value) {
    return maskToken(props.modelValue.ustcToken);
  }

  return tokenDraft.value;
});

function handleTokenFocus() {
  if (props.tokenState.valid && !tokenEditing.value) {
    tokenEditing.value = true;
    tokenDraft.value = "";
  }
}

function handleTokenBlur() {
  if (tokenEditing.value && !String(tokenDraft.value || "").trim() && props.tokenState.valid) {
    tokenEditing.value = false;
    tokenDraft.value = String(props.modelValue.ustcToken || "");
  }
}

function handleTokenInput(value) {
  tokenEditing.value = true;
  tokenDraft.value = String(value || "");
  emit("update:model-value", {
    ustcToken: String(value || "").trim()
  });
}

async function copyText(value, detail = "内容已复制") {
  if (!value) {
    toast.add({ severity: "secondary", summary: "复制", detail: "内容为空", life: 1800 });
    return;
  }

  try {
    await navigator.clipboard.writeText(String(value));
    toast.add({ severity: "success", summary: "复制", detail, life: 1800 });
  } catch {
    toast.add({ severity: "error", summary: "复制失败", detail: "当前环境不支持复制", life: 1800 });
  }
}

</script>

<template>
  <div class="page-shell">
    <div class="home-grid home-grid--summary">
      <Card>
        <template #title>
          <div class="summary-card-title">
            <span>运行状态</span>
            <span class="status-line" :class="statusMeta.className">
              <span class="status-line__icon" :class="statusMeta.icon" aria-hidden="true" />
              <span>{{ statusMeta.text }}</span>
            </span>
          </div>
        </template>
        <template #content>
          <div class="summary-stack">
            <template v-if="serviceState.running">
              <div class="summary-list summary-list--compact">
                <div class="summary-row">
                  <span>运行端口</span>
                  <strong>{{ serviceState.port || "--" }}</strong>
                </div>
                <div class="summary-row">
                  <span>运行 PID</span>
                  <strong>{{ serviceState.pid || "--" }}</strong>
                </div>
                <div class="summary-row">
                  <span>运行时间</span>
                  <strong>{{ formattedUptime }}</strong>
                </div>
              </div>

              <div class="service-form">
                <div class="service-form__row">
                  <div class="service-form__label-line">
                    <span class="service-form__label-line-main">
                      <span class="service-form__label">USTChat Token</span>
                      <Button
                        icon="pi pi-question-circle"
                        severity="secondary"
                        text
                        rounded
                        class="inline-help-button"
                        @click="emit('navigate', { page: 'help', anchor: 'ustc-token' })"
                      />
                    </span>
                    <span
                      class="token-state"
                      :class="tokenState.valid ? 'token-state--valid' : tokenState.checked ? 'token-state--invalid' : 'token-state--idle'"
                    >
                      {{ tokenStatusLabel }}
                    </span>
                  </div>
                  <InputText
                    :model-value="displayedToken"
                    fluid
                    placeholder="粘贴 USTChat token"
                    class="service-form__input"
                    @focus="handleTokenFocus"
                    @blur="handleTokenBlur"
                    @update:model-value="handleTokenInput"
                  />
                </div>
                <div class="flat-actions">
                  <Button
                    label="自动获取"
                    severity="secondary"
                    text
                    class="panel-action panel-action--small panel-action--primary token-action"
                    :loading="tokenState.pendingAction === 'auto-fetch'"
                    @click="emit('auto-fetch-token')"
                  />
                  <Button
                    label="手动获取"
                    severity="secondary"
                    text
                    class="panel-action panel-action--small token-action"
                    @click="emit('open-ustc')"
                  />
                </div>
              </div>

              <div class="flat-actions">
                <Button
                  label="终止服务"
                  severity="secondary"
                  text
                  class="panel-action panel-action--danger"
                  :loading="serviceState.pendingAction === 'stop'"
                  @click="emit('stop-service')"
                />
              </div>
            </template>

            <template v-else>
              <div class="service-form">
                <div class="service-form__row">
                  <div class="service-form__label-line">
                    <span class="service-form__label-line-main">
                      <span class="service-form__label">USTChat Token</span>
                      <Button
                        icon="pi pi-question-circle"
                        severity="secondary"
                        text
                        rounded
                        class="inline-help-button"
                        @click="emit('navigate', { page: 'help', anchor: 'ustc-token' })"
                      />
                    </span>
                    <span
                      class="token-state"
                      :class="tokenState.valid ? 'token-state--valid' : tokenState.checked ? 'token-state--invalid' : 'token-state--idle'"
                    >
                      {{ tokenStatusLabel }}
                    </span>
                  </div>
                  <InputText
                    :model-value="displayedToken"
                    fluid
                    placeholder="粘贴 USTChat token"
                    class="service-form__input"
                    @focus="handleTokenFocus"
                    @blur="handleTokenBlur"
                    @update:model-value="handleTokenInput"
                  />
                </div>
                <div class="flat-actions">
                  <Button
                    label="自动获取"
                    severity="secondary"
                    text
                    class="panel-action panel-action--small panel-action--primary token-action"
                    :loading="tokenState.pendingAction === 'auto-fetch'"
                    @click="emit('auto-fetch-token')"
                  />
                  <Button
                    label="手动获取"
                    severity="secondary"
                    text
                    class="panel-action panel-action--small token-action"
                    @click="emit('open-ustc')"
                  />
                </div>
                <div class="service-form__row">
                  <span class="service-form__label">运行端口</span>
                  <InputNumber
                    v-model="portModel"
                    input-id="servicePort"
                    fluid
                    :use-grouping="false"
                    :min="1"
                    :max="65535"
                    inputmode="numeric"
                    placeholder="输入端口"
                    class="service-form__input"
                  />
                </div>
                <div class="service-form__row">
                  <div class="service-form__label-line">
                    <span class="service-form__label">监听地址</span>
                    <span class="service-form__label">{{ listenHostModel ? "0.0.0.0" : "127.0.0.1" }}</span>
                  </div>
                  <div class="host-switch-row">
                    <ToggleSwitch v-model="listenHostModel" input-id="listenHostMode" />
                    <label for="listenHostMode" class="host-switch-label">
                      {{ listenHostModel ? "局域网可访问" : "仅本机可访问" }}
                    </label>
                  </div>
                </div>
              </div>

              <div class="flat-actions">
                <Button
                  label="启动服务"
                  severity="secondary"
                  text
                  class="panel-action panel-action--success"
                  :loading="serviceState.pendingAction === 'start'"
                  :disabled="serviceBusy"
                  @click="emit('start-service')"
                />
              </div>
            </template>
          </div>
        </template>
      </Card>

      <Card>
        <template #title>API 密钥管理</template>
        <template #content>
          <div class="summary-stack">
            <div class="summary-list summary-list--compact">
              <div v-for="key in latestApiKeys" :key="key.id" class="summary-row summary-row--key">
                <div class="key-main">
                  <span class="key-name">{{ key.label }}</span>
                  <strong class="key-value">{{ maskKey(key.value) }}</strong>
                </div>
                <Button
                  icon="pi pi-copy"
                  severity="secondary"
                  text
                  rounded
                  class="copy-action"
                  @click="copyText(key.value, '密钥已复制')"
                />
              </div>
              <div v-if="latestApiKeys.length === 0" class="summary-row">
                <span>暂无密钥</span>
                <strong>--</strong>
              </div>
            </div>

            <div class="flat-actions">
              <Button label="进入管理" severity="secondary" text class="panel-action panel-action--primary" @click="emit('navigate', 'api-keys')" />
            </div>
          </div>
        </template>
      </Card>

      <Card class="home-card--wide">
        <template #title>API调用</template>
        <template #content>
          <div class="summary-stack">
            <div class="docs-toolbar">
              <div class="docs-field">
                <span class="service-form__label">模型</span>
                <Select v-model="selectedModel" :options="modelOptions" option-label="label" option-value="value" fluid />
              </div>
              <div class="docs-field">
                <span class="service-form__label">API Key</span>
                <Select
                  v-model="selectedApiKeyId"
                  :options="apiKeyOptions"
                  option-label="label"
                  option-value="value"
                  fluid
                />
              </div>
            </div>

            <TabView v-model:activeIndex="apiUsageTabIndex" class="api-usage-tabs">
              <TabPanel header="OpenAI API">
                <div class="docs-stack">
                  <div class="doc-row">
                    <div class="doc-row__main">
                      <span>baseURL</span>
                      <code>{{ serviceBaseUrl }}</code>
                    </div>
                    <Button icon="pi pi-copy" severity="secondary" text rounded class="copy-action copy-action--copy" @click="copyText(serviceBaseUrl, 'baseURL 已复制')" />
                  </div>
                  <div class="doc-row">
                    <div class="doc-row__main">
                      <span>API_KEY</span>
                      <code>{{ selectedApiKey?.value || "--" }}</code>
                    </div>
                    <Button icon="pi pi-copy" severity="secondary" text rounded class="copy-action copy-action--copy" @click="copyText(selectedApiKey?.value || '', 'API Key 已复制')" />
                  </div>
                  <div class="doc-block">
                    <div class="doc-block__header">
                      <span>Python 调用代码</span>
                      <Button icon="pi pi-copy" severity="secondary" text rounded class="copy-action copy-action--copy" @click="copyText(openAiPythonCode, 'Python 代码已复制')" />
                    </div>
                    <pre>{{ openAiPythonCode }}</pre>
                  </div>
                </div>
              </TabPanel>

              <TabPanel header="Claude code">
                <div class="docs-stack">
                  <div class="doc-row">
                    <div class="doc-row__main">
                      <span>ANTHROPIC_BASE_URL</span>
                      <code>{{ claudeBaseUrl }}</code>
                    </div>
                    <Button icon="pi pi-copy" severity="secondary" text rounded class="copy-action copy-action--copy" @click="copyText(claudeBaseUrl, 'ANTHROPIC_BASE_URL 已复制')" />
                  </div>
                  <div class="doc-row">
                    <div class="doc-row__main">
                      <span>ANTHROPIC_AUTH_TOKEN</span>
                      <code>{{ selectedApiKey?.value || "--" }}</code>
                    </div>
                    <Button icon="pi pi-copy" severity="secondary" text rounded class="copy-action copy-action--copy" @click="copyText(selectedApiKey?.value || '', 'ANTHROPIC_AUTH_TOKEN 已复制')" />
                  </div>
                  <div class="doc-row">
                    <div class="doc-row__main">
                      <span>ANTHROPIC_MODEL</span>
                      <code>{{ selectedModel }}</code>
                    </div>
                    <Button icon="pi pi-copy" severity="secondary" text rounded class="copy-action copy-action--copy" @click="copyText(selectedModel, 'ANTHROPIC_MODEL 已复制')" />
                  </div>
                  <div class="doc-block">
                    <div class="doc-block__header">
                      <span>环境变量配置</span>
                      <Button icon="pi pi-copy" severity="secondary" text rounded class="copy-action copy-action--copy" @click="copyText(claudeEnvCode, 'Claude 环境变量已复制')" />
                    </div>
                    <pre>{{ claudeEnvCode }}</pre>
                  </div>
                </div>
              </TabPanel>

              <TabPanel header="Openclaw">
                <div class="docs-stack">
                  <div class="doc-block">
                    <div class="doc-block__header">
                      <span>JSON 配置</span>
                      <Button icon="pi pi-copy" severity="secondary" text rounded class="copy-action copy-action--copy" @click="copyText(openClawConfig, 'Openclaw 配置已复制')" />
                    </div>
                    <pre>{{ openClawConfig }}</pre>
                  </div>
                </div>
              </TabPanel>
            </TabView>
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>
