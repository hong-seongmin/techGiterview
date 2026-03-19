import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

const usePolling =
  process.env.VITE_USE_POLLING === 'true' ||
  process.env.CHOKIDAR_USEPOLLING === 'true'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  
  // 개발 서버 설정
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.PORT || '3000'),
    open: false, // Docker 환경에서 false로 설정
    watch: {
      usePolling,
      interval: usePolling ? parseInt(process.env.CHOKIDAR_INTERVAL || '1000', 10) : undefined,
      ignored: ['**/.git/**', '**/node_modules/**', '**/dist/**'],
    },
    proxy: {
      // API 프록시 설정 (Docker 기본 타깃: backend:8002)
      '/api': {
        target: process.env.VITE_API_URL || 'http://backend:8002',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('Proxy error:', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('Proxy request:', req.method, req.url, '-> target:', proxyReq.path);
          });
        }
      },
      // WebSocket 프록시 설정 (IPv4 강제)
      '/ws': {
        target: process.env.VITE_WS_URL || 'ws://backend:8002',
        changeOrigin: true,
        ws: true,
      }
    }
  },
  
  // 빌드 설정
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // 벤더 청크 분리
          vendor: ['react', 'react-dom', 'react-router-dom'],
        }
      }
    }
  },
  
  // 경로 별칭 설정
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@components': resolve(__dirname, 'src/components'),
      '@pages': resolve(__dirname, 'src/pages'),
      '@services': resolve(__dirname, 'src/services'),
      '@types': resolve(__dirname, 'src/types'),
      '@utils': resolve(__dirname, 'src/utils'),
      '@assets': resolve(__dirname, 'src/assets'),
    }
  },
  
  // 테스트 설정
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
      ]
    }
  },
  
  // 환경 변수 설정
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version),
  },
  
  // CSS 설정
  css: {
    devSourcemap: true
  }
})
