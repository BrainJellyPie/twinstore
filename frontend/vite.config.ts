/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Files excluded from React Compiler — only components that use R3F hooks
// (useFrame / useLoader / useGLTF / useAnimations etc.). Other files are auto-memoized by the Compiler.
const REACT_COMPILER_EXCLUDES = [
  "src/views/simulation/SimulationLayout.tsx",
  "src/features/playback/components/PlaybackScene.tsx",
  "src/features/playback/components/PersonaView.tsx",
  "src/features/playback/hooks/useSimulationLoop.ts",
  "src/features/store-viewer/components/SolidFloor.tsx",
  "src/features/store-viewer/components/AssetWall.tsx",
  "src/features/store-viewer/components/AssetRug.tsx",
  "src/features/store-viewer/components/AssetFixture.tsx",
  "src/features/store-viewer/components/AssetPersona.tsx",
  "src/shared/hooks/useGlbModel.ts",
];

export default defineConfig({
  plugins: [
    // router plugin must come before react()
    tanstackRouter({
      target: "react",
      routesDirectory: "./src/routes",
      generatedRouteTree: "./src/routeTree.gen.ts",
      autoCodeSplitting: true,
    }),
    react(),
    babel({
      plugins: [
        [
          "babel-plugin-react-compiler",
          {
            sources: (filename: string) =>
              !REACT_COMPILER_EXCLUDES.some((p) => filename.endsWith(p)),
          },
        ],
      ],
    }),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    // Screens with many controls render for several seconds on a busy two-core machine; 5 s made them flaky.
    testTimeout: 15_000,
  },
});
