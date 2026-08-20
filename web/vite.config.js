import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: ".",
  base: "/",
  // Com junction (C:\np) ou cwd no caminho real, impede o Vite de derivar o
  // caminho longo do subst N: e o rollup de emitir index.html absoluto.
  resolve: {
    preserveSymlinks: true,
  },
  plugins: [react()],
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
});
