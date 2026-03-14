<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import Card from "primevue/card";
import Checkbox from "primevue/checkbox";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(["create-api-key", "remove-api-key"]);
const toast = useToast();
const rootRef = ref(null);
const visibleKeys = ref({});
const isCreating = ref(false);

const draft = reactive({
  id: "__draft__",
  label: "",
  neverExpires: true,
  expiresAt: null,
  unlimitedUsage: true,
  maxUsage: -1
});

const apiKeys = computed(() => [...props.modelValue.apiKeys].sort((a, b) => b.createdAt - a.createdAt));
const tableRows = computed(() => (isCreating.value ? [{ id: draft.id, isDraft: true }, ...apiKeys.value] : apiKeys.value));

function resetDraft() {
  draft.label = "";
  draft.neverExpires = true;
  draft.expiresAt = null;
  draft.unlimitedUsage = true;
  draft.maxUsage = -1;
}

function startCreate() {
  isCreating.value = true;
}

function cancelCreate() {
  isCreating.value = false;
  resetDraft();
}

function generateApiKey() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  let value = "sk-";

  for (let index = 0; index < 28; index += 1) {
    value += chars[Math.floor(Math.random() * chars.length)];
  }

  return value;
}

function formatTimestamp(value) {
  if (value === null || value === undefined || value === "") {
    return "永不过期";
  }

  const timestamp = Number(value);
  if (!Number.isFinite(timestamp) || timestamp <= 0) {
    return "--";
  }

  return new Date(timestamp).toLocaleString("zh-CN", { hour12: false });
}

function formatUsage(row) {
  if (row.maxUsage === -1) {
    return "无限";
  }

  return `${row.usageCount ?? 0} / ${row.maxUsage}`;
}

function maskKey(value, visible) {
  const text = String(value || "");
  if (visible) {
    return text || "空";
  }

  if (!text) {
    return "空";
  }

  return `${text.slice(0, 5)}${"*".repeat(Math.max(6, text.length - 5))}`;
}

async function copyKey(value) {
  try {
    await navigator.clipboard.writeText(String(value || ""));
    toast.add({ severity: "success", summary: "复制", detail: "密钥已复制", life: 1600 });
  } catch {
    toast.add({ severity: "error", summary: "复制失败", detail: "当前环境不支持复制", life: 1600 });
  }
}

function toggleVisible(id) {
  visibleKeys.value = {
    ...visibleKeys.value,
    [id]: !visibleKeys.value[id]
  };
}

function confirmCreate() {
  if (!isCreating.value) {
    return;
  }

  if (!draft.label.trim()) {
    cancelCreate();
    return;
  }

  const expiresAt = draft.neverExpires ? null : Number(draft.expiresAt);
  if (!draft.neverExpires && (!Number.isFinite(expiresAt) || expiresAt <= 0)) {
    toast.add({ severity: "warn", summary: "新增失败", detail: "请输入有效时间戳", life: 1800 });
    return;
  }

  const maxUsage = draft.unlimitedUsage ? -1 : Number(draft.maxUsage);
  if (!draft.unlimitedUsage && (!Number.isInteger(maxUsage) || maxUsage < 0)) {
    toast.add({ severity: "warn", summary: "新增失败", detail: "请输入合法访问次数", life: 1800 });
    return;
  }

  emit("create-api-key", {
    label: draft.label.trim(),
    value: generateApiKey(),
    createdAt: Date.now(),
    expiresAt,
    maxUsage,
    usageCount: 0
  });

  isCreating.value = false;
  resetDraft();
  toast.add({ severity: "success", summary: "新增成功", detail: "已生成新的 API 密钥", life: 1600 });
}

function handleDocumentPointer(event) {
  if (!isCreating.value || !rootRef.value) {
    return;
  }

  if (rootRef.value.contains(event.target)) {
    return;
  }

  confirmCreate();
}

onMounted(() => {
  document.addEventListener("pointerdown", handleDocumentPointer);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", handleDocumentPointer);
});
</script>

