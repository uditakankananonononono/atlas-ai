import {test,expect} from '@playwright/test';
test('A02 A03 A05 A06 actual React Tailwind graph and chart with controlled API fixtures',async({page})=>{
 await page.addInitScript(()=>{
  localStorage.setItem('atlas:onboarding:complete','1');
  localStorage.setItem('sb-test-auth-token',JSON.stringify({access_token:'test-token',refresh_token:'refresh',expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,token_type:'bearer',user:{id:'user-1',aud:'authenticated',role:'authenticated',email:'owner@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}}));
 });
 await page.route('**/auth/v1/**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'user-1'}})}));
 await page.route('**/api/v1/modules',r=>r.fulfill({status:200,contentType:'application/json',body:'[]'}));
 await page.route('**/api/v1/executive-dashboard/**',r=>{
  const url=r.request().url();
  const body=url.includes('/kpis')?[
   {id:'a',label:'Fixture A',value:3,unit:'count',window_hours:24,evidence_refs:[]},
   {id:'b',label:'Fixture B',value:7,unit:'count',window_hours:24,evidence_refs:[]},
   {id:'c',label:'Fixture C',value:5,unit:'count',window_hours:24,evidence_refs:[]}
  ]:url.includes('/view')?{}:[];
  return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('/');
 const chart=page.getByLabel('Current KPI values by unit');await expect(chart).toBeVisible();
 await expect(chart.locator('svg.recharts-surface')).toBeVisible();
 await expect(chart.locator('path.recharts-rectangle')).toHaveCount(3);
 expect(await page.locator('main').first().evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgb(2, 6, 23)');
 await page.screenshot({path:'../audits/rebuild-20261008/source-units/frontend-render/chart.png',fullPage:true});
 await page.route('**/api/v1/knowledge-workspace/nodes/*/neighborhood*',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({nodes:[{id:'seed',node_type:'paper',title:'Controlled paper',body:'Fixture evidence',metadata:{}},{id:'target',node_type:'claim',title:'Controlled claim',metadata:{}}],edges:[{id:'edge1',source_id:'seed',target_id:'target',relationship:'supports',confidence:1}]})}));
 await page.getByRole('button',{name:'knowledge',exact:true}).click();await page.getByPlaceholder('Select or paste an ID').fill('seed');
 const graph=page.getByLabel('Knowledge graph');await expect(graph.locator('.react-flow__node')).toHaveCount(2);
 await expect(graph.locator('.react-flow__edge')).toHaveCount(1);
 await expect(graph.locator('.react-flow__minimap')).toBeVisible();
 await page.screenshot({path:'../audits/rebuild-20261008/source-units/frontend-render/graph.png',fullPage:true});
 await graph.getByRole('button',{name:'claim',exact:true}).click();await expect(graph.locator('.react-flow__node')).toHaveCount(1);await expect(graph.locator('.react-flow__edge')).toHaveCount(0);
});
