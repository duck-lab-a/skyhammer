-- Skyhammer Air Support - the terminal's aircraft pictures (transparent PNGs in media/ui)
-- SkyhammerAircraftDiagram.draw asks this first; a support without a picture (or a picture
-- that does not load) keeps its line schematic. Add-ons add theirs with Register.
SkyhammerTerminalArt = SkyhammerTerminalArt or {}
local A = SkyhammerTerminalArt
local paths = {
    ac130 = "media/ui/SH_Art_AC130.png",
    apache = "media/ui/SH_Art_Apache.png",
    b2 = "media/ui/SH_Art_B2.png",
}
local cached = {}

-- a support key -> its picture (the add-on's ground team uses media/ui/SH_Art_Team.png)
function A.Register(key, path)
    if type(key) ~= "string" or key == "" or type(path) ~= "string" then return end
    paths[key] = path
    cached[key] = nil
end
function A.RegisterTeam(key) A.Register(key, "media/ui/SH_Art_Team.png") end

-- Draws the picture of `kind` fitted inside (x, y, w, h), keeping its proportions.
-- Returns false when there is none, so the caller draws the schematic instead.
function A.Draw(panel, kind, x, y, w, h, alpha)
    local path = paths[kind]
    if not path or w <= 0 or h <= 0 then return false end
    local texture = cached[kind]
    if texture == nil then
        texture = getTexture(path)
        cached[kind] = texture or false
    end
    if not texture then return false end
    local iw, ih = texture:getWidth(), texture:getHeight()
    if iw <= 0 or ih <= 0 then return false end
    local scale = math.min(w / iw, h / ih)
    local dw, dh = math.floor(iw * scale), math.floor(ih * scale)
    -- already coloured: a white tint keeps it as painted
    panel:drawTextureScaled(texture, x + math.floor((w - dw) / 2), y + math.floor((h - dh) / 2),
        dw, dh, math.max(0, math.min(1, alpha or 1)), 1, 1, 1)
    return true
end
