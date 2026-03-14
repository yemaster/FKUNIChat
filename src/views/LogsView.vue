<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import Button from "primevue/button";
import Card from "primevue/card";
import TabPanel from "primevue/tabpanel";
import TabView from "primevue/tabview";
import { useToast } from "primevue/usetoast";

const props = defineProps({
  appLogs: {
    type: Array,
    required: true
  },
  serviceLogs: {
    type: Array,
    required: true
  }
});

const emit = defineEmits(["clear-app-logs", "clear-service-logs"]);
const toast = useToast();
const activeTabIndex = ref(0);
const appLogWindowRef = ref(null);
const serviceLogWindowRef = ref(null);

const currentLogs = computed(() => (activeTabIndex.value === 0 ? props.appLogs : props.serviceLogs));

function scrollToBottom(targetRef) {
  void nextTick(() => {
    if (!targetRef.value) {
      return;
    }

    targetRef.value.scrollTop = targetRef.value.scrollHeight;
  });
}

onMounted(() => {
  scrollToBottom(appLogWindowRef);
  scrollToBottom(serviceLogWindowRef);
});

watch(
  () => props.appLogs.length,
  () => {
    scrollToBottom(appLogWindowRef);
  },
  { flush: "post" }
);

watch(
  () => props.serviceLogs.length,
  () => {
    scrollToBottom(serviceLogWindowRef);
  },
  { flush: "post" }
);

async function copyLogs() {
  const content = currentLogs.value
    .map((entry) => `[${entry.time}] [${entry.source}] [${entry.level}] ${entry.message}`)
    .join("\n");

  if (!content) {
    toast.add({ severity: "secondary", summary: "复制", detail: "暂无日志", life: 1800 });
    return;
  }

  try {
    await navigator.clipboard.writeText(content);
    toast.add({ severity: "success", summary: "复制", detail: "日志已复制", life: 1800 });
  } catch {
    toast.add({ severity: "error", summary: "复制失败", detail: "当前环境不支持复制", life: 1800 });
  }
}

function clearCurrentLogs() {
  if (activeTabIndex.value === 0) {
    emit("clear-app-logs");
    return;
  }

  emit("clear-service-logs");
}
</script>

<template>
  <div class="page-shell">
    <Card class="home-card--wide">
      <template #title>运行日志</template>
      <template #content>
        <div class="summary-stack">
          <div class="flat-actions">
            <Button label="复制日志" severity="secondary" text class="panel-action panel-action--small" @click="copyLogs" />
            <Button label="清空当前日志" severity="secondary" text class="panel-action panel-action--small" @click="clearCurrentLogs" />
          </div>

          <TabView v-model:activeIndex="activeTabIndex" class="api-usage-tabs">
            <TabPanel header="应用日志">
              <div ref="appLogWindowRef" class="log-window">
                <div v-if="appLogs.length === 0" class="log-empty">暂无日志</div>
                <div v-for="entry in appLogs" :key="entry.id" class="log-entry" :class="`log-entry--${entry.level}`">
                  <span class="log-entry__meta">[{{ entry.time }}] [{{ entry.source }}] [{{ entry.level }}]</span>
                  <span class="log-entry__message">{{ entry.message }}</span>
                </div>
              </div>
            </TabPanel>

            <TabPanel header="服务日志">
              <div ref="serviceLogWindowRef" class="log-window">
                <div v-if="serviceLogs.length === 0" class="log-empty">暂无日志</div>
                <div v-for="entry in serviceLogs" :key="entry.id" class="log-entry" :class="`log-entry--${entry.level}`">
                  <span class="log-entry__meta">[{{ entry.time }}] [{{ entry.source }}] [{{ entry.level }}]</span>
                  <span class="log-entry__message">{{ entry.message }}</span>
                </div>
              </div>
            </TabPanel>
          </TabView>
        </div>
      </template>
    </Card>
  </div>
</template>
