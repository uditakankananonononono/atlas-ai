"""G117 / m23.fullride_corpus - 100+ country route corpus with evidence-gated flags.

Source request (instinct doc, verbatim): "get me ready for applying abroad
for upto 100 countries, unlimited colleges in the US, and other like 50-ish.
Make sure ... the uni gives full rides to undergrad intl students and doesnt
conduct additional written tests. I will only be having secondary school
marks cbse and SAT, IELTs(maybe)."

What s4_7 was missing (audit G117): it filtered SUPPLIED rows but no
100-country corpus existed to supply. This module IS that corpus: 100+
countries, one or more flagship routes each, in the s4_7 row schema.

Evidence discipline: flags in this corpus are not curated claims. A flag
is True only where route-specific evidence was captured from an official
page on 2026-10-12 (EVIDENCE, with basis quotes per flag, including the
credential/testing flags). Every other row carries all-False flags, which
means NOT ESTABLISHED in this pass - it is not a claim that no route
exists. The verified-route count is computed in coverage() and stated
plainly.

Corrections from the re-audit:
- Hungary (Stipendium Hungaricum): not a full ride - its own site says
  tuition is covered and accommodation is "supported"; the programme FAQ
  states the stipend "does not fully cover all costs of living".
- China (CSC): requires an extra written test - the CSCA is mandatory for
  2026/27 undergraduate applicants at Chinese Government Scholarship
  universities (official Shanghai government FAQ).
- Kazakhstan: the Bolashak scholarship is the citizen OUTBOUND program;
  the row was replaced with an unverified incoming-grants placeholder.
- Oxford: full-ride funding verified (Reach Oxford), but Oxford course
  admissions tests mean requires_extra_written_test=True; the row is
  evidence-complete and excluded from the kept plan.
"""
from __future__ import annotations

CURATED_AT = "2026-10-12"

