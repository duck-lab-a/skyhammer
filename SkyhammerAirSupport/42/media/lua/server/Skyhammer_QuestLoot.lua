-- Skyhammer Air Support - where Haven's signal manual turns up (the unlock quest)
-- Military sites only, rarest outside the electronics stores. Added to the game's own loot
-- lists before they are merged.

require "Items/ProceduralDistributions"

local MANUAL = "Skyhammer.HavenSignalManual"
local LISTS = {
    ArmyStorageElectronics = 4,
    ArmyBunkerStorage = 2,
    ArmyBunkerLockers = 1,
    LockerArmyBedroom = 0.5,
    ArmyStorageOutfit = 0.5,
}

local function addManual()
    local lists = ProceduralDistributions and ProceduralDistributions.list
    if not lists then return end
    for name, weight in pairs(LISTS) do
        local list = lists[name]
        if list and list.items then
            table.insert(list.items, MANUAL)
            table.insert(list.items, weight)
        end
    end
end
Events.OnPreDistributionMerge.Add(addManual)
