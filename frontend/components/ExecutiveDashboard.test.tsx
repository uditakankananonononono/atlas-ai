import {cleanup,render,screen,waitFor} from "@testing-library/react";
import {afterEach,beforeEach,describe,expect,it,vi} from "vitest";
import ExecutiveDashboard from "./ExecutiveDashboard";
import RerunScheduleCard from "./executive-dashboard/RerunScheduleCard";
import type {RerunScheduleCard as Card} from "./executive-dashboard/api";

const {apiMock}=vi.hoisted(()=>({apiMock:{
  getView:vi.fn(),kpis:vi.fn(),modules:vi.fn(),blockers:vi.fn(),approvals:vi.fn(),digest:vi.fn(),snapshot:vi.fn(),
  rerunSchedules:vi.fn(),saveView:vi.fn(),decide:vi.fn(),bulkDecide:vi.fn(),execute:vi.fn(),preview:vi.fn(),sweep:vi.fn(),project:vi.fn(),
}}));
vi.mock("./executive-dashboard/api",async importOriginal=>{
  const original=await importOriginal<typeof import("./executive-dashboard/api")>();
  return {...original,dashboardApi:()=>apiMock};
});
vi.mock("./OperationsChart",()=>({default:()=>null}));

const card:Card={available:true,reason:null,as_of:"2026-10-05T09:00:00Z",schedules_total:3,schedules_active:2,schedules_due_now:1,proposals_total:5,
  by_state:{pending:2,approved_not_executed:1,executed:2,denied:0,expired:0},awaiting_approval:2,approved_not_executed:1,overdue_total:1,
  verdicts:{reproduced:1,diverged:1},overdue:[{schedule_id:"s1",original_approval_id:"orig-7",rerun_approval_id:"r1",state:"approved_not_executed",filed_at:"2026-10-01T09:00:00Z",age_hours:96,overdue:true,verdict:null}],recent:[]};
const view={updated_at:"2026-10-05T09:00:00Z",widgets:[
  {id:"blockers",kind:"blockers",kpi_id:null,visible:true,position:0},
  {id:"approvals",kind:"approvals",kpi_id:null,visible:true,position:1},
  {id:"rerun_schedules",kind:"rerun_schedules",kpi_id:null,visible:true,position:2}]};
const blocker={id:"b1",kind:"stalled",severity:"warning",summary:"Agent 7 stalled",module_id:7,evidence:[],recommended_action:"restart",detected_at:"2026-10-05T08:00:00Z"};

beforeEach(()=>{
  for(const fn of Object.values(apiMock))fn.mockReset();
  apiMock.getView.mockResolvedValue(view);apiMock.kpis.mockResolvedValue([]);apiMock.modules.mockResolvedValue([]);
  apiMock.blockers.mockResolvedValue([blocker]);apiMock.approvals.mockResolvedValue([]);apiMock.digest.mockResolvedValue(null);
  apiMock.snapshot.mockResolvedValue({version:1,last_sequence:0,generated_at:"2026-10-05T09:00:00Z",data:{}});
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
    for(const write of [apiMock.saveView,apiMock.decide,apiMock.bulkDecide,apiMock.execute,apiMock.sweep,apiMock.project])expect(write).not.toHaveBeenCalled();
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
});
