import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

/** Dev-only: where `/api` is proxied. Override in `frontend/.env` (see `.env.example`). */
const DEFAULT_API = "http://127.0.0.1:8000";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.PARKSMART_DEV_API_URL?.trim() || DEFAULT_API;

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
        },
      },
    },
  };
});
