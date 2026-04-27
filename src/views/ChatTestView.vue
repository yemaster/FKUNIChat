<script setup>
import { computed, nextTick, reactive, ref, watch } from "vue";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import Card from "primevue/card";
import Checkbox from "primevue/checkbox";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Select from "primevue/select";
import TabPanel from "primevue/tabpanel";
import TabView from "primevue/tabview";
import Textarea from "primevue/textarea";

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  },
  serviceState: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(["update:model-value", "navigate"]);
const toast = useToast();

const prompt = ref("");
const pending = ref(false);
const activeTabIndex = ref(1);
const chatMessages = ref([]);
const activeStreamMessageId = ref("");
const chatWindowRef = ref(null);
const shouldFollowChatBottom = ref(true);
const draft = reactive({
  systemPrompt: "",
  withSearch: false,
  toolsText: ""
});

const modelOptions = [
  { label: "Deepseek v4 Flash", value: "deepseek-v4-flash" },
  { label: "Deepseek Reasoner", value: "deepseek-reasoner" },
  { label: "Deepseek v4 Pro", value: "deepseek-v4-pro" }
];

const selectedModel = computed({
  get() {
    return props.modelValue.selectedModel || "deepseek-v4-flash";
  },
  set(value) {
    emit("update:model-value", {
      selectedModel: value || "deepseek-v4-flash"
    });
  }
});

const selectedApiKey = computed(
  () => props.modelValue.apiKeys.find((item) => item.id === props.modelValue.selectedApiKeyId) || props.modelValue.apiKeys[0] || null
);

const endpoint = computed(() => `http://127.0.0.1:${props.serviceState.port || props.modelValue.port || "28080"}/v1/chat/completions`);
const canUseTools = computed(() => selectedModel.value === "deepseek-v4-flash" || selectedModel.value === "deepseek-v4-pro");
const canSend = computed(() => props.serviceState.running && !pending.value && prompt.value.trim());

function isNearBottom(element) {
  if (!element) {
    return true;
  }

  const threshold = 20;
  const remaining = element.scrollHeight - element.scrollTop - element.clientHeight;
  return remaining <= threshold;
}

function handleChatScroll() {
  shouldFollowChatBottom.value = isNearBottom(chatWindowRef.value);
}

function scrollChatToBottom() {
  const element = chatWindowRef.value;
  if (!element) {
    return;
  }

  element.scrollTop = element.scrollHeight;
}

watch(
  chatMessages,
  async () => {
    if (!shouldFollowChatBottom.value) {
      return;
    }

    await nextTick();
    scrollChatToBottom();
  },
  { flush: "post" }
);

function createMessage(role, content = "") {
  return reactive({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    reasoning: "",
    toolCalls: []
  });
}

function parseTools() {
  const source = draft.toolsText.trim();
  if (!source) {
    return [];
  }

  const parsed = JSON.parse(source);
  if (!Array.isArray(parsed)) {
    throw new Error("tools 必须是 JSON 数组。");
  }

  return parsed;
}

function buildRequestMessages(userMessage) {
  const messages = [];

  if (draft.systemPrompt.trim()) {
    messages.push({
      role: "system",
      content: draft.systemPrompt.trim()
    });
  }

  for (const item of chatMessages.value) {
    if (item.role === "user") {
      messages.push({
        role: "user",
        content: item.content
      });
      continue;
    }

    if (item.role !== "assistant") {
      continue;
    }

    const message = {
      role: "assistant",
      content: item.content || ""
    };

    if (Array.isArray(item.toolCalls) && item.toolCalls.length > 0) {
      message.tool_calls = item.toolCalls;
    }

    messages.push(message);
  }

  messages.push({
    role: "user",
    content: userMessage
  });

  return messages;
}

function ensureToolCall(target, incoming) {
  const index = Number(incoming?.index ?? 0);
  if (!target[index]) {
    target[index] = {
      id: incoming?.id || "",
      type: incoming?.type || "function",
      function: {
        name: incoming?.function?.name || "",
        arguments: ""
      }
    };
  }

  if (incoming?.id) {
    target[index].id = incoming.id;
  }

  if (incoming?.type) {
    target[index].type = incoming.type;
  }

  if (incoming?.function?.name) {
    target[index].function.name = incoming.function.name;
  }

  if (typeof incoming?.function?.arguments === "string") {
    target[index].function.arguments += incoming.function.arguments;
  }
}

