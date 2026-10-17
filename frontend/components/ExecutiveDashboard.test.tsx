import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,beforeEach,describe,expect,it,vi} from "vitest";
import ExecutiveDashboard from "./ExecutiveDashboard";
import RerunScheduleCard from "./executive-dashboard/RerunScheduleCard";
import type {RerunScheduleCard as Card} from "./executive-dashboard/api";

const {apiMock}=vi.hoisted(()=>({apiMock:{
  getView:vi.fn(),kpis:vi.fn(),modules:vi.fn(),blockers:vi.fn(),approvals:vi.fn(),digest:vi.fn(),snapshot:vi.fn(),
  rerunSchedules:vi.fn(),approvalRequest:vi.fn(),approvalAudit:vi.fn(),decideApprovalRequest:vi.fn(),approvalRequests:vi.fn(),contactTimeline:vi.fn(),messageCadence:vi.fn(),saveView:vi.fn(),decide:vi.fn(),bulkDecide:vi.fn(),execute:vi.fn(),preview:vi.fn(),sweep:vi.fn(),project:vi.fn(),
}}));
vi.mock("./executive-dashboard/api",async importOriginal=>{
  const original=await importOriginal<typeof import("./executive-dashboard/api")>();
  return {...original,dashboardApi:()=>apiMock};
});
vi.mock("./OperationsChart",()=>({default:()=>null}));

const card:Card={available:true,reason:null,as_of:"2026-10-05T09:00:00Z",schedules_total:3,schedules_active:2,schedules_due_now:1,proposals_total:5,
  by_state:{pending:2,approved_not_executed:1,executed:2,denied:0,expired:0},awaiting_approval:2,approved_not_executed:1,overdue_total:1,
  verdicts:{reproduced:1,diverged:1},overdue:[{schedule_id:"s1",original_approval_id:"orig-7",rerun_approval_id:"r1",state:"approved_not_executed",filed_at:"2026-10-01T09:00:00Z",age_hours:96,overdue:true,verdict:null,approval_path:"/approval-center/requests/r1"}],recent:[]};
const view={version:4,updated_at:"2026-10-05T09:00:00Z",widgets:[
  {id:"blockers",kind:"blockers",kpi_id:null,visible:true,position:0},
  {id:"approvals",kind:"approvals",kpi_id:null,visible:true,position:1},
  {id:"rerun_schedules",kind:"rerun_schedules",kpi_id:null,visible:true,position:2}]};
const blocker={id:"b1",kind:"stalled",severity:"warning",summary:"Agent 7 stalled",module_id:7,evidence:[],recommended_action:"restart",detected_at:"2026-10-05T08:00:00Z"};

beforeEach(()=>{
  for(const fn of Object.values(apiMock))fn.mockReset();
  apiMock.getView.mockResolvedValue(view);apiMock.kpis.mockResolvedValue([]);apiMock.modules.mockResolvedValue([]);
  apiMock.blockers.mockResolvedValue([blocker]);apiMock.approvals.mockResolvedValue([]);apiMock.digest.mockResolvedValue(null);
  apiMock.snapshot.mockResolvedValue({version:1,last_sequence:0,generated_at:"2026-10-05T09:00:00Z",data:{}});
  apiMock.approvalRequests.mockResolvedValue([]);
});
afterEach(cleanup);

