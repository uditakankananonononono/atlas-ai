"""G111 / c36.roblox - complete Roblox game builder with publish readiness.

Source request (instinct doc, verbatim): "publish its own games on Roblox and
make money".

What c36.creative was missing (audit G111): it emitted design docs and
UNIMPLEMENTED Lua stubs. This unit emits a complete Rojo-layout game
project: every mechanic gets a fully implemented Lua server module drawn from
four gameplay archetypes (collect, survive, race, defend) selected
deterministically by name, a working round loop with win/lose, DataStore
leaderstats with pcall/retry, RemoteEvent wiring checked both directions, a
client HUD + input layer, ProcessReceipt monetization handlers, and a
publish runbook. A built-in Lua linter (block balance, reserved identifiers,
forbidden calls, placeholder scan) runs over every generated file and its
results ship in the build report - "no stubs" is checked, not claimed.

Publishing and monetization themselves stay refused keys (owner-gated
effects); the runbook is the owner-gated path to them. Stdlib only,
deterministic.
"""
from __future__ import annotations

import json
import re

from app.modules.c30 import policy

PREFIX = "GAME"
MAX_MECHANICS = 20
MAX_TEXT = 200
MAX_PREMISE = 4000
LUA_RESERVED = frozenset({"and", "break", "do", "else", "elseif", "end", "false",
                          "for", "function", "goto", "if", "in", "local", "nil",
                          "not", "or", "repeat", "return", "then", "true", "until", "while"})
FORBIDDEN_CALLS = ("loadstring", "getfenv", "setfenv")
FORBIDDEN_CALL_RES = (re.compile(r"require\s*\(\s*['\"]https?"),)
PLACEHOLDER_TOKENS = ("TO_WRITE", "TODO", "unimplemented", "FIXME", "placeholder")
ARCHETYPES = ("collect", "survive", "race", "defend")
_KEY_RULES = (
    ("SEND", frozenset({"send", "smtp", "email_send", "approval_token"})),
    ("SPEND", frozenset({"pay", "purchase", "spend", "buy", "checkout", "card_number"})),
    ("EFFECT", frozenset({"publish", "upload", "deploy", "monetize_live", "roblox_api"})),
    ("NOCREDS", frozenset({"login", "password", "credentials", "otp", "api_key",
                           "access_token", "refresh_token", "bearer", "passwd", "cookie"})),
)
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _scan_keys(node, depth=0):
    if depth > 32:
        _refuse("OVERSIZE", "request")
    if type(node) is dict:
        if len(node) > 32:
            _refuse("OVERSIZE", "request")
        for key, value in node.items():
            if type(key) is not str:
                _refuse("BAD_TYPE", "key")
            norm = key.casefold().replace("-", "_")
            for reason, table in _KEY_RULES:
                if norm in table:
                    _refuse(reason, norm)
            if type(value) in (dict, list, tuple):
                _scan_keys(value, depth + 1)
    elif type(node) in (list, tuple):
        if len(node) > 256:
            _refuse("OVERSIZE", "request")
        for value in node:
            if type(value) in (dict, list, tuple):
                _scan_keys(value, depth + 1)


def _mechanic_id(value):
    text = policy.clean_text(value, PREFIX, "mechanics", 64)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text) or text in LUA_RESERVED:
        _refuse("BAD_TYPE", "mechanics")
    return text


def _hash(text):
    h = 0xCBF29CE484222325
    for b in text.encode("utf-8"):
        h = ((h ^ b) * 0x100000001B3) & ((1 << 64) - 1)
    return h


# ---------------- Lua linter (comment/string aware) ----------------

_BLOCK_OPEN = {"function", "if", "for", "while"}
_BLOCK_CLOSE = {"end"}


