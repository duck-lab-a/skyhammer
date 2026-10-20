-- Skyhammer ODIN - its own Mod Options page: the sortie's times, the cannon's recharge, how many
-- orbital laser strikes and full power shots a sortie, the robot's size, walking speed and
-- distance from the player, the cockpit scene and a quieter pilot.
-- (The time labels are the main mod's, as the Wraith add-on's are.)

local OPTIONS = {
    { "odinInboundSec", "IGUI_SH_OptInbound", 10, 120, 1,    25 },
    { "odinStationMin", "IGUI_SH_OptStation", 1,  15,  0.5,  5 },
    { "odinRearmMin",   "IGUI_SH_OptRearm",   0,  180, 1,    30 },
    { "odinCannonSec",  "IGUI_SJ_OptCannon",  10, 120, 5,    30 },
    { "odinOrbitUses",  "IGUI_SJ_OptOrbitUses", 0, 5, 1,     1 },
    { "odinFinalUses",  "IGUI_SJ_OptFinalUses", 0, 5, 1,     1 },
    { "odinSize",       "IGUI_SJ_OptSize",    0.1, 2,  0.05, 1 },
    { "odinWalkSpeed",  "IGUI_SJ_OptWalkSpeed", 0.5, 2, 0.1, 1 },
    { "odinFollowDist", "IGUI_SJ_OptFollowDist", 6, 30, 1,   12 },
}
-- on / off options: id, label key, default
local TICKS = {
    { "odinCockpit", "IGUI_SJ_OptCockpit", true },
    { "odinQuiet",   "IGUI_SJ_OptQuiet",   false },
}
local page, defaults = nil, {}
for _, o in ipairs(OPTIONS) do defaults[o[1]] = o[6] end
for _, o in ipairs(TICKS) do defaults[o[1]] = o[3] end
pcall(function()
    if not (PZAPI and PZAPI.ModOptions) then return end
    page = PZAPI.ModOptions:create("SkyhammerOdin", getText("IGUI_SJ_OptTitle"))
    page:addTitle(getText("IGUI_SJ_OptSection"))
    for _, o in ipairs(OPTIONS) do
        page:addSlider(o[1], getText(o[2]), o[3], o[4], o[5], o[6], getText(o[2] .. "_tt"))
    end
    for _, o in ipairs(TICKS) do
        page:addTickBox(o[1], getText(o[2]), o[3], getText(o[2] .. "_tt"))
    end
end)

function SkyhammerOdinOpt(id)
    if page then
        local ok, v = pcall(function() return page:getOption(id):getValue() end)
        if ok and type(v) == "boolean" then return v end
        if ok and tonumber(v) then return tonumber(v) end
    end
    return defaults[id]
end