<template>
  <div ref="rootRef" class="page-shell">
    <Card>
      <template #title>令牌列表</template>
      <template #content>
        <div class="flat-actions token-toolbar">
          <Button
            v-if="!isCreating"
            label="新增令牌"
            icon="pi pi-plus"
            severity="secondary"
            text
            class="panel-action panel-action--small panel-action--primary"
            @click="startCreate"
          />
        </div>

        <div class="token-table-wrap">
          <DataTable
            :value="tableRows"
            paginator
            scrollable
            :rows="5"
            :rows-per-page-options="[5, 10, 20]"
            :table-style="{ minWidth: '56rem' }"
            class="token-table"
            paginator-template="PrevPageLink PageLinks NextPageLink RowsPerPageDropdown"
            data-key="id"
          >
            <Column header="名称">
              <template #body="{ data }">
                <InputText v-if="data.isDraft" v-model="draft.label" fluid placeholder="输入令牌名字" />
                <span v-else>{{ data.label }}</span>
              </template>
            </Column>

            <Column header="密钥">
              <template #body="{ data }">
                <span v-if="data.isDraft" class="token-placeholder">保存后自动生成</span>
                <div v-else class="token-secret">
                  <span>{{ maskKey(data.value, visibleKeys[data.id]) }}</span>
                  <div class="token-secret__actions">
                    <Button
                      :icon="visibleKeys[data.id] ? 'pi pi-eye-slash' : 'pi pi-eye'"
                      severity="secondary"
                      text
                      rounded
                      class="copy-action copy-action--view"
                      @click="toggleVisible(data.id)"
                    />
                    <Button
                      icon="pi pi-copy"
                      severity="secondary"
                      text
                      rounded
                      class="copy-action copy-action--copy"
                      @click="copyKey(data.value)"
                    />
                  </div>
                </div>
              </template>
            </Column>

            <Column header="有效期">
              <template #body="{ data }">
                <div v-if="data.isDraft" class="draft-cell">
                  <div class="checkbox-line">
                    <Checkbox v-model="draft.neverExpires" binary input-id="draftNeverExpires" />
                    <label for="draftNeverExpires">永不过期</label>
                  </div>
                  <InputNumber
                    v-model="draft.expiresAt"
                    fluid
                    :use-grouping="false"
                    :disabled="draft.neverExpires"
                    placeholder="时间戳"
                  />
                </div>
                <span v-else>{{ formatTimestamp(data.expiresAt) }}</span>
              </template>
            </Column>

            <Column header="访问次数">
              <template #body="{ data }">
                <div v-if="data.isDraft" class="draft-cell">
                  <div class="checkbox-line">
                    <Checkbox v-model="draft.unlimitedUsage" binary input-id="draftUnlimitedUsage" />
                    <label for="draftUnlimitedUsage">无限</label>
                  </div>
                  <InputNumber
                    v-model="draft.maxUsage"
                    fluid
                    :use-grouping="false"
                    :disabled="draft.unlimitedUsage"
                    placeholder="次数"
                  />
                </div>
                <span v-else>{{ formatUsage(data) }}</span>
              </template>
            </Column>

            <Column header="创建时间">
              <template #body="{ data }">
                <span v-if="data.isDraft">--</span>
                <span v-else>{{ formatTimestamp(data.createdAt) }}</span>
              </template>
            </Column>

            <Column header="操作" :style="{ width: '8rem' }">
              <template #body="{ data }">
                <div v-if="data.isDraft" class="token-secret__actions">
                  <Button icon="pi pi-check" severity="secondary" text rounded class="copy-action copy-action--confirm" @click="confirmCreate" />
                  <Button icon="pi pi-times" severity="secondary" text rounded class="copy-action copy-action--cancel" @click="cancelCreate" />
                </div>
                <div v-else class="token-secret__actions">
                  <Button
                    icon="pi pi-trash"
                    severity="secondary"
                    text
                    rounded
                    class="copy-action copy-action--delete"
                    @click="emit('remove-api-key', data.id)"
                  />
                </div>
              </template>
            </Column>
          </DataTable>
        </div>
      </template>
    </Card>
  </div>
</template>
