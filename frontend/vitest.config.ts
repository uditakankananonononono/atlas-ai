import {defineConfig} from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({plugins:[react()],test:{environment:"jsdom",setupFiles:["./vitest.setup.ts"],include:["components/**/*.test.tsx"],globals:false}});
