import {test,expect} from '@playwright/test';
// Only the public-provider UI/session shell is mocked. Every M09 request goes
// through Next's proxy, real HTTP routing, signature/claim checks and PostgreSQL.
test('signed-fixture HTTP graph edits conflict, reload and persist through the UI',async({page,request})=>{
 const api=process.env.ATLAS_BRIDGE_API_URL!,token=process.env.ATLAS_BRIDGE_TOKEN!;
 const base=api+'/api/v1/knowledge-workspace/nodes';
 const headers={Authorization:`Bearer ${token}`};
 const create=await request.post(base,{headers,data:{node_type:'note',title:'HTTP original',body:'Real PG note'}});expect(create.status()).toBe(201);const node=await create.json();
 const hood=`${base}/${node.id}/neighborhood`;
 expect((await request.get(hood)).status()).toBe(401);
 const parts=token.split('.');parts[2]=(parts[2][0]==='A'?'B':'A')+parts[2].slice(1);expect((await request.get(hood,{headers:{Authorization:`Bearer ${parts.join('.')}`}})).status()).toBe(401);
 expect((await request.get(hood,{headers:{Authorization:`Bearer ${process.env.ATLAS_BRIDGE_EXPIRED_TOKEN}`}})).status()).toBe(401);
 expect((await request.get(hood,{headers:{Authorization:`Bearer ${process.env.ATLAS_BRIDGE_OTHER_TOKEN}`}})).status()).toBe(404);
 await page.addInitScript(({token})=>{localStorage.setItem('atlas:onboarding:complete','1');localStorage.setItem('sb-test-auth-token',JSON.stringify({access_token:token,refresh_token:'fixture-refresh',expires_in:900,expires_at:Math.floor(Date.now()/1000)+900,token_type:'bearer',user:{id:'fixture-owner',aud:'authenticated',role:'authenticated',email:'owner@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}}))},{token});
 await page.route('**/auth/v1/**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'fixture-owner',email:'owner@example.test'}})}));
 await page.route('**/api/v1/modules',route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));
 await page.route('**/api/v1/executive-dashboard/**',route=>route.fulfill({status:200,contentType:'application/json',body:route.request().url().endsWith('/view')?'{}':'[]'}));
 await page.route('**/api/v1/approval-center/**',route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));
 await page.goto('/');await page.getByRole('button',{name:'knowledge'}).click();await page.getByLabel('Knowledge node ID').fill(node.id);
 await page.locator('.react-flow__node',{hasText:'HTTP original'}).dblclick();
 const competing=await request.patch(`${base}/${node.id}`,{headers,data:{title:'HTTP competing',expected_version:1}});expect(competing.status()).toBe(200);
 await page.getByLabel('Node title',{exact:true}).fill('HTTP draft');
 const stale=page.waitForResponse(r=>r.url().endsWith(`/nodes/${node.id}`)&&r.request().method()==='PATCH');
 await page.getByRole('button',{name:'Save changes'}).click();expect((await stale).status()).toBe(409);
 await expect(page.getByLabel('Node details').getByRole('alert')).toContainText('This node changed');await expect(page.getByLabel('Node title',{exact:true})).toHaveValue('HTTP draft');
 await page.getByRole('button',{name:'Reload latest (discard draft)'}).click();await expect(page.getByLabel('Node title',{exact:true})).toHaveValue('HTTP competing');
 await page.getByLabel('Node title',{exact:true}).fill('HTTP saved');await page.getByLabel('Node notes').fill('Actual API persisted');
 const saved=page.waitForResponse(r=>r.url().endsWith(`/nodes/${node.id}`)&&r.request().method()==='PATCH');await page.getByRole('button',{name:'Save changes'}).click();expect((await saved).status()).toBe(200);
 await expect(page.getByText('Version 3.',{exact:false})).toBeVisible();
 const read=await request.get(hood,{headers});expect(read.status()).toBe(200);const persisted=(await read.json()).nodes.find((n:any)=>n.id===node.id);expect(persisted.title).toBe('HTTP saved');expect(persisted.body).toBe('Actual API persisted');expect(persisted.version).toBe(3);
 await page.reload();await page.getByRole('button',{name:'knowledge'}).click();await page.getByLabel('Knowledge node ID').fill(node.id);await expect(page.locator('.react-flow__node',{hasText:'HTTP saved'})).toBeVisible();
 await page.locator('.react-flow__node',{hasText:'HTTP saved'}).dblclick();await expect(page.getByLabel('Node notes')).toHaveValue('Actual API persisted');
 await page.getByLabel('Node details').screenshot({path:'test-results/knowledge-http-editor.png'});
});
