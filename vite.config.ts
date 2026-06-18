import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'node:path';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    headers: {
      'Cross-Origin-Embedder-Policy': 'require-corp',
      'Cross-Origin-Opener-Policy': 'same-origin',
    },
  },
  build: {
    target: 'es2022',
    // 默认不出 sourcemap（产物更小）；需要调试时设 VITE_SOURCEMAP=true
    sourcemap: process.env.VITE_SOURCEMAP === 'true',
    assetsInlineLimit: 0,
    rollupOptions: {
      output: {
        manualChunks: (id: string): string | undefined => {
          if (id.includes('node_modules/vue') || id.includes('node_modules/pinia')) {
            return 'vendor-vue';
          }
          if (id.includes('node_modules/naive-ui')) {
            return 'vendor-ui';
          }
          if (id.includes('node_modules/konva')) {
            return 'vendor-canvas';
          }
          // stockfish 不打包 (走 public/ 静态资源)
          return undefined;
        },
      },
    },
  },
  worker: {
    format: 'es',
  },
});
