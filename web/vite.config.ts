import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ command }) => ({
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  plugins: [react()],
  server: { host: '127.0.0.1', port: 7777, strictPort: false },
  build: { sourcemap: command === 'serve' },
}));
