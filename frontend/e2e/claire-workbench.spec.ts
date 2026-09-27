import {test,expect} from '@playwright/test';

test('Claire workbench shows consent-gated interview and source-backed opportunity card',async({page})=>{
 await page.addInitScript(()=>{
  localStorage.setItem('atlas:onboarding:complete','1');
  localStorage.setItem('sb-test-auth-token',JSON.stringify({access_token:'test-token',refresh_token:'refresh',expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,token_type:'bearer',user:{id:'owner',aud:'authenticated',role:'authenticated',email:'owner@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}}));
 });
 await page.route('**/auth/v1/**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'owner',email:'owner@example.test'}})}));
 await page.route('**/api/v1/modules',route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));
 await page.route('**/api/v1/executive-dashboard/**',route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));
 let consentRequest:any;
 await page.route('**/api/v1/claire/interview/consent',route=>{consentRequest=route.request();return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({enabled:true})})});
 await page.route('**/api/v1/claire/opportunities/triage',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({cards:[{title:'Robotics challenge',url:'https://official.example/contest',status:'needs_official_rules_and_owner_eligibility_review',application_submitted:false}],external_effects:[]})}));
 await page.goto('/');
 await page.getByRole('button',{name:'workbench'}).click();
 await page.getByRole('button',{name:'M21 Claire'}).click();
 await expect(page.getByText('No automatic sends or applications.')).toBeVisible();
 await page.getByLabel('Action').selectOption({label:'PUT - Allow owner interview'});
 await page.getByRole('button',{name:'Run exact action'}).click();
 await expect(page.locator('pre[aria-live="polite"]')).toContainText('"enabled": true');
 expect(consentRequest.method()).toBe('PUT');
 expect(consentRequest.postDataJSON()).toEqual({enabled:true});
 await page.getByLabel('Action').selectOption({label:'POST - Review public opportunities'});
 await page.getByRole('button',{name:'Run exact action'}).click();
 await expect(page.locator('pre[aria-live="polite"]')).toContainText('needs_official_rules_and_owner_eligibility_review');
 await expect(page.locator('pre[aria-live="polite"]')).toContainText('"application_submitted": false');
});
