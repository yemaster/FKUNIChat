<script setup>
import { nextTick, onMounted, watch } from "vue";
import Card from "primevue/card";

const props = defineProps({
  helpAnchor: {
    type: String,
    default: ""
  },
  helpAnchorToken: {
    type: Number,
    default: 0
  }
});

const helpCards = [
  {
    id: "ustc-token",
    title: "USTChat Token",
    items: [
      "用于登录 USTChat 并使用相关服务。",
      "自动获取会调用内置浏览器，登录之后会自动获取并保存 Token。",
      "手动获取则需要自己打开网站，登录之后，读取 localStorage 中的相关内容，并粘贴到输入框中。"
    ]
  },
  {
    id: "service-start",
    title: "如何使用启动的服务",
    items: [
      "API 兼容 OpenAI, Codex 和 Claude Code，参考首页给出的调用参考即可。"
    ]
  },
  {
    id: "api-keys",
    title: "API 密钥",
    items: [
      "在密钥页新增本地 API Key。",
      "启动后可在首页直接复制调用参数。",
      "删除密钥不会影响已保存的 USTChat Token。"
    ]
  }
];

async function scrollToAnchor(anchor) {
  const normalizedAnchor = String(anchor || "").trim();
  if (!normalizedAnchor) {
    return;
  }

  await nextTick();
  const element = document.getElementById(normalizedAnchor);
  element?.scrollIntoView({ behavior: "smooth", block: "start" });
}

onMounted(() => {
  void scrollToAnchor(props.helpAnchor);
});

watch(
  () => props.helpAnchorToken,
  () => {
    void scrollToAnchor(props.helpAnchor);
  }
);
</script>

<template>
  <div class="page-shell help-shell">
    <div class="help-grid">
      <Card
        v-for="card in helpCards"
        :id="card.id"
        :key="card.id"
        class="help-card"
      >
        <template #title>{{ card.title }}</template>
        <template #content>
          <div class="help-list">
            <p v-for="item in card.items" :key="item">{{ item }}</p>
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>
