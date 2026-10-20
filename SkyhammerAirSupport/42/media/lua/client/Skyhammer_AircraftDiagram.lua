-- Original vector schematics for the terminal. UI only: no world model or combat state.
-- A support with a picture (Skyhammer_TerminalArt) shows that instead.
require "Skyhammer_TerminalArt"
SkyhammerAircraftDiagram = SkyhammerAircraftDiagram or {}
local D = SkyhammerAircraftDiagram

-- Coordinates in a 100 x 40 drawing area. AC-130 port elevation / B-2 plan view.
local AC130 = {
    { 3,27, 6,24, 10,23, 14,19, 24,18, 38,18, 61,20, 77,19, 83,15,
      86,3, 90,3, 90,21, 97,24, 91,26, 79,27, 67,30, 22,30, 8,29, 3,27 },
    { 13,23, 16,20, 23,20, 23,24, 13,24, 13,23 },
    { 18,20, 18,24 }, { 24,19, 28,23, 28,29 },
    { 32,19, 44,15, 53,15, 65,22, 47,23, 32,19 },
    { 41,20, 47,32, 54,32, 53,24 },
    { 76,23, 91,20, 98,21, 85,26, 76,23 },
    { 82,17, 88,7, 88,21 }, { 7,27, 69,27, 78,24 },
    { 33,25, 37,25, 37,28, 33,28, 33,25 },
    { 58,23, 62,23, 62,27, 58,27, 58,23 },
    { 44,16, 49,16, 49,20, 44,20, 44,16 },
    { 46,12, 46,24 }, { 44,14, 48,22 },
    { 53,19, 59,19, 59,23, 53,23, 53,19 },
    { 55,14, 55,27 }, { 53,16, 57,25 },
    { 37,27, 32,31 }, { 35,26, 30,29 },
    { 12,31, 17,31 }, { 66,31, 72,31 },
}
local B2 = {
    { 50,4, 97,28, 83,29, 78,25, 72,30, 65,27, 59,34, 50,30,
      41,34, 35,27, 28,30, 22,25, 17,29, 3,28, 50,4 },
    { 50,4, 50,30 }, { 50,8, 40,21, 41,34 }, { 50,8, 60,21, 59,34 },
    { 3,28, 40,21, 50,25, 60,21, 97,28 },
    { 21,23, 33,24, 28,30 }, { 79,23, 67,24, 72,30 },
    { 45,12, 48,10, 52,10, 55,12, 52,15, 48,15, 45,12 },
    { 40,20, 43,18, 43,25, 40,25, 40,20 },
    { 60,20, 57,18, 57,25, 60,25, 60,20 },
    { 33,16, 35,27 }, { 67,16, 65,27 },
}
-- AH-64 port elevation: tandem canopy, mast and blades, stub wing with a rocket pod, chin gun
local APACHE = {
    { 6,24, 10,20, 18,18, 24,14, 34,13, 42,15, 58,15, 60,20, 88,21, 92,16, 95,16, 94,23, 60,26, 46,28, 20,28, 10,27, 6,24 },
    { 14,19, 20,15, 30,14, 34,18, 14,19 }, { 24,14, 24,18 },
    { 46,15, 46,10 }, { 12,9, 80,10 }, { 42,9, 50,9 },
    { 93,10, 95,22 }, { 90,15, 98,17 },
    { 40,22, 56,22 }, { 42,23, 54,23, 54,26, 42,26, 42,23 },
    { 16,28, 18,31, 25,31 },
    { 22,28, 22,33 }, { 19,33, 25,33 }, { 52,27, 52,32 }, { 49,32, 55,32 }, { 85,22, 86,26 },
}
D.shapes = { ac130 = AC130, b2 = B2, apache = APACHE }
-- an add-on's aircraft: a list of polylines in the same 100 x 40 area
function D.Register(kind, lines) D.shapes[kind] = lines end

function D.draw(panel, kind, x, y, w, h, color, alpha)
    if SkyhammerTerminalArt.Draw(panel, kind, x, y, w, h, alpha) then return end
    local lines = D.shapes[kind] or AC130
    local scale = math.min(w / 100, h / 40)
    local ox, oy = x + (w - scale * 100) / 2, y + (h - scale * 40) / 2
    local a = alpha or 1
    -- Registration ticks stay subtle; the aircraft outline remains readable at small sizes.
    panel:drawRect(x, y + h - 2, w, 1, 0.14, color[1], color[2], color[3])
    for _, points in ipairs(lines) do
        for i = 1, #points - 2, 2 do
            panel:drawLine(nil, ox + points[i] * scale, oy + points[i + 1] * scale,
                ox + points[i + 2] * scale, oy + points[i + 3] * scale,
                1, a, color[1], color[2], color[3])
        end
    end
end
