import { defineConfig } from "@playwright/test";

/**
 * Fumaça do Benefits (bundle de produção).
 *
 *   cd web
 *   npm run smoke
 *
 * Sobe `vite preview` na 4173, mocka API e robô, navega rotas/etapas.
 * Falha se houver exceção não tratada, erro no console ou tela vazia.
 * Não fala com a API 8002 nem com o robô 8600 reais.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 12_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    channel: process.env.PW_CHANNEL || "msedge",
    headless: true,
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  webServer: {
    command: "node ./node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4173 --strictPort",
    port: 4173,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
