import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Instância alternativa (rede etapa 5) — proxy 8003, porta 5174. */
export default defineConfig({
  root: ".",
  base: "/",
  cacheDir: "node_modules/.vite-alt",
  resolve: {
    preserveSymlinks: true,
  },
  plugins: [react()],
  server: {
    host: true,
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8003",
    },
  },
  build: {
    outDir: "dist-alt",
    emptyOutDir: true,
  },
});