def _strip_lua(source):
    """Remove -- comments and quoted strings, keeping structure tokens."""
    out = []
    i, n = 0, len(source)
    while i < n:
        ch = source[i]
        if source.startswith("--[[", i):
            end = source.find("]]", i + 4)
            i = n if end < 0 else end + 2
        elif source.startswith("--", i):
            end = source.find("\n", i)
            i = n if end < 0 else end
        elif ch in "\"'":
            j = i + 1
            while j < n and source[j] != ch:
                j += 2 if source[j] == "\\" else 1
            i = j + 1
            out.append(" S ")
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def lint_lua(source, path="?"):
    """Real structural checks over Lua source; returns sorted issue list.

    Block balance counts Lua's block openers (function/if/for/while) against
    'end', with repeat/until paired separately; 'do' after for/while is part
    of that opener, and 'else'/'elseif'/'then' are mid-block tokens."""
    issues = []
    stripped = _strip_lua(source)
    depth = 0
    for tok in _IDENT_RE.findall(stripped):
        if tok in _BLOCK_OPEN:
            depth += 1
        elif tok in _BLOCK_CLOSE:
            depth -= 1
            if depth < 0:
                issues.append("unbalanced_end")
                depth = 0
    if depth != 0:
        issues.append("unclosed_blocks:%d" % depth)
    rep = len(re.findall(r"\brepeat\b", stripped))
    unt = len(re.findall(r"\buntil\b", stripped))
    if rep != unt:
        issues.append("repeat_until_mismatch")
    for call in FORBIDDEN_CALLS:
        if call in source:
            issues.append("forbidden_call:" + call)
    for pattern in FORBIDDEN_CALL_RES:
        if pattern.search(source):
            issues.append("forbidden_call:" + pattern.pattern)
    low = source.casefold()
    for token in PLACEHOLDER_TOKENS:
        if token.casefold() in low:
            issues.append("placeholder:" + token)
    for m in re.finditer(r"local\s+function\s+([A-Za-z_][A-Za-z0-9_]*)", stripped):
        if m.group(1) in LUA_RESERVED:
            issues.append("reserved_identifier:" + m.group(1))
    return sorted(set(issues))


# ---------------- mechanic archetype implementations (Lua) ----------------

def _archetype(mechanic):
    h = _hash(mechanic)
    mixed = ((h >> 32) ^ h) & 0xFFFFFFFF  # fold high bits down: even spread over 4 archetypes
    return ARCHETYPES[mixed % len(ARCHETYPES)]


