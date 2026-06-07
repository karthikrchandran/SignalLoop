import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react-swc"
import { defineConfig } from "vite"

// https://vitejs.dev/config/
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return
          }

          if (
            id.includes("/react/") ||
            id.includes("/react-dom/") ||
            id.includes("/scheduler/")
          ) {
            return "vendor-core"
          }

          if (id.includes("/@tanstack/")) {
            return "vendor-tanstack"
          }

          if (id.includes("/@radix-ui/")) {
            return "vendor-radix"
          }

          if (id.includes("/lucide-react/") || id.includes("/react-icons/")) {
            return "vendor-icons"
          }

          if (
            id.includes("/recharts/") ||
            id.includes("/d3-") ||
            id.includes("/victory-vendor/")
          ) {
            return "vendor-charts"
          }

          if (
            id.includes("/@hookform/") ||
            id.includes("/react-hook-form/") ||
            id.includes("/date-fns/") ||
            id.includes("/zod/") ||
            id.includes("/axios/")
          ) {
            return "vendor-utils"
          }

          return "vendor-core"
        },
      },
    },
  },
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
    }),
    react(),
    tailwindcss(),
  ],
})
