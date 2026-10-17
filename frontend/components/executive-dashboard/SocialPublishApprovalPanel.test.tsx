import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,describe,expect,it,vi} from "vitest";
import SocialPublishApprovalPanel from "./SocialPublishApprovalPanel";
import {parsePublishSnapshot,validAccountId} from "./social-publish-snapshot";
import type {ApprovalCenterRequest} from "./api";
import realXThread from "./fixtures/m06-x-thread-m00-request.json";
afterEach(cleanup);
const snap=(over:Record<string,unknown>={})=>({version:2,publish_target:{platform:"linkedin",account_id:"123"},plan_id:"p",platform:"linkedin",format:"article_post",text:"Synthetic review text",publish_at:"2026-10-20T12:00:00+00:00",media_urls:[],alt_texts:[],thread_chunks:[],link:null,sponsored:false,...over});
const req=(payloadOver:Record<string,unknown>={},snapOver:Record<string,unknown>|null={},status="pending"):ApprovalCenterRequest=>({id:"r1",module_id:6,action_type:"schedule_post",user_id:"t",status,created_at:"2026-10-17T08:00:00Z",expires_at:null,decided_at:null,approved_by:null,
  payload:{platform:"linkedin",copy:"Synthetic review text",publish_at:"2026-10-20T12:00:00+00:00",sponsored:false,...(snapOver===null?{}:{publish_snapshot:snap(snapOver)}),...payloadOver}});
const mount=(r:ApprovalCenterRequest,onDecide=vi.fn())=>{render(<SocialPublishApprovalPanel state={{request:r,error:null}} onDecide={onDecide} onClose={()=>{}} busy={false}/>);return onDecide};
describe("SocialPublishApprovalPanel",()=>{
  it("shows exact platform, account ID, content and time and lets a complete snapshot be approved",async()=>{
    const d=mount(req());
    expect(screen.getByTestId("account-id").textContent).toBe("123");
    expect(screen.getByLabelText("Post content").textContent).toBe("Synthetic review text");
    expect(screen.getByText(/2026-10-20T12:00:00.000Z/)).toBeTruthy();
    expect(screen.queryByText(/Account name/)).toBeNull();
    await userEvent.click(screen.getByRole("button",{name:"Approve"}));
    expect(d).toHaveBeenCalledWith("approved");
  });
  it("shows media, alt text, thread parts and link verbatim without fetching media",()=>{
    mount(req({},{media_urls:["https://example.invalid/a.png"],alt_texts:["a chart"],thread_chunks:["part one","part two"],link:"https://example.invalid/x",platform:"twitter",publish_target:{platform:"twitter",account_id:"9"}},"pending"));
    expect(document.querySelector("img")).toBeNull();
  });
  it("renders media and thread details when the whole snapshot is consistent",()=>{
    mount(req({platform:"twitter"},{platform:"twitter",publish_target:{platform:"twitter",account_id:"9"},media_urls:["https://example.invalid/a.png"],alt_texts:["a chart"],thread_chunks:["part one","part two"],link:"https://example.invalid/x"}));
    expect(screen.getByText("https://example.invalid/a.png")).toBeTruthy();
    expect(screen.getByText(/Alt: a chart/)).toBeTruthy();
    expect(screen.getByText("part two")).toBeTruthy();
    expect(screen.getByText("https://example.invalid/x")).toBeTruthy();
    expect(document.querySelector("img")).toBeNull();
  });
  it("wraps a 256-character account ID instead of overflowing",()=>{
    const long="a".repeat(120)+"_"+"b".repeat(135);
    mount(req({platform:"tiktok"},{platform:"tiktok",publish_target:{platform:"tiktok",account_id:long}}));
    const el=screen.getByTestId("account-id");expect(el.textContent).toBe(long);expect(el.className).toContain("break-all");
  });
  for(const [name,r] of [
    ["legacy request without a snapshot",req({},null)],
    ["version 1 snapshot",req({},{version:1})],
    ["snapshot without a target",req({},{publish_target:undefined})],
    ["target platform differs",req({},{publish_target:{platform:"twitter",account_id:"123"}})],
    ["non-numeric linkedin account",req({},{publish_target:{platform:"linkedin",account_id:"abc"}})],
    ["extra target key",req({},{publish_target:{platform:"linkedin",account_id:"123",name:"x"}})],
    ["text differs from request",req({copy:"Different"})],
    ["time differs from request",req({publish_at:"2026-10-21T12:00:00+00:00"})],
    ["naive publish time",req({publish_at:"2026-10-20T12:00:00"},{publish_at:"2026-10-20T12:00:00"})],
    ["sponsored flag differs",req({sponsored:true})],
  ] as [string,ApprovalCenterRequest][]){
    it(`fails closed: ${name} cannot be approved but can be denied`,async()=>{
      const d=mount(r);
      expect(screen.getByText(/Destination not verified/)).toBeTruthy();
      expect(screen.queryByTestId("account-id")).toBeNull();
      expect((screen.getByRole("button",{name:"Approve"}) as HTMLButtonElement).disabled).toBe(true);
      await userEvent.click(screen.getByRole("button",{name:"Approve"}));
      expect(d).not.toHaveBeenCalled();
      await userEvent.click(screen.getByRole("button",{name:"Deny"}));
      expect(d).toHaveBeenCalledWith("denied");
    });
  }
  it("offers no decision once the request is already decided",()=>{
    mount(req({},{},"approved"));
    expect(screen.queryByRole("button",{name:"Approve"})).toBeNull();
    expect(screen.getByText("No decision needed.")).toBeTruthy();
  });
  it("validates account IDs like the backend",()=>{
    expect(validAccountId("tiktok","open_id.1:x-y")).toBe(true);
    expect(validAccountId("instagram","open_id")).toBe(false);
    expect(validAccountId("linkedin","1".repeat(257))).toBe(false);
    expect(parsePublishSnapshot({}).ok).toBe(false);
  });
  it("accepts a real M00 request generated by the M06 backend (X thread, copy unsplit, text equal)",()=>{
    const r=realXThread as unknown as ApprovalCenterRequest;
    const p=r.payload as Record<string,any>;
    expect(p.copy).toBe(p.publish_snapshot.text);expect(p.publish_snapshot.thread_chunks.length).toBeGreaterThan(1);
    const parsed=parsePublishSnapshot(p);expect(parsed.ok).toBe(true);
    mount(r);
    expect(screen.getByTestId("account-id").textContent).toBe(p.publish_snapshot.publish_target.account_id);
    expect(screen.getByLabelText("Post content").textContent).toBe(p.copy);
    expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(p.publish_snapshot.thread_chunks.length);
  });
  for(const status of ["expired","consumed","denied","some_future_status"])it(`offers no decision for ${status} requests`,()=>{
    mount(req({},{},status));
    expect(screen.queryByRole("button",{name:"Approve"})).toBeNull();expect(screen.queryByRole("button",{name:"Deny"})).toBeNull();
  });
});