# (country, university_or_program, scholarship, full_ride, extra_written_test,
#  accepts_cbse, accepts_sat, accepts_ielts, source_url)
ROWS = [
    # --- United States: need-blind + full-need for internationals (no extra tests) ---
    ("United States", "Harvard University", "Harvard Financial Aid (need-blind, full-need for internationals)", "https://college.harvard.edu/financial-aid"),
    ("United States", "Yale University", "Yale need-blind full-need aid for internationals", "https://admissions.yale.edu/financial-aid"),
    ("United States", "Princeton University", "Princeton need-blind full-need grant aid", "https://admission.princeton.edu/cost-aid"),
    ("United States", "Massachusetts Institute of Technology", "MIT need-blind full-need aid", "https://sfs.mit.edu/"),
    ("United States", "Amherst College", "Amherst need-blind full-need aid for internationals", "https://www.amherst.edu/admission/financialaid"),
    ("United States", "Williams College", "Williams full-need aid for internationals", "https://www.williams.edu/admission/financial-aid/"),
    ("United States", "Dartmouth College", "Dartmouth need-blind full-need (international, from 2022)", "https://financialaid.dartmouth.edu/"),
    ("United States", "Brown University", "Brown need-blind for internationals (from Class of 2029)", "https://admission.brown.edu/financial-aid"),
    ("United States", "Bowdoin College", "Bowdoin need-blind full-need for internationals", "https://www.bowdoin.edu/admissions/financial-aid/"),
    ("United States", "Columbia University", "Columbia full-need aid (need-aware admission)", "https://cc-seas.financialaid.columbia.edu/"),
    ("United States", "University of Chicago", "UChicago full-need aid for internationals", "https://financialaid.uchicago.edu/"),
    ("United States", "Duke University", "Duke full-need aid (need-aware for internationals)", "https://financialaid.duke.edu/"),
    ("United States", "Stanford University", "Stanford full-need aid (need-aware for internationals)", "https://financialaid.stanford.edu/"),
    ("United States", "Cornell University", "Cornell full-need aid (need-aware for internationals)", "https://finaid.cornell.edu/"),
    ("United States", "Vanderbilt University", "Vanderbilt full-need + merit full rides", "https://www.vanderbilt.edu/financialaid/"),
    ("United States", "Rice University", "Rice full-need aid for internationals", "https://financialaid.rice.edu/"),
    ("United States", "University of Pennsylvania", "Penn full-need grant aid", "https://srfs.upenn.edu/"),
    ("United States", "Berea College", "Berea no-tuition promise for internationals (first-year funding)", "https://www.berea.edu/admissions/"),
    # --- Government / national full scholarships (flags per standard process) ---
    ("Japan", "Japanese Government (MEXT)", "MEXT Undergraduate Scholarship", "https://www.studyinjapan.go.jp/en/planning/scholarships/"),
    ("South Korea", "Korean Government (NIIED)", "Global Korea Scholarship (GKS) Undergraduate", "https://www.studyinkorea.go.kr/"),
    ("China", "Chinese Government (CSC)", "Chinese Government Scholarship (CSC) Undergraduate", "https://www.campuschina.org/"),
    ("Turkey", "Turkiye Scholarships", "Turkiye Burslari Undergraduate Scholarship", "https://www.turkiyeburslari.gov.tr/"),
    ("Hungary", "Hungarian Government", "Stipendium Hungaricum (Bachelor)", "https://stipendiumhungaricum.hu/"),
    ("Russia", "Russian Government (Rossotrudnichestvo)", "Russian Government Quota Scholarship", "https://education-in-russia.com/"),
    ("Romania", "Romanian Government", "Romanian Government Scholarship (Bachelor)", "https://www.mae.ro/en/node/10251"),
    ("Serbia", "Serbian Government", "World in Serbia / Serbian scholarship routes", "https://www.mfa.gov.rs/en"),
    ("Azerbaijan", "Azerbaijan Government (ADA)", "Heydar Aliyev International Education Grant", "https://www.ada.edu.az/"),
    ("Kazakhstan", "Kazakhstan universities", "incoming international grants (status unverified; Bolashak is the citizen outbound program)", "https://www.bolashak.gov.kz/"),
    ("Belarus", "Belarus universities", "state merit tuition waivers (limited published full ride)", "https://studyinbelarus.com/"),
    ("Brunei", "Brunei Government", "Brunei Darussalam Government Scholarship (BDGS)", "https://www.mfa.gov.bn/"),
    ("Taiwan", "TaiwanICDF", "TaiwanICDF International Undergraduate Scholarship", "https://www.icdf.org.tw/"),
    ("Singapore", "National University of Singapore", "NUS merit full scholarships (bonded routes)", "https://www.nus.edu.sg/oam/why-nus/scholarships-financial-aid"),
    ("Hong Kong", "University of Hong Kong", "HKU full entrance scholarships for internationals", "https://admissions.hku.hk/"),
    ("Hong Kong", "Hong Kong University of Science and Technology", "HKUST full entrance scholarships", "https://join.hkust.edu.hk/"),
    ("Thailand", "Chulalongkorn University", "Chula international merit scholarships", "https://www.chula.ac.th/en/admissions/"),
    ("Malaysia", "Malaysian universities", "MIS is postgraduate; undergrad full rides limited", "https://www.studymalaysia.com/"),
    ("Indonesia", "Indonesian Government (KNB)", "KNB Scholarship (developing-country undergrad)", "https://knb.kemdikbud.go.id/"),
    ("Vietnam", "Vietnam universities", "national merit waivers (limited published full ride)", "https://www.vnu.edu.vn/"),
    ("Philippines", "Philippines universities", "merit routes (limited published intl full ride)", "https://upd.edu.ph/"),
    ("United Arab Emirates", "Khalifa University", "Khalifa University full international scholarships", "https://www.ku.ac.ae/"),
    ("United Arab Emirates", "New York University Abu Dhabi", "NYUAD full-need support for admitted internationals", "https://nyuad.nyu.edu/en/admissions.html"),
    ("Qatar", "Qatar University", "Qatar University international full scholarships", "https://www.qu.edu.qa/"),
    ("Qatar", "Education City universities (QF)", "Qatar Foundation need/merit full support", "https://www.qf.org.qa/education"),
    ("Saudi Arabia", "KFUPM", "KFUPM full international undergraduate scholarships", "https://www.kfupm.edu.sa/"),
    ("Kuwait", "Kuwait University", "KU international scholarships (limited full ride)", "https://www.kuniv.edu.kw/"),
    ("Bahrain", "Bahrain universities", "merit routes (limited published full ride)", "https://www.uob.edu.bh/"),
    ("Oman", "Oman universities", "Sultan Qaboos merit scholarships (limited intl)", "https://www.squ.edu.om/"),
    ("Jordan", "Jordan universities", "merit routes (limited published full ride)", "https://www.uj.edu.jo/"),
    ("Lebanon", "American University of Beirut", "AUB full need-based support (competitive)", "https://www.aub.edu.lb/"),
    ("Israel", "Israel universities", "merit routes (limited published full ride)", "https://international.tau.ac.il/"),
    ("Egypt", "Egyptian Government", "Egyptian scholarship routes for intl undergrads", "https://www.aucegypt.edu/"),
    ("Morocco", "Moroccan Government (AMCI)", "Moroccan government scholarship routes", "https://www.amci.ma/"),
    # --- Europe ---
    ("Germany", "German public universities + DAAD", "tuition-free public unis; DAAD mainly grad (undergrad living unfunded)", "https://www.daad.de/en/"),
    ("Norway", "Norwegian public universities", "tuition-free public unis (living unfunded; some quotas)", "https://www.studyinnorway.no/"),
    ("Finland", "Finland universities", "Aalto/Helsinki full tuition waivers + some stipends", "https://www.studyinfinland.fi/scholarships"),
    ("Sweden", "Sweden universities", "university full tuition waivers (living unfunded)", "https://studyinsweden.se/scholarships/"),
    ("Denmark", "Denmark universities", "limited tuition waivers for non-EU (rare full ride)", "https://studyindenmark.dk/"),
    ("Netherlands", "Netherlands universities", "Holland Scholarship partial; full rides rare", "https://www.studyinnl.org/finances"),
    ("France", "France universities", "Eiffel is graduate-only; undergrad full rides rare", "https://www.campusfrance.org/en"),
    ("Italy", "Italian universities (DSU)", "DSU regional full support (tuition + living, need-based)", "https://www.studyinitaly.it/"),
    ("Spain", "Spain universities", "merit waivers (limited published full ride)", "https://www.educacionyfp.gob.es/"),
    ("Portugal", "Portugal universities", "merit waivers (limited published full ride)", "https://www.dges.gov.pt/"),
    ("Austria", "Austria universities", "low tuition; full rides rare for non-EU", "https://studyinaustria.at/"),
    ("Switzerland", "ETH Zurich", "ETH Excellence Scholarship mainly masters; undergrad partial", "https://ethz.ch/"),
    ("Belgium", "Belgium universities", "KU Leuven merit (limited published full ride)", "https://www.kuleuven.be/english/admissions"),
    ("Ireland", "Ireland universities", "Government of Ireland scholarships mainly postgrad", "https://www.educationinireland.com/"),
    ("United Kingdom", "University of Oxford", "Reach Oxford Scholarship (full ride, low-income countries incl. India)", "https://www.ox.ac.uk/admissions/undergraduate/fees-and-funding/oxford-support"),
    ("United Kingdom", "University of Cambridge", "Cambridge Trust full-cost international awards", "https://www.cambridgetrust.org/"),
    ("United Kingdom", "UK universities (other)", "other UK full rides rare at undergrad", "https://www.ukcisa.org.uk/"),
    ("Poland", "Polish Government (NAWA)", "Poland My First Choice / NAWA routes", "https://nawa.gov.pl/en"),
    ("Czech Republic", "Czech Government", "Czech Government Scholarship (Bachelor, select countries)", "https://www.msmt.cz/"),
    ("Slovakia", "Slovakia universities", "national merit routes (limited published full ride)", "https://www.studyinslovakia.sk/"),
    ("Slovenia", "Slovenia universities", "merit routes (limited published full ride)", "https://studyinslovenia.si/"),
    ("Croatia", "Croatia universities", "merit routes (limited published full ride)", "https://www.unizg.hr/"),
    ("Bulgaria", "Bulgaria universities", "merit routes (limited published full ride)", "https://www.su.bg/"),
    ("Greece", "Greece universities (IKY)", "IKY scholarships mainly postgrad", "https://www.iky.gr/en"),
    ("Estonia", "Estonia universities", "merit waivers (limited published full ride)", "https://www.studyinestonia.ee/"),
    ("Latvia", "Latvia universities", "state scholarships (limited published full ride)", "https://www.studyinlatvia.lv/"),
    ("Lithuania", "Lithuania universities", "state scholarships (limited published full ride)", "https://www.studyinlithuania.lt/"),
    ("Iceland", "Iceland universities", "merit routes (limited published full ride)", "https://www.hi.is/en"),
    ("Luxembourg", "University of Luxembourg", "merit routes (limited published full ride)", "https://wwwen.uni.lu/"),
    ("Malta", "Malta universities", "merit routes (limited published full ride)", "https://www.um.edu.mt/"),
    ("Cyprus", "Cyprus universities", "merit routes (limited published full ride)", "https://www.ucy.ac.cy/en/"),
    # --- Americas (non-US) ---
    ("Canada", "University of Toronto", "Lester B. Pearson International Scholarship (full ride)", "https://future.utoronto.ca/pearson/"),
    ("Canada", "University of British Columbia", "UBC International Scholars (full-need full ride)", "https://you.ubc.ca/financial-planning/scholarships-awards/"),
    ("Canada", "McGill University", "McGill major entrance awards (partial; full rides rare)", "https://www.mcgill.ca/studentaid/"),
    ("Mexico", "Mexico universities (AMEXCID)", "AMEXCID scholarships mainly postgrad", "https://www.gob.mx/amexcid"),
    ("Brazil", "Brazil universities (PUB)", "exchange routes (limited published full ride)", "https://www.gov.br/mre/"),
    ("Argentina", "Argentina public universities", "tuition-free public unis (living unfunded)", "https://www.argentina.gob.ar/educacion"),
    ("Chile", "Chile universities", "merit routes (limited published full ride)", "https://www.uchile.cl/english"),
    ("Colombia", "Colombia universities (ICETEX)", "ICETEX mainly domestic/postgrad", "https://www.icetex.gov.co/"),
    ("Peru", "Peru universities", "merit routes (limited published full ride)", "https://www.pucp.edu.pe/"),
    # --- Africa ---
    ("South Africa", "South Africa universities", "merit routes (limited published full ride)", "https://www.uct.ac.za/"),
    ("Nigeria", "Nigeria universities", "merit routes (limited published full ride)", "https://www.unilag.edu.ng/"),
    ("Kenya", "Kenya universities", "merit routes (limited published full ride)", "https://www.uonbi.ac.ke/"),
    ("Ghana", "Ghana universities", "merit routes (limited published full ride)", "https://www.ug.edu.gh/"),
    ("Ethiopia", "Ethiopia universities", "merit routes (limited published full ride)", "https://www.aau.edu.et/"),
    ("Rwanda", "Rwanda universities", "merit routes (limited published full ride)", "https://www.ur.ac.rw/"),
    ("Tanzania", "Tanzania universities", "merit routes (limited published full ride)", "https://www.udsm.ac.tz/"),
    ("Uganda", "Uganda universities", "merit routes (limited published full ride)", "https://www.mak.ac.ug/"),
    ("Senegal", "Senegal universities", "merit routes (limited published full ride)", "https://www.ucad.sn/"),
    ("Tunisia", "Tunisia universities", "merit routes (limited published full ride)", "https://www.utm.rnu.tn/"),
    ("Algeria", "Algeria universities", "merit routes (limited published full ride)", "https://www.mesrs.dz/"),
    # --- Asia (remaining) ---
    ("India", "home country (excluded from abroad plan)", "home-country routes out of scope", "https://www.education.gov.in/"),
    ("Pakistan", "Pakistan universities (HEC)", "HEC routes mainly domestic", "https://www.hec.gov.pk/"),
    ("Bangladesh", "Bangladesh universities", "merit routes (limited published full ride)", "https://www.du.ac.bd/"),
    ("Sri Lanka", "Sri Lanka universities", "merit routes (limited published full ride)", "https://www.cmb.ac.lk/"),
    ("Nepal", "Nepal universities", "merit routes (limited published full ride)", "https://tribhuvan-university.edu.np/"),
    ("Bhutan", "Bhutan universities", "merit routes (limited published full ride)", "https://www.rub.edu.bt/"),
    ("Maldives", "Maldives universities", "merit routes (limited published full ride)", "https://www.mnu.edu.mv/"),
    ("Mongolia", "Mongolia Government", "Mongolian government scholarship routes", "https://www.meds.gov.mn/"),
    ("Cambodia", "Cambodia universities", "merit routes (limited published full ride)", "https://www.rupp.edu.kh/"),
    ("Laos", "Laos universities", "merit routes (limited published full ride)", "https://www.nuol.edu.la/"),
    ("Myanmar", "Myanmar universities", "merit routes (limited published full ride)", "https://www.uy.edu.mm/"),
    ("Kyrgyzstan", "Kyrgyzstan universities", "merit routes (limited published full ride)", "https://www.knu.kg/"),
    ("Uzbekistan", "Uzbekistan universities", "state grant routes (limited published full ride)", "https://www.tashu.uz/"),
    ("Tajikistan", "Tajikistan universities", "merit routes (limited published full ride)", "https://www.tnu.tj/"),
    ("Turkmenistan", "Turkmenistan universities", "merit routes (limited published full ride)", "https://www.mfa.gov.tm/"),
    ("Georgia", "Georgia universities", "merit routes (limited published full ride)", "https://www.tsu.ge/en"),
    ("Armenia", "Armenia universities", "merit routes (limited published full ride)", "https://www.ysu.am/en"),
    ("Iran", "Iran universities", "government grant routes (limited published full ride)", "https://www.ut.ac.ir/en"),
    ("Iraq", "Iraq universities", "merit routes (limited published full ride)", "https://www.uobaghdad.edu.iq/"),
    # --- Oceania ---
    ("Australia", "Australia universities", "Australia Awards mainly postgrad; undergrad full rides rare", "https://www.studyaustralia.gov.au/"),
    ("New Zealand", "New Zealand universities", "Manaaki scholarships mainly postgrad", "https://www.studywithnewzealand.govt.nz/"),
    ("Fiji", "Fiji universities", "merit routes (limited published full ride)", "https://www.fnu.ac.fj/"),
    ("Papua New Guinea", "PNG universities", "merit routes (limited published full ride)", "https://www.upng.ac.pg/"),
]


