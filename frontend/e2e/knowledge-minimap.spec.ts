import {test,expect,Page} from '@playwright/test';
async function signedIn(page:Page){
 await page.addInitScript(()=>{localStorage.setItem('atlas:onboarding:complete','1');localStorage.setItem('sb-test-auth-token',JSON.stringify({access_token:'test-token',refresh_token:'refresh',expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,token_type:'bearer',user:{id:'user-1',aud:'authenticated',role:'authenticated',email:'owner@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}}));});
 await page.route('**/auth/v1/**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'user-1',email:'owner@example.test'}})}));
 await page.route('**/api/v1/modules',route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));
 await page.route('**/api/v1/executive-dashboard/**',route=>route.fulfill({status:200,contentType:'application/json',body:route.request().url().endsWith('/view')?'{}':'[]'}));
 await page.goto('/');await page.getByRole('button',{name:'knowledge'}).click();
}
test('knowledge graph minimap renders node rectangles and fits all nodes',async({page})=>{
 await signedIn(page);
 const nodes=Array.from({length:12},(_,i)=>({id:'n'+i,node_type:i%2?'note':'source',title:'Node '+i,metadata:{}}));
 const edges=[{id:'e1',source_id:'n0',target_id:'n1',relationship:'cites',confidence:1}];
 await page.route('**/api/v1/knowledge-workspace/nodes/**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({nodes,edges})}));
 await page.getByLabel('Knowledge node ID').fill('seed-1');
 await expect(page.getByLabel('Knowledge graph')).toBeVisible();
 const mm=page.locator('.react-flow__minimap');
 await expect(mm).toBeVisible();
 await page.waitForTimeout(800);
 const rects=await page.locator('.react-flow__minimap-node').count();
 const widths=await page.locator('.react-flow__minimap-node').evaluateAll(els=>els.map(e=>Number(e.getAttribute('width'))));
 console.log('MINIMAP_NODE_RECTS',rects,'WIDTHS',JSON.stringify(widths.slice(0,4)));
 await mm.screenshot({path:'test-results/knowledge-minimap.png'});
 await page.locator('.react-flow').screenshot({path:'test-results/knowledge-graph.png'});
 expect(rects).toBe(12);
});
