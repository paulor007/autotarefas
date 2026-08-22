import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, loadEnv } from "vite";

/**
 * Porta padrao do backend.
 *
 * E o MESMO valor do `PORT` em `apps/api/app/config.py`, do
 * `Dockerfile` e do README. Mudar a porta do backend deve exigir mexer em uma
 * fonte so: a variavel de ambiente abaixo — nunca em componente React.
 */
const DEFAULT_API_TARGET = "http://127.0.0.1:7860";

export default defineConfig(({ mode }) => {
  // `loadEnv` le .env / .env.local / .env.<mode> desta pasta.
  const env = loadEnv(mode, process.cwd(), "");

  // Onde o proxy de DESENVOLVIMENTO encaminha /api. Em producao isto nao
  // existe: o FastAPI serve o dist/ na propria origem, e as chamadas do front
  // sao relativas (/api/...), sem host nem porta no bundle.
  const apiTarget = env.VITE_API_TARGET || DEFAULT_API_TARGET;
  const devPort = Number(env.VITE_DEV_PORT) || 5173;

  return {
    plugins: [react(), tailwindcss()],
    base: "./",
    server: {
      port: devPort,
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
      },
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
    test: {
      // jsdom porque os testes exercitam componentes React de verdade.
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});
