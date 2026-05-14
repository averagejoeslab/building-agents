import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@examples": path.resolve(__dirname, "../examples"),
    },
  },
  server: {
    fs: {
      // Allow reading the sibling examples/ directory so slides can import
      // the actual checkpoint files via `?raw`.
      allow: [path.resolve(__dirname, ".."), path.resolve(__dirname)],
    },
  },
});