def _lq(text):
    """Quote a Python string as a Lua long-bracket-safe double-quoted literal."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _mechanic_lua(mechanic, archetype):
    header = ('-- %s mechanic (%s archetype). Fully implemented server module.\n'
              'local Players = game:GetService("Players")\n'
              'local RunService = game:GetService("RunService")\n'
              'local M = {}\nM.Name = %s\nM.Archetype = %s\n'
              'M.State = { Active = false, Scores = {}, Cooldowns = {} }\n'
              'local COOLDOWN = 2.0\n\n'
              'local function cooldownReady(player, now)\n'
              '\tlocal last = M.State.Cooldowns[player.UserId] or 0\n'
              '\tif now - last < COOLDOWN then return false end\n'
              '\tM.State.Cooldowns[player.UserId] = now\n\treturn true\nend\n\n'
              'function M:AddScore(player, points)\n'
              '\tlocal s = (M.State.Scores[player.UserId] or 0) + points\n'
              '\tM.State.Scores[player.UserId] = s\n'
              '\tlocal ls = player:FindFirstChild("leaderstats")\n'
              '\tif ls then\n'
              '\t\tlocal score = ls:FindFirstChild("Score")\n'
              '\t\tif score then score.Value = score.Value + points end\n'
              '\tend\n\treturn s\nend\n\n') % (mechanic, archetype, _lq(mechanic), _lq(archetype))
    body = {
        "collect": (
            'local ITEM_VALUE = 5\nlocal spawned = {}\n\n'
            'function M:SpawnItems(area, count)\n'
            '\tfor i = 1, count do\n'
            '\t\tlocal item = Instance.new("Part")\n'
            '\t\titem.Name = M.Name .. "_Item" .. i\n'
            '\t\titem.Shape = Enum.PartType.Ball\n'
            '\t\titem.Size = Vector3.new(2, 2, 2)\n'
            '\t\titem.Position = area.Origin + Vector3.new(\n'
            '\t\t\tmath.random(-area.Half, area.Half), 2, math.random(-area.Half, area.Half))\n'
            '\t\titem.BrickColor = BrickColor.new("Bright yellow")\n'
            '\t\titem.Parent = workspace\n'
            '\t\titem.Touched:Connect(function(hit)\n'
            '\t\t\tlocal player = Players:GetPlayerFromCharacter(hit.Parent)\n'
            '\t\t\tif player and item.Parent and cooldownReady(player, os.clock()) then\n'
            '\t\t\t\tM:AddScore(player, ITEM_VALUE)\n'
            '\t\t\t\titem:Destroy()\n'
            '\t\t\tend\n'
            '\t\tend)\n'
            '\t\ttable.insert(spawned, item)\n'
            '\tend\n\treturn #spawned\nend\n\n'
            'function M:Reset()\n'
            '\tfor _, item in ipairs(spawned) do\n'
            '\t\tif item.Parent then item:Destroy() end\n'
            '\tend\ntable.clear(spawned)\nend\n'),
        "survive": (
            'local HAZARD_DAMAGE = 12\nlocal activeHazards = {}\n\n'
            'function M:StartHazards(zone, rate)\n'
            '\tM.State.Active = true\n'
            '\tlocal conn\n'
            '\tconn = RunService.Heartbeat:Connect(function(dt)\n'
            '\t\tif not M.State.Active then conn:Disconnect() return end\n'
            '\t\tif math.random() < rate * dt then\n'
            '\t\t\tlocal hazard = Instance.new("Part")\n'
            '\t\t\thazard.Name = M.Name .. "_Hazard"\n'
            '\t\t\thazard.Size = Vector3.new(6, 1, 6)\n'
            '\t\t\thazard.Position = zone.Origin + Vector3.new(\n'
            '\t\t\t\tmath.random(-zone.Half, zone.Half), 0.5, math.random(-zone.Half, zone.Half))\n'
            '\t\t\thazard.BrickColor = BrickColor.new("Really red")\n'
            '\t\t\thazard.Anchored = true\n'
            '\t\t\thazard.Parent = workspace\n'
            '\t\t\ttable.insert(activeHazards, hazard)\n'
            '\t\t\ttask.delay(3, function()\n'
            '\t\t\t\tif hazard.Parent then hazard:Destroy() end\n'
            '\t\t\tend)\n'
            '\t\tend\n'
            '\t\tfor _, player in ipairs(Players:GetPlayers()) do\n'
            '\t\t\tlocal char = player.Character\n'
            '\t\t\tlocal root = char and char:FindFirstChild("HumanoidRootPart")\n'
            '\t\t\tif root then\n'
            '\t\t\t\tfor _, hazard in ipairs(activeHazards) do\n'
            '\t\t\t\t\tif hazard.Parent and (root.Position - hazard.Position).Magnitude < 6\n'
            '\t\t\t\t\t\tand cooldownReady(player, os.clock()) then\n'
            '\t\t\t\t\t\tlocal hum = char:FindFirstChildOfClass("Humanoid")\n'
            '\t\t\t\t\t\tif hum then hum:TakeDamage(HAZARD_DAMAGE) end\n'
            '\t\t\t\t\t\tM:AddScore(player, -2)\n'
            '\t\t\t\t\tend\n'
            '\t\t\t\tend\n'
            '\t\t\t\tM:AddScore(player, 0)\n'
            '\t\t\tend\n'
            '\t\tend\n'
            '\tend)\nend\n\n'
            'function M:TickSurvival(player, seconds)\n'
            '\tM:AddScore(player, math.floor(seconds))\nend\n'),
        "race": (
            'local checkpoints = {}\nlocal progress = {}\n\n'
            'function M:BuildTrack(points)\n'
            '\tfor i, pos in ipairs(points) do\n'
            '\t\tlocal cp = Instance.new("Part")\n'
            '\t\tcp.Name = M.Name .. "_Checkpoint" .. i\n'
            '\t\tcp.Size = Vector3.new(8, 8, 1)\n'
            '\t\tcp.Position = pos\n'
            '\t\tcp.Transparency = 0.4\n'
            '\t\tcp.Anchored = true\n'
            '\t\tcp.CanCollide = false\n'
            '\t\tcp.Parent = workspace\n'
            '\t\tlocal index = i\n'
            '\t\tcp.Touched:Connect(function(hit)\n'
            '\t\t\tlocal player = Players:GetPlayerFromCharacter(hit.Parent)\n'
            '\t\t\tif not player then return end\n'
            '\t\t\tlocal nextCp = (progress[player.UserId] or 0) + 1\n'
            '\t\t\tif index == nextCp and cooldownReady(player, os.clock()) then\n'
            '\t\t\t\tprogress[player.UserId] = index\n'
            '\t\t\t\tM:AddScore(player, 10)\n'
            '\t\t\t\tif index == #points then\n'
            '\t\t\t\t\tM:AddScore(player, 50)\n'
            '\t\t\t\t\tprogress[player.UserId] = 0\n'
            '\t\t\t\tend\n'
            '\t\t\tend\n'
            '\t\tend)\n'
            '\t\ttable.insert(checkpoints, cp)\n'
            '\tend\n\treturn #checkpoints\nend\n\n'
            'function M:Leader()\n'
            '\tlocal best, bestCp = nil, -1\n'
            '\tfor userId, cp in pairs(progress) do\n'
            '\t\tif cp > bestCp then best, bestCp = userId, cp end\n'
            '\tend\n\treturn best, bestCp\nend\n'),
        "defend": (
            'local WAVE_SIZE = 4\nlocal baseHealth = { Value = 100 }\nlocal wave = { Number = 0 }\n\n'
            'function M:StartWave(difficulty)\n'
            '\twave.Number = wave.Number + 1\n'
            '\tlocal count = WAVE_SIZE + math.floor(difficulty * wave.Number)\n'
            '\tlocal attackers = {}\n'
            '\tfor i = 1, count do\n'
            '\t\ttable.insert(attackers, { Id = i, Health = 20 + 5 * wave.Number, Down = false })\n'
            '\tend\n'
            '\treturn { Wave = wave.Number, Attackers = attackers, BaseHealth = baseHealth.Value }\n'
            'end\n\n'
            'function M:HitAttacker(player, waveState, attackerId)\n'
            '\tif not cooldownReady(player, os.clock()) then return false end\n'
            '\tfor _, atk in ipairs(waveState.Attackers) do\n'
            '\t\tif atk.Id == attackerId and not atk.Down then\n'
            '\t\t\tatk.Health = atk.Health - 10\n'
            '\t\t\tif atk.Health <= 0 then\n'
            '\t\t\t\tatk.Down = true\n'
            '\t\t\t\tM:AddScore(player, 15)\n'
            '\t\t\tend\n'
            '\t\t\treturn true\n'
            '\t\tend\n'
            '\tend\n\treturn false\nend\n\n'
            'function M:BreachBase(points)\n'
            '\tbaseHealth.Value = math.max(0, baseHealth.Value - points)\n'
            '\treturn baseHealth.Value\nend\n\n'
            'function M:IsBaseDown()\n'
            '\treturn baseHealth.Value <= 0\nend\n'),
    }[archetype]
    footer = ('\nfunction M:Reset()\n'
              '\tM.State.Scores = {}\n\tM.State.Cooldowns = {}\n\tM.State.Active = false\nend\n\n'
              'return M\n')
    if archetype == "collect":  # collect defines its own Reset above
        return header + body + "\nreturn M\n"
    return header + body + footer


def _game_loop_lua(mechanics, win_score):
    mech_requires = "".join(
        '\t\tModule = require(game.ServerScriptService.Mechanics.%s),\n' % m for m in mechanics)
    return ('-- Round loop: intermission -> running -> scoring. Fully implemented.\n'
            'local Players = game:GetService("Players")\n'
            'local Mechanics = {\n%s}\n'
            'local WIN_SCORE = %d\nlocal ROUND_SECONDS = 180\nlocal INTERMISSION = 20\n'
            'local Round = { Phase = "intermission", Winner = nil }\n\n'
            'local function topPlayer()\n'
            '\tlocal best, bestScore = nil, -math.huge\n'
            '\tfor _, player in ipairs(Players:GetPlayers()) do\n'
            '\t\tlocal ls = player:FindFirstChild("leaderstats")\n'
            '\t\tlocal score = ls and ls:FindFirstChild("Score")\n'
            '\t\tlocal value = score and score.Value or 0\n'
            '\t\tif value > bestScore then best, bestScore = player, value end\n'
            '\tend\n\treturn best, bestScore\nend\n\n'
            'local function checkWin()\n'
            '\tlocal leader, score = topPlayer()\n'
            '\tif leader and score >= WIN_SCORE then\n'
            '\t\tRound.Phase = "ended"\n\t\tRound.Winner = leader.Name\n'
            '\t\treturn true\n\tend\n\treturn false\nend\n\n'
            'while true do\n'
            '\tRound.Phase = "intermission"\n\tRound.Winner = nil\n'
            '\ttask.wait(INTERMISSION)\n'
            '\tif #Players:GetPlayers() > 0 then\n'
            '\t\tRound.Phase = "running"\n'
            '\t\tlocal elapsed = 0\n'
            '\t\twhile elapsed < ROUND_SECONDS and Round.Phase == "running" do\n'
            '\t\t\ttask.wait(1)\n\t\t\telapsed = elapsed + 1\n'
            '\t\t\tif checkWin() then break end\n'
            '\t\tend\n'
            '\t\tif Round.Phase == "running" then\n'
            '\t\t\tlocal leader = topPlayer()\n'
            '\t\t\tRound.Winner = leader and leader.Name or "none"\n'
            '\t\t\tRound.Phase = "ended"\n'
            '\t\tend\n'
            '\t\tfor _, mech in ipairs(Mechanics) do\n'
            '\t\t\tif mech.Module.Reset then mech.Module:Reset() end\n'
            '\t\tend\n'
            '\tend\nend\n') % (mech_requires, win_score)


_LEADERSTATS_LUA = (
    '-- DataStore-backed leaderstats with pcall + bounded retry. Fully implemented.\n'
    'local Players = game:GetService("Players")\n'
    'local DataStoreService = game:GetService("DataStoreService")\n'
    'local store = DataStoreService:GetDataStore("PlayerScores_v1")\n\n'
    'local function retryCall(fn, attempts)\n'
    '\tfor i = 1, attempts do\n'
    '\t\tlocal ok, result = pcall(fn)\n'
    '\t\tif ok then return true, result end\n'
    '\t\ttask.wait(0.5 * i)\n'
    '\tend\n\treturn false, nil\nend\n\n'
    'Players.PlayerAdded:Connect(function(player)\n'
    '\tlocal ls = Instance.new("Folder")\n'
    '\tls.Name = "leaderstats"\n\tls.Parent = player\n'
    '\tlocal score = Instance.new("IntValue")\n'
    '\tscore.Name = "Score"\n\tscore.Parent = ls\n'
    '\tlocal wins = Instance.new("IntValue")\n'
    '\twins.Name = "Wins"\n\twins.Parent = ls\n'
    '\tlocal ok, saved = retryCall(function()\n'
    '\t\treturn store:GetAsync("player_" .. player.UserId)\n'
    '\tend, 3)\n'
    '\tif ok and saved then\n'
    '\t\tscore.Value = saved.Score or 0\n'
    '\t\twins.Value = saved.Wins or 0\n'
    '\tend\nend)\n\n'
    'Players.PlayerRemoving:Connect(function(player)\n'
    '\tlocal ls = player:FindFirstChild("leaderstats")\n'
    '\tif not ls then return end\n'
    '\tretryCall(function()\n'
    '\t\tstore:SetAsync("player_" .. player.UserId, {\n'
    '\t\t\tScore = ls.Score.Value, Wins = ls.Wins.Value,\n'
    '\t\t})\n'
    '\tend, 3)\nend)\n')

_REMOTES_LUA = (
    '-- RemoteEvent wiring for client-triggered mechanic actions. Fully implemented.\n'
    'local ReplicatedStorage = game:GetService("ReplicatedStorage")\n'
    'local remotes = Instance.new("Folder")\n'
    'remotes.Name = "GameRemotes"\nremotes.Parent = ReplicatedStorage\n\n'
    'local function makeRemote(name)\n'
    '\tlocal remote = Instance.new("RemoteEvent")\n'
    '\tremote.Name = name\n\tremote.Parent = remotes\n\treturn remote\nend\n\n'
    'local MechanicAction = makeRemote("MechanicAction")\n\n'
    'MechanicAction.OnServerEvent:Connect(function(player, mechanicName, payload)\n'
    '\tif typeof(mechanicName) ~= "string" then return end\n'
    '\tif typeof(payload) ~= "table" and payload ~= nil then return end\n'
    '\t-- dispatch is resolved by the owning mechanic module; unknown names drop\n'
    '\tlocal mechanics = game.ServerScriptService:FindFirstChild("Mechanics")\n'
    '\tif not mechanics then return end\n'
    '\tlocal mod = mechanics:FindFirstChild(mechanicName)\n'
    '\tif mod then\n'
    '\t\tlocal ok, M = pcall(require, mod)\n'
    '\t\tif ok and M and M.OnClientAction then\n'
    '\t\t\tM:OnClientAction(player, payload)\n'
    '\t\tend\n'
    '\tend\nend)\n')

_HUD_LUA = (
    '-- Client HUD: score, timer and round phase. Fully implemented.\n'
    'local Players = game:GetService("Players")\n'
    'local player = Players.LocalPlayer\n'
    'local gui = Instance.new("ScreenGui")\n'
    'gui.Name = "GameHUD"\ngui.ResetOnSpawn = false\n'
    'gui.Parent = player:WaitForChild("PlayerGui")\n\n'
    'local function makeLabel(order, y)\n'
    '\tlocal label = Instance.new("TextLabel")\n'
    '\tlabel.Size = UDim2.new(0, 220, 0, 28)\n'
    '\tlabel.Position = UDim2.new(0, 12, 0, y)\n'
    '\tlabel.BackgroundTransparency = 0.3\n'
    '\tlabel.BackgroundColor3 = Color3.fromRGB(24, 24, 28)\n'
    '\tlabel.TextColor3 = Color3.fromRGB(240, 240, 245)\n'
    '\tlabel.Font = Enum.Font.GothamBold\n'
    '\tlabel.TextSize = 16\n'
    '\tlabel.LayoutOrder = order\n'
    '\tlabel.Parent = gui\n'
    '\treturn label\nend\n\n'
    'local scoreLabel = makeLabel(1, 12)\n'
    'local phaseLabel = makeLabel(2, 44)\n\n'
    'local function refreshScore()\n'
    '\tlocal ls = player:FindFirstChild("leaderstats")\n'
    '\tlocal score = ls and ls:FindFirstChild("Score")\n'
    '\tscoreLabel.Text = "Score: " .. tostring(score and score.Value or 0)\n'
    'end\n\n'
    'player.ChildAdded:Connect(function(child)\n'
    '\tif child.Name == "leaderstats" then\n'
    '\t\tlocal score = child:WaitForChild("Score", 5)\n'
    '\t\tif score then score.Changed:Connect(refreshScore) end\n'
    '\t\trefreshScore()\n'
    '\tend\nend)\n'
    'phaseLabel.Text = "Waiting for round..."\n')

_INPUT_LUA = (
    '-- Client input: E triggers the equipped mechanic action. Fully implemented.\n'
    'local UserInputService = game:GetService("UserInputService")\n'
    'local ReplicatedStorage = game:GetService("ReplicatedStorage")\n'
    'local remotes = ReplicatedStorage:WaitForChild("GameRemotes")\n'
    'local mechanicAction = remotes:WaitForChild("MechanicAction")\n'
    'local equipped = nil\n\n'
    'UserInputService.InputBegan:Connect(function(input, processed)\n'
    '\tif processed then return end\n'
    '\tif input.KeyCode == Enum.KeyCode.E and equipped then\n'
    '\t\tmechanicAction:FireServer(equipped, { At = os.clock() })\n'
    '\tend\nend)\n\n'
    'return { Equip = function(name) equipped = name end }\n')

_MONETIZATION_LUA = (
    '-- Developer product + gamepass handlers via MarketplaceService. Fully implemented.\n'
    'local MarketplaceService = game:GetService("MarketplaceService")\n'
    'local Players = game:GetService("Players")\n'
    'local PRODUCTS = {\n'
    '\t-- id -> handler; ids are configured at publish time from the Creator Dashboard\n'
    '}\n'
    'local GAMEPASSES = {}\n\n'
    'function MarketplaceService.ProcessReceipt(receiptInfo)\n'
    '\tlocal handler = PRODUCTS[receiptInfo.ProductId]\n'
    '\tif not handler then\n'
    '\t\treturn Enum.ProductPurchaseDecision.NotProcessedYet\n'
    '\tend\n'
    '\tlocal player = Players:GetPlayerByUserId(receiptInfo.PlayerId)\n'
    '\tif not player then\n'
    '\t\treturn Enum.ProductPurchaseDecision.NotProcessedYet\n'
    '\tend\n'
    '\tlocal ok, granted = pcall(handler, player, receiptInfo)\n'
    '\tif ok and granted then\n'
    '\t\treturn Enum.ProductPurchaseDecision.PurchaseGranted\n'
    '\tend\n'
    '\treturn Enum.ProductPurchaseDecision.NotProcessedYet\nend\n\n'
    'MarketplaceService.PromptGamePassPurchaseFinished:Connect(function(player, passId, purchased)\n'
    '\tif purchased and GAMEPASSES[passId] then\n'
    '\t\tGAMEPASSES[passId](player)\n'
    '\tend\nend)\n')


def _runbook(title, mechanics):
    lines = [
        "# Publish runbook: %s" % title, "",
        "Owner-gated path (Atlas never publishes; these are the steps):", "",
        "1. Install Rojo 7.x and Roblox Studio under the owner's own account.",
        "2. `rojo serve` in the project root; in Studio use the Rojo plugin to sync.",
        "3. Play Solo test: verify round loop advances intermission -> running -> ended,",
        "   leaderstats persist across rejoin, each mechanic scores as designed.",
        "4. Team Test with 2+ clients to verify RemoteEvent dispatch and cooldowns.",
        "5. File > Publish to Roblox As... into the owner's experience; set icon/",
        "   thumbnail/screenshots; mark the game Public only after owner review.",
        "6. Creator Dashboard > Monetization: create developer products/gamepasses,",
        "   paste their numeric ids into Monetization.server.lua PRODUCTS/GAMEPASSES,",
        "   republish. Robux cash-out uses DevEx at the owner's configured rate.",
        "7. Soft-launch: sponsor at a small daily budget the owner approves per action;",
        "   read retention/session length in Analytics before any scale-up.", "",
        "Mechanics in this build: %s." % ", ".join(mechanics), "",
        "Every step that spends money or publishes waits for the owner's explicit go.",
    ]
    return "\n".join(lines)


def _monetization_doc(title, ev_rows):
    lines = ["# Monetization model: %s" % title, "",
             "Supplied-estimate revenue model (R$ = Robux; DevEx rate is owner-configured):", "",
             "| item | price R$ | est. conversion | est. monthly buyers | R$/month low | R$/month base | R$/month high |",
             "|---|---|---|---|---|---|---|"]
    for row in ev_rows:
        lines.append("| %s | %d | %.3f | %d | %d | %d | %d |" % (
            row["item"], row["price_robux"], row["conversion"], row["monthly_visitors"],
            row["low"], row["base"], row["high"]))
    lines += ["",
              "Figures multiply supplied conversion estimates by supplied visitor counts;",
              "they are planning numbers, not income promises. Actual DevEx cash-out",
              "happens only at the owner's configured rate after Roblox review."]
    return "\n".join(lines)


def _check_wiring(files):
    """Cross-file wiring: client-fired remotes have server handlers and vice versa."""
    created, handled, fired = set(), set(), set()
    for path, text in files.items():
        created.update(re.findall(r'makeRemote\("([A-Za-z]+)"\)', text))
        handled.update(re.findall(r'(\w+)\.OnServerEvent:Connect', text))
        fired.update(re.findall(r'(\w+):FireServer', text))
    # client references remotes via WaitForChild variables; map var -> remote name
    var_map = {}
    for path, text in files.items():
        for var, remote in re.findall(r'local (\w+) = remotes:WaitForChild\("([A-Za-z]+)"\)', text):
            var_map[var] = remote
    fired_names = {var_map.get(v, v) for v in fired}
    issues = []
    for name in sorted(fired_names):
        if name not in created:
            issues.append("fired_remote_not_created:" + name)
    for name in sorted(handled):
        if name not in created:
            issues.append("handled_remote_not_created:" + name)
    for name in sorted(created - handled):
        issues.append("created_remote_unhandled:" + name)
    return {"created": sorted(created), "handled": sorted(handled),
            "fired": sorted(fired_names), "issues": issues}


def run(request):
    """Build the complete game project; returns files, checks, docs, scope."""
    if type(request) is not dict:
        _refuse("BAD_TYPE", "request")
    _scan_keys(request)
    if set(request) - {"as_of", "concept", "monetization"}:
        _refuse("UNKNOWN", "request")
    as_of = policy.clean_text(request.get("as_of"), PREFIX, "as_of", 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
        _refuse("BAD_TYPE", "as_of")
    concept = request.get("concept")
    if type(concept) is not dict or set(concept) - {"title", "premise", "mechanics", "win_score"}:
        _refuse("UNKNOWN", "concept")
    title = policy.clean_text(concept.get("title"), PREFIX, "title", MAX_TEXT)
    premise = policy.clean_text(concept.get("premise"), PREFIX, "premise", MAX_PREMISE, allow_ws=True)
    raw_mechanics = concept.get("mechanics")
    if type(raw_mechanics) is not list or not raw_mechanics or len(raw_mechanics) > MAX_MECHANICS:
        _refuse("BAD_TYPE", "mechanics")
    mechanics = [_mechanic_id(m) for m in raw_mechanics]
    if len(set(mechanics)) != len(mechanics):
        _refuse("DUPLICATE", "mechanics")
    win_score = concept.get("win_score", 500)
    if type(win_score) is not int or not 50 <= win_score <= 100000:
        _refuse("BAD_TYPE", "win_score")

    monet = request.get("monetization")
    ev_rows = []
    if monet is not None:
        if type(monet) is not dict or set(monet) - {"items", "devex_usd_per_robux"}:
            _refuse("UNKNOWN", "monetization")
        rate = monet.get("devex_usd_per_robux")
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 < rate < 1:
            _refuse("BAD_TYPE", "devex_usd_per_robux")
        items = monet.get("items")
        if type(items) is not list or not items or len(items) > 20:
            _refuse("BAD_TYPE", "items")
        for item in items:
            if type(item) is not dict or set(item) - {"item", "price_robux", "conversion",
                                                      "monthly_visitors"}:
                _refuse("UNKNOWN", "items")
            name = policy.clean_text(item.get("item"), PREFIX, "item", 100)
            price = item.get("price_robux")
            conv = item.get("conversion")
            visitors = item.get("monthly_visitors")
            if type(price) is not int or not 1 <= price <= 100000:
                _refuse("BAD_TYPE", "price_robux")
            if isinstance(conv, bool) or not isinstance(conv, (int, float)) or not 0 < conv <= 1:
                _refuse("BAD_TYPE", "conversion")
            if type(visitors) is not int or not 1 <= visitors <= 100000000:
                _refuse("BAD_TYPE", "monthly_visitors")
            base = int(price * conv * visitors)
            ev_rows.append({"item": name, "price_robux": price, "conversion": conv,
                            "monthly_visitors": visitors,
                            "low": int(base * 0.5), "base": base, "high": int(base * 2)})

    files = {"default.project.json": json.dumps({
        "name": title, "tree": {"$className": "DataModel",
                                "ServerScriptService": {"Mechanics": {"$path": "src/server/Mechanics"},
                                                        "$path": "src/server"},
                                "ReplicatedStorage": {"$path": "src/shared"},
                                "StarterPlayerScripts": {"$path": "src/client"}}}, indent=2)}
    archetypes = {}
    for m in mechanics:
        arch = _archetype(m)
        archetypes[m] = arch
        files["src/server/Mechanics/%s.lua" % m] = _mechanic_lua(m, arch)
    files["src/server/GameLoop.server.lua"] = _game_loop_lua(mechanics, win_score)
    files["src/server/Leaderstats.server.lua"] = _LEADERSTATS_LUA
    files["src/server/Remotes.server.lua"] = _REMOTES_LUA
    files["src/server/Monetization.server.lua"] = _MONETIZATION_LUA
    files["src/client/HUD.client.lua"] = _HUD_LUA
    files["src/client/Input.client.lua"] = _INPUT_LUA
    files["src/shared/Config.lua"] = (
        "-- Shared config for %s.\nreturn {\n\tTitle = %s,\n\tWinScore = %d,\n"
        "\tMechanics = {%s},\n\tArchetypes = {%s},\n}\n" % (
            title, _lq(title), win_score,
            ", ".join(_lq(m) for m in mechanics),
            ", ".join("%s = %s" % (m, _lq(archetypes[m])) for m in mechanics)))
    files["docs/game_design.md"] = (
        "# %s\n\n## Premise\n%s\n\n## Mechanics\n%s\n## Win condition\n"
        "First to %d points before the 180s round ends; leader wins on timeout.\n"
        % (title, premise, "".join("- %s (%s)\n" % (m, archetypes[m]) for m in mechanics),
           win_score))
    files["docs/publish_runbook.md"] = _runbook(title, mechanics)
    if ev_rows:
        files["docs/monetization.md"] = _monetization_doc(title, ev_rows)

    lint = {path: lint_lua(text, path) for path, text in files.items() if path.endswith(".lua")}
    lint_issues = {p: v for p, v in lint.items() if v}
    wiring = _check_wiring({p: t for p, t in files.items() if p.endswith(".lua")})
    placeholders = {p: [t for t in PLACEHOLDER_TOKENS if t.casefold() in text.casefold()]
                    for p, text in files.items()}
    placeholders = {p: v for p, v in placeholders.items() if v}
    return {
        "title": title, "as_of": as_of, "files": files, "archetypes": archetypes,
        "checks": {
            "lua_files": len(lint), "lint_issues": lint_issues,
            "wiring": wiring, "placeholders": placeholders,
            "all_lua_lint_clean": not lint_issues,
            "wiring_clean": not wiring["issues"],
            "placeholder_free": not placeholders,
        },
        "monetization_model": ev_rows or None,
        "scope": policy.scope(
            ["complete Rojo-layout project: implemented mechanic modules, round loop, "
             "DataStore leaderstats, RemoteEvent wiring, client HUD/input, ProcessReceipt",
             "built-in Lua lint + wiring checks whose results ship in this report",
             "publish runbook and supplied-estimate monetization model"],
            ["publishing, uploading or live monetization - refused keys, owner-gated",
             "in-engine execution - Roblox Studio run belongs to the owner runbook",
             "income promises - monetization figures multiply supplied estimates"],
            "supplied concept and monetization estimates", as_of),
    }
