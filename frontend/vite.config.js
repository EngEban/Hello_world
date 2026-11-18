import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export function createDevApiProxy(target = 'http://127.0.0.1:8000') {
  return {
    target,
    changeOrigin: true,
    configure(proxy) {
      proxy.on('proxyReq', (proxyRequest, request) => {
        // Bridge ONLY same-origin browser requests through the development
        // proxy. Foreign origins remain unchanged and fail Django's CSRF check.
        try {
          const sourceOrigin = `${request.socket?.encrypted ? 'https' : 'http'}://${request.headers.host}`;
          if (request.headers.origin && new URL(request.headers.origin).origin === sourceOrigin) {
            proxyRequest.setHeader('Origin', new URL(target).origin);
          }
        } catch { /* Invalid origins are left for Django to reject. */ }
      });
    },
  };
}

const devBackendTarget = process.env.VITE_DEV_API_PROXY_TARGET || process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000';

export default defineConfig({
  // The Docker deployment sets this to /static/ so Django/WhiteNoise can
  // serve Vite's hashed files.  Local Vite and the standalone static site
  // retain their existing root-relative asset URLs.
  base: process.env.VITE_ASSET_BASE_PATH || '/',
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            // React + router change far less often than app code: a separate
            // chunk stays cached in browsers across most deployments.
            { name: 'react-vendor', test: /[\/]node_modules[\/](react|react-dom|scheduler|react-router|react-router-dom|cookie|set-cookie-parser)[\/]/, priority: 20 },
          ],
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': createDevApiProxy(devBackendTarget),
      // Uploaded files (article images, imported WordPress uploads) are served by Django.
      '/media': { target: devBackendTarget, changeOrigin: true },
    },
  },
});
