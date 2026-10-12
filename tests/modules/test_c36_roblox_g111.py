"""G111: roblox game builder - complete project, real Lua lint, wiring, refusals."""
from __future__ import annotations

import json

import pytest

from app.modules.c36 import roblox


def _req(**kw):
    r = {"as_of": "2026-10-12",
         "concept": {"title": "Gem Rush",
                     "premise": "Players race to gather falling gems while dodging hazards.",
                     "mechanics": ["CollectGems", "DodgeStorm", "CheckpointRun", "BaseGuard"],
                     "win_score": 500},
         "monetization": {"devex_usd_per_robux": 0.0038,
                          "items": [{"item": "2x Score Pass", "price_robux": 199,
                                     "conversion": 0.02, "monthly_visitors": 5000}]}}
    r.update(kw)
    return r


def test_project_tree_complete_and_json_valid():
    out = roblox.run(_req())
    files = out["files"]
    project = json.loads(files["default.project.json"])
    assert project["name"] == "Gem Rush"
    for mech in ("CollectGems", "DodgeStorm", "CheckpointRun", "BaseGuard"):
        assert "src/server/Mechanics/%s.lua" % mech in files
    for path in ("src/server/GameLoop.server.lua", "src/server/Leaderstats.server.lua",
                 "src/server/Remotes.server.lua", "src/server/Monetization.server.lua",
                 "src/client/HUD.client.lua", "src/client/Input.client.lua",
                 "src/shared/Config.lua", "docs/game_design.md", "docs/publish_runbook.md",
                 "docs/monetization.md"):
        assert path in files, path


def test_generated_lua_is_fully_implemented_not_stubs():
    out = roblox.run(_req())
    assert out["checks"]["all_lua_lint_clean"] is True
    assert out["checks"]["placeholder_free"] is True
    assert out["checks"]["wiring_clean"] is True
    for path, text in out["files"].items():
        assert "TO_WRITE" not in text and "unimplemented" not in text
    # every mechanic module returns a table and implements scoring
    for mech in ("CollectGems", "DodgeStorm", "CheckpointRun", "BaseGuard"):
        text = out["files"]["src/server/Mechanics/%s.lua" % mech]
        assert "return M" in text
        assert "function M:AddScore" in text
        assert "cooldownReady" in text


def test_archetypes_deterministic_and_distinct_implementations():
    out1, out2 = roblox.run(_req()), roblox.run(_req())
    assert out1 == out2
    archs = set(out1["archetypes"].values())
    assert len(archs) >= 2, "four mechanics must not all collapse to one archetype"
    bodies = {out1["files"]["src/server/Mechanics/%s.lua" % m] for m in out1["archetypes"]}
    assert len(bodies) >= 2


def test_linter_catches_real_defects():
    assert "unclosed_blocks:1" in roblox.lint_lua("local function f()\n\treturn 1\n")
    assert "unbalanced_end" in roblox.lint_lua("end\n")
    assert "forbidden_call:loadstring" in roblox.lint_lua('loadstring("x")()')
    assert "reserved_identifier:end" in roblox.lint_lua("local function end()\nend\n")
    assert "placeholder:TO_WRITE" in roblox.lint_lua("-- TO_WRITE later\nreturn {}\n")
    assert roblox.lint_lua("local function f()\n\tif true then return 1 end\nend\nreturn f\n") == []
    # comments and strings do not confuse the block counter
    src = '-- function fake()\nlocal s = "if then end"\nlocal function g()\n\tfor i=1,2 do end\nend\nreturn g\n'
    assert roblox.lint_lua(src) == []


def test_leaderstats_uses_pcall_and_datastore():
    text = roblox.run(_req())["files"]["src/server/Leaderstats.server.lua"]
    assert "DataStoreService:GetDataStore" in text
    assert "pcall" in text and "SetAsync" in text and "GetAsync" in text


def test_monetization_process_receipt_and_model():
    out = roblox.run(_req())
    monet = out["files"]["src/server/Monetization.server.lua"]
    assert "MarketplaceService.ProcessReceipt" in monet
    assert "NotProcessedYet" in monet and "PurchaseGranted" in monet
    row = out["monetization_model"][0]
    assert row["base"] == int(199 * 0.02 * 5000)
    assert row["low"] == int(row["base"] * 0.5) and row["high"] == int(row["base"] * 2)
    assert "planning numbers, not income promises" in out["files"]["docs/monetization.md"]


def test_runbook_is_real_steps_not_boilerplate():
    text = roblox.run(_req())["files"]["docs/publish_runbook.md"]
    assert "rojo serve" in text
    assert "Publish to Roblox As" in text
    assert "Creator Dashboard" in text
    assert "owner" in text


def test_refusals():
    with pytest.raises(ValueError, match="GAME_REFUSED_EFFECT:publish"):
        roblox.run(_req(publish=True))
    with pytest.raises(ValueError, match="GAME_REFUSED_SPEND:buy"):
        roblox.run(_req(buy="robux"))
    with pytest.raises(ValueError, match="GAME_REFUSED_NOCREDS:cookie"):
        roblox.run(_req(cookie=".ROBLOSECURITY"))
    with pytest.raises(ValueError, match="GAME_REFUSED_BAD_TYPE:mechanics"):
        bad = _req()
        bad["concept"]["mechanics"] = ["not a lua ident!"]
        roblox.run(bad)
    with pytest.raises(ValueError, match="GAME_REFUSED_DUPLICATE"):
        bad = _req()
        bad["concept"]["mechanics"] = ["Jump", "Jump"]
        roblox.run(bad)
    with pytest.raises(ValueError, match="GAME_REFUSED_UNKNOWN"):
        roblox.run(_req(bogus=1))
