import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // 将所有 /api 开头的请求代理到 FastAPI 服务器，以避免CORS问题
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
