import { createApp } from "vue";
import PrimeVue from "primevue/config";
import Ripple from "primevue/ripple";
import ToastService from "primevue/toastservice";
import "primeicons/primeicons.css";
import App from "./App.vue";
import { createThemePreset, DARK_MODE_SELECTOR, DEFAULT_THEME_COLOR } from "./lib/theme";
import "./styles.css";

const app = createApp(App);

app.use(PrimeVue, {
  ripple: true,
  theme: {
    preset: createThemePreset(DEFAULT_THEME_COLOR),
    options: {
      darkModeSelector: DARK_MODE_SELECTOR
    }
  }
});
app.use(ToastService);
app.directive("ripple", Ripple);

app.mount("#app");
