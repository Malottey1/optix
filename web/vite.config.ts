import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// base "./": the built site works from any static host or sub-path (routes are hash routes).
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  server: { host: "127.0.0.1", port: 5173 },
  preview: { host: "127.0.0.1" },
  build: {
    target: "es2022",
    sourcemap: false,
    // fonts are emitted as files; never inline them as data: URIs
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 300,
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
    setupFiles: ["src/test/setup.ts"],
    restoreMocks: true,
  },
});
