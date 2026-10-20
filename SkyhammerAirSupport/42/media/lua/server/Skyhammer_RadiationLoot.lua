-- Skyhammer Air Support - where the Prussian Blue capsules turn up (radiation)
-- Pharmacies, clinics, hospitals and military medical stores, about a fifth as often as the
-- game's beta blockers there (2026-10-20: twice the first weights, now that it is the only
-- medicine against the fallout). None with the sandbox's radiation off. Added to the game's own
-- loot lists before they are merged.

require "Items/ProceduralDistributions"
require "Skyhammer_Radiation"

local BLUE = "Skyhammer.PrussianBlue"
local LISTS = {
    MedicalStorageDrugs = 2,
    MedicalClinicDrugs = 1,
    HospitalRoomShelves = 1,
    TestingLab = 2,
    ArmyStorageMedical = 4,
    ArmyBunkerMedical = 4,
}

local function addBlue()
    if SkyhammerRadiation and not SkyhammerRadiation.Enabled() then return end
    local lists = ProceduralDistributions and ProceduralDistributions.list
    if not lists then return end
    for name, weight in pairs(LISTS) do
        local list = lists[name]
        if list and list.items then
            table.insert(list.items, BLUE)
            table.insert(list.items, weight)
        end
    end
end
Events.OnPreDistributionMerge.Add(addBlue)
