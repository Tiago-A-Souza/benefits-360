import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const raiz = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(join(raiz, "package.json"), "utf8"));

function commitCurto() {
  const env = process.env.VITE_BUILD_COMMIT || process.env.GITHUB_SHA || "";
  if (env) return String(env).slice(0, 7);
  try {
    return execSync("git rev-parse --short HEAD", {
      cwd: raiz,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
}

export default defineConfig({
  root: ".",
  base: "/",
  // Com junction (C:\np) ou cwd no caminho real, impede o Vite de derivar o
  // caminho longo do subst N: e o rollup de emitir index.html absoluto.
  resolve: {
    preserveSymlinks: true,
  },
  plugins: [react()],
  define: {
    __BENEFITS_VERSAO__: JSON.stringify(pkg.version),
    __BENEFITS_COMMIT__: JSON.stringify(commitCurto()),
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    // API local: 8002 evita processo uvicorn fantasma que às vezes fica preso na 8001
    proxy: {
      "/api": "http://127.0.0.1:8002",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**"],
  },
});
