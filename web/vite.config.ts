import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const API = "http://127.0.0.1:8000";

// The build lands in the Python package, flat and with stable names: the API serves the page
// at GET / and every asset under /static/, and package-data only globs api/static/*.
export default defineConfig({
  plugins: [react()],
  base: "/static/",
  build: {
    outDir: "../src/lexbridge/api/static",
    emptyOutDir: true,
    assetsDir: "",
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "[name].js",
        assetFileNames: "[name][extname]",
      },
    },
  },
  server: {
    proxy: { "/chat": API, "/section": API, "/map": API, "/feedback": API, "/health": API },
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    setupFiles: ["tests/setup.ts"],
    coverage: {
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx"],
      thresholds: { lines: 80, functions: 80, branches: 80, statements: 80 },
    },
  },
});
