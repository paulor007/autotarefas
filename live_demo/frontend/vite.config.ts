import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// O front consome a API real do backend. Em dev, o proxy evita CORS: tudo sai
// de http://localhost:5173 e o Vite encaminha /api -> backend. Em producao, o
// FastAPI serve o build (dist/) na raiz, entao e a mesma origem (sem CORS).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./",
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:7860", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
