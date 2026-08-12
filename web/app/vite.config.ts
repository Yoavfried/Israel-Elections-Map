import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve: {
    alias: [
      {
        find: /^rtl-text-plugin(?=\?url$)/,
        replacement: fileURLToPath(
          new URL(
            './node_modules/@mapbox/mapbox-gl-rtl-text/dist/mapbox-gl-rtl-text.js',
            import.meta.url,
          ),
        ),
      },
    ],
  },
  build: {
    sourcemap: mode !== 'deployment',
    // MapLibre is intentionally isolated behind React.lazy; its minified chunk is about 1.03 MB.
    chunkSizeWarningLimit: 1_100,
  },
  server: {
    port: 4173,
    strictPort: true,
  },
}))
