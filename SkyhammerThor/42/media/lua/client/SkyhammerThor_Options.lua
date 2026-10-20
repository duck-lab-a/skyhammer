-- Skyhammer THOR - its own Mod Options page: the sortie's times, how many rods a strike window
-- holds, the kill radius, the strike scene, whether it reaches indoors, the impact's noise and
-- fires.
-- (The time labels are the main mod's, as the other add-ons' are.)

local OPTIONS = {
    { "thorInboundSec", "IGUI_SH_OptInbound", 10, 300, 5,   25 },
    { "thorStationMin", "IGUI_SH_OptStation", 1,  15,  0.5, 3 },
    { "thorRearmMin",   "IGUI_SH_OptRearm",   0,  240, 5,   90 },
    { "thorRods",       "IGUI_ST_OptRods",    1,  3,   1,   1 },
    { "thorRadius",     "IGUI_ST_OptRadius",  25, 150, 5,   90 },
    { "thorReach",      "IGUI_ST_OptReach",   60, 300, 10,  150 },
    { "thorNoise",      "IGUI_ST_OptNoise",   0,  300, 10,  150 },
    { "thorFlattenRadius", "IGUI_ST_OptFlattenRadius", 10, 100, 5, 50 },
    { "thorShake",      "IGUI_ST_OptShake",   0,  2,   0.1, 1 },
}
-- on / off options: id, label key, default
local TICKS = {
    { "thorCinematic", "IGUI_ST_OptCinematic", true },
    { "thorIndoor", "IGUI_ST_OptIndoor", true },
    { "thorFire",   "IGUI_ST_OptFire",   false },
}
local page, defaults = nil, {}
for _, o in ipairs(OPTIONS) do defaults[o[1]] = o[6] end
for _, o in ipairs(TICKS) do defaults[o[1]] = o[3] end
pcall(function()
    if not (PZAPI and PZAPI.ModOptions) then return end
    page = PZAPI.ModOptions:create("SkyhammerThor", getText("IGUI_ST_OptTitle"))
    page:addTitle(getText("IGUI_ST_OptSection"))
    for _, o in ipairs(OPTIONS) do
        page:addSlider(o[1], getText(o[2]), o[3], o[4], o[5], o[6], getText(o[2] .. "_tt"))
    end
    for _, o in ipairs(TICKS) do
        page:addTickBox(o[1], getText(o[2]), o[3], getText(o[2] .. "_tt"))
    end
end)

function SkyhammerThorOpt(id)
    if page then
        local ok, v = pcall(function() return page:getOption(id):getValue() end)
        if ok and type(v) == "boolean" then return v end
        if ok and tonumber(v) then return tonumber(v) end
    end
    return defaults[id]
end
