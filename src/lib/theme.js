import Aura from "@primeuix/themes/aura";
import { definePreset, palette, useTheme } from "@primeuix/themes";

export const DEFAULT_THEME_COLOR = "#0ea5e9";
export const DEFAULT_THEME_MODE = "light";
export const DARK_MODE_SELECTOR = ".app-dark";

export function normalizeThemeColor(value) {
  const input = String(value || "").trim();
  const normalized = input.startsWith("#") ? input : `#${input}`;

  if (/^#[0-9a-fA-F]{3}$/.test(normalized)) {
    const [, r, g, b] = normalized;
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase();
  }

  if (/^#[0-9a-fA-F]{6}$/.test(normalized)) {
    return normalized.toLowerCase();
  }

  return DEFAULT_THEME_COLOR;
}

export function normalizeThemeMode(value) {
  return ["light", "dark", "system"].includes(value) ? value : DEFAULT_THEME_MODE;
}

export function resolveThemeMode(themeMode, prefersDark = false) {
  const normalizedMode = normalizeThemeMode(themeMode);
  return normalizedMode === "system" ? (prefersDark ? "dark" : "light") : normalizedMode;
}

export function createThemePreset(themeColor) {
  return definePreset(Aura, {
    semantic: {
      primary: palette(normalizeThemeColor(themeColor))
    }
  });
}

export function applyThemeSettings({ themeColor, themeMode, prefersDark = false }) {
  const normalizedColor = normalizeThemeColor(themeColor);
  const normalizedMode = normalizeThemeMode(themeMode);
  const resolvedMode = resolveThemeMode(normalizedMode, prefersDark);

  useTheme({
    preset: createThemePreset(normalizedColor),
    options: {
      darkModeSelector: DARK_MODE_SELECTOR
    }
  });

  if (typeof document !== "undefined") {
    const root = document.documentElement;
    root.classList.toggle("app-dark", resolvedMode === "dark");
    root.dataset.themeMode = normalizedMode;
    root.dataset.colorMode = resolvedMode;
    root.style.colorScheme = resolvedMode;
  }

  return {
    themeColor: normalizedColor,
    themeMode: normalizedMode,
    resolvedMode
  };
}
