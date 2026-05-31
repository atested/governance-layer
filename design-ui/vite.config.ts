import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "dockview/dist/styles/dockview.css": fileURLToPath(
        new URL("./node_modules/dockview/dist/styles/dockview.css", import.meta.url),
      )
    }
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:4174"
    }
  }
});
