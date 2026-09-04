import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
  },
  build: {
    // genlayer-js is a chunky SDK used by every page via wallet + contract
    // reads; it ships as its own cached chunk.
    chunkSizeWarningLimit: 550,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          genlayer: ["genlayer-js"],
        },
      },
    },
  },
});
