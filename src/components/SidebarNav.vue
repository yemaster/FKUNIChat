<script setup>
import { computed } from "vue";

const props = defineProps({
  collapsed: {
    type: Boolean,
    required: true
  },
  mobile: {
    type: Boolean,
    default: false
  },
  open: {
    type: Boolean,
    default: false
  },
  activePage: {
    type: String,
    required: true
  },
  limitedMode: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(["toggle", "navigate"]);

const fullPrimaryItems = [
  { id: "home", label: "控制", icon: "pi pi-sliders-h" },
  { id: "chat-test", label: "测试", icon: "pi pi-comments" },
  { id: "api-keys", label: "密钥", icon: "pi pi-key" },
  { id: "logs", label: "日志", icon: "pi pi-file-edit" }
];

const primaryItems = computed(() => (
  props.limitedMode
    ? [{ id: "setup", label: "初始化", icon: "pi pi-sparkles" }]
    : fullPrimaryItems
));

const secondaryItems = computed(() => (
  props.limitedMode
    ? [{ id: "settings", label: "设置", icon: "pi pi-cog" }]
    : [
        { id: "help", label: "帮助", icon: "pi pi-question-circle" },
        { id: "settings", label: "设置", icon: "pi pi-cog" }
      ]
));
</script>

<template>
  <aside class="sidebar" :class="{ collapsed, mobile, open }">
    <div class="sidebar__brand" :class="{ 'sidebar__brand--collapsed': collapsed }">
      <div class="sidebar__brand-copy">
        <span class="sidebar__brand-mark" />
        <strong v-if="!collapsed">FKUNIChat NG</strong>
        <strong v-else>FK</strong>
      </div>
      <button v-ripple class="sidebar__toggle" type="button" @click="emit('toggle')">
        <span :class="collapsed ? 'pi pi-angle-right' : 'pi pi-angle-left'" aria-hidden="true" />
      </button>
    </div>

    <div class="sidebar__body">
      <nav class="sidebar__nav">
        <button
          v-for="item in primaryItems"
          :key="item.id"
          type="button"
          class="nav-link"
          :class="{ active: activePage === item.id }"
          v-ripple
          @click="emit('navigate', item.id)"
        >
          <span class="nav-link__icon" :class="item.icon" aria-hidden="true" />
          <span v-if="!collapsed" class="nav-link__label">{{ item.label }}</span>
        </button>
      </nav>

      <nav class="sidebar__nav sidebar__nav--secondary">
        <button
          v-for="item in secondaryItems"
          :key="item.id"
          type="button"
          class="nav-link"
          :class="{ active: activePage === item.id }"
          v-ripple
          @click="emit('navigate', item.id)"
        >
          <span class="nav-link__icon" :class="item.icon" aria-hidden="true" />
          <span v-if="!collapsed" class="nav-link__label">{{ item.label }}</span>
        </button>
      </nav>
    </div>
  </aside>
</template>
