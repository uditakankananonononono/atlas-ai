import {test,expect,Page} from '@playwright/test';
async function signedIn(page:Page){
 await page.addInitScript(()=>{localStorage.setItem('atlas:onboarding:complete','1');localStorage.setItem('sb-test-auth-token',JSON.stringify({access_token:'test-token',refresh_token:'refresh',expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,token_type:'bearer',user:{id:'user-1',aud:'authenticated',role:'authenticated',email:'owner@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}}));});
 await page.route('**/auth/v1/**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'user-1',email:'owner@example.test'}})}));
 await page.route('**/api/v1/modules',route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));
 await page.route('**/api/v1/executive-dashboard/**',route=>route.fulfill({status:200,contentType:'application/json',body:route.request().url().endsWith('/view')?'{}':'[]'}));
 await page.goto('/');await page.getByRole('button',{name:'workbench'}).click();
}
test('M18 guided experiment sends exact bounded payload and renders receipt',async({page})=>{
 await signedIn(page);let sent:any;
 await page.route('**/api/v1/side-hustle-scraper/durable-runs',async route=>{sent=route.request().postDataJSON();await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:'run-1',max_budget:0})})});
 await page.getByLabel('Experiment name').fill('Lab pilot');await page.getByLabel('First test').fill('Five interviews');await page.getByLabel('Maximum budget (USD)').fill('0');await page.getByRole('button',{name:'Create experiment'}).click();
 await expect(page.getByText('"id": "run-1"')).toBeVisible();expect(sent).toEqual({title:'Lab pilot',first_experiment:'Five interviews',max_budget:0,source_urls:[]});
});
test('M24 preview is non-charging and sends verified user inputs',async({page})=>{
 await signedIn(page);await page.getByRole('button',{name:'Preview a subscription'}).click();let sent:any;
 await page.route('**/api/v1/billing/commitment-preview',async route=>{sent=route.request().postDataJSON();await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({exact_charge:'29.00',executed:false})})});
 await page.getByLabel('Verified tax rate (%)').fill('0');await page.getByRole('button',{name:'Calculate exact preview'}).click();await expect(page.getByText('"executed": false')).toBeVisible();expect(sent.plan_id).toBe('pro');expect(sent.cancellation_policy).toBe('Cancel before renewal');
});
test('M25 capture stays disabled until exact scope review and then sends selection',async({page})=>{
 await signedIn(page);await page.getByRole('button',{name:'Start selected-screen capture'}).click();const submit=page.getByRole('button',{name:'Start reviewed capture'});await expect(submit).toBeDisabled();let sent:any;
 await page.route('**/api/v1/knowledge-copilot/sessions',async route=>{sent=route.request().postDataJSON();await route.fulfill({status:201,contentType:'application/json',body:JSON.stringify({id:'session-1',indicator_visible:true})})});
 await page.getByLabel(/Start capture only/).check();await expect(submit).toBeEnabled();await submit.click();await expect(page.getByText('"indicator_visible": true')).toBeVisible();expect(sent).toEqual({device_id:'paired-device',selected_screen_ids:['screen-1'],redactions:[]});
});
