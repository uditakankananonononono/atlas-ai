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

test('minimap and controls do not cover any node card (desktop and mobile)',async({page})=>{
 for(const vp of [{width:1280,height:800},{width:390,height:844}]){
  await page.setViewportSize(vp);
  await signedIn(page);
  const nodes=Array.from({length:12},(_,i)=>({id:'n'+i,node_type:i%2?'note':'source',title:'Node '+i,metadata:{}}));
  await page.route('**/api/v1/knowledge-workspace/nodes/**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({nodes,edges:[]})}));
  await page.getByLabel('Knowledge node ID').fill('seed-1');
  await expect(page.locator('.react-flow__minimap')).toBeVisible();
  await page.waitForTimeout(800);
  const overlaps=await page.evaluate(()=>{
   const boxes=['.react-flow__minimap','.react-flow__controls'].map(q=>document.querySelector(q)!.getBoundingClientRect());
   return Array.from(document.querySelectorAll('.react-flow__node')).filter(n=>{const r=n.getBoundingClientRect();return boxes.some(b=>r.left<b.right&&r.right>b.left&&r.top<b.bottom&&r.bottom>b.top)}).map(n=>n.textContent);
  });
  await page.locator('.react-flow').screenshot({path:`test-results/knowledge-graph-${vp.width}.png`});
  expect(overlaps).toEqual([]);
 }
});

test('dragged positions survive a type filter toggle and a stale seed response is ignored',async({page})=>{
 await signedIn(page);
 const mk=(p:string)=>Array.from({length:4},(_,i)=>({id:p+i,node_type:i%2?'note':'source',title:p+' '+i,metadata:{}}));
 await page.route('**/api/v1/knowledge-workspace/nodes/**',async route=>{
  const slow=route.request().url().includes('/slow/');
  if(slow)await new Promise(r=>setTimeout(r,1500));
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({nodes:mk(slow?'S':'F'),edges:[]})});
 });
 const seed=page.getByLabel('Knowledge node ID');
 await seed.fill('slow');await seed.fill('fast');
 await expect(page.getByText('F 0')).toBeVisible();
 await page.waitForTimeout(2200);
 await expect(page.getByText('S 0')).toHaveCount(0);
 const card=page.locator('.react-flow__node',{hasText:'F 0'});
 const before=await card.boundingBox();
 await page.mouse.move(before!.x+20,before!.y+20);await page.mouse.down();await page.mouse.move(before!.x+20,before!.y+90,{steps:5});await page.mouse.up();
 const dragged=await card.boundingBox();
 expect(Math.abs(dragged!.y-before!.y)).toBeGreaterThan(40);
 await page.getByRole('button',{name:'note'}).click();await page.getByRole('button',{name:'note'}).click();
 await expect(page.locator('.react-flow__node',{hasText:'F 0'})).toBeVisible();
 const after=await page.locator('.react-flow__node',{hasText:'F 0'}).boundingBox();
 expect(Math.abs(after!.y-dragged!.y)).toBeLessThan(5);
});
