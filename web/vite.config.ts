/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { svelteTesting } from "@testing-library/svelte/vite";
import { configDefaults } from "vitest/config";

export default defineConfig({
  plugins: [svelte(), svelteTesting()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8080", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest-setup.ts"],
    // Playwright owns browser specs; they fail to load under vitest.
    exclude: [...configDefaults.exclude, "e2e/**", "docs-screenshots/**"],
  },
});
