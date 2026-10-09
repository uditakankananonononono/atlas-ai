import {test,expect} from '@playwright/test';
test('A32 authenticated minimal SSE refresh, injected data refused, bounded retries and logout',async({page})=>{
 await page.addInitScript(()=>{
  localStorage.setItem('atlas:onboarding:complete','1');
  localStorage.setItem('sb-test-auth-token',JSON.stringify({access_token:'test-token',refresh_token:'refresh',expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,token_type:'bearer',user:{id:'user-1',aud:'authenticated',role:'authenticated',email:'owner@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}}));
  const original=window.fetch.bind(window);let sequence=0;
  (window as unknown as {streamAttempts:number;streamCancels:number;streamHeaders:string[]}).streamAttempts=0;
  (window as unknown as {streamCancels:number}).streamCancels=0;
  (window as unknown as {streamHeaders:string[]}).streamHeaders=[];
  window.fetch=async(input,init)=>{
   if(String(input).endsWith('/approval-center/events')){
    const state=window as unknown as {streamAttempts:number;streamCancels:number;streamHeaders:string[]};
    state.streamAttempts++;state.streamHeaders.push(new Headers(init?.headers).get('Authorization')??'');
    const encoder=new TextEncoder();sequence++;
    if(sequence===1){
     let timeout:ReturnType<typeof setTimeout>;
     const body=new ReadableStream<Uint8Array>({start(controller){
      controller.enqueue(encoder.encode('data: {"type":"approval_request","approval_id":"owned","tenant_id":"foreign"}\n\ndata: {"type":"approval_request","approval_id":"owned","approval":{"title":"INJECTED"}}\n\n'));
      timeout=setTimeout(()=>{controller.enqueue(encoder.encode('data: {"type":"approval_dec'));controller.enqueue(encoder.encode('ision","approval_id":"owned"}\n\n'));controller.close()},600);
     },cancel(){clearTimeout(timeout);state.streamCancels++}});
     return new Response(body,{headers:{'Content-Type':'text/event-stream'}});
    }
    if(sequence===5)return new Response(new ReadableStream<Uint8Array>({cancel(){state.streamCancels++}}),{headers:{'Content-Type':'text/event-stream'}});
    return new Response('',{status:503});
   }
   return original(input,init);
  };
 });
 await page.route('**/auth/v1/**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'user-1'}})}));
 await page.route('**/api/v1/modules',r=>r.fulfill({status:200,contentType:'application/json',body:'[]'}));
 let listReads=0;
 await page.route('**/api/v1/approval-center/requests*',r=>{listReads++;return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify([{id:'owned',module_id:5,action_type:'send',payload:{subject:listReads>=3?'Authoritative refreshed approval':'Original approval',recipient:'fixture'},status:'pending',user_id:'a'}])})});
 await page.route('**/api/v1/executive-dashboard/**',r=>{
  const body=r.request().url().includes('/view')?{version:1,widgets:[{id:'approvals',kind:'approvals',visible:true,position:0}]}:r.request().url().includes('/snapshot')?{data:{}}:[];
  return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('/');
 await expect(page.getByLabel('Approval stream status')).toHaveText('Approval updates connected');
 await expect(page.getByText('INJECTED',{exact:true})).toHaveCount(0);
 await expect(page.getByText('Authoritative refreshed approval',{exact:false})).toBeVisible();
 await expect(page.getByLabel('Approval stream status')).toHaveText('Approval updates disconnected; polling',{timeout:15000});
 expect(await page.evaluate(()=>(window as unknown as {streamAttempts:number}).streamAttempts)).toBe(4);
 expect(await page.evaluate(()=>(window as unknown as {streamHeaders:string[]}).streamHeaders.every(x=>x==='Bearer test-token'))).toBe(true);
 await page.screenshot({path:'../audits/rebuild-20261008/source-units/frontend-render/a32-disconnected.png',fullPage:true});
 await page.getByRole('button',{name:'Retry updates'}).click();
 await expect.poll(()=>page.evaluate(()=>(window as unknown as {streamAttempts:number}).streamAttempts)).toBe(5);
 await expect(page.getByLabel('Approval stream status')).toHaveText('Approval updates connected');
 await page.getByRole('button',{name:'modules',exact:true}).click();
 await expect.poll(()=>page.evaluate(()=>(window as unknown as {streamCancels:number}).streamCancels)).toBe(1);
 await page.getByRole('button',{name:'dashboard',exact:true}).click();
 await expect.poll(()=>page.evaluate(()=>(window as unknown as {streamAttempts:number}).streamAttempts)).toBe(6);
 await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await expect(page.getByText('Sign in to open your private workspace.')).toBeVisible();
 const count=await page.evaluate(()=>(window as unknown as {streamAttempts:number}).streamAttempts);
 await page.waitForTimeout(1500);
 expect(await page.evaluate(()=>(window as unknown as {streamAttempts:number}).streamAttempts)).toBe(count);
});

test('A32 silent connected stream times out and recovers with bounded attempts',async({page})=>{
 await page.clock.install();
 await page.addInitScript(()=>{
  localStorage.setItem('atlas:onboarding:complete','1');
  localStorage.setItem('sb-test-auth-token',JSON.stringify({access_token:'test-token',refresh_token:'refresh',expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,token_type:'bearer',user:{id:'user-1',aud:'authenticated',role:'authenticated',email:'owner@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}}));
  const original=window.fetch.bind(window);
  const state=window as unknown as {idleAttempts:number;idleCancels:number};state.idleAttempts=0;state.idleCancels=0;
  window.fetch=async(input,init)=>{
   if(String(input).endsWith('/approval-center/events')){
    state.idleAttempts++;
    return new Response(new ReadableStream<Uint8Array>({cancel(){state.idleCancels++}}),{headers:{'Content-Type':'text/event-stream'}});
   }
   return original(input,init);
  };
 });
 await page.route('**/auth/v1/**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'user-1'}})}));
 await page.route('**/api/v1/modules',r=>r.fulfill({status:200,contentType:'application/json',body:'[]'}));
 await page.route('**/api/v1/approval-center/requests*',r=>r.fulfill({status:200,contentType:'application/json',body:'[]'}));
 await page.route('**/api/v1/executive-dashboard/**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(r.request().url().includes('/view')?{version:1,widgets:[]}:r.request().url().includes('/snapshot')?{data:{}}:[])}));
 await page.goto('/');
 await expect(page.getByLabel('Approval stream status')).toHaveText('Approval updates connected');
 for(let i=0;i<4;i++){
  await page.clock.runFor(45001);
  if(i<3){await page.clock.runFor([1000,2000,4000][i]+1);await expect.poll(()=>page.evaluate(()=>(window as unknown as {idleAttempts:number}).idleAttempts)).toBe(i+2)}
 }
 await expect(page.getByLabel('Approval stream status')).toHaveText('Approval updates disconnected; polling');
 expect(await page.evaluate(()=>(window as unknown as {idleAttempts:number}).idleAttempts)).toBe(4);
 expect(await page.evaluate(()=>(window as unknown as {idleCancels:number}).idleCancels)).toBe(4);
 await page.screenshot({path:'../audits/rebuild-20261009/a32-stream-idle/idle-disconnected.png',fullPage:true});
});
