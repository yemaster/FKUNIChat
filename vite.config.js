import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import fs from "node:fs";

const packageJson = JSON.parse(fs.readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

export default defineConfig({
  plugins: [vue()],
  base: "./",
  define: {
    __APP_VERSION__: JSON.stringify(packageJson.version)
  },
  build: {
    outDir: "dist/renderer",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return;
          }

          if (id.includes("primeicons")) {
            return "primeicons";
          }

          if (id.includes("/vue/")) {
            return "vue";
          }

          if (id.includes("primevue/datatable") || id.includes("primevue/column") || id.includes("primevue/paginator")) {
            return "primevue-table";
          }

          if (
            id.includes("primevue/inputtext") ||
            id.includes("primevue/inputnumber") ||
            id.includes("primevue/checkbox") ||
            id.includes("primevue/select")
          ) {
            return "primevue-form";
          }

          if (
            id.includes("primevue/button") ||
            id.includes("primevue/card") ||
            id.includes("primevue/toast") ||
            id.includes("primevue/toastservice") ||
            id.includes("primevue/usetoast")
          ) {
            return "primevue-ui";
          }

          if (id.includes("primevue")) {
            return "primevue-core";
          }
        }
      }
    }
  }
});
