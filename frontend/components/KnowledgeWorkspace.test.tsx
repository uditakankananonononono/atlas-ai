import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,beforeEach,expect,it,vi} from "vitest";
import KnowledgeWorkspace from "./KnowledgeWorkspace";
const {api}=vi.hoisted(()=>({api:vi.fn()}));
vi.mock("../lib/supabase",()=>({authFetch:api}));
vi.mock("@xyflow/react",()=>({ReactFlow:({nodes,onNodeDoubleClick,children}:any)=><div>{nodes.map((n:any)=><button key={n.id} onDoubleClick={()=>onNodeDoubleClick(null,n)}>{n.data.title}</button>)}{children}</div>,Background:()=>null,Controls:()=>null,MiniMap:()=>null,Handle:()=>null,Position:{Left:"left",Right:"right"},applyNodeChanges:(_:any,n:any)=>n}));
const node={id:"n1",node_type:"note",title:"Original",body:"Old notes",metadata:{},version:1,source_uri:"https://example.test/source"};
const ok=(data:any)=>({ok:true,status:200,json:async()=>data});
beforeEach(()=>api.mockReset());afterEach(cleanup);
it("keeps conflict draft, reloads version, then saves exact expected version and renders server result",async()=>{
 api.mockResolvedValueOnce(ok({nodes:[node],edges:[]})).mockResolvedValueOnce({ok:false,status:409}).mockResolvedValueOnce(ok({nodes:[{...node,title:"Newer",version:2}],edges:[]})).mockResolvedValueOnce(ok({...node,title:"Saved",body:"Readback",version:3}));
 const user=userEvent.setup();render(<KnowledgeWorkspace seedId="n1"/>);
 await user.dblClick(await screen.findByRole("button",{name:"Original"}));
 const title=screen.getByLabelText("Node title");await user.clear(title);await user.type(title,"Draft");await user.click(screen.getByRole("button",{name:"Save changes"}));
 expect(await screen.findByRole("alert")).toHaveTextContent("This node changed");expect(title).toHaveValue("Draft");
 await user.click(screen.getByRole("button",{name:"Reload latest (discard draft)"}));
 await waitFor(()=>expect(title).toHaveValue("Newer"));
 await user.click(screen.getByRole("button",{name:"Save changes"}));
 await waitFor(()=>expect(title).toHaveValue("Saved"));
 const [,options]=api.mock.calls[3];expect(JSON.parse(options.body)).toEqual({title:"Newer",body:"Old notes",expected_version:2});
 expect(screen.getByLabelText("Node notes")).toHaveValue("Readback");expect(screen.getByRole("link",{name:"Open source"})).toHaveAttribute("rel","noopener noreferrer");
});
it("does not render unsafe source URI and preserves draft on save failure",async()=>{
 api.mockResolvedValueOnce(ok({nodes:[{...node,source_uri:"javascript:alert(1)"}],edges:[]})).mockRejectedValueOnce(Error("offline"));
 const user=userEvent.setup();render(<KnowledgeWorkspace seedId="n1"/>);await user.dblClick(await screen.findByRole("button",{name:"Original"}));
 expect(screen.queryByRole("link")).toBeNull();await user.click(screen.getByRole("button",{name:"Save changes"}));expect(await screen.findByRole("alert")).toHaveTextContent("offline");expect(screen.getByLabelText("Node title")).toHaveValue("Original");
});
