import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // 개발 중에는 같은 출처로 보내 CORS를 신경 쓰지 않는다. 배포에서는
    // VITE_API_BASE_URL이 채워지고 이 프록시는 쓰이지 않는다.
    proxy: {
      "/api": { target: process.env.VITE_DEV_API ?? "http://localhost:8000", changeOrigin: true },
    },
  },
});
