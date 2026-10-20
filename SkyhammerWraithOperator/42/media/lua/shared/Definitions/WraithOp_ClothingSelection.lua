-- Starting clothes for the Wraith operator. Keys are body locations; the profession's name is the id without its namespace.
-- Camo comes in three patterns (woodland, desert, urban) for both shirt and trousers.
local kit = {
    Mask = { items = { "Base.Hat_BalaclavaFull" } },
    Shirt = { items = { "Base.Shirt_CamoGreen", "Base.Shirt_CamoDesert", "Base.Shirt_CamoUrban" } },
    Pants = { items = { "Base.Trousers_CamoGreen", "Base.Trousers_CamoDesert", "Base.Trousers_CamoUrban" } },
    Shoes = { items = { "Base.Shoes_ArmyBoots" } },
    Hands = { items = { "Base.Gloves_LeatherGlovesBlack" } },
    Necklace = { items = { "Base.Necklace_DogTag" } },
    LeftWrist = { items = { "Base.WristWatch_Left_ClassicMilitary" } },
}

ClothingSelectionDefinitions = ClothingSelectionDefinitions or {}
ClothingSelectionDefinitions.wraithoperator = { Female = kit, Male = kit }
