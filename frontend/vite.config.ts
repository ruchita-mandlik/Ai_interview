import { defineConfig, Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

const appHistoryRewritePlugin = (): Plugin => ({
  name: 'app-history-rewrite',
  configureServer(server) {
    server.middlewares.use((req, _res, next) => {
      const url = req.url || '';
      if (url === '/app' || url.startsWith('/app?') || url.startsWith('/app#') || url.startsWith('/app/')) {
        req.url = '/app.html';
      }
      next();
    });
  }
});

export default defineConfig({
  plugins: [react(), appHistoryRewritePlugin()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: false,
    rollupOptions: {
      input: {
        app: resolve(__dirname, 'app.html')
      }
    }
  }
});

