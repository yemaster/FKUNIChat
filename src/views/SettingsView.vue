<script setup>
import { computed } from "vue";
import Card from "primevue/card";
import Select from "primevue/select";
import { normalizeThemeColor, normalizeThemeMode, resolveThemeMode } from "../lib/theme";

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  },
  appVersion: {
    type: String,
    required: true
  },
  environmentLabel: {
    type: String,
    required: true
  }
});

const emit = defineEmits(["update:model-value", "navigate"]);

const themeColorOptions = [
  { label: "天蓝", value: "#0ea5e9" },
  { label: "青绿", value: "#10b981" },
  { label: "琥珀", value: "#f59e0b" },
  { label: "珊瑚", value: "#f97316" },
  { label: "玫红", value: "#e11d48" },
  { label: "紫罗兰", value: "#8b5cf6" },
  { label: "靛蓝", value: "#4f46e5" },
  { label: "石墨", value: "#475569" }
];

const themeModeOptions = [
  { label: "亮色", value: "light" },
  { label: "暗黑", value: "dark" },
  { label: "跟随主题", value: "system" }
];

const selectedThemeColor = computed({
  get() {
    return normalizeThemeColor(props.modelValue.themeColor);
  },
  set(value) {
    emit("update:model-value", {
      themeColor: normalizeThemeColor(value)
    });
  }
});

const themeModeModel = computed({
  get() {
    return normalizeThemeMode(props.modelValue.themeMode);
  },
  set(value) {
    emit("update:model-value", {
      themeMode: normalizeThemeMode(value)
    });
  }
});
</script>

<template>
  <div class="page-shell settings-shell">
    <div class="settings-grid">
      <Card class="settings-card">
        <template #title>主题色</template>
        <template #content>
          <div class="theme-swatch-list">
            <label
              v-for="option in themeColorOptions"
              :key="option.value"
              class="theme-swatch"
              :title="option.label"
            >
              <input
                :checked="selectedThemeColor === option.value"
                :aria-label="option.label"
                class="theme-swatch__input"
                name="theme-color"
                type="radio"
                :value="option.value"
                @change="selectedThemeColor = option.value"
              />
              <span class="theme-swatch__control" :style="{ '--swatch-color': option.value }">
                <i v-if="selectedThemeColor === option.value" class="pi pi-check" />
              </span>
            </label>
          </div>
        </template>
      </Card>

      <Card class="settings-card">
        <template #title>显示模式</template>
        <template #content>
          <Select
            v-model="themeModeModel"
            :options="themeModeOptions"
            class="settings-select"
            option-label="label"
            option-value="value"
          />
        </template>
      </Card>
    </div>

    <section class="settings-about">
      <h3>关于 FKUNIChat NG</h3>
      <p>Flexible & Keystone UNI Chat API Framework. 用于将 USTChat 接入你的 AI 应用。</p>
      <div class="settings-about-links">
        <button type="button" class="settings-about-link" @click="emit('navigate', 'service-terms')">查看服务协议</button>
        <button type="button" class="settings-about-link" @click="emit('navigate', 'privacy')">查看隐私条款</button>
      </div>
      <p>{{ environmentLabel }} 构建版本 {{ appVersion }}</p>
      <p>
        Made by 
        <a class="settings-about-link" href="https://github.com/yemaster" target="_blank" rel="noopener noreferrer">yemaster</a>
        with ❤️. Github: 
        <a class="settings-about-link" href="https://github.com/yemaster/FKUNIChat" target="_blank" rel="noopener noreferrer">FKUNIChat</a>
      </p>
    </section>
  </div>
</template>