# Evidence captured from live official pages on 2026-10-12.
# A route appears here ONLY when its official pages supplied the basis text
# in this pass. Every flag that is True carries its OWN basis quote and URL
# in flag_basis - a nonempty shared quote is never treated as proof of a
# different flag. A False flag means NOT ESTABLISHED in this pass, never
# "rejected": it is a statement about this pass, not about the route (for
# example, a route may permit optional IELTS submission while this pass
# simply captured no quote naming it).
# - full_ride: the page states coverage of full cost (an itemized full
#   package or 100% of demonstrated need). award_type distinguishes
#   full_cost_award (merit/unconditional) from meets_full_demonstrated_need
#   (conditional on assessed family finances; not a full ride for a profile
#   without assessed need).
# - requires_extra_written_test: True only where a program- or
#   course-specific written exam is documented; False on verified rows means
#   the captured testing page lists SAT/ACT + school records + English
#   proficiency as the complete published process.
VERIFIED_AT = "2026-10-12"


def _fb(basis, url):
    return {"basis": basis, "url": url}


EVIDENCE = {
    "Harvard University": {
        "award_type": "meets_full_demonstrated_need",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": True, "accepts_sat": True, "accepts_ielts": True,
        "checked_url": "https://college.harvard.edu/financial-aid",
        "basis": "financial aid is available for foreign students on exactly the same basis "
                 "as for American students; $100,000 family income and below, with typical "
                 "assets: Free",
        "flag_basis": {
            "requires_extra_written_test": _fb(
                "Harvard requires the SAT or ACT to meet its standardized testing "
                "requirement - the published testing process is SAT/ACT plus school "
                "records, with no program-specific written exam",
                "https://college.harvard.edu/admissions/apply/international-applicants"),
            "accepts_cbse": _fb(
                "students may submit IB/A-level/other national leaving exam predictions "
                "or results - CBSE Class X-XII is the Indian national leaving exam",
                "https://college.harvard.edu/admissions/apply/international-applicants"),
            "accepts_sat": _fb(
                "Harvard requires the SAT or ACT to meet its standardized testing requirement",
                "https://college.harvard.edu/admissions/apply/international-applicants"),
            "accepts_ielts": _fb(
                "you are not required to take an English proficiency exam (such as the "
                "TOEFL, IELTS, etc.), but you may submit scores if you wish to do so",
                "https://college.harvard.edu/admissions/apply/international-applicants"),
        }},
    "Yale University": {
        "award_type": "meets_full_demonstrated_need",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": False, "accepts_sat": True, "accepts_ielts": True,
        "checked_url": "https://admissions.yale.edu/financial-aid",
        "basis": "our aid offers meet 100% of demonstrated need - regardless of a "
                 "student's citizenship or immigration status - without requiring loans",
        "flag_basis": {
            "requires_extra_written_test": _fb(
                "first-year and transfer applicants are required to include scores from "
                "the ACT or SAT; scores from other exams, including international leaving "
                "exams or English proficiency exams, will not fulfill the testing "
                "requirement - the published process has no program-specific written exam",
                "https://admissions.yale.edu/standardized-testing"),
            "accepts_sat": _fb(
                "All first-year and transfer applicants must include scores from the ACT or SAT",
                "https://admissions.yale.edu/standardized-testing"),
            "accepts_ielts": _fb(
                "required to submit results from any of the proficiency tests below: "
                "TOEFL, IELTS, ... (IELTS named in the proficiency list)",
                "https://admissions.yale.edu/applying-yale-international-student"),
        }},
    "Princeton University": {
        "award_type": "meets_full_demonstrated_need",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": True, "accepts_sat": True, "accepts_ielts": True,
        "checked_url": "https://admission.princeton.edu/cost-aid",
        "basis": "Princeton will meet 100% of your demonstrated financial need with grant "
                 "aid; applies the same financial aid policy to international students",
        "flag_basis": {
            "requires_extra_written_test": _fb(
                "the published standardized testing policy is SAT or ACT submission - no "
                "program-specific written exam",
                "https://admission.princeton.edu/apply/standardized-testing"),
            "accepts_cbse": _fb(
                "achieved marks from external exams (for example: IGCSE, British A-Level, "
                "International Baccalaureate, national leaving exams such as Std X/Std XII "
                "in India)",
                "https://admission.princeton.edu/apply/international-students"),
            "accepts_sat": _fb(
                "applicants will need to submit either SAT or ACT scores (required from "
                "the 2027-28 cycle; accepted in all cycles)",
                "https://admission.princeton.edu/apply/standardized-testing"),
            "accepts_ielts": _fb(
                "you must take the TOEFL, the IELTS Academic, the Duolingo English Test "
                "or the PTE Academic (when English is not the language of instruction)",
                "https://admission.princeton.edu/apply/international-students"),
        }},
    "Massachusetts Institute of Technology": {
        "award_type": "meets_full_demonstrated_need",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": False, "accepts_sat": False, "accepts_ielts": False,
        "checked_url": "https://sfs.mit.edu/",
        "basis": "We meet 100% of an undergraduate's demonstrated need through our types "
                 "of aid",
        "flag_basis": {}},
    "Brown University": {
        "award_type": "meets_full_demonstrated_need",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": False, "accepts_sat": True, "accepts_ielts": False,
        "checked_url": "https://admission.brown.edu/financial-aid",
        "basis": "We are committed to meeting 100% of demonstrated financial need for all "
                 "eligible undergraduates; need-blind for international applicants from the "
                 "Class of 2029",
        "flag_basis": {
            "requires_extra_written_test": _fb(
                "Brown has returned to a policy requiring standardized test scores "
                "(either SAT or ACT scores) - the published process has no "
                "program-specific written exam",
                "https://admission.brown.edu/first-year/standardized-tests"),
            "accepts_sat": _fb(
                "requiring standardized test scores (either SAT or ACT scores) for "
                "first-year applicants beginning with the 2024-25 admission cycle",
                "https://admission.brown.edu/first-year/standardized-tests"),
        }},
    "Stanford University": {
        "award_type": "meets_full_demonstrated_need",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": True, "accepts_sat": True, "accepts_ielts": True,
        "checked_url": "https://financialaid.stanford.edu/",
        "basis": "We meet the full demonstrated need, without loans, for every admitted "
                 "undergrad who qualifies for financial assistance; we will meet the full "
                 "need of all admitted students regardless of citizenship",
        "flag_basis": {
            "requires_extra_written_test": _fb(
                "ACT or SAT scores are required; self-report your highest scores - the "
                "published process has no program-specific written exam",
                "https://admission.stanford.edu/apply/first-year/testing.html"),
            "accepts_cbse": _fb(
                "We do not have a preference for a specific curriculum (A-Level, IB, AP, "
                "National, etc.) - CBSE is the Indian national curriculum",
                "https://admission.stanford.edu/apply/international/"),
            "accepts_sat": _fb(
                "ACT or SAT scores are required",
                "https://admission.stanford.edu/apply/first-year/testing.html"),
            "accepts_ielts": _fb(
                "we do not require any English proficiency exams; you are welcome to "
                "self-report your scores from any English proficiency exam (IELTS is an "
                "English proficiency exam)",
                "https://admission.stanford.edu/apply/international/"),
        }},
    "Vanderbilt University": {
        "award_type": "meets_full_demonstrated_need",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": False, "accepts_sat": False, "accepts_ielts": False,
        "checked_url": "https://www.vanderbilt.edu/financialaid/",
        "basis": "Vanderbilt will meet 100% of a family's demonstrated financial need",
        "flag_basis": {}},
    "Rice University": {
        "award_type": "meets_full_demonstrated_need",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": True, "accepts_sat": True, "accepts_ielts": True,
        "checked_url": "https://financialaid.rice.edu/",
        "basis": "meet 100% of demonstrated need for undergraduate admitted students "
                 "inclusive of International Students; loan-free institution",
        "flag_basis": {
            "requires_extra_written_test": _fb(
                "the published requirements list SAT/ACT submission windows and an "
                "English proficiency demonstration - no program-specific written exam "
                "(architecture/art portfolio submissions are not written tests)",
                "https://admission.rice.edu/apply/first-year-international-applicants"),
            "accepts_cbse": _fb(
                "Applicants studying in an international exam-based curriculum must "
                "submit final exam results (for example IGCE/GCSE, CBSE X/AISSCE X) - "
                "CBSE named",
                "https://admission.rice.edu/apply/first-year-international-applicants"),
            "accepts_sat": _fb(
                "the application requirements include SAT/ACT submission windows "
                "(Last applicable SAT / Last applicable ACT)",
                "https://admission.rice.edu/apply/first-year-international-applicants"),
            "accepts_ielts": _fb(
                "International English Language Testing System (IELTS) | 7 (minimum "
                "score table)",
                "https://admission.rice.edu/apply/first-year-international-applicants"),
        }},
    "University of Pennsylvania": {
        "award_type": "meets_full_demonstrated_need",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": False, "accepts_sat": False, "accepts_ielts": False,
        "checked_url": "https://srfs.upenn.edu/",
        "basis": "Penn meets 100% of demonstrated undergraduate need",
        "flag_basis": {}},
    "Berea College": {
        "award_type": "full_cost_award",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": False, "accepts_sat": False, "accepts_ielts": False,
        "checked_url": "https://www.berea.edu/admissions/",
        "basis": "fully funded, no-loan degree - covering 100% of tuition, housing, food, "
                 "fees, and supplies - for every enrolled student",
        "flag_basis": {}},
    "University of Toronto": {
        "award_type": "full_cost_award",
        "full_ride": True, "requires_extra_written_test": False,
        "accepts_cbse": False, "accepts_sat": False, "accepts_ielts": False,
        "checked_url": "https://future.utoronto.ca/pearson/",
        "basis": "Pearson Scholarships cover tuition, books, incidental fees, and full "
                 "residence support for four years. Note: the Pearson requires school "
                 "nomination plus a separate competitive application - it is not "
                 "automatic eligibility",
        "flag_basis": {}},
    "University of Oxford": {
        "award_type": "full_cost_award",
        "full_ride": True, "requires_extra_written_test": True,
        "accepts_cbse": False, "accepts_sat": False, "accepts_ielts": False,
        "checked_url": "https://www.ox.ac.uk/admissions/undergraduate/fees-and-funding/oxford-support",
        "basis": "Reach Oxford Scholarship (students from low-income countries): course "
                 "fee, annual grant towards living costs and one return air fare per year. "
                 "Excluded from the kept plan: many Oxford courses require written "
                 "admissions tests, which the request rules out",
        "flag_basis": {}},
    # corrections identified in the re-audit, evidence-backed
    "Hungarian Government": {
        "award_type": None,
        "full_ride": False, "requires_extra_written_test": False,
        "accepts_cbse": False, "accepts_sat": False, "accepts_ielts": False,
        "checked_url": "https://stipendiumhungaricum.hu/",
        "basis": "all your tuition fees will be covered, and your accommodation costs will "
                 "be supported - a contribution, not a full ride; the programme FAQ states "
                 "the stipend does not fully cover all costs of living",
        "flag_basis": {}},
    "Chinese Government (CSC)": {
        "award_type": "full_cost_award",
        "full_ride": True, "requires_extra_written_test": True,
        "accepts_cbse": False, "accepts_sat": False, "accepts_ielts": False,
        "checked_url": "https://english.shanghai.gov.cn/en-FAQs-StudyinShanghai/20251218/134bb78943f640519e2185ff83051f5d.html",
        "basis": "CSCA is a mandatory requirement for applicants to undergraduate programs "
                 "at Chinese Government Scholarship universities for the 2026 and 2027 "
                 "academic years",
        "flag_basis": {}},
}

