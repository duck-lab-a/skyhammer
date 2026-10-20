-- Skyhammer Air Support - the B-2's tactical nuke: its damage zones (napalm_nuke_plan)
-- Shared by the client (Skyhammer_Nuke, single player) and the server (Skyhammer_Server, online),
-- so both judge the infected the same way. Distances in tiles from ground zero, on every floor.
--   fireball  the infected are vaporized (no body); a player dies
--   blast     the infected are killed; a player dies
--   edge      the infected are killed (EdgeChance, all of them since 2026-10-17); a player loses
--             60 health
--   noise     the infected are drawn in by the noise
--   danger    the nearest the player may mark it; countdownMs from the release to the blast

SkyhammerNukeZones = SkyhammerNukeZones or {}
local Z = SkyhammerNukeZones

-- (danger: 2026-10-17, the user found 120 too tight; 60 keeps the player just out of the fireball.
-- With "protect the player" off the mark must be past the edge instead: Skyhammer_Nuke MinDistance)
Z.ZONE = { fireball = 50, blast = 90, edge = 140, noise = 300, danger = 60, countdownMs = 15000 }

-- "vaporize", "kill", "edge", or nil beyond the edge
function Z.Band(d)
    if d <= Z.ZONE.fireball then return "vaporize" end
    if d <= Z.ZONE.blast then return "kill" end
    if d <= Z.ZONE.edge then return "edge" end
    return nil
end

-- the chance (percent) the edge kills: all of them. (2026-10-17, the user: some of the infected
-- inside the ring drawn on the map lived; it was 90 falling to 30, the rest knocked down)
function Z.EdgeChance(d)
    return 100
end
