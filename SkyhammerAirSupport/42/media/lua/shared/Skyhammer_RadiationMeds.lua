-- Skyhammer Air Support - the medicine against the fallout (radiation; 2026-10-20, with Codex:
-- source/CODEX_RADIATION_REPLY_2026-10-20.md)
-- The Prussian Blue capsules (Skyhammer.PrussianBlue, scripts/Skyhammer_Radiation.txt): the game
-- calls the item's OnEat, SkyhammerRad_TakeBlue, when a capsule is swallowed. It runs where the
-- pill action completes and where the player's dose is kept: alone in single player, on the
-- server online (Skyhammer_RadiationServer); a client online leaves it to the server, so one dose
-- never counts twice. What it does is RadiationBody.meds. (Food is not medicine here: lemongrass
-- and the like do nothing for radiation.)

require "Skyhammer_Radiation"
require "Skyhammer_RadiationBody"

local RAD = SkyhammerRadiation

-- the item's OnEat (called by the game with the item and who took it)
function SkyhammerRad_TakeBlue(item, character)
    if isClient() or not character or not instanceof(character, "IsoPlayer") then return end
    RAD.body.meds(character, "radblue")
end
