import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/__tests__/setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/__tests__/**', 'src/app.tsx', 'src/main.tsx', 'src/features/analytics/AnalyticsPage.tsx', 'src/features/auth/context/AuthContext.tsx'],
      reporter: ['text', 'lcov'],
      // Current baseline: lines 71%, functions 48%, branches 80%, statements 71%.
      // Hooks and API client are untested â€” raise these as coverage grows.
      thresholds: {
        lines: 70,
        functions: 45,
        branches: 79,
        statements: 70,
      },
    },
  },
})

