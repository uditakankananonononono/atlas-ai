import {render,screen,waitFor,fireEvent} from "@testing-library/react";
import {vi,it,expect} from "vitest";
import StudyAbroadPlanning from "./StudyAbroadPlanning";
import {authFetch} from "../lib/supabase";
vi.mock("../lib/supabase",()=>({authFetch:vi.fn(async()=>({status:200,json:async()=>({upcoming:[{id:"essay",days_left:6}]})}))}));
it("runs the selected student-owned check and renders the actual API result",async()=>{
 render(<StudyAbroadPlanning/>);
 expect(screen.getByRole("combobox",{name:"Tool"}).querySelectorAll("option")).toHaveLength(20);
 fireEvent.click(screen.getByRole("button",{name:"Run planning check"}));
 await waitFor(()=>expect(screen.getByText(/days_left/)).toBeInTheDocument());
 expect(vi.mocked(authFetch)).toHaveBeenCalledWith("/api/v1/study-abroad/planning/deadline_triage",expect.objectContaining({method:"POST"}));
});
