"""G112: anime production pipeline - scripts, shots, boards, schedule, checks."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from app.modules.c36 import anime


def _req(**kw):
    r = {"as_of": "2026-10-12", "seed": 11,
         "concept": {"title": "Skybound Courier",
                     "premise": "A courier crew delivers impossible packages across floating cities.",
                     "characters": [{"id": "mira", "name": "Mira", "traits": ["bold", "curious"]},
                                    {"id": "dev", "name": "Dev", "traits": ["analytical"]},
                                    {"id": "zoe", "name": "Zoe", "traits": ["playful", "kind"]}],
                     "episodes": 3}}
    r.update(kw)
    return r


def test_full_package_present():
    out = anime.run(_req())
    assert len(out["scripts"]) == 3
    assert set(out["shot_lists"]) == {1, 2, 3}
    assert set(out["storyboards"]) == {1, 2, 3}
    assert out["manifest"]["episodes"][0]["scenes"] == 6
    assert out["total_weeks"] > 0 and out["schedule"]
    assert out["bible"]["title"] == "Skybound Courier"


def test_scripts_have_real_dialogue_no_placeholders():
    out = anime.run(_req())
    assert out["checks"]["placeholder_free"] is True
    assert out["checks"]["issues"] == []
    for ep in out["scripts"]:
        assert len(ep["acts"]) == 3
        for act in ep["acts"]:
            for scene in act["scenes"]:
                assert scene["beat"]
                assert len(scene["dialogue"]) == 3
                for line in scene["dialogue"]:
                    assert len(line["text"]) > 20
                    assert "TO_WRITE" not in line["text"]


def test_dialogue_is_trait_driven():
    bold = {"id": "b", "name": "B", "traits": ["bold"]}
    calm = {"id": "c", "name": "C", "traits": ["calm"]}
    lb = anime._line(bold, "the gate opens", 1, 0)
    lc = anime._line(calm, "the gate opens", 1, 0)
    assert lb != lc
    assert any(p in lb for p in anime.DICTION["bold"])
    assert any(p in lc for p in anime.DICTION["calm"])


def test_every_scene_has_shots_with_camera():
    out = anime.run(_req())
    assert out["checks"]["every_scene_shot"] is True
    for ep_no, shots in out["shot_lists"].items():
        assert shots
        for shot in shots:
            assert shot["kind"] in anime.SHOT_KINDS
            assert shot["camera"] in anime.CAMERA_MOVES
            assert 2 <= shot["duration_s"] <= 6
            assert shot["on_screen"]


def test_storyboards_render_and_parse():
    out = anime.run(_req())
    for svg in out["storyboards"].values():
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")
        assert "SYNTHETIC-AI" in svg


def test_schedule_overlaps_and_covers_all_phases():
    out = anime.run(_req())
    phases = {r["phase"] for r in out["schedule"]}
    assert phases == {p for p, _ in anime.PHASES}
    eps = {r["episode"] for r in out["schedule"]}
    assert eps == {1, 2, 3}
    for r in out["schedule"]:
        assert r["end_week"] >= r["start_week"]


def test_determinism():
    assert anime.run(_req()) == anime.run(_req())


def test_refusals():
    with pytest.raises(ValueError, match="SHOW_REFUSED_EFFECT:broadcast"):
        anime.run(_req(broadcast=True))
    with pytest.raises(ValueError, match="SHOW_REFUSED_SPEND:pay"):
        anime.run(_req(pay="studio"))
    with pytest.raises(ValueError, match="SHOW_REFUSED_DUPLICATE"):
        bad = _req()
        bad["concept"]["characters"] = bad["concept"]["characters"][:1] * 2
        anime.run(bad)
    with pytest.raises(ValueError, match="SHOW_REFUSED_BAD_TYPE:episodes"):
        bad = _req()
        bad["concept"]["episodes"] = 99
        anime.run(bad)
    with pytest.raises(ValueError, match="SHOW_REFUSED_UNKNOWN"):
        anime.run(_req(bogus=1))
