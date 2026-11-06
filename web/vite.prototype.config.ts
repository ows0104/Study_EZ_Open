import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

// UI/UX 개편 비주얼 프로토타입. 서버·로그인 없이 가짜 데이터로만 그린다.
export default defineConfig({
  plugins: [
    react(),
    {
      // 주소 루트로 들어와도 운영 앱(index.html) 대신 프로토타입을 연다.
      name: 'prototype-root',
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url === '/' || req.url === '/index.html') req.url = '/redesign-prototype.html';
          next();
        });
      },
    },
  ],
  base: './',
  publicDir: false,
  server: { host: '127.0.0.1', port: 5187, strictPort: true },
  preview: { host: '127.0.0.1', port: 5187, strictPort: true },
  build: {
    outDir: 'prototype-dist',
    rollupOptions: { input: fileURLToPath(new URL('./redesign-prototype.html', import.meta.url)) },
  },
});
