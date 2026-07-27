import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
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
