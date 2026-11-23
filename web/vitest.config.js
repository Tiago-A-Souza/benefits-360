import { defineConfig } from "vitest/config";
import viteConfig from "./vite.config.js";

export default defineConfig({
  ...viteConfig,
  test: {
    ...(viteConfig.test || {}),
    exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**"],
  },
});
