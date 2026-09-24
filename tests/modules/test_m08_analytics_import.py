from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m08_startup_growth.analytics_import import ImportError_, from_mapped, from_plausible
from app.modules.m08_startup_growth.experiments import ExperimentBoard, ExperimentRefused

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


class Approvals:
    def put(self, item, *, user_id=None):
        return item


def board(tmp_path):
    e = create_engine(f"sqlite:///{tmp_path/'x.db'}"); Base.metadata.create_all(e)
    return (ExperimentBoard("t1", approvals=Approvals(), session_factory=sessionmaker(bind=e), clock=lambda: T0),)


def card(b):
    return b.create(title="Waitlist from Reddit", hypothesis="If we post the demo in r/SaaS, at least 5% of visitors join the waitlist.",
                    metric="waitlist signups / visitors", success_rate=0.05, max_days=14, max_effort_hours=6,
                    tools=[{"name": "Reddit r/SaaS post"}])

VISITORS = "date,visitors,pageviews,bounces,visits,visit_duration\n2026-10-01,120,300,40,130,5000\n2026-10-02,80,150,30,90,3000\n2026-10-03,50,60,20,55,900\n"
EVENTS = ("date,name,link_url,path,visitors,events\n2026-10-01,Signup,,,6,6\n2026-10-02,Signup,,,4,5\n"
          "2026-10-02,Outbound Link: Click,https://x.test,,9,12\n2026-10-03,Signup,,,1,1\n")


def test_plausible_window_and_goal():
    out = from_plausible(visitors_csv=VISITORS, custom_events_csv=EVENTS, goal="Signup",
                         start=date(2026, 10, 1), end=date(2026, 10, 2))
    assert (out["exposures"], out["conversions"], out["days"]) == (200, 10, 2)
    assert "visitor-days" in out["unit"]
    with pytest.raises(ImportError_, match="not found"):
        from_plausible(visitors_csv=VISITORS, custom_events_csv=EVENTS, goal="Purchase")
    with pytest.raises(ImportError_, match="missing columns"):
        from_plausible(visitors_csv="day,people\n2026-10-01,3\n", custom_events_csv=EVENTS, goal="Signup")


def test_mapped_csv_with_filter():
    csv_text = "day,utm_source,views,signups\n2026-10-01,reddit,100,7\n2026-10-01,hn,50,1\n2026-10-02,reddit,40,2\n"
    out = from_mapped(csv_text=csv_text, exposures_col="views", conversions_col="signups", date_col="day",
                      filter_col="utm_source", filter_value="reddit", label="umami")
    assert (out["exposures"], out["conversions"], out["rows"]) == (140, 9, 2)
    with pytest.raises(ImportError_):
        from_mapped(csv_text=csv_text, exposures_col="views", conversions_col="signups", start=date(2026, 10, 1))
    with pytest.raises(ImportError_, match="exceed"):
        from_mapped(csv_text="a,b\n1,5\n", exposures_col="a", conversions_col="b")


def test_import_records_once_on_the_board(tmp_path):
    b, *_ = board(tmp_path)
    c = card(b)
    parsed = from_plausible(visitors_csv=VISITORS, custom_events_csv=EVENTS, goal="Signup")
    got = b.import_observation(c["id"], parsed, effort_hours=1)
    assert got["result"]["exposures"] == 250 and got["result"]["conversions"] == 11
    assert got["observations"][0]["fingerprint"] == parsed["fingerprint"]
    with pytest.raises(ExperimentRefused, match="already imported"):
        b.import_observation(c["id"], parsed)


def test_http_import_routes(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m08_startup_growth import routes
    monkeypatch.setenv("ATLAS_ENV", "development")
    app = FastAPI(); app.include_router(routes.router)
    cl = TestClient(app)
    ok = cl.post("/startup-growth/experiments", json={"title": "x", "hypothesis": "A launch post brings 3% signups.", "metric": "signups",
                                                       "success_rate": 0.03, "max_days": 7, "max_effort_hours": 2,
                                                       "tools": [{"name": "Hacker News Show HN"}]})
    eid = ok.json()["id"]
    body = {"visitors_csv": VISITORS, "custom_events_csv": EVENTS, "goal": "Signup", "start": "2026-10-01", "end": "2026-10-02"}
    r = cl.post(f"/startup-growth/experiments/{eid}/import/plausible", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["result"]["conversions"] == 10 and r.json()["import"]["days"] == 2
    assert cl.post(f"/startup-growth/experiments/{eid}/import/plausible", json=body).status_code in (409, 422)
    bad = cl.post(f"/startup-growth/experiments/{eid}/import/plausible", json=body | {"goal": "Nope"})
    assert bad.status_code == 422 and "not found" in bad.text
    m = cl.post(f"/startup-growth/experiments/{eid}/import/csv",
                json={"csv_text": "views,signups\n30,2\n", "exposures_col": "views", "conversions_col": "signups", "label": "umami"})
    assert m.status_code == 200 and m.json()["result"]["exposures"] == 230
