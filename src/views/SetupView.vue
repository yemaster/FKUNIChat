<script setup>
import { computed } from "vue";
import Button from "primevue/button";
import Card from "primevue/card";
import Checkbox from "primevue/checkbox";

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  },
  initializationState: {
    type: Object,
    required: true
  },
  initializationReady: {
    type: Boolean,
    required: true
  }
});

const emit = defineEmits([
  "update:model-value",
  "refresh-initialization",
  "open-python-download",
  "create-venv",
  "install-dependencies",
  "complete-initialization",
  "navigate"
]);

const agreementAccepted = computed({
  get() {
    return Boolean(props.modelValue.setupAcceptedPrivacy && props.modelValue.setupAcceptedServiceTerms);
  },
  set(value) {
    emit("update:model-value", {
      setupAcceptedPrivacy: Boolean(value),
      setupAcceptedServiceTerms: Boolean(value)
    });
  }
});

function statusMeta(done) {
  return done
    ? { icon: "pi pi-check-circle", text: "已完成", className: "done" }
    : { icon: "pi pi-minus-circle", text: "未完成", className: "idle" };
}

const pythonStatus = computed(() => statusMeta(props.initializationState.pythonAvailable));
const venvStatus = computed(() => statusMeta(props.initializationState.venvReady));
const dependencyStatus = computed(() => statusMeta(props.initializationState.dependenciesInstalled));
const agreementStatus = computed(() => statusMeta(agreementAccepted.value));
const missingDependencyText = computed(() => props.initializationState.missingDependencies.join(", "));
const venvLogs = computed(() => (
  Array.isArray(props.initializationState.venvLogs)
    ? props.initializationState.venvLogs
    : []
));
const dependencyLogs = computed(() => (
  Array.isArray(props.initializationState.dependencyLogs)
    ? props.initializationState.dependencyLogs
    : []
));
</script>

<template>
  <div class="page-shell setup-shell">
    <div class="setup-header">
      <Button
        label="重新检查"
        severity="secondary"
        text
        class="panel-action"
        :loading="initializationState.pendingAction === 'refresh'"
        @click="emit('refresh-initialization')"
      />
    </div>

    <div class="setup-grid">
      <Card class="setup-card">
        <template #title>
          <div class="setup-card__title">
            <span>步骤 1 检查 Python</span>
            <span class="setup-status" :class="`setup-status--${pythonStatus.className}`">
              <i :class="pythonStatus.icon" aria-hidden="true" />
              <span>{{ pythonStatus.text }}</span>
            </span>
          </div>
        </template>
        <template #content>
          <div class="setup-card__body">
            <p v-if="initializationState.pythonVersion">Python {{ initializationState.pythonVersion }}</p>
            <p v-if="initializationState.pythonExecutable" class="setup-card__meta">{{ initializationState.pythonExecutable }}</p>
            <Button
              v-if="!initializationState.pythonAvailable"
              label="安装 Python"
              severity="secondary"
              text
              class="panel-action"
              @click="emit('open-python-download')"
            />
          </div>
        </template>
      </Card>

      <Card class="setup-card">
        <template #title>
          <div class="setup-card__title">
            <span>步骤 2 创建 venv</span>
            <span class="setup-status" :class="`setup-status--${venvStatus.className}`">
              <i :class="venvStatus.icon" aria-hidden="true" />
              <span>{{ venvStatus.text }}</span>
            </span>
          </div>
        </template>
        <template #content>
          <div class="setup-card__body">
            <p v-if="initializationState.venvVersion">Python {{ initializationState.venvVersion }}</p>
            <p v-if="initializationState.venvDirectory" class="setup-card__meta">{{ initializationState.venvDirectory }}</p>
            <Button
              v-if="!initializationState.venvReady"
              :label="initializationState.systemPythonAvailable ? '创建 venv' : '先装 Python'"
              severity="secondary"
              text
              class="panel-action"
              :disabled="!initializationState.systemPythonAvailable"
              :loading="initializationState.pendingAction === 'create-venv'"
              @click="emit('create-venv')"
            />
            <div v-if="venvLogs.length > 0" class="setup-log">
              <p v-for="(line, index) in venvLogs" :key="`venv-log-${index}`">{{ line }}</p>
            </div>
          </div>
        </template>
      </Card>

      <Card class="setup-card">
        <template #title>
          <div class="setup-card__title">
            <span>步骤 3 安装依赖</span>
            <span class="setup-status" :class="`setup-status--${dependencyStatus.className}`">
              <i :class="dependencyStatus.icon" aria-hidden="true" />
              <span>{{ dependencyStatus.text }}</span>
            </span>
          </div>
        </template>
        <template #content>
          <div class="setup-card__body">
            <p v-if="initializationState.dependenciesInstalled">requirements 已安装</p>
            <p v-else-if="missingDependencyText" class="setup-card__meta">{{ missingDependencyText }}</p>
            <Button
              v-if="!initializationState.dependenciesInstalled"
              label="安装依赖"
              severity="secondary"
              text
              class="panel-action"
              :disabled="!initializationState.venvReady"
              :loading="initializationState.pendingAction === 'install-dependencies'"
              @click="emit('install-dependencies')"
            />
            <div v-if="dependencyLogs.length > 0" class="setup-log">
              <p v-for="(line, index) in dependencyLogs" :key="`dependency-log-${index}`">{{ line }}</p>
            </div>
          </div>
        </template>
      </Card>

      <Card class="setup-card">
        <template #title>
          <div class="setup-card__title">
            <span>步骤 4 同意协议</span>
            <span class="setup-status" :class="`setup-status--${agreementStatus.className}`">
              <i :class="agreementStatus.icon" aria-hidden="true" />
              <span>{{ agreementStatus.text }}</span>
            </span>
          </div>
        </template>
        <template #content>
          <div class="setup-card__body">
            <label class="checkbox-line setup-agreement-line" for="setupAgreement">
              <Checkbox v-model="agreementAccepted" input-id="setupAgreement" binary />
              <span>
                同意
                <button type="button" class="settings-about-link" @click.stop="emit('navigate', 'privacy')">隐私条款</button>
                和
                <button type="button" class="settings-about-link" @click.stop="emit('navigate', 'service-terms')">服务协议</button>
              </span>
            </label>
          </div>
        </template>
      </Card>
    </div>

    <div class="setup-footer">
      <p v-if="initializationState.error" class="setup-error">{{ initializationState.error }}</p>
      <Button
        label="开始使用项目"
        severity="secondary"
        text
        class="panel-action"
        :disabled="!initializationReady"
        @click="emit('complete-initialization')"
      />
    </div>
  </div>
</template>
