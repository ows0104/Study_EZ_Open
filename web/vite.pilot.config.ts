import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  base: './',
  publicDir: false,
  server: { host: '127.0.0.1', port: 5186, strictPort: true },
  preview: { host: '127.0.0.1', port: 5186, strictPort: true },
  build: {
    outDir: 'pilot-dist',
    rollupOptions: { input: fileURLToPath(new URL('./connection-pilot.html', import.meta.url)) },
  },
});
