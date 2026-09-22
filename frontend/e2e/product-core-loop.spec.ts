import {test,expect,Page,Route} from '@playwright/test';
import {readFileSync} from 'fs';
import {join} from 'path';

const fixture=(name:string)=>JSON.parse(readFileSync(join(__dirname,'fixtures','product-core-loop',name),'utf8'));
const json=(route:Route,body:unknown,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});

async function mockAuth(page:Page){
 await page.route('**/auth/v1/**',route=>json(route,{user:{id:'user-1',email:'owner@example.test'}}));
 await page.route('**/api/v1/modules',route=>json(route,[]));
}
async function signedIn(page:Page){
 await page.addInitScript(()=>{localStorage.setItem('atlas:onboarding:complete','1');localStorage.setItem('sb-test-auth-token',JSON.stringify({access_token:'test-token',refresh_token:'refresh',expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,token_type:'bearer',user:{id:'user-1',aud:'authenticated',role:'authenticated',email:'owner@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}}));});
 await mockAuth(page);
}
async function mockDashboard(page:Page,approvals:()=>unknown){
 await page.route('**/api/v1/executive-dashboard/view',route=>json(route,fixture('dashboard-view.json')));
 await page.route('**/api/v1/executive-dashboard/kpis',route=>json(route,fixture('empty-list.json')));
 await page.route('**/api/v1/executive-dashboard/modules',route=>json(route,fixture('empty-list.json')));
 await page.route('**/api/v1/executive-dashboard/blockers',route=>json(route,fixture('empty-list.json')));
 await page.route('**/api/v1/executive-dashboard/digest',route=>json(route,fixture('digest.json')));
 await page.route('**/api/v1/executive-dashboard/snapshot',route=>json(route,fixture('snapshot.json')));
 await page.route('**/api/v1/executive-dashboard/approvals',route=>json(route,approvals()));
}

test('unauthenticated visitors get the sign-in gate, not the workspace',async({page})=>{
 await mockAuth(page);
 await page.goto('/');
 await expect(page.getByText('Sign in to open your private workspace.')).toBeVisible();
 await expect(page.getByRole('button',{name:'Continue with GitHub'})).toBeVisible();
 await expect(page.getByRole('button',{name:'workbench'})).toHaveCount(0);
});

test('product core loop: create goal, review approval, observe the queue clear',async({page})=>{
 let pending=true;
 await signedIn(page);
 await mockDashboard(page,()=>pending?fixture('approval-pending.json'):fixture('empty-list.json'));
 let executedPreview:string|null=null;
 await page.route('**/api/v1/executive-dashboard/commands/preview',route=>json(route,fixture('command-preview.json')));
 await page.route('**/api/v1/executive-dashboard/commands/preview-1/execute',async route=>{executedPreview=route.request().url();await json(route,fixture('command-execute.json'));});
 let decision:{approve:boolean,note:string|null}|null=null;
 await page.route('**/api/v1/executive-dashboard/approvals/approval-goal-1/decision',async route=>{decision=route.request().postDataJSON();pending=false;await json(route,fixture('approval-decided.json'));});

 await page.goto('/');
 // Create goal: the command bar prepares the goal and routes it to approvals.
 await page.getByLabel('Ask Atlas or prepare an action').fill('Launch the cited pilot');
 await page.getByRole('button',{name:'Preview'}).click();
 await expect(page.getByText('Requires approval before any action')).toBeVisible();
 await page.getByRole('button',{name:'Send to approvals'}).click();
 await expect.poll(()=>executedPreview).toContain('/api/v1/executive-dashboard/commands/preview-1/execute');

 // Review approval: the queue shows the goal's request with its risk class.
 await expect(page.getByText('Approval queue (1)')).toBeVisible();
 await expect(page.getByText('Execute plan for goal: Launch the cited pilot')).toBeVisible();
 await expect(page.getByText('external')).toBeVisible();
 await page.getByRole('button',{name:'Approve'}).click();
 await expect.poll(()=>decision).toEqual({approve:true,note:null});

 // Observe result: the decided request leaves the queue.
 await expect(page.getByText('Queue is clear.')).toBeVisible();
});

test('rejected decisions surface the skip reason instead of disappearing',async({page})=>{
 await signedIn(page);
 await mockDashboard(page,()=>fixture('approval-pending.json'));
 await page.route('**/api/v1/executive-dashboard/approvals/bulk-decision',route=>json(route,{decided:[],skipped:[{id:'approval-goal-1',reason:'expired before decision'}]}));
 await page.goto('/');
 await expect(page.getByText('Approval queue (1)')).toBeVisible();
 await page.getByLabel('select Execute plan for goal: Launch the cited pilot').check();
 await page.getByRole('button',{name:'Approve 1'}).click();
 await expect(page.getByText('skipped: approval-goal-1 (expired before decision)')).toBeVisible();
});

test('workbench shows the exact failure when execution is not approved',async({page})=>{
 await signedIn(page);
 await page.route('**/api/v1/executive-dashboard/**',route=>json(route,fixture('empty-list.json')));
 let sent:any;
 await page.route('**/api/v1/api/modules/20/execution-truth-ledger',async route=>{sent=route.request().postDataJSON();await json(route,{detail:'plan execution is not approved (decision: pending)'},403);});
 await page.goto('/');
 await page.getByRole('button',{name:'workbench'}).click();
 await page.getByRole('button',{name:'Cognitive Worker'}).click();
 await page.getByRole('button',{name:'Run exact action'}).click();
 await expect(page.getByText(/403/)).toBeVisible();
 await expect(page.getByText(/not approved/)).toBeVisible();
 expect(sent).toEqual({items:[{id:'plan-1',claim:'Workflow prepared',state:'planned',evidence_ids:[]}]});
});