describe("Scheduled re-runs card",()=>{
  it("shows due, awaiting, overdue counts and verdicts next to the existing cards",async()=>{
    apiMock.rerunSchedules.mockResolvedValue(card);
    render(<ExecutiveDashboard/>);
    const section=await screen.findByRole("region",{name:"Scheduled re-runs"});
    expect(section.textContent).toContain("Awaiting approval2");
    expect(section.textContent).toContain("Overdue1");
    expect(section.textContent).toContain("1 reproduced, 1 diverged");
    expect(section.textContent).toContain("Re-run of orig-7");
    expect(section.textContent).toContain("approved, not run · 96h");
    expect(screen.getByText("Agent 7 stalled")).toBeTruthy();
    expect(screen.getByText("Approval queue (0)")).toBeTruthy();
  });
  it("is read-only: rendering never files, decides, executes or saves anything",async()=>{
    apiMock.rerunSchedules.mockResolvedValue(card);
    render(<ExecutiveDashboard/>);
    await screen.findByRole("region",{name:"Scheduled re-runs"});
    for(const write of [apiMock.decideApprovalRequest,apiMock.saveView,apiMock.decide,apiMock.bulkDecide,apiMock.execute,apiMock.sweep,apiMock.project])expect(write).not.toHaveBeenCalled();
  });
  it("an M04 failure leaves the other cards and shows no error banner",async()=>{
    apiMock.rerunSchedules.mockRejectedValue(new Error("GET /executive-dashboard/rerun-schedules failed: 500"));
    render(<ExecutiveDashboard/>);
    await screen.findByText("Agent 7 stalled");
    await waitFor(()=>expect(apiMock.rerunSchedules).toHaveBeenCalled());
    expect(screen.queryByRole("region",{name:"Scheduled re-runs"})).toBeNull();
    expect(screen.queryByText(/failed: 500/)).toBeNull();
  });
  it("renders the backend's unavailable reason and the empty state",()=>{
    const {rerender}=render(<RerunScheduleCard card={{...card,available:false,reason:"M04 research scientist module is not installed"}}/>);
    expect(screen.getByText("M04 research scientist module is not installed")).toBeTruthy();
    rerender(<RerunScheduleCard card={{...card,schedules_total:0,schedules_active:0,overdue:[],overdue_total:0}}/>);
    expect(screen.getByText("No re-run schedules yet.")).toBeTruthy();
  });
  it("an overdue row opens its approval-center request; approving records the decision and refreshes, nothing executes",async()=>{
    const pending={id:"r1",module_id:4,action_type:"rerun_sandboxed_analysis",payload:{reason:"scheduled re-run (s1)"},user_id:"t",status:"pending",created_at:"2026-10-01T09:00:00Z",expires_at:null,decided_at:null,approved_by:null};
    apiMock.rerunSchedules.mockResolvedValue({...card,overdue:[{...card.overdue[0],state:"pending"}]});
    apiMock.approvalRequest.mockResolvedValueOnce(pending).mockResolvedValueOnce({...pending,status:"approved",approved_by:"udita"});
    apiMock.approvalAudit.mockResolvedValue([{event:"submitted",actor:"t",at:"2026-10-01T09:00:00Z"}]);
    apiMock.decideApprovalRequest.mockResolvedValue({...pending,status:"approved"});
    const user=userEvent.setup();
    render(<ExecutiveDashboard/>);
    await user.click(await screen.findByRole("button",{name:"Open approval for re-run of orig-7"}));
    const panel=await screen.findByRole("dialog",{name:"Re-run approval"});
    expect(apiMock.approvalRequest).toHaveBeenCalledWith("/approval-center/requests/r1");
    expect(apiMock.approvalAudit).toHaveBeenCalledWith("/approval-center/requests/r1");
    await waitFor(()=>expect(panel.textContent).toContain("scheduled re-run (s1)"));
    expect(panel.textContent).toContain("submitted");
    const cardCalls=apiMock.rerunSchedules.mock.calls.length;
    await user.click(screen.getByRole("button",{name:"Approve"}));
    expect(apiMock.decideApprovalRequest).toHaveBeenCalledWith("/approval-center/requests/r1","approved");
    await waitFor(()=>expect(panel.textContent).toContain("Approved; waiting to be executed from M04."));
    expect(screen.queryByRole("button",{name:"Approve"})).toBeNull();
    await waitFor(()=>expect(apiMock.rerunSchedules.mock.calls.length).toBeGreaterThan(cardCalls));
    expect(apiMock.execute).not.toHaveBeenCalled();expect(apiMock.decide).not.toHaveBeenCalled();
  });
  it("shows the load error in the panel when the approval can't be read",async()=>{
    apiMock.rerunSchedules.mockResolvedValue(card);
    apiMock.approvalRequest.mockRejectedValue(new Error("GET /approval-center/requests/r1 failed: 404"));
    apiMock.approvalAudit.mockResolvedValue([]);
    const user=userEvent.setup();
    render(<ExecutiveDashboard/>);
    await user.click(await screen.findByRole("button",{name:"Open approval for re-run of orig-7"}));
    expect(await screen.findByText("GET /approval-center/requests/r1 failed: 404")).toBeTruthy();
    expect(screen.queryByRole("button",{name:"Approve"})).toBeNull();
  });
});