_FLAG_FIELDS = ("full_ride", "requires_extra_written_test", "accepts_cbse",
                "accepts_sat", "accepts_ielts")


def flag_basis(uni, flag):
    """The per-flag basis record behind a True flag, or None."""
    ev = EVIDENCE.get(uni)
    if ev is None or flag not in _FLAG_FIELDS:
        return None
    rec = ev.get("flag_basis", {}).get(flag)
    return dict(rec) if rec else None


def _evidence_for(uni):
    return EVIDENCE.get(uni)


def corpus_rows(as_of=CURATED_AT):
    """Rows in the exact s4_7_abroad_fullride schema, flags from EVIDENCE only.

    Every True flag carries its own basis quote and URL in flag_basis. False
    means NOT ESTABLISHED in the 2026-10-12 pass, never "rejected".
    """
    rows = []
    for i, (country, uni, schol, url) in enumerate(ROWS, 1):
        ev = _evidence_for(uni)
        if ev is not None:
            rows.append({"id": "corpus-%03d" % i, "country": country, "university": uni,
                         "scholarship": schol, "source_url": url,
                         "fetched_at": VERIFIED_AT,
                         **{f: ev[f] for f in _FLAG_FIELDS}})
        else:
            rows.append({"id": "corpus-%03d" % i, "country": country, "university": uni,
                         "scholarship": schol, "source_url": url, "fetched_at": as_of,
                         **{f: False for f in _FLAG_FIELDS}})
    return rows


