import {test,expect} from '@playwright/test';
import {readFileSync} from 'fs';
import {join} from 'path';
const fixture=(name:string)=>JSON.parse(readFileSync(join(__dirname,'fixtures','product-core-loop',name),'utf8'));
test('failed dashboard snapshot is unavailable, never live',async({page})=>{
 await page.addInitScript(()=>{localStorage.setItem('atlas:onboarding:complete','1');localStorage.setItem('sb-test-auth-token',JSON.stringify({access_token:'fixture-token',refresh_token:'fixture',expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,token_type:'bearer',user:{id:'fixture-user',aud:'authenticated',role:'authenticated',email:'fixture@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}}));});
 await page.route('**/auth/v1/**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'fixture-user',email:'fixture@example.test'}})}));
 await page.route('**/api/v1/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/snapshot'))return route.fulfill({status:503,contentType:'application/json',body:'{"detail":"fixture snapshot unavailable"}'});
  const body=path.endsWith('/view')?fixture('dashboard-view.json'):path.endsWith('/digest')?fixture('digest.json'):[];
  return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('/');
 await expect(page.getByRole('status')).toContainText('Unavailable');
 await expect(page.getByText('Live',{exact:true})).toHaveCount(0);
 await page.screenshot({path:'/downloads/dashboard-unavailable-local.png',fullPage:true});
});

test('bounded client fetch status becomes stale and recovers',async({page})=>{
 await page.addInitScript(()=>{localStorage.setItem('atlas:onboarding:complete','1');localStorage.setItem('sb-test-auth-token',JSON.stringify({access_token:'fixture-token',refresh_token:'fixture',expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,token_type:'bearer',user:{id:'fixture-user',aud:'authenticated',role:'authenticated',email:'fixture@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}}));});
 await page.route('**/auth/v1/**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'fixture-user',email:'fixture@example.test'}})}));

 await page.clock.install();let hang=false;
 await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/snapshot')&&hang)return;
  const body=path.endsWith('/view')?fixture('dashboard-view.json'):path.endsWith('/digest')?fixture('digest.json'):path.endsWith('/snapshot')?{data:{},version:1}:[];
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('/');await expect(page.getByRole('status')).toContainText('Updated');
 hang=true;await page.clock.runFor(30000);await page.clock.runFor(10001);
 await expect(page.getByRole('status')).toContainText('Stale data');
 await expect(page.getByText('Dashboard fetch timed out after 10 seconds')).toBeVisible();
 await page.screenshot({path:'/downloads/dashboard-stale-local.png',fullPage:true});
 hang=false;await page.clock.runFor(20000);await expect(page.getByRole('status')).toContainText('Updated');
 await expect(page.getByText('Fetch status only. Source data freshness is not verified.')).toBeVisible();
 await page.screenshot({path:'/downloads/dashboard-recovered-local.png',fullPage:true});
});
