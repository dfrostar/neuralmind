import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

// Component and gate tests for the performance record (test/). Components are
// rendered with react-dom/server: the site is a static export, so the markup
// the build writes is the thing to assert on.
export default defineConfig({
    esbuild: { jsx: 'automatic' },
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    test: { include: ['test/**/*.test.{ts,tsx}'], environment: 'node' },
});