const outreachReq={id:"ap-9",module_id:5,action_type:"send_outreach_email",user_id:"t1",status:"pending",created_at:"2026-10-05T08:00:00Z",expires_at:null,decided_at:null,approved_by:null,
  payload:{tenant_id:"t1",message_id:"m-new",campaign_id:"c2",contact_id:"k2",recipient:"rao@example.edu",subject:"Grant mentor question",body:"Hello Dr. Rao",cadence:{allowed:true,reasons:[],policy_version:1}}};
const timeline={person:"email:rao@example.edu",relationship:"cold",rule:{min_gap_days:7,max_per_30_days:2},live_thread_days:21,policy_version:1,contact_records:["k1","k2"],messages:[
  {message_id:"m-old",campaign_id:"c1",campaign:"Lab search",contact_id:"k1",kind:"initial",sequence:0,status:"sent",subject:"Summer lab inquiry",sent_at:"2026-09-01T10:00:00Z",updated_at:"2026-09-01T10:00:00Z"},
  {message_id:"m-new",campaign_id:"c2",campaign:"Grant mentor",contact_id:"k2",kind:"initial",sequence:0,status:"pending_approval",subject:"Grant mentor question",sent_at:null,updated_at:"2026-10-05T08:00:00Z"}]};

describe("Outreach approval card with contact timeline",()=>{
  it("lists pending M05 requests and shows every earlier message to that person inside the card",async()=>{
    apiMock.rerunSchedules.mockResolvedValue(card);apiMock.approvalRequests.mockResolvedValue([outreachReq]);
    apiMock.contactTimeline.mockResolvedValue(timeline);
    apiMock.messageCadence.mockResolvedValue({allowed:false,reasons:[{code:"too_soon",detail:"last message 2 days ago"}],next_allowed_at:"2026-10-10T08:00:00Z",policy_version:2});
    render(<ExecutiveDashboard/>);
    await screen.findByText("Outreach sends in the approval center (1)");
    expect(apiMock.approvalRequests).toHaveBeenCalledWith({status:"pending",module_id:5});
    await userEvent.click(screen.getByRole("button",{name:"Review"}));
    const dialog=await screen.findByRole("dialog",{name:"Outreach approval"});
    const history=await screen.findByRole("region",{name:"Contact timeline"});
    expect(apiMock.contactTimeline).toHaveBeenCalledWith("k2");
    expect(apiMock.messageCadence).toHaveBeenCalledWith("m-new");
    await waitFor(()=>expect(history.textContent).toContain("Summer lab inquiry"));
    expect(history.textContent).toContain("Earlier messages to this person (1)");
    expect(history.textContent).toContain("Lab search");
    expect(history.textContent).toContain("2 contact records");
    expect(history.textContent).not.toContain("pending_approval");
    expect(dialog.textContent).toContain("Cadence when filed: allowed");
    expect(dialog.textContent).toContain("Cadence now: blocked");
    expect(dialog.textContent).toContain("too_soon: last message 2 days ago");
    for(const write of [apiMock.decideApprovalRequest,apiMock.decide,apiMock.bulkDecide,apiMock.execute])expect(write).not.toHaveBeenCalled();
  });
  it("approving records the M00 decision for that request only",async()=>{
    apiMock.rerunSchedules.mockResolvedValue(card);apiMock.approvalRequests.mockResolvedValue([outreachReq]);
    apiMock.contactTimeline.mockResolvedValue(timeline);apiMock.messageCadence.mockResolvedValue({allowed:true,reasons:[]});
    apiMock.decideApprovalRequest.mockResolvedValue({...outreachReq,status:"approved",approved_by:"executive-dashboard"});
    render(<ExecutiveDashboard/>);
    await userEvent.click(await screen.findByRole("button",{name:"Review"}));
    await screen.findByText("Summer lab inquiry");
    await userEvent.click(screen.getByRole("button",{name:"Approve"}));
    expect(apiMock.decideApprovalRequest).toHaveBeenCalledWith("/approval-center/requests/ap-9","approved");
    expect(await screen.findByText("No decision needed.")).toBeTruthy();
  });
  it("a timeline failure is shown as a warning, not hidden, and first contact reads as first contact",async()=>{
    apiMock.rerunSchedules.mockResolvedValue(card);apiMock.approvalRequests.mockResolvedValue([outreachReq]);
    apiMock.contactTimeline.mockRejectedValueOnce(new Error("GET /outreach-manager/contacts/k2/timeline failed: 404"));
    apiMock.messageCadence.mockResolvedValue({allowed:true,reasons:[]});
    render(<ExecutiveDashboard/>);
    await userEvent.click(await screen.findByRole("button",{name:"Review"}));
    expect(await screen.findByText(/Could not load this person's history: GET \/outreach-manager\/contacts\/k2\/timeline failed: 404/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button",{name:"Close"}));
    apiMock.contactTimeline.mockResolvedValue({...timeline,contact_records:["k2"],messages:[timeline.messages[1]]});
    await userEvent.click(screen.getByRole("button",{name:"Review"}));
    expect(await screen.findByText("No earlier messages. This would be the first contact.")).toBeTruthy();
  });
  it("an M00 list failure leaves the M16 queue untouched with no banner",async()=>{
    apiMock.rerunSchedules.mockResolvedValue(card);apiMock.approvalRequests.mockRejectedValue(new Error("GET /approval-center/requests failed: 500"));
    render(<ExecutiveDashboard/>);
    await screen.findByText("Approval queue (0)");
    await waitFor(()=>expect(apiMock.approvalRequests).toHaveBeenCalled());
    expect(screen.queryByText(/Outreach sends/)).toBeNull();
    expect(screen.queryByText(/failed: 500/)).toBeNull();
  });
});

describe("Layout saves are versioned",()=>{
  const layoutOpen=async()=>{render(<ExecutiveDashboard/>);await userEvent.click(await screen.findByRole("button",{name:"Layout"}))};
  it("sends the version it read as base_version and keeps the server's new version",async()=>{
    apiMock.rerunSchedules.mockResolvedValue(card);
    apiMock.saveView.mockImplementation(async(w:unknown[])=>({...view,widgets:w,version:5}));
    await layoutOpen();
    await userEvent.click(screen.getAllByRole("button",{name:"Down"})[0]);
    await waitFor(()=>expect(apiMock.saveView).toHaveBeenCalledTimes(1));
    expect(apiMock.saveView.mock.calls[0][1]).toBe(4);
    await userEvent.click(screen.getAllByRole("button",{name:"Down"})[0]);
    await waitFor(()=>expect(apiMock.saveView).toHaveBeenCalledTimes(2));
    expect(apiMock.saveView.mock.calls[1][1]).toBe(5);
  });
  it("on a 409 it reloads the server layout and says the edit was not applied",async()=>{
    apiMock.rerunSchedules.mockResolvedValue(card);
    apiMock.saveView.mockRejectedValue(new Error("dashboard layout changed (server version 9)"));
    await layoutOpen();
    apiMock.getView.mockResolvedValue({...view,version:9});
    await userEvent.click(screen.getAllByRole("button",{name:"Down"})[0]);
    expect((await screen.findByRole("status",{name:""})).textContent).toMatch(/changed elsewhere/i);
    expect(apiMock.getView.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});

describe("Social post approval review",()=>{
  const social={id:"sp-1",module_id:6,action_type:"schedule_post",user_id:"t1",status:"pending",created_at:"2026-10-17T08:00:00Z",expires_at:null,decided_at:null,approved_by:null,
    payload:{platform:"linkedin",copy:"Synthetic review text",publish_at:"2026-10-20T12:00:00+00:00",sponsored:false,publish_snapshot:{version:2,publish_target:{platform:"linkedin",account_id:"123"},plan_id:"p",platform:"linkedin",format:"article_post",text:"Synthetic review text",publish_at:"2026-10-20T12:00:00+00:00",media_urls:[],alt_texts:[],thread_chunks:[],link:null,sponsored:false}}};
  beforeEach(()=>{apiMock.rerunSchedules.mockResolvedValue(card)});
  it("lists M06 requests from M00, shows the exact account before any decision, and decides via M00 only on click",async()=>{
    apiMock.approvalRequests.mockImplementation(async(q:{module_id?:number})=>q.module_id===6?[social]:[]);
    apiMock.decideApprovalRequest.mockResolvedValue({...social,status:"approved",approved_by:"executive-dashboard"});
    render(<ExecutiveDashboard/>);
    await screen.findByText("Social posts in the approval center (1)");
    expect(apiMock.approvalRequests).toHaveBeenCalledWith({status:"pending",module_id:6});
    expect(apiMock.decideApprovalRequest).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button",{name:"Review"}));
    const dialog=await screen.findByRole("dialog",{name:"Social publish approval"});
    expect(dialog.textContent).toContain("123");expect(dialog.textContent).toContain("Synthetic review text");
    expect(apiMock.decideApprovalRequest).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button",{name:"Approve"}));
    await waitFor(()=>expect(apiMock.decideApprovalRequest).toHaveBeenCalledWith("/approval-center/requests/sp-1","approved"));
  });
  it("a legacy request without a snapshot never reaches the decision API on approve",async()=>{
    const legacy={...social,payload:{platform:"linkedin",copy:"x",publish_at:"2026-10-20T12:00:00+00:00"}};
    apiMock.approvalRequests.mockImplementation(async(q:{module_id?:number})=>q.module_id===6?[legacy]:[]);
    render(<ExecutiveDashboard/>);
    await userEvent.click(await screen.findByRole("button",{name:"Review"}));
    expect(await screen.findByText(/Destination not verified/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button",{name:"Approve"}));
    expect(apiMock.decideApprovalRequest).not.toHaveBeenCalled();
  });
  it("when a decision fails because the request was decided elsewhere, re-reads it and shows its real status",async()=>{
    apiMock.approvalRequests.mockImplementation(async(q:{module_id?:number})=>q.module_id===6?[social]:[]);
    apiMock.decideApprovalRequest.mockRejectedValue(new Error("POST /approval-center/requests/sp-1/decision failed: 409"));
    apiMock.approvalRequest.mockResolvedValue({...social,status:"denied",approved_by:"other"});
    render(<ExecutiveDashboard/>);
    await userEvent.click(await screen.findByRole("button",{name:"Review"}));
    await userEvent.click(await screen.findByRole("button",{name:"Approve"}));
    const alert=await screen.findByRole("alert");
    expect(alert.textContent).toContain("409");expect(alert.textContent).toContain("now denied");
    await waitFor(()=>expect(screen.queryByRole("button",{name:"Approve"})).toBeNull());
    expect(apiMock.approvalRequest).toHaveBeenCalledWith("/approval-center/requests/sp-1");
  });
  it("a server error with the request still pending keeps it pending and decidable",async()=>{
    apiMock.approvalRequests.mockImplementation(async(q:{module_id?:number})=>q.module_id===6?[social]:[]);
    apiMock.decideApprovalRequest.mockRejectedValue(new Error("POST /approval-center/requests/sp-1/decision failed: 500"));
    apiMock.approvalRequest.mockResolvedValue(social);
    render(<ExecutiveDashboard/>);
    await userEvent.click(await screen.findByRole("button",{name:"Review"}));
    await userEvent.click(await screen.findByRole("button",{name:"Approve"}));
    expect((await screen.findByRole("alert")).textContent).toContain("500");
    expect((screen.getByRole("button",{name:"Approve"}) as HTMLButtonElement).disabled).toBe(false);
  });
  it("unknown after-commit failure: decision fails and the re-read fails, so controls stay off until a status check succeeds",async()=>{
    apiMock.approvalRequests.mockImplementation(async(q:{module_id?:number})=>q.module_id===6?[social]:[]);
    apiMock.decideApprovalRequest.mockRejectedValue(new Error("POST /approval-center/requests/sp-1/decision failed: 504"));
    apiMock.approvalRequest.mockRejectedValue(new Error("GET /approval-center/requests/sp-1 failed: 503"));
    render(<ExecutiveDashboard/>);
    await userEvent.click(await screen.findByRole("button",{name:"Review"}));
    await userEvent.click(await screen.findByRole("button",{name:"Approve"}));
    await screen.findByText(/Status unknown/);
    const dlg=screen.getByRole("dialog",{name:"Social publish approval"});expect(dlg.textContent).toContain("unknown (last seen pending)");expect(dlg.textContent).not.toContain("No decision needed.");
    expect(screen.queryByRole("button",{name:"Approve"})).toBeNull();expect(screen.queryByRole("button",{name:"Deny"})).toBeNull();
    expect(apiMock.decideApprovalRequest).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button",{name:"Check status"}));
    await waitFor(()=>expect(apiMock.approvalRequest).toHaveBeenCalledTimes(2));
    expect(screen.getByText(/Status unknown/)).toBeTruthy();expect(screen.queryByRole("button",{name:"Approve"})).toBeNull();
    apiMock.approvalRequest.mockResolvedValue({...social,status:"approved",approved_by:"executive-dashboard"});
    await userEvent.click(screen.getByRole("button",{name:"Check status"}));
    await waitFor(()=>expect(screen.queryByText(/Status unknown/)).toBeNull());
    expect(screen.getByText(/now approved/)).toBeTruthy();expect(screen.queryByRole("button",{name:"Approve"})).toBeNull();
    expect(apiMock.decideApprovalRequest).toHaveBeenCalledTimes(1);
  });
  it("a status check that finds the request still pending turns the controls back on",async()=>{
    apiMock.approvalRequests.mockImplementation(async(q:{module_id?:number})=>q.module_id===6?[social]:[]);
    apiMock.decideApprovalRequest.mockRejectedValue(new Error("timeout"));
    apiMock.approvalRequest.mockRejectedValueOnce(new Error("down"));
    render(<ExecutiveDashboard/>);
    await userEvent.click(await screen.findByRole("button",{name:"Review"}));
    await userEvent.click(await screen.findByRole("button",{name:"Approve"}));
    await screen.findByText(/Status unknown/);
    apiMock.approvalRequest.mockResolvedValue(social);
    await userEvent.click(screen.getByRole("button",{name:"Check status"}));
    expect((await screen.findByRole("button",{name:"Approve"}) as HTMLButtonElement).disabled).toBe(false);
  });
  it("the refreshed list no longer shows a request once it is decided",async()=>{
    let decided=false;
    apiMock.approvalRequests.mockImplementation(async(q:{module_id?:number})=>q.module_id===6&&!decided?[social]:[]);
    apiMock.decideApprovalRequest.mockImplementation(async()=>{decided=true;return {...social,status:"approved",approved_by:"executive-dashboard"}});
    render(<ExecutiveDashboard/>);
    await screen.findByText("Social posts in the approval center (1)");
    await userEvent.click(screen.getByRole("button",{name:"Review"}));
    await userEvent.click(await screen.findByRole("button",{name:"Approve"}));
    await waitFor(()=>expect(screen.queryByText(/Social posts in the approval center/)).toBeNull());
    expect(screen.getByRole("dialog",{name:"Social publish approval"}).textContent).toContain("No decision needed.");
  });
  it("a slow older list read that finishes last cannot bring back a request a newer read already dropped",async()=>{
    const held:Array<(rows:unknown[])=>void>=[];let tracking=false;
    apiMock.approvalRequests.mockImplementation((q:{module_id?:number})=>q.module_id!==6?Promise.resolve([]):tracking?new Promise(res=>{held.push(res)}):Promise.resolve([social]));
    apiMock.decideApprovalRequest.mockRejectedValue(new Error("POST failed: 504"));
    apiMock.approvalRequest.mockRejectedValueOnce(new Error("GET failed: 503"));
    render(<ExecutiveDashboard/>);
    await userEvent.click(await screen.findByRole("button",{name:"Review"}));
    tracking=true;
    await userEvent.click(await screen.findByRole("button",{name:"Approve"}));
    await screen.findByText(/Status unknown\. Decision/);
    await waitFor(()=>expect(held.length).toBe(1));            // read A: older, still pending
    apiMock.approvalRequest.mockResolvedValue({...social,status:"approved",approved_by:"executive-dashboard"});
    await userEvent.click(screen.getByRole("button",{name:"Check status"}));
    await waitFor(()=>expect(held.length).toBe(2));            // read B: newer
    held[1]([]);                                               // newer read: request is no longer pending
    await waitFor(()=>expect(screen.queryByText(/Social posts in the approval center/)).toBeNull());
    held[0]([social]);                                         // older read finishes last, still showing it pending
    await new Promise(r=>setTimeout(r,30));
    expect(screen.queryByText(/Social posts in the approval center/)).toBeNull();
  });
  it("closing and reopening a request whose status is unknown keeps it held and never re-sends the decision",async()=>{
    apiMock.approvalRequests.mockImplementation(async(q:{module_id?:number})=>q.module_id===6?[social]:[]);
    apiMock.decideApprovalRequest.mockRejectedValue(new Error("POST failed: 504"));
    apiMock.approvalRequest.mockRejectedValue(new Error("GET failed: 503"));
    render(<ExecutiveDashboard/>);
    await userEvent.click(await screen.findByRole("button",{name:"Review"}));
    await userEvent.click(await screen.findByRole("button",{name:"Approve"}));
    await screen.findByText(/Status unknown\. Decision/);
    await userEvent.click(screen.getByRole("button",{name:"Close"}));
    expect(screen.queryByRole("dialog",{name:"Social publish approval"})).toBeNull();
    // reopen from the (stale, still-pending) list copy while detail reads are still down
    await userEvent.click(screen.getByRole("button",{name:"Review"}));
    await screen.findByText(/Status unknown\. Decision/);
    expect(screen.queryByRole("button",{name:"Approve"})).toBeNull();expect(screen.queryByRole("button",{name:"Deny"})).toBeNull();
    expect(apiMock.decideApprovalRequest).toHaveBeenCalledTimes(1);
    // reopening read the detail on its own; once it works the real state replaces the stale copy
    apiMock.approvalRequest.mockResolvedValue({...social,status:"approved",approved_by:"executive-dashboard"});
    await userEvent.click(screen.getByRole("button",{name:"Check status"}));
    await waitFor(()=>expect(screen.queryByText(/Status unknown\. Decision/)).toBeNull());
    expect(screen.getByText(/now approved/)).toBeTruthy();expect(apiMock.decideApprovalRequest).toHaveBeenCalledTimes(1);
  });
  it("reopening an unknown request whose detail now reads pending re-enables the controls only after that fresh read",async()=>{
    apiMock.approvalRequests.mockImplementation(async(q:{module_id?:number})=>q.module_id===6?[social]:[]);
    apiMock.decideApprovalRequest.mockRejectedValue(new Error("timeout"));
    apiMock.approvalRequest.mockRejectedValueOnce(new Error("down"));
    render(<ExecutiveDashboard/>);
    await userEvent.click(await screen.findByRole("button",{name:"Review"}));
    await userEvent.click(await screen.findByRole("button",{name:"Approve"}));
    await screen.findByText(/Status unknown\. Decision/);
    await userEvent.click(screen.getByRole("button",{name:"Close"}));
    apiMock.approvalRequest.mockResolvedValue(social);
    await userEvent.click(screen.getByRole("button",{name:"Review"}));
    expect((await screen.findByRole("button",{name:"Approve"}) as HTMLButtonElement).disabled).toBe(false);
    expect(apiMock.decideApprovalRequest).toHaveBeenCalledTimes(1);
  });
  it("ignores non-publish M06 requests such as A/B tests",async()=>{
    apiMock.approvalRequests.mockImplementation(async(q:{module_id?:number})=>q.module_id===6?[{...social,action_type:"ab_test"}]:[]);
    render(<ExecutiveDashboard/>);
    await screen.findByText("Agent 7 stalled");
    await waitFor(()=>expect(apiMock.approvalRequests).toHaveBeenCalledWith({status:"pending",module_id:6}));
    expect(screen.queryByText(/Social posts in the approval center/)).toBeNull();
  });
});