function normalizeToolCalls(toolCalls) {
  return toolCalls
    .filter(Boolean)
    .map((item) => ({
      id: item.id || "",
      type: item.type || "function",
      function: {
        name: item.function?.name || "",
        arguments: item.function?.arguments || ""
      }
    }));
}

function applyStreamChunk(targetMessage, payload, toolCalls) {
  const choice = payload?.choices?.[0];
  if (!choice) {
    return;
  }

  const delta = choice.delta || {};
  const reasoningText =
    (typeof delta.reasoning_content === "string" && delta.reasoning_content) ||
    (typeof delta.reasoning === "string" && delta.reasoning) ||
    (typeof delta.reasoningText === "string" && delta.reasoningText) ||
    "";

  if (reasoningText) {
    targetMessage.reasoning += reasoningText;
  }

  if (typeof delta.content === "string") {
    targetMessage.content += delta.content;
  }

  if (Array.isArray(delta.tool_calls)) {
    for (const item of delta.tool_calls) {
      ensureToolCall(toolCalls, item);
    }
    targetMessage.toolCalls = normalizeToolCalls(toolCalls);
  }

  chatMessages.value = [...chatMessages.value];
}

async function consumeStream(response, targetMessage) {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("当前环境不支持流式读取。");
  }

  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  const toolCalls = [];

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const lines = rawEvent
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);

      for (const line of lines) {
        if (!line.startsWith("data: ")) {
          continue;
        }

        const payload = line.slice(6).trim();
        if (!payload || payload === "[DONE]") {
          continue;
        }

        let parsed;
        try {
          parsed = JSON.parse(payload);
        } catch {
          continue;
        }

        applyStreamChunk(targetMessage, parsed, toolCalls);
      }
    }
  }

  if (buffer.trim().startsWith("data: ")) {
    const payload = buffer.trim().slice(6).trim();
    if (payload && payload !== "[DONE]") {
      try {
        applyStreamChunk(targetMessage, JSON.parse(payload), toolCalls);
      } catch {
        // Ignore incomplete trailing chunk.
      }
    }
  }
}

async function sendMessage() {
  const userMessage = prompt.value.trim();
  if (!userMessage || pending.value || !props.serviceState.running) {
    return;
  }

  let tools = [];
  try {
    tools = parseTools();
  } catch (error) {
    toast.add({ severity: "error", summary: "tools 无效", detail: error.message, life: 2600 });
    return;
  }

  const requestMessages = buildRequestMessages(userMessage);
  const userEntry = createMessage("user", userMessage);
  const assistantEntry = createMessage("assistant");
  prompt.value = "";
  pending.value = true;
  activeStreamMessageId.value = assistantEntry.id;
  chatMessages.value = [...chatMessages.value, userEntry, assistantEntry];

  try {
    const headers = {
      "Content-Type": "application/json"
    };

    if (selectedApiKey.value?.value) {
      headers.Authorization = `Bearer ${selectedApiKey.value.value}`;
    }

    const response = await fetch(endpoint.value, {
      method: "POST",
      headers,
      body: JSON.stringify({
        model: selectedModel.value,
        messages: requestMessages,
        stream: true,
        with_search: draft.withSearch,
        tools: canUseTools.value ? tools : []
      })
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.error?.message || `请求失败: HTTP ${response.status}`);
    }

    await consumeStream(response, assistantEntry);

    if (!assistantEntry.content && !assistantEntry.reasoning && assistantEntry.toolCalls.length === 0) {
      throw new Error("接口未返回有效回复。");
    }
  } catch (error) {
    assistantEntry.role = "error";
    assistantEntry.content = error.message || "发送失败";
    assistantEntry.reasoning = "";
    assistantEntry.toolCalls = [];
    chatMessages.value = [...chatMessages.value];
    toast.add({ severity: "error", summary: "发送失败", detail: assistantEntry.content, life: 2600 });
  } finally {
    pending.value = false;
    activeStreamMessageId.value = "";
  }
}

function clearHistory() {
  chatMessages.value = [];
  toast.add({ severity: "secondary", summary: "历史记录", detail: "已清空", life: 1600 });
}
</script>

