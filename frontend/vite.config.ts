import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, new URL('..', import.meta.url).pathname, 'FAIR_HDF5_');
  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': env.FAIR_HDF5_API_TARGET || `http://127.0.0.1:${env.FAIR_HDF5_PORT || '8000'}`,
      },
    },
    build: { outDir: 'dist', emptyOutDir: true },
  };
});
