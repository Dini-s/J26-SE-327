import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Tests of the TypeScript modules under src/modules (the shell itself has none yet). Styles are not processed in tests.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/modules/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/modules/requirement-intelligence/test/setup.ts'],
    css: false,
    testTimeout: 30_000,
  },
})
