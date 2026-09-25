import {render,screen,waitFor} from "@testing-library/react";
import {vi,it,expect} from "vitest";
import AdmittedCaseReader from "./AdmittedCaseReader";
vi.mock("../lib/supabase",()=>({authFetch:vi.fn(async()=>({ok:true,json:async()=>({cases:[{id:"hamilton",publisher:"Hamilton College",title:"Essays that Worked",url:"https://www.hamilton.edu/admission/apply/college-essays-that-worked",example_school:"Hamilton College",evidence_type:"institution_published_essay",reading_mode:"publisher_page",scope_note:"Publisher example"}]})}))}));
it("shows an original publisher reading link rather than essay text",async()=>{
 render(<AdmittedCaseReader/>);
 await waitFor(()=>expect(screen.getByText("Essays that Worked")).toBeInTheDocument());
 const link=screen.getByRole("link",{name:/Read Essays that Worked at Hamilton College/});
 expect(link).toHaveAttribute("href","https://www.hamilton.edu/admission/apply/college-essays-that-worked");
 expect(link).toHaveAttribute("target","_blank");
 expect(link).toHaveAttribute("rel","noopener noreferrer");
 expect(screen.getByText(/Atlas does not copy, store, or rehost it/)).toBeInTheDocument();
});
