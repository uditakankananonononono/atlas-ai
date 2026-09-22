import {defineConfig,devices} from '@playwright/test';
// NEXT_PUBLIC_* values are inlined by `next build`, so the web server command
// rebuilds with the same test Supabase env the specs mock against.
const testEnv={NEXT_PUBLIC_SUPABASE_URL:'https://test.supabase.co',NEXT_PUBLIC_SUPABASE_ANON_KEY:'test-anon-key'};
export default defineConfig({testDir:'./e2e',timeout:30000,use:{baseURL:'http://127.0.0.1:3100',trace:'retain-on-failure'},webServer:{command:'npm run build && npm run start -- -p 3100',url:'http://127.0.0.1:3100',reuseExistingServer:false,timeout:240000,env:testEnv},projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}]});