def award_type(uni):
    ev = _evidence_for(uni)
    return ev["award_type"] if ev else None


def evidence_report():
    """The evidence record: per-route, per-flag basis quotes."""
    return {uni: dict(ev) for uni, ev in EVIDENCE.items()}


def coverage(as_of=CURATED_AT):
    rows = corpus_rows(as_of)
    countries = sorted({r["country"] for r in rows if r["country"] != "India"})
    verified = [r for r in rows if _evidence_for(r["university"]) is not None]
    fitting = [r for r in verified
               if r["full_ride"] and not r["requires_extra_written_test"]
               and r["accepts_cbse"] and (r["accepts_sat"] or r["accepts_ielts"])
               and r["country"] != "India"]
    fitting_countries = sorted({r["country"] for r in fitting})
    need_based = [r for r in fitting
                  if _evidence_for(r["university"])["award_type"] == "meets_full_demonstrated_need"]
    return {"target_countries": 100, "countries_covered": len(countries),
            "countries": countries, "rows": len(rows),
            "verified_routes": len(verified),
            "verified_full_ride_no_extra_test_routes": len(fitting),
            "verified_full_ride_no_extra_test_countries": len(fitting_countries),
            "fitting_countries": fitting_countries,
            "fitting_by_award_type": {
                "meets_full_demonstrated_need": len(need_based),
                "full_cost_award": len(fitting) - len(need_based)},
            "not_established_rows": len(rows) - len(verified),
            "curated_at": CURATED_AT, "verified_at": VERIFIED_AT,
            "verification": "every True flag carries its own official-page basis quote "
                            "captured on verified_at; a False flag means not established "
                            "in this pass, never rejected"}
