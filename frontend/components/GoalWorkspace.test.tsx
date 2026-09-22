import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,beforeEach,describe,expect,it,vi} from "vitest";
import GoalWorkspace from "./GoalWorkspace";
import {ApiError} from "./goal-workspace-api";

const {apiMock}=vi.hoisted(()=>({apiMock:{
  createGoal:vi.fn(),getGoal:vi.fn(),buildPlan:vi.fn(),
  requestApproval:vi.fn(),execute:vi.fn(),executionState:vi.fn(),
}}));
vi.mock("./goal-workspace-api",async importOriginal=>{
  const original=await importOriginal<typeof import("./goal-workspace-api")>();
  return {...original,goalWorkspaceApi:()=>apiMock};
});

const goal={id:"goal-1",tenant_id:"t",statement:"Launch the cited pilot",status:"registered",created_at:"2026-09-23T00:00:00Z",sources:[{id:"src-1",uri:"https://example.test/spec",note:"spec"},{id:"src-2",uri:"https://example.test/metrics",note:""}],steps:[],approval_id:null};
const plannedGoal={...goal,status:"planned",steps:[{id:"step-1",title:"Draft checklist",action_type:"draft_document",risk:"reversible",citations:["src-1"],detail:""}]};
const emptyState={goal_id:"goal-1",tenant_id:"t",statement:goal.statement,status:"registered",approval_id:null,approval_decision:null,errors:{},ledger:{counts:{planned:0,simulated:0,externally_executed:0,independently_verified:0},highest_observed_state:null,items:[],verified_fraction:0,boundary:"Plans and simulations are never promoted."}};
const executedState={...emptyState,status:"executed",approval_id:"ap-1",approval_decision:"approved",ledger:{...emptyState.ledger,counts:{planned:0,simulated:1,externally_executed:1,independently_verified:0},items:[{id:"step-1",claim:"Draft checklist",state:"externally_executed",evidence_ids:["ev-1"],verifier:null,source_module:"m20_product_orchestrator"}],verified_fraction:0}};

beforeEach(()=>{for(const fn of Object.values(apiMock))fn.mockReset()});
afterEach(cleanup);

describe("GoalWorkspace",()=>{
 it("registers a goal with its sources and then demands citations per step",async()=>{
   apiMock.createGoal.mockResolvedValue(goal);
   apiMock.executionState.mockResolvedValue(emptyState);
   apiMock.getGoal.mockResolvedValue(goal);
   const user=userEvent.setup();
   render(<GoalWorkspace/>);
   await user.type(screen.getByLabelText("Goal"),"Launch the cited pilot");
   await user.type(screen.getByLabelText(/Sources/),"https://example.test/spec\nhttps://example.test/metrics");
   await user.click(screen.getByRole("button",{name:"Register goal"}));
   expect(apiMock.createGoal).toHaveBeenCalledWith("Launch the cited pilot",[{uri:"https://example.test/spec"},{uri:"https://example.test/metrics"}]);
   const submit=await screen.findByRole("button",{name:"Submit cited plan"});
   expect(submit).toBeDisabled();
   await user.type(screen.getByLabelText("Step title"),"Draft checklist");
   await user.type(screen.getByLabelText("Action type"),"draft_document");
   expect(submit).toBeDisabled();
   await user.click(screen.getByRole("checkbox",{name:"https://example.test/spec"}));
   expect(submit).toBeEnabled();
 });
 it("walks plan -> approval -> approved execution -> readback",async()=>{
   apiMock.createGoal.mockResolvedValue(goal);
   apiMock.executionState.mockResolvedValue(emptyState);
   apiMock.getGoal.mockResolvedValue(goal);
   const user=userEvent.setup();
   render(<GoalWorkspace/>);
   await user.type(screen.getByLabelText("Goal"),"Launch the cited pilot");
   await user.type(screen.getByLabelText(/Sources/),"https://example.test/spec");
   await user.click(screen.getByRole("button",{name:"Register goal"}));
   await user.type(await screen.findByLabelText("Step title"),"Draft checklist");
   await user.type(screen.getByLabelText("Action type"),"draft_document");
   await user.click(screen.getByRole("checkbox",{name:"https://example.test/spec"}));
   apiMock.buildPlan.mockResolvedValue(plannedGoal);
   apiMock.getGoal.mockResolvedValue(plannedGoal);
   await user.click(screen.getByRole("button",{name:"Submit cited plan"}));
   expect(apiMock.buildPlan).toHaveBeenCalledWith("goal-1",[{title:"Draft checklist",action_type:"draft_document",citations:["src-1"]}]);
   const approvedGoal={...plannedGoal,approval_id:"ap-1",status:"waiting_approval"};
   apiMock.requestApproval.mockResolvedValue({goal_id:"goal-1",approval_id:"ap-1"});
   apiMock.getGoal.mockResolvedValue(approvedGoal);
   apiMock.executionState.mockResolvedValue({...emptyState,approval_id:"ap-1",approval_decision:"pending"});
   await user.click(await screen.findByRole("button",{name:"Request approval"}));
   expect(apiMock.requestApproval).toHaveBeenCalledWith("goal-1");
   const execButton=await screen.findByRole("button",{name:"Execute approved plan"});
   expect(execButton).toBeDisabled();
   apiMock.getGoal.mockResolvedValue(approvedGoal);
   apiMock.executionState.mockResolvedValue({...emptyState,approval_id:"ap-1",approval_decision:"approved"});
   await user.click(screen.getByRole("button",{name:"Refresh decision"}));
   expect(await screen.findByRole("button",{name:"Execute approved plan"})).toBeEnabled();
   apiMock.execute.mockResolvedValue({goal_id:"goal-1",status:"executed",failed_steps:0});
   apiMock.getGoal.mockResolvedValue({...approvedGoal,status:"executed"});
   apiMock.executionState.mockResolvedValue(executedState);
   await user.click(screen.getByRole("button",{name:"Execute approved plan"}));
   expect(apiMock.execute).toHaveBeenCalledWith("goal-1","ap-1");
   await waitFor(()=>expect(screen.getByText("externally_executed: 1")).toBeInTheDocument());
   expect(screen.getByText(/evidence: ev-1/)).toBeInTheDocument();
 });
 it("shows the exact API failure instead of hiding it",async()=>{
   apiMock.createGoal.mockRejectedValue(new ApiError(422,"a goal needs at least one source before it can be planned"));
   const user=userEvent.setup();
   render(<GoalWorkspace/>);
   await user.type(screen.getByLabelText("Goal"),"Sourceless goal");
   await user.type(screen.getByLabelText(/Sources/),"   ");
   // enable the button by providing a source line, then let the API reject
   await user.clear(screen.getByLabelText(/Sources/));
   await user.type(screen.getByLabelText(/Sources/),"https://example.test/spec");
   await user.click(screen.getByRole("button",{name:"Register goal"}));
   expect(await screen.findByRole("alert")).toHaveTextContent("a goal needs at least one source before it can be planned");
 });
});
