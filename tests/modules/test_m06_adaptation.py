from app.modules.m06_social_media_manager.adaptation import figures, preview, source_claims

SOURCE = (
    "Our pilot cut clinic wait times by 38% across 12 sites [1]. "
    "Volunteers logged 4,200 hours in 2025 (https://example.org/report). "
    "We think every district should try it."
)
REFS = {1: {"url": "https://health.example.gov/study", "title": "District Health Study"}}


def _p(out, platform):
    return next(p for p in out["platforms"] if p["platform"] == platform)


def test_claims_are_extracted_with_citations():
    claims = source_claims(SOURCE, REFS)
    assert [c["id"] for c in claims] == ["c1", "c2"]
    assert claims[0]["figures"] == ["12", "38%"]
    assert claims[0]["citations"][0]["domain"] == "health.example.gov"
    assert claims[1]["citations"][0]["url"] == "https://example.org/report"


def test_parity_matrix_flags_dropped_citation_and_distorted_figure():
    out = preview(SOURCE, [
        {"platform": "linkedin", "format": "article_post",
         "post_copy": "Our pilot cut wait times by 38% across 12 sites (District Health Study). "
                      "Volunteers gave 4,200 hours: example.org/report"},
        {"platform": "twitter", "format": "thread",
         "post_copy": "Wait times down 40% in our pilot! Volunteers logged 4,200 hours."},
    ], references=REFS)
    li, x = _p(out, "linkedin"), _p(out, "twitter")
    assert li["blocking"] is False and out["parity"]["c1"]["linkedin"] == "kept_cited"
    assert out["parity"]["c2"]["linkedin"] == "kept_cited"
    assert x["unsupported_figures"] == ["40%"]
    assert out["parity"]["c2"]["twitter"] == "kept_uncited"
    codes = {i["code"] for i in x["issues"]}
    assert {"unsupported_figure", "citation_dropped"} <= codes and x["blocking"] and out["ready"] is False


def test_platform_limits_and_thread_chunks_are_previewed():
    long = ("Our pilot cut clinic wait times by 38% across 12 sites health.example.gov " * 12).strip()
    out = preview(SOURCE, [{"platform": "twitter", "format": "thread", "post_copy": long},
                           {"platform": "instagram", "format": "single_image", "post_copy": long + " #a" * 31}],
                  references=REFS)
    x, ig = _p(out, "twitter"), _p(out, "instagram")
    assert len(x["chunks"]) > 1 and all(c["chars"] <= 280 for c in x["chunks"])
    assert x["unsupported_figures"] == []  # "1/4" thread numbering is not a figure
    assert any(i["code"] == "too_many_hashtags" for i in ig["issues"])


def test_sponsored_disclosure_still_enforced_and_clean_drafts_are_ready():
    ok = preview(SOURCE, [{"platform": "linkedin", "post_copy": "#ad Our pilot cut wait times by 38% across 12 sites [1]."}],
                 references=REFS, sponsored=True)
    assert ok["ready"] is True and ok["platforms"][0]["claims_dropped"] == ["c2"]
    bad = preview(SOURCE, [{"platform": "linkedin", "post_copy": "Our pilot cut wait times by 38% across 12 sites [1]."}],
                  references=REFS, sponsored=True)
    assert any(i["code"] == "missing_disclosure" for i in bad["platforms"][0]["issues"])


def test_figure_normalisation():
    assert figures("1,200 people, 3.5 million views, 2x growth, 7 days") == {"1200", "3.5m", "2x"}


def test_plan_preview_uses_stored_drafts_and_brief():
    from datetime import datetime, timezone

    from app.modules.m06_social_media_manager.models import ContentPlan, Platform, PlatformDraft
    from app.modules.m06_social_media_manager.service import MemorySocialRepository, Service

    class Store:
        def put(self, item, **kw):
            return item

    async def gen(*a, **k):
        return ""

    repo = MemorySocialRepository()
    svc = Service(approval_store=Store(), generate=gen, repository=repo)
    repo.save_plan(ContentPlan(id="p1", brief=SOURCE, created_at=datetime.now(timezone.utc), drafts=[
        PlatformDraft(Platform.LINKEDIN, "article_post", "Our pilot cut wait times by 38% across 12 sites [1]."),
        PlatformDraft(Platform.TWITTER, "thread", "Pilot cut waits 50%!"),
    ]))
    out = svc.adaptation_preview("p1", references=REFS)
    assert out["parity"]["c1"] == {"linkedin": "kept_cited", "twitter": "dropped"}
    assert _p(out, "twitter")["unsupported_figures"] == ["50%"]


def _gate_service(drafts):
    from datetime import datetime, timezone

    from app.modules.m06_social_media_manager.models import ContentPlan, PlatformDraft
    from app.modules.m06_social_media_manager.service import MemorySocialRepository, Service

    class Store:
        def __init__(self):
            self.items = []

        def put(self, item, **kw):
            self.items.append(item)
            return item

    async def gen(*a, **k):
        return ""

    repo, store = MemorySocialRepository(), Store()
    svc = Service(approval_store=store, generate=gen, repository=repo)
    repo.save_plan(ContentPlan(id="p1", brief=SOURCE, created_at=datetime.now(timezone.utc),
                               drafts=[PlatformDraft(p, f, c) for p, f, c in drafts]))
    return svc, store


def test_schedule_is_refused_when_adaptation_blocks():
    import pytest

    from app.modules.m06_social_media_manager.models import Platform
    from app.modules.m06_social_media_manager.service import DraftComplianceError

    svc, store = _gate_service([
        (Platform.LINKEDIN, "article_post", "Our pilot cut wait times by 38% across 12 sites [1]."),
        (Platform.TWITTER, "thread", "Pilot cut waits 50%! Volunteers logged 4,200 hours."),
    ])
    with pytest.raises(DraftComplianceError) as err:
        svc.request_schedule("p1", references=REFS)
    codes = {i.code for i in err.value.issues}
    assert codes == {"unsupported_figure", "citation_dropped"}
    assert all(i.message.startswith("twitter:") for i in err.value.issues)
    assert store.items == [] and svc.get_plan("p1").status == "draft"


def test_clean_adaptation_schedules_and_parity_rides_in_approval():
    from app.modules.m06_social_media_manager.models import Platform

    svc, store = _gate_service([
        (Platform.LINKEDIN, "article_post", "Our pilot cut wait times by 38% across 12 sites [1]."),
    ])
    reqs = svc.request_schedule("p1", references=REFS)
    assert len(reqs) == 1 and reqs[0].payload["adaptation_parity"] == {"c1": "kept_cited", "c2": "dropped"}
