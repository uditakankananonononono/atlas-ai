import {defineConfig,devices} from '@playwright/test';
const port=process.env.ATLAS_BRIDGE_UI_PORT;
if(!port||!process.env.ATLAS_BRIDGE_API_URL||!process.env.ATLAS_BRIDGE_TOKEN)throw Error('Run scripts/audit/m09_http_ui_bridge.py with the project Python environment');
export default defineConfig({testDir:'./e2e',testMatch:'knowledge-http-bridge.spec.ts',timeout:30000,use:{baseURL:`http://127.0.0.1:${port}`,trace:'retain-on-failure'},webServer:{command:`npm run build && npm run start -- -p ${port}`,url:`http://127.0.0.1:${port}`,reuseExistingServer:false,timeout:240000},projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}]});
