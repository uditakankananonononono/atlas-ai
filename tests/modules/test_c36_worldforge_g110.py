"""G110: worldforge - rendered AI people/worlds/storyboards, behavior engine."""
from __future__ import annotations

import struct
import zlib
import xml.etree.ElementTree as ET

import pytest

from app.modules.c36 import worldforge


def _req(**kw):
    r = {"as_of": "2026-10-12", "seed": 42,
         "world": {"name": "Aurora City", "places": ["harbor", "atelier", "market", "garden"],
                   "steps": 12},
         "agents": [
             {"id": "a1", "name": "Mira", "traits": ["curious", "creative"],
              "actions": ["explore", "create", "talk"]},
             {"id": "a2", "name": "Dev", "traits": ["analytical", "focused"],
              "actions": ["study", "build", "walk"]},
             {"id": "a3", "name": "Zoe", "traits": ["playful", "bold"],
              "actions": ["play", "perform", "talk"]}],
         "scenario": {"kind": "commercial_storyboard", "product": "Glow Serum"}}
    r.update(kw)
    return r


def _png_chunks(png):
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pos, chunks = 8, []
    while pos < len(png):
        ln = struct.unpack(">I", png[pos:pos + 4])[0]
        tag = png[pos + 4:pos + 8]
        data = png[pos + 8:pos + 8 + ln]
        crc = struct.unpack(">I", png[pos + 8 + ln:pos + 12 + ln])[0]
        assert zlib.crc32(tag + data) & 0xFFFFFFFF == crc, "bad CRC on %r" % tag
        chunks.append((tag, data))
        pos += 12 + ln
    return chunks


def test_person_png_is_decodable_raster():
    out = worldforge.run(_req())
    for pid, png in out["renders"]["people_png"].items():
        chunks = _png_chunks(png)
        tags = [t for t, _ in chunks]
        assert tags == [b"IHDR", b"tEXt", b"IDAT", b"IEND"]
        w, h, bitdepth, colortype = struct.unpack(">IIBB", chunks[0][1][:10])
        assert (w, h, bitdepth, colortype) == (64, 64, 8, 2)
        raw = zlib.decompress(chunks[2][1])
        assert len(raw) == (w * 3 + 1) * h
        # two content rows carry painted pixels (not a blank canvas)
        mid = raw[10 * (w * 3 + 1) + 1: 10 * (w * 3 + 1) + 1 + w * 3]
        assert len(set(mid)) > 4


def test_png_label_spells_synthetic_ai_in_legible_glyphs():
    out = worldforge.run(_req())
    png = out["renders"]["people_png"]["a1"]
    idat = [d for t, d in _png_chunks(png) if t == b"IDAT"][0]
    raw = zlib.decompress(idat)
    size = 64
    rows = [raw[y * (size * 3 + 1) + 1:(y + 1) * (size * 3 + 1)] for y in range(size)]
    bright = {(x, y) for y in range(size - 6, size) for x in range(size)
              if bytes(rows[y][x * 3:x * 3 + 3]) == bytes((240, 240, 246))}
    expected_bits = sum(bin(g).count("1") for ch in worldforge.LABEL
                        for g in worldforge._FONT3X5[ch])
    assert expected_bits > 40  # twelve real glyphs, not a decorative stripe
    assert len(bright) == expected_bits  # exactly the glyph pixels, nothing else


def test_png_carries_text_metadata_marker():
    out = worldforge.run(_req())
    png = out["renders"]["people_png"]["a1"]
    tags = [tag for tag, _ in _png_chunks(png)]
    assert b"tEXt" in tags
    text = [data for tag, data in _png_chunks(png) if tag == b"tEXt"][0]
    assert text == b"Description\x00SYNTHETIC-AI"


def test_png_label_band_present_in_pixels():
    out = worldforge.run(_req())
    png = out["renders"]["people_png"]["a1"]
    idat = [d for t, d in _png_chunks(png) if t == b"IDAT"][0]
    raw = zlib.decompress(idat)
    w = 64
    last = raw[(w * 3 + 1) * 63 + 1:]  # final row
    assert bytes(last[:3]) == bytes((30, 30, 34))  # label band color


def test_people_params_trait_deterministic_and_distinct():
    p1 = worldforge.person_params("a1", "Mira", ["curious", "creative"])
    p1b = worldforge.person_params("a1", "Mira", ["curious", "creative"])
    p2 = worldforge.person_params("a2", "Dev", ["analytical", "focused"])
    assert p1 == p1b
    assert p1 != p2
    assert p1["label"] == "SYNTHETIC-AI" and p1["ai_generated"] is True


def test_svg_renders_parse_and_carry_label():
    out = worldforge.run(_req())
    for svg in list(out["renders"]["people_svg"].values()) + [
            out["renders"]["world_svg"], out["renders"]["storyboard_svg"]]:
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")
        assert "SYNTHETIC-AI" in svg
    assert "Glow Serum" in out["renders"]["storyboard_svg"]
    assert "Aurora City" in out["renders"]["world_svg"]


def test_storyboard_panels_cover_events():
    out = worldforge.run(_req())
    n_actions = sum(1 for e in out["events"] if "action" in e)
    assert out["coverage"]["storyboard_panels"] == min(24, n_actions)
    assert out["coverage"]["storyboard_panels"] > 0


def test_behavior_engine_trait_weighting():
    # single-trait curious agent over many seeds explores more than a bold one
    curious = worldforge.simulate({"places": ["x", "y"]},
                                  [{"id": "c", "name": "C", "traits": ["curious"],
                                    "actions": ["explore", "rest"]}], 40, 7, "2026-10-12")[0]
    bold = worldforge.simulate({"places": ["x", "y"]},
                               [{"id": "b", "name": "B", "traits": ["bold"],
                                 "actions": ["explore", "rest"]}], 40, 7, "2026-10-12")[0]
    c_explore = sum(1 for e in curious if e.get("action") == "explore")
    b_explore = sum(1 for e in bold if e.get("action") == "explore")
    assert c_explore > b_explore


def test_encounters_form_bonds():
    out = worldforge.run(_req())
    encounters = [e for e in out["events"] if e.get("kind") == "encounter"]
    assert encounters, "co-located agents must encounter"
    assert out["relationships"]
    assert all(r["strength"] >= 1 for r in out["relationships"])


def test_determinism_byte_identical():
    a, b = worldforge.run(_req()), worldforge.run(_req())
    assert a == b
    assert a["renders"]["people_png"]["a1"] == b["renders"]["people_png"]["a1"]


def test_refusals():
    with pytest.raises(ValueError, match="VENT_REFUSED_DECEPTIVE:likeness"):
        worldforge.run(_req(likeness="a real celebrity"))
    with pytest.raises(ValueError, match="VENT_REFUSED_EFFECT:publish"):
        worldforge.run(_req(render={"publish": True}))
    with pytest.raises(ValueError, match="VENT_REFUSED_SPEND:buy"):
        worldforge.run(_req(buy="ads"))
    with pytest.raises(ValueError, match="VENT_REFUSED_UNKNOWN"):
        worldforge.run(_req(bogus=1))
    with pytest.raises(ValueError, match="VENT_REFUSED_BAD_TYPE:seed"):
        worldforge.run(_req(seed="42"))
    with pytest.raises(ValueError, match="VENT_REFUSED_DUPLICATE"):
        r = _req()
        r["agents"] = r["agents"][:1] * 2
        worldforge.run(r)