<template>
  <div class="page-shell">
    <Card v-if="!serviceState.running">
      <template #title>聊天测试</template>
      <template #content>
        <div class="summary-stack">
          <Message severity="warn" :closable="false">服务尚未启动，当前无法发送测试消息。</Message>
          <div class="flat-actions">
            <Button label="前往启动" severity="secondary" text class="panel-action" @click="emit('navigate', 'home')" />
          </div>
        </div>
      </template>
    </Card>

    <Card v-else class="chat-test-card">
      <template #title>聊天测试</template>
      <template #content>
        <TabView v-model:activeIndex="activeTabIndex" class="api-usage-tabs chat-test-tabs">
          <TabPanel header="设置">
            <div class="summary-stack">
              <div class="docs-toolbar">
                <div class="docs-field">
                  <span class="service-form__label">模型</span>
                  <Select v-model="selectedModel" :options="modelOptions" option-label="label" option-value="value" fluid />
                </div>
                <div class="docs-field">
                  <span class="service-form__label">服务地址</span>
                  <InputText :model-value="endpoint" fluid readonly class="service-form__input" />
                </div>
              </div>

              <div class="chat-meta-row">
                <div class="checkbox-line">
                  <Checkbox v-model="draft.withSearch" binary input-id="withSearch" />
                  <label for="withSearch">启用在线搜索</label>
                </div>
                <span class="chat-meta-note">
                  {{
                    canUseTools
                      ? "当前模型支持 tools 透传。"
                      : "当前模型不支持 tools 透传。"
                  }}
                </span>
              </div>

              <div class="service-form__row">
                <span class="service-form__label">System Prompt</span>
                <Textarea v-model="draft.systemPrompt" rows="3" auto-resize class="chat-system-input" />
              </div>

              <div class="service-form__row">
                <span class="service-form__label">Tools JSON</span>
                <Textarea
                  v-model="draft.toolsText"
                  rows="4"
                  auto-resize
                  class="chat-system-input"
                  placeholder='例如：[{"type":"function","function":{"name":"ping","description":"test","parameters":{"type":"object","properties":{}}}}]'
                />
              </div>
            </div>
          </TabPanel>

          <TabPanel header="聊天">
            <div class="summary-stack">
              <div ref="chatWindowRef" class="chat-window" @scroll="handleChatScroll">
                <div v-if="chatMessages.length === 0" class="chat-empty">暂无消息，发送一条测试消息开始。</div>
                <div
                  v-for="message in chatMessages"
                  :key="message.id"
                  class="chat-bubble"
                  :class="[
                    `chat-bubble--${message.role}`,
                    {
                      'chat-bubble--streaming': pending && activeStreamMessageId === message.id
                    }
                  ]"
                >
                  <div class="chat-bubble__role">
                    {{
                      message.role === "user"
                        ? "你"
                        : message.role === "assistant"
                          ? "服务"
                          : "错误"
                    }}
                  </div>
                  <div v-if="message.reasoning" class="chat-reasoning">
                    <div class="chat-reasoning__title">思考</div>
                    <div class="chat-reasoning__content">{{ message.reasoning }}</div>
                  </div>
                  <div v-if="message.content" class="chat-bubble__content">{{ message.content }}</div>
                  <div v-if="message.toolCalls?.length" class="chat-tools">
                    <div v-for="toolCall in message.toolCalls" :key="`${message.id}-${toolCall.id}-${toolCall.function.name}`" class="chat-tool">
                      <div class="chat-tool__title">{{ toolCall.function.name || "tool_call" }}</div>
                      <pre>{{ toolCall.function.arguments }}</pre>
                    </div>
                  </div>
                  <div
                    v-if="pending && activeStreamMessageId === message.id && !message.content && !message.reasoning && !message.toolCalls?.length"
                    class="chat-loading"
                  >
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              </div>

              <div class="chat-input-bar">
                <Textarea
                  v-model="prompt"
                  rows="3"
                  auto-resize
                  class="chat-input"
                  placeholder="输入一条测试消息"
                  @keydown.enter.exact.prevent="sendMessage"
                />
                <div class="flat-actions">
                  <Button
                    label="清空历史记录"
                    severity="secondary"
                    text
                    class="panel-action panel-action--small"
                    @click="clearHistory"
                  />
                  <Button
                    label="发送"
                    severity="secondary"
                    text
                    class="panel-action panel-action--primary"
                    :loading="pending"
                    :disabled="!canSend"
                    @click="sendMessage"
                  />
                </div>
              </div>
            </div>
          </TabPanel>
        </TabView>
      </template>
    </Card>
  </div>
</template>
