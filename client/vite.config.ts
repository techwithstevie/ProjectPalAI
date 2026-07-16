import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/lecture": "http://localhost:5001",
      "/charts": "http://localhost:5001",
    },
  },
});
