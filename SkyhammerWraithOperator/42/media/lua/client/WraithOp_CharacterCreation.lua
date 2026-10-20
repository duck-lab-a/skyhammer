-- Character creation: for the Wraith operator, drop the hat, glasses, tank top and T-shirt rows
-- that the vanilla default clothing list adds to every occupation (and don't dress the avatar in them).
require "OptionScreens/CharacterCreationMain"

local HIDE = { Hat = true, Eyes = true, TankTop = true, Tshirt = true }
-- the Wraith Team add-on's suit: worn from the start when that add-on is on (it is a coverall,
-- so the camo trousers stay in the list but are not put on with it)
local SUIT = "WraithGear.TacticalSuit"

local function isWraith()
    local desc = MainScreen.instance and MainScreen.instance.desc
    local prof = desc and desc:getCharacterProfession()
    return prof ~= nil and prof:getName() == "wraithoperator"
end

local function trim(def)
    local default = ClothingSelectionDefinitions.default
    if not default or (def ~= default.Female and def ~= default.Male) or not isWraith() then return def end
    local out = {}
    for loc, entry in pairs(def) do
        if not HIDE[loc] then out[loc] = entry end
    end
    return out
end

local function withSuit(def, dressing)
    local mine = ClothingSelectionDefinitions.wraithoperator
    if not mine or (def ~= mine.Female and def ~= mine.Male) then return def end
    if not ScriptManager.instance:FindItem(SUIT) then return def end
    local out = {}
    for loc, entry in pairs(def) do
        if not (dressing and loc == "Pants") then out[loc] = entry end
    end
    out.Boilersuit = { items = { SUIT } }
    return out
end

for _, name in ipairs({ "doClothingCombo", "dressWithDefinitions" }) do
    local base = CharacterCreationMain[name]
    local dressing = name == "dressWithDefinitions"
    CharacterCreationMain[name] = function(self, def, ...)
        return base(self, withSuit(trim(def), dressing), ...)
    end
end
