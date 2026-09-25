import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Array form so the photo regex can sit beside the path alias. Static
    // image imports must resolve to StaticImageData, as the real bundler
    // produces, or next/image throws in any test that renders a photo.
    alias: [
      {
        find: /^.*\.(webp|png|jpe?g|avif)$/,
        replacement: resolve(
          fileURLToPath(new URL(".", import.meta.url)),
          "./src/test/static-image-stub.ts",
        ),
      },
      {
        find: "@",
        replacement: resolve(fileURLToPath(new URL(".", import.meta.url)), "./src"),
      },
    ],
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
