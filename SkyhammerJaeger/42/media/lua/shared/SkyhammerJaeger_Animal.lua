-- Skyhammer ODIN - the robot's game model, registered as an "animal" type
-- The plain isometric view draws 3D models only for characters, vehicles and animals, so ODIN
-- borrows the animal kind, as the main mod's Apache does. SkyhammerJaeger_Body.lua spawns,
-- moves and removes it; nothing else ever makes one. Every animal habit is switched off.

SKYHAMMER_ODIN_ANIMAL = "skyhammerOdin"
SKYHAMMER_ODIN_BREED = "odin"

AnimalDefinitions = AnimalDefinitions or {}
AnimalDefinitions.stages = AnimalDefinitions.stages or {}
AnimalDefinitions.breeds = AnimalDefinitions.breeds or {}
AnimalDefinitions.genome = AnimalDefinitions.genome or {}
AnimalDefinitions.animals = AnimalDefinitions.animals or {}

local TYPE, BREED = SKYHAMMER_ODIN_ANIMAL, SKYHAMMER_ODIN_BREED
local MODEL = "SkyhammerJaeger.SH_Jaeger"
local TEXTURE = "SkyhammerJaeger/SH_Jaeger"   -- media/textures/Body/SkyhammerJaeger/SH_Jaeger.png

AnimalDefinitions.stages[TYPE] = { stages = { [TYPE] = { ageToGrow = 999999 } } }
AnimalDefinitions.breeds[TYPE] = {
    breeds = {
        [BREED] = { name = BREED, texture = TEXTURE, textureMale = TEXTURE, rottenTexture = TEXTURE },
    },
}
AnimalDefinitions.genome[TYPE] = {
    genes = {
        maxSize = "maxSize", maxWeight = "maxWeight", lifeExpectancy = "lifeExpectancy",
        strength = "strength", stress = "stress",
    },
}
AnimalDefinitions.animals[TYPE] = {
    bodyModel = MODEL,
    bodyModelSkel = MODEL,
    modelscript = MODEL,
    textureSkeleton = TEXTURE,
    textureSkeletonBloody = TEXTURE,
    animset = "pig",
    shadoww = 0, shadowfm = 0, shadowbm = 0,
    turnDelta = 1.0,
    animalSize = 0.05,
    minSize = 1, maxSize = 1,
    stages = AnimalDefinitions.stages[TYPE].stages,
    breeds = AnimalDefinitions.breeds[TYPE].breeds,
    genes = AnimalDefinitions.genome[TYPE].genes,
    group = TYPE,
    alwaysFleeHumans = false,
    fleeZombies = false,
    canBeAlerted = false,
    attackBack = false,
    attackIfStressed = false,
    canClimbFences = false,
    idleEmoteChance = 0,
    wild = false,
    canBeAttached = false,
    canBePet = false,
    canBePicked = false,
    canThump = false,
    sitRandomly = false,
    wanderMul = 100000,
    idleTypeNbr = 1,
    hungerMultiplier = 0,
    thirstMultiplier = 0,
    healthLossMultiplier = 0,
    dungChancePerDay = 0,
    stressAboveGround = false,
    stressUnderRain = false,
    collisionSize = 0.15,
    collidable = false,
    minWeight = 5, maxWeight = 5,
    minBlood = 0, maxBlood = 0,
    luredPossibleItems = {},
}
