import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

// Vite configuration for React app
export default defineConfig({
  plugins: [react()],
  base: "/static/",
  build: {
    outDir: resolve(__dirname, "../backend/static"), // Output build files to backend/static
    emptyOutDir: true, // Clear the output directory before building
  },
});
