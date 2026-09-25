# M23 public admitted-student examples (checked September 25, 2026)

`admitted_cases.json` is a curated index of 20 public pages from 20 separate publishers. It stores an observed page URL, source name, example school (where named), type of example, and provenance caveat. The reading shelf in the M23 workbench opens the publisher page in a new tab. This is the sole enabled reading mode for these 20 sources, since a public URL does not grant a commercial product rights to rehost full text. The `/admitted-cases/{id}/read` route returns the source link and `source_only` status without fetching source text. No publisher has been cleared for product-side essay text extraction. The API `GET /study-abroad/admitted-cases?q=&evidence_type=&limit=` searches that catalog; `GET /study-abroad/admitted-cases/{id}/live-metadata` checks robots.txt and fetches title/description on demand. Both use the existing M23 router. A reachability check is **not** independent verification of the admission claim.

These are links to examples, not a dataset of copied essays or complete admissions records. Public access does not grant text-mining, redistribution, or model-training rights. Atlas neither stores nor reproduces applicant prose. Some pages are anthologies, first-person student reports, or third-party presentations, rather than confirmed institutional admissions files. No essay is proof that its wording caused an admission. No school-specific acceptance rates or predictions are inferred. On a missing/denied robots.txt or redirect, no page body is fetched. A full licensed case corpus would require explicit rights, access checks, and separate implementation.

## Source index

| Site | Public example |
|---|---|
| Olin College | [Incoming Class of 2028 essay snippets](https://www.olin.edu/blogs/voices-olins-class-2028-college-essay-snippets) (institution_published_essay) |
| Hamilton College | [Essays by incoming Hamilton students](https://www.hamilton.edu/admission/apply/college-essays-that-worked) (institution_published_essay) |
| Connecticut College | [Edie Banovic essay](https://www.conncoll.edu/admission/apply/essays-that-worked/edie-banovic-25/) (institution_published_essay) |
| Johns Hopkins University | [Queen’s Gambit](https://apply.jhu.edu/hopkins-insider/queens-gambit/) (institution_published_essay) |
| MIT | [My College Essay](https://mitadmissions.org/blogs/entry/my_college_essay/) (student_reported_admission) |
| Tufts University | [How I Wrote my College Essay](https://admissions.tufts.edu/blogs/jumbo-talk/post/how-i-wrote-my-college-essay/) (student_reported_admission) |
| Emory University | [Selected Exceptional Essays](https://blog.emoryadmission.com/2025/10/strong-personal-statement-selected-exceptional-essays/) (institution_published_essay) |
| Pomona College | [My Admissions Journey to Pomona](https://sagehenstories.pomona.edu/2026/04/my-admissions-journey-to-pomona/) (student_reported_admission) |
| Princeton University | [An Application Story](https://admission.princeton.edu/blogs/application-story) (student_reported_admission) |
| Dartmouth College | [My Dartmouth Acceptance, One Year Later](https://admissions.dartmouth.edu/follow/blog/julia-cappio/my-dartmouth-acceptance-one-year-later) (student_reported_admission) |
| CollegeVine | [Vanderbilt essay example from accepted student](https://blog.collegevine.com/vanderbilt-essay-examples) (third_party_accepted_essay) |
| PrepScholar | [Successful Harvard application](https://blog.prepscholar.com/successful-harvard-application-common-application-harvard-supplement) (self_reported_application) |
| College Essay Guy | [College essay examples anthology](https://www.collegeessayguy.com/blog/college-essay-examples) (third_party_accepted_essay) |
| College Raptor | [Application essays that worked](https://www.collegeraptor.com/getting-in/articles/college-applications/application-essays-that-got-students-accepted-into-impressive-schools/) (third_party_accepted_essay) |
| College Transitions | [Bethlehem Central Cornell case study](https://www.collegetransitions.com/blog/college-transitions-case-study-bethlehem-central/) (third_party_case_study) |
| AdmitRaven | [Xander UChicago case study](https://admitraven.com/en/case-studies/cdd76171-e4ae-44be-bd7f-c3fb7d747074) (third_party_case_study) |
| AdmitSee | [Stanford admitted profile, public metadata only](https://www.admitsee.com/profile-detail/123956) (third_party_profile) |
| Borderless | [Notre Dame admission story](https://borderless.so/stories/how-my-tripod-of-family-faith-and-voice-led-me-to-the-university-of-notre-dame) (student_reported_admission) |
| Cornell University | [Application process leading to Cornell](https://business.cornell.edu/hub/2018/11/19/college-application-process-led-me-to-cornell/) (student_reported_admission) |
| The Harvard Crimson | [Ten successful Harvard essays, 2025](https://business.thecrimson.com/10-successful-harvard-essays-2025) (third_party_accepted_essay) |
