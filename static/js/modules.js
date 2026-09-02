/** Hand-crafted dungeon modules. */

const DUNGEON_MODULES = {
  crooked_tower: {
    name: "The Crooked Tower",
    level: 1,
    campaign_id: "ashen_hollow",
    chapter: 1,
    map_pos: { x: 20, y: 75 },
    requires: [],
    tutorial: true,
    tutorial_steps: [
      { id: "welcome", text: "Welcome to Sanctuary. Click highlighted tiles to move.", once: true },
      { id: "room", text: "Each room has a description in the Adventure Log. Explore carefully.", once: true },
      { id: "door", text: "Doors block movement until opened. Click an adjacent door to open it.", once: true },
      { id: "monster", text: "Monsters are red tokens. Click an adjacent monster to attack.", once: true },
      { id: "attack", text: "Each character can attack once per round. End your turn when done.", once: true },
      { id: "rest", text: "Use the Rest button to recover HP when the area is safe.", once: true },
      { id: "chest", text: "Click chests to loot them.", once: true },
      { id: "trap", text: "Traps are hidden. Thieves can search adjacent tiles for traps.", once: true },
      { id: "boss", text: "Bosses are tougher and may have better morale. Use potions and spells wisely.", once: true },
      { id: "exit", text: "Reach the beacon to escape the dungeon.", once: true },
    ],
    unlocks: "sunken_crypt",
    blurb: "Lord Huet's fallen keep. Something gnaws in the cellars beneath.",
    story: "Lord Huet was a feared warrior who drove the valley's goblin tribes into the hills. After his death the keep was abandoned, and now travelers report torchlight in the tower windows and missing livestock. The local reeve offers a modest purse for anyone who clears out whatever has taken root below.",
    objective: "Explore the cellars beneath the Crooked Tower, defeat the creatures lairing there, and reach the beacon that marks the old escape tunnel.",
    story_objective: "Recover the Black Sun amulet from Grik the Goblin Chieftain.",
    story_reward: "Black Sun Amulet — a jet disc carved with a sun that shines darkness. Grik did not find it; he was sent to retrieve it.",
    intro: "You descend a crumbling stair into damp torchlight. Somewhere ahead, something scrapes stone against stone.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Entrance Hall" },
      { id: "antechamber",x: 8, y: 10, w: 5, h: 5, label: "Antechamber" },
      { id: "storage",    x: 16, y: 10, w: 5, h: 4, label: "Storage Room" },
      { id: "crossing",   x: 8, y: 6,  w: 6, h: 3, label: "Crossing" },
      { id: "westhall",   x: 2, y: 5,  w: 5, h: 3, label: "West Hall" },
      { id: "shrine",     x: 16, y: 5,  w: 5, h: 5, label: "Shrine" },
      { id: "throne",     x: 2, y: 1,  w: 7, h: 4, label: "Throne Room" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Exit Chamber" },
    ],
    room_descriptions: {
      entrance: "The entrance hall stinks of mildew and old blood. Rusted sconces still hold guttering torches.",
      antechamber: "A cramped antechamber where sentries once warmed themselves. Now kobold paw-prints streak the dust.",
      storage: "Cracked casks and rotted sacks line the walls. Something has gnawed through the grain barrels.",
      crossing: "A low crossing where three passages meet. The floor is unnaturally smooth, worn by recent traffic.",
      westhall: "A narrow hall leading toward the old throne room. Trip-wires glint in the torchlight.",
      shrine: "A forgotten shrine to a nameless god. Its altar has been desecrated and used as a larder.",
      throne: "Lord Huet's throne room. A hunched figure in rusted mail sits on the dais, gnawing a bone.",
      exit: "The old escape tunnel ends at a brass beacon, cold and dim. Beyond it lies the surface."
    },
    corridors: [
      ["entrance", "antechamber"],
      ["antechamber", "storage"],
      ["antechamber", "crossing"],
      ["crossing", "shrine"],
      ["crossing", "westhall"],
      ["westhall", "throne"],
      ["shrine", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "antechamber", type: "Kobold" },
      { room: "storage",     type: "Giant Rat" },
      { room: "shrine",      type: "Skeleton" },
      { room: "exit",        type: "Orc" },
      { room: "throne",      type: "Goblin", boss: true, name: "Grik the Goblin Chieftain" },
    ],
    chests: ["storage", "shrine"],
    traps: [{ room: "westhall", type: "pit" }],
    secret_doors: ["westhall"],
  },
  sunken_crypt: {
    name: "The Sunken Crypt",
    level: 1,
    campaign_id: "ashen_hollow",
    chapter: 2,
    map_pos: { x: 40, y: 25 },
    requires: ["crooked_tower"],
    unlocks: "goblin_warren",
    blurb: "A flooded river-tomb where the drowned dead walk again.",
    story: "The old kings of the River Mere were buried in tombs cut into the chalk beneath the watermeadows. After the spring floods a faint green light has been seen down there, and villagers speak of figures dragging themselves through the marsh at night. The churchwarden offers coin for anyone who seals the lower vault.",
    objective: "Descend into the flooded crypts, destroy the walking dead, and reach the seal-stone that bars the lowest vault.",
    story_objective: "Examine the Drowned King's crown and find where the Black Sun sigil leads.",
    story_reward: "Drowned Crown — the king's bronze crown bears the same Black Sun. A waterlogged journal names the Broken Ridge warren as the next signpost.",
    intro: "You wade down a slime-slick stair. The air smells of river mud and old bone. Somewhere ahead, water drips into still water.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Flooded Entry" },
      { id: "catacombs",  x: 8, y: 10, w: 5, h: 5, label: "Catacombs" },
      { id: "cistern",    x: 16, y: 10, w: 5, h: 4, label: "Cistern" },
      { id: "crossing",   x: 8, y: 6,  w: 6, h: 3, label: "Sunken Crossing" },
      { id: "ossuary",    x: 2, y: 5,  w: 5, h: 3, label: "Ossuary" },
      { id: "shrine",     x: 16, y: 5,  w: 5, h: 5, label: "Shrine of Weeds" },
      { id: "tomb",       x: 2, y: 1,  w: 7, h: 4, label: "King's Tomb" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Seal Chamber" },
    ],
    room_descriptions: {
      entrance: "The entry stair is half-flooded. Rusted lanterns still hang from the ceiling, swaying in a draught from below.",
      catacombs: "Narrow alcoves hold stacked bones. Something has pulled many of them loose and scattered them across the floor.",
      cistern: "A cistern of black water fills the southern end of the room. Shapes move beneath the surface.",
      crossing: "Three passages meet in a low vault where the water is ankle-deep and unnaturally cold.",
      ossuary: "A chamber of heaped bones. Fresh mud and water stain the walls, as if something climbed up from below.",
      shrine: "A river-shrine to a forgotten god. Its altar is overgrown with weeds and circled by standing water.",
      tomb: "The royal tomb. A crowned figure in rotted silk stands knee-deep in water, its head lolling to one side.",
      exit: "The seal-stone stands in the centre of the chamber, carved with warnings against disturbing the dead."
    },
    corridors: [
      ["entrance", "catacombs"],
      ["catacombs", "cistern"],
      ["catacombs", "crossing"],
      ["crossing", "shrine"],
      ["crossing", "ossuary"],
      ["ossuary", "tomb"],
      ["shrine", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "catacombs", type: "Giant Rat" },
      { room: "cistern",   type: "Zombie" },
      { room: "ossuary",   type: "Skeleton" },
      { room: "shrine",    type: "Zombie" },
      { room: "tomb",      type: "Ghoul", boss: true, name: "The Drowned King" },
    ],
    chests: ["cistern", "shrine"],
    traps: [{ room: "crossing", type: "poison_needle" }],
    secret_doors: ["ossuary"],
  },
  goblin_warren: {
    name: "The Goblin Warren",
    level: 2,
    campaign_id: "ashen_hollow",
    chapter: 3,
    map_pos: { x: 60, y: 75 },
    requires: ["crooked_tower"],
    unlocks: "forgotten_shrine",
    blurb: "A reeking cave-complex where goblins breed spiders and raid the valley.",
    story: "Shepherds have vanished near the Broken Ridge, and scouts report torchlight in the old warren. The reeve offers a bounty for clearing the tunnels and breaking the goblin chieftain's grip.",
    objective: "Rout the goblin tribe, slay their hobgoblin champion, and seal the warren's back exit.",
    story_objective: "Learn who Krag the Hobgoblin serves and why they want the Black Sun relics.",
    story_reward: "Herald's Brand — Krag carries a bronze token stamped with the Black Sun. He served a 'pale herald' who seeks a relic beneath the Quiet Veil shrine.",
    intro: "The tunnel reeks of smoke and wet fur. Ahead, crude drums echo and something skitters in the dark.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Warren Mouth" },
      { id: "guardpost",  x: 8, y: 10, w: 5, h: 5, label: "Guard Post" },
      { id: "commonroom", x: 16, y: 10, w: 5, h: 4, label: "Common Cave" },
      { id: "pit",        x: 8, y: 6,  w: 6, h: 3, label: "Spider Pit" },
      { id: "storeroom",  x: 2, y: 5,  w: 5, h: 3, label: "Storeroom" },
      { id: "breeding",   x: 16, y: 5,  w: 5, h: 5, label: "Breeding Chamber" },
      { id: "chieftain",  x: 2, y: 1,  w: 7, h: 4, label: "Chieftain's Hall" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Back Tunnel" },
    ],
    room_descriptions: {
      entrance: "The warren mouth is littered with bones and cracked shields. Goblin grafitti covers the walls.",
      guardpost: "A crude guard post where sentries squat among piles of stolen gear.",
      commonroom: "Goblin beds of filthy straw and a smouldering cook-fire. The floor is slick with grease.",
      pit: "A natural pit bridged by rotten planks. Pale shapes crawl along the ceiling.",
      storeroom: "Crates and barrels looted from caravans. Most have been emptied.",
      breeding: "Giant spider egg-sacs hang from the ceiling, gently pulsing.",
      chieftain: "A raised dais of skulls and rusted shields. A hulking hobgoblin waits on a throne of bones.",
      exit: "A narrow back tunnel leads toward the ridge. A heavy stone could seal it forever."
    },
    corridors: [
      ["entrance", "guardpost"],
      ["guardpost", "commonroom"],
      ["guardpost", "pit"],
      ["pit", "breeding"],
      ["pit", "storeroom"],
      ["storeroom", "chieftain"],
      ["breeding", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "guardpost", type: "Kobold" },
      { room: "commonroom", type: "Goblin" },
      { room: "pit", type: "Giant Spider" },
      { room: "breeding", type: "Giant Spider" },
      { room: "chieftain", type: "Hobgoblin", boss: true, name: "Krag the Hobgoblin" },
    ],
    chests: ["storeroom", "breeding"],
    traps: [{ room: "pit", type: "spike" }],
    secret_doors: ["storeroom"],
  },
  forgotten_shrine: {
    name: "The Forgotten Shrine",
    level: 3,
    campaign_id: "ashen_hollow",
    chapter: 4,
    map_pos: { x: 80, y: 50 },
    requires: ["sunken_crypt", "goblin_warren"],
    blurb: "A desecrated temple where dead zealots and tomb-robbers clash in the dark.",
    story: "Pilgrims once left offerings at the Shrine of the Quiet Veil. Now bandits camp in its outer halls and the dead walk the inner sanctum. The church offers indulgences to anyone who reconsecrates the altar.",
    objective: "Drive out the looters, destroy the shrine wight, and relight the altar beacon.",
    story_objective: "Keep the Quiet Veil relic from the pale herald's servants.",
    story_reward: "Veil Shard — a splinter of pale stone from the shrine altar. It hums when the Black Sun amulet is near. The herald has not yet reached the deeper vaults.",
    intro: "Dust and incense hang thick in the air. Somewhere ahead, a dead voice intones prayers in a forgotten tongue.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Porch" },
      { id: "vestibule",  x: 8, y: 10, w: 5, h: 5, label: "Vestibule" },
      { id: "camp",       x: 16, y: 10, w: 5, h: 4, label: "Bandit Camp" },
      { id: "crossing",   x: 8, y: 6,  w: 6, h: 3, label: "Crossing" },
      { id: "crypt",      x: 2, y: 5,  w: 5, h: 3, label: "Crypt" },
      { id: "reliquary",  x: 16, y: 5,  w: 5, h: 5, label: "Reliquary" },
      { id: "sanctuary",  x: 2, y: 1,  w: 7, h: 4, label: "Inner Sanctuary" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Altar Chamber" },
    ],
    room_descriptions: {
      entrance: "The porch is choked with dead leaves and broken offerings.",
      vestibule: "A marble vestibule defaced with bandit graffiti and crude camp-fires.",
      camp: "Bedrolls and looted relics show where the tomb-robbers have made camp.",
      crossing: "Three passages meet beneath a cracked dome. Water drips steadily from above.",
      crypt: "Rows of niches hold mouldering bones. Several have been pried open.",
      reliquary: "Golden vessels and torn tapestries. The most sacred items are already gone.",
      sanctuary: "The inner sanctuary. A withered figure in priestly robes kneels before a cold altar.",
      exit: "The altar chamber. A single brazier stands ready to be relit."
    },
    corridors: [
      ["entrance", "vestibule"],
      ["vestibule", "camp"],
      ["vestibule", "crossing"],
      ["crossing", "reliquary"],
      ["crossing", "crypt"],
      ["crypt", "sanctuary"],
      ["reliquary", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "camp", type: "Bandit" },
      { room: "vestibule", type: "Skeleton" },
      { room: "crypt", type: "Zombie" },
      { room: "reliquary", type: "Bandit" },
      { room: "sanctuary", type: "Wight", boss: true, name: "The Shrine Wight" },
    ],
    chests: ["camp", "reliquary"],
    traps: [{ room: "crossing", type: "spike" }],
    secret_doors: ["crypt"],
  },
  axe_head_wreck: {
    name: "The Wreck of the Axe-Head",
    level: 1,
    campaign_id: "iron_spire",
    chapter: 1,
    map_pos: { x: 25, y: 50 },
    requires: [],
    tutorial: true,
    tutorial_steps: [
      { id: "welcome", text: "Welcome to the Iron Spire. Click highlighted tiles to move.", once: true },
      { id: "room", text: "Each room has a description in the Adventure Log. Explore carefully.", once: true },
      { id: "door", text: "Doors block movement until opened. Click an adjacent door to open it.", once: true },
      { id: "monster", text: "Monsters are red tokens. Click an adjacent monster to attack.", once: true },
      { id: "attack", text: "Each character can attack once per round. End your turn when done.", once: true },
      { id: "rest", text: "Use the Rest button to recover HP when the area is safe.", once: true },
      { id: "chest", text: "Click chests to loot them.", once: true },
      { id: "trap", text: "Traps are hidden. Thieves can search adjacent tiles for traps.", once: true },
      { id: "boss", text: "Bosses are tougher and may have better morale. Use potions and spells wisely.", once: true },
      { id: "exit", text: "Reach the beacon to escape the wreck.", once: true },
    ],
    unlocks: "ash_fall_caves",
    blurb: "A dwarven cog-ship brought down in the Ashfall. Clockwork sentinels still guard its hold.",
    story: "The Axe-Head was a dwarven sky-freighter bound for the Iron Spire with ore and engineers. It crashed in the northern wastes during the Ashfall, and now scavengers and ghost-driven clockwork fight over its wreckage. Salvagers speak of a still-active sentinel in the engine chapel.",
    objective: "Search the crashed cog-ship, disable the clockwork sentinel, and find a safe path into the lava tubes below.",
    story_objective: "Recover the Engine-Sigil from the Clockwork Sentinel.",
    story_reward: "Engine-Sigil — a brass token stamped with the Axe-Head's wheel. It still turns when held near the spire.",
    intro: "You pick your way through black snow and twisted brass. The wreck groans as the wind shifts, and somewhere inside a gear clicks with mechanical patience.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Impact Crater" },
      { id: "cargo",      x: 8, y: 10, w: 5, h: 5, label: "Cargo Hold" },
      { id: "galley",     x: 16, y: 10, w: 5, h: 4, label: "Galley" },
      { id: "crossing",   x: 8, y: 6,  w: 6, h: 3, label: "Broken Passage" },
      { id: "workshop",   x: 2, y: 5,  w: 5, h: 3, label: "Engineer's Workshop" },
      { id: "shrine",     x: 16, y: 5,  w: 5, h: 5, label: "Ancestor Shrine" },
      { id: "chapel",     x: 2, y: 1,  w: 7, h: 4, label: "Engine Chapel" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Hatch to the Depths" },
    ],
    room_descriptions: {
      entrance: "The impact crater is littered with scorched timbers and brass fittings. Ash drifts across the frozen mud.",
      cargo: "The cargo hold stinks of oil and spilled grain. Crates have been pried open by scavenger hands.",
      galley: "A dwarven galley with overturned benches. A cook-fire has burned down to cold ash.",
      crossing: "A collapsed passage where three corridors meet. Wind whistles through gaps in the hull.",
      workshop: "An engineer's workshop. Half-built devices lie scattered among tools scavengers did not recognise.",
      shrine: "A small shrine to dwarven ancestors. The statues are soot-blackened but intact.",
      chapel: "The engine chapel. Gears as tall as a man still turn slowly, and a brass sentinel blocks the far door.",
      exit: "A hatch in the deck leads down into warmth and the reek of sulphur."
    },
    corridors: [
      ["entrance", "cargo"],
      ["cargo", "galley"],
      ["cargo", "crossing"],
      ["crossing", "shrine"],
      ["crossing", "workshop"],
      ["workshop", "chapel"],
      ["shrine", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "cargo", type: "Giant Rat" },
      { room: "galley", type: "Kobold" },
      { room: "workshop", type: "Skeleton" },
      { room: "shrine", type: "Zombie" },
      { room: "chapel", type: "Hobgoblin", boss: true, name: "Clockwork Sentinel" },
    ],
    chests: ["cargo", "shrine"],
    traps: [{ room: "crossing", type: "spike" }],
    secret_doors: ["workshop"],
  },
  ash_fall_caves: {
    name: "Ash-Fall Caves",
    level: 2,
    campaign_id: "iron_spire",
    chapter: 2,
    map_pos: { x: 75, y: 50 },
    requires: ["axe_head_wreck"],
    unlocks: "sky_forge_heart",
    blurb: "Lava tubes beneath the spire where fire beetles breed and dwarven dead remember their oaths.",
    story: "The Ash-Fall Caves are the veins of the Iron Spire itself, cracked open when the sky-forge fell. Scavengers who venture too deep speak of glowing beetles and the drone of a hive-queen. The Engine-Sigil grows warm here.",
    objective: "Descend through the lava tubes, destroy the fire beetle hive-queen, and reach the seal that bars the forge heart.",
    story_objective: "Slay the Fire Beetle Hive-Queen before her brood reaches the surface.",
    story_reward: "Hive-Crown — a fused plate of chitin and ember-glass from the queen's crest. It smells of sulphur and old magic.",
    intro: "Heat washes up from below. The tunnel walls glow dull red, and the air shivers with the click of countless mandibles.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Cave Mouth" },
      { id: "tunnel",     x: 8, y: 10, w: 5, h: 5, label: "Ash Tunnel" },
      { id: "vent",       x: 16, y: 10, w: 5, h: 4, label: "Steam Vent" },
      { id: "crossing",   x: 8, y: 6,  w: 6, h: 3, label: "Magma Bridge" },
      { id: "forge",      x: 2, y: 5,  w: 5, h: 3, label: "Old Forge" },
      { id: "shrine",     x: 16, y: 5,  w: 5, h: 5, label: "Obsidian Shrine" },
      { id: "hive",       x: 2, y: 1,  w: 7, h: 4, label: "Queen's Hive" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Forge Seal" },
    ],
    room_descriptions: {
      entrance: "The cave mouth opens into a lava tube choked with ash and discarded chitin.",
      tunnel: "An ash tunnel where the walls are glazed black by old eruptions. Footprints of scavengers and beetles alike mark the floor.",
      vent: "A steam vent hisses from a crack in the floor. The air is hot enough to sting exposed skin.",
      crossing: "A natural bridge of cooled magma spans a glowing crevasse. Beetles skitter along the underside.",
      forge: "An old forge carved by dwarf hands before the fall. Its fires are cold, but the anvil still hums when struck.",
      shrine: "An obsidian shrine to the forge god. Offerings of brass and bone have melted into the walls.",
      hive: "The queen's hive. The chamber throbs with heat and the glow of a hundred fire beetles.",
      exit: "The forge seal. A runed valve blocks the way to the sky-forge heart, too hot to touch."
    },
    corridors: [
      ["entrance", "tunnel"],
      ["tunnel", "vent"],
      ["tunnel", "crossing"],
      ["crossing", "shrine"],
      ["crossing", "forge"],
      ["forge", "hive"],
      ["shrine", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "tunnel", type: "Giant Rat" },
      { room: "vent", type: "Giant Spider" },
      { room: "forge", type: "Skeleton" },
      { room: "shrine", type: "Zombie" },
      { room: "hive", type: "Ghoul", boss: true, name: "Fire Beetle Hive-Queen" },
    ],
    chests: ["vent", "shrine"],
    traps: [{ room: "crossing", type: "pit" }],
    secret_doors: ["forge"],
  },
  sky_forge_heart: {
    name: "The Sky-Forge Heart",
    level: 3,
    campaign_id: "iron_spire",
    chapter: 3,
    map_pos: { x: 90, y: 50 },
    requires: ["ash_fall_caves"],
    unlocks: null,
    blurb: "The sky-forge's burning core, where the last dwarf-warden keeps a dead oath.",
    story: "Beneath the Ash-Fall Caves lies the heart of the fallen sky-forge: a chamber of perpetual flame and dwarven dead. The Engine-Sigil opens the final seal. Within, the last forge warden still guards the Axe-Head's master-cog, mindless and terrible.",
    objective: "Enter the sky-forge heart, defeat the forge warden, and recover the master-cog that can restore the spire.",
    story_objective: "Recover the Axe-Head Master-Cog from the Forge Warden.",
    story_reward: "Master-Cog — a flawless brass gear from the sky-forge heart. It turns without wear and whispers of dwarven oaths.",
    intro: "The seal groans open on rivers of brass and ember. Ahead, the forge heart roars, and a burning silhouette turns to face you.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Seal Hall" },
      { id: "forge_hall", x: 8, y: 10, w: 5, h: 5, label: "Forge Hall" },
      { id: "coal_pit",   x: 16, y: 10, w: 5, h: 4, label: "Coal Pit" },
      { id: "crossing",   x: 8, y: 6,  w: 6, h: 3, label: "Brass Crossing" },
      { id: "armory",     x: 2, y: 5,  w: 5, h: 3, label: "Dwarven Armory" },
      { id: "shrine",     x: 16, y: 5,  w: 5, h: 5, label: "Forge Shrine" },
      { id: "heart",      x: 2, y: 1,  w: 7, h: 4, label: "Sky-Forge Heart" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Lift to the Spire" },
    ],
    room_descriptions: {
      entrance: "The seal hall is scorched clean. Brass gears turn in the walls, driving nothing.",
      forge_hall: "A vast hall of anvils and tongs. The air shimmers with heat, and soot cakes every surface.",
      coal_pit: "A pit heaped with black coal. Something has been feeding the fires from below.",
      crossing: "Three brass walkways meet above a river of molten slag. The heat is suffocating.",
      armory: "Racks of dwarf-forged arms stand untouched. Whoever fell here did not die fighting.",
      shrine: "A shrine to the forge father. Its altar has become a crucible for melted offerings.",
      heart: "The sky-forge heart. Gears as tall as houses turn around a burning anvil, and the forge warden waits.",
      exit: "A lift shaft rises toward the broken spire. The master-cog fits the mechanism perfectly."
    },
    corridors: [
      ["entrance", "forge_hall"],
      ["forge_hall", "coal_pit"],
      ["forge_hall", "crossing"],
      ["crossing", "shrine"],
      ["crossing", "armory"],
      ["armory", "heart"],
      ["shrine", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "forge_hall", type: "Orc" },
      { room: "coal_pit", type: "Giant Rat" },
      { room: "armory", type: "Skeleton" },
      { room: "shrine", type: "Zombie" },
      { room: "heart", type: "Hobgoblin", boss: true, name: "The Forge Warden" },
    ],
    chests: ["coal_pit", "shrine"],
    traps: [{ room: "crossing", type: "spike" }],
    secret_doors: ["armory"],
  },
  pale_herald_camp: {
    name: "The Pale Herald's Camp",
    level: 4,
    campaign_id: "ashen_hollow",
    chapter: 5,
    map_pos: { x: 85, y: 25 },
    requires: ["forgotten_shrine"],
    unlocks: "black_sun_vault",
    blurb: "A ruined manor-camp where the pale herald's servants ready the Black Sun rite.",
    story: "With the Veil Shard in hand you follow the Black Sun's pull to a crumbling manor on the ridge. Bandits, scavengers, and pale-robed cultists camp among the ruins, and a lieutenant of the herald commands them. Stopping the rite here may delay the awakening.",
    objective: "Infiltrate the camp, slay the herald's lieutenant, and learn where the final vault lies.",
    story_objective: "Slay the Pale Herald's lieutenant and recover the Black Sun route-map.",
    story_reward: "Herald's Route-Map — a skin map inked in ash, pointing to the Black Sun Vault beneath the ruined Huet manor.",
    intro: "Rain hammers the broken manor. Fires gutter between toppled columns, and pale figures move among the tents with dire purpose.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",    x: 1, y: 12, w: 6, h: 4, label: "Ruined Gate" },
      { id: "outer_camp",  x: 8, y: 10, w: 5, h: 5, label: "Outer Camp" },
      { id: "supply",      x: 16, y: 10, w: 5, h: 4, label: "Supply Stores" },
      { id: "crossing",    x: 8, y: 6,  w: 6, h: 3, label: "Courtyard" },
      { id: "prisoners",   x: 2, y: 5,  w: 5, h: 3, label: "Prison Pens" },
      { id: "command",     x: 16, y: 5,  w: 5, h: 5, label: "Command Tent" },
      { id: "herald_tent", x: 2, y: 1,  w: 7, h: 4, label: "Herald's Tent" },
      { id: "exit",        x: 16, y: 1,  w: 5, h: 4, label: "Manor Cellar" },
    ],
    room_descriptions: {
      entrance: "The manor gate hangs open. Mud and ash have swallowed the old road.",
      outer_camp: "Tents of scavengers and bandits crowd the courtyard. The herald's servants watch from the shadows.",
      supply: "Crates of stolen grain, lamp oil, and Black Sun trappings are stacked for the road.",
      crossing: "The ruined courtyard. A broken fountain bears the same sun-that-shines-darkness you have seen before.",
      prisoners: "Wooden pens hold sullen villagers and captured road-guards. Some have the Black Sun burned into their forearms.",
      command: "A command tent of black canvas. Maps and trophies show raids across the whole vale.",
      herald_tent: "The herald's own tent, pale as a shroud. A tall figure in bone-white robes waits within.",
      exit: "A cellar stair descends toward the ridge. The route-map points to a vault beneath the old Huet manor."
    },
    corridors: [
      ["entrance", "outer_camp"],
      ["outer_camp", "supply"],
      ["outer_camp", "crossing"],
      ["crossing", "command"],
      ["crossing", "prisoners"],
      ["prisoners", "herald_tent"],
      ["command", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "outer_camp", type: "Bandit" },
      { room: "supply", type: "Orc" },
      { room: "prisoners", type: "Hobgoblin" },
      { room: "command", type: "Bandit" },
      { room: "herald_tent", type: "Ghoul", boss: true, name: "The Pale Herald's Lieutenant" },
    ],
    chests: ["supply", "command"],
    traps: [{ room: "crossing", type: "poison_needle" }],
    secret_doors: ["prisoners"],
  },
  black_sun_vault: {
    name: "The Black Sun Vault",
    level: 5,
    campaign_id: "ashen_hollow",
    chapter: 6,
    map_pos: { x: 90, y: 75 },
    requires: ["pale_herald_camp"],
    unlocks: null,
    blurb: "The campaign finale: a buried vault where the Black Sun rite will awaken an ancient horror.",
    story: "The route-map leads beneath the ruined Huet manor to a vault older than the valley. Here the pale herald means to complete the Black Sun rite and call forth a shadow horror that slept when the world was young. Stop him, or the Vale of Ashen Hollow will never see dawn again.",
    objective: "Descend into the Black Sun Vault, defeat the pale herald, and destroy the rite before the horror awakens.",
    story_objective: "Defeat the Pale Herald and end the Black Sun rite.",
    story_reward: "Shattered Black Sun — the broken amulet no longer hums. The herald's rite is ended, for now.",
    intro: "The cellar walls give way to cyclopean stone. Ahead, black light spills from a vault older than memory, and a voice rises in prayer to the sun that shines darkness.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",     x: 1, y: 12, w: 6, h: 4, label: "Manor Cellar" },
      { id: "antechamber",  x: 8, y: 10, w: 5, h: 5, label: "Antechamber" },
      { id: "reliquary",    x: 16, y: 10, w: 5, h: 4, label: "Reliquary" },
      { id: "crossing",     x: 8, y: 6,  w: 6, h: 3, label: "Vault Crossing" },
      { id: "prison",       x: 2, y: 5,  w: 5, h: 3, label: "Ritual Prison" },
      { id: "ritual",       x: 16, y: 5,  w: 5, h: 5, label: "Ritual Chamber" },
      { id: "vault",        x: 2, y: 1,  w: 7, h: 4, label: "Black Sun Vault" },
      { id: "exit",         x: 16, y: 1,  w: 5, h: 4, label: "Sealed Escape" },
    ],
    room_descriptions: {
      entrance: "The manor cellar stinks of old wine and fresh blood. A hidden door stands open to the vaults below.",
      antechamber: "A vestibule of black stone. Frescoes show a dark sun swallowing the moon and stars.",
      reliquary: "Stolen relics from every shrine in the vale lie heaped in offering to the Black Sun.",
      crossing: "Three passages meet beneath a dome painted with eclipses. The air tastes of copper.",
      prison: "Cells meant for sacrifices. A few prisoners still live, bound and gagged beneath the black glyph.",
      ritual: "The ritual chamber. Chalk circles and Black Sun candles surround a pit that opens on nothing.",
      vault: "The Black Sun Vault. The pale herald stands before the pit, arms raised, as darkness gathers into a shape.",
      exit: "A sealed escape tunnel. Beyond it lies the surface and the first grey light of dawn."
    },
    corridors: [
      ["entrance", "antechamber"],
      ["antechamber", "reliquary"],
      ["antechamber", "crossing"],
      ["crossing", "ritual"],
      ["crossing", "prison"],
      ["prison", "vault"],
      ["ritual", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "antechamber", type: "Skeleton" },
      { room: "reliquary", type: "Zombie" },
      { room: "prison", type: "Orc" },
      { room: "ritual", type: "Hobgoblin" },
      { room: "vault", type: "Ghoul", boss: true, name: "The Pale Herald" },
    ],
    chests: ["reliquary", "ritual"],
    traps: [{ room: "crossing", type: "pit" }],
    secret_doors: ["prison"],
  },
};

let currentModule = null;
let roomIdGrid = [];
let roomsVisited = new Set();

function loadDungeonModule(name) {
  const mod = DUNGEON_MODULES[name];
  if (!mod) {
    console.warn("Unknown module", name);
    return false;
  }
  currentModule = mod;
  roomsVisited = new Set();

  MAP_W = mod.width;
  MAP_H = mod.height;
  const grid = makeEmptyMap();
  const roomGrid = makeEmptyMap();
  roomIdGrid = makeEmptyMap();
  const roomById = {};

  for (const room of mod.rooms) {
    carveRoom(grid, room);
    carveRoom(roomGrid, room);
    for (let y = room.y; y < room.y + room.h; y++) {
      for (let x = room.x; x < room.x + room.w; x++) {
        if (y > 0 && y < MAP_H - 1 && x > 0 && x < MAP_W - 1) {
          roomIdGrid[y][x] = room.id;
        }
      }
    }
    roomById[room.id] = room;
  }

  // Carve corridors.
  for (const [aId, bId] of mod.corridors) {
    const a = roomCenter(roomById[aId]);
    const b = roomCenter(roomById[bId]);
    carveCorridor(grid, a.x, a.y, b.x, b.y);
  }

  // Place doors where corridors meet rooms.
  for (let y = 1; y < MAP_H - 1; y++) {
    for (let x = 1; x < MAP_W - 1; x++) {
      if (grid[y][x] !== TILE.FLOOR) continue;
      const isRoom = roomGrid[y][x] === TILE.FLOOR;
      if (isRoom) continue;
      for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
        if (roomGrid[y + dy][x + dx] === TILE.FLOOR) {
          grid[y][x] = TILE.DOOR;
          break;
        }
      }
    }
  }

  // Reset state.
  chestsOpened.clear();
  doorsOpened.clear();
  trapsTriggered.clear();
  trapsDiscovered.clear();
  secretDoorsDiscovered.clear();
  trapData.clear();

  // Player and exit.
  playerPos = roomCenter(roomById[mod.playerStart]);
  const exitPos = roomCenter(roomById[mod.exitRoom]);
  grid[exitPos.y][exitPos.x] = TILE.EXIT;

  // Chests.
  for (const roomId of mod.chests) {
    const pos = roomCenter(roomById[roomId]);
    grid[pos.y][pos.x] = TILE.CHEST;
  }

  // Traps.
  for (const entry of mod.traps || []) {
    const roomId = typeof entry === "string" ? entry : entry.room;
    const type = typeof entry === "string" ? randomTrapType() : (entry.type || randomTrapType());
    const pos = roomCenter(roomById[roomId]);
    grid[pos.y][pos.x] = TILE.TRAP;
    trapData.set(`${pos.x},${pos.y}`, type);
  }

  // Secret doors: replace a normal door adjacent to the named room(s).
  for (const roomId of mod.secret_doors || []) {
    const doorTile = findDoorTileAdjacentToRoom(grid, roomIdGrid, roomId);
    if (doorTile) {
      grid[doorTile.y][doorTile.x] = TILE.SECRET_DOOR;
    }
  }

  // Monsters.
  monsters = [];
  for (const entry of mod.monsters) {
    const pos = roomCenter(roomById[entry.room]);
    const monsterId = findMonsterIdByName(entry.type);
    if (!monsterId) {
      console.warn("Unknown monster type in module:", entry.type);
      continue;
    }
    const template = getMonsterTemplate(monsterId);
    if (!template) continue;
    const isBoss = entry.boss;
    const stats = scaleMonsterStats(template, dungeonLevel);
    const hp = Math.floor(stats.hp * (isBoss ? 1.5 : 1));
    const thac0 = Math.max(1, stats.thac0 - (isBoss ? 1 : 0));
    const damage = isBoss
      ? `1d${Math.min(12, parseInt(template.damage.slice(2)) + 2)}`
      : template.damage;
    const xp = Math.floor(stats.xp * (isBoss ? 2 : 1));
    monsters.push({
      id: `${monsterId}-${pos.x}-${pos.y}-${dungeonLevel}`,
      name: entry.name || template.name,
      hd: template.hd || 1,
      boss: isBoss,
      x: pos.x,
      y: pos.y,
      hp: hp,
      maxHp: hp,
      acDesc: template.ac_descending,
      thac0: thac0,
      damage: damage,
      xp: xp,
      morale: template.morale,
      ranged: template.ranged || null,
      alive: true,
      fled: false,
      moraleChecked: false,
      turned: 0,
    });
  }

  mapData = grid;
  computeVisibility();
  return true;
}

function checkRoomEntry(x, y) {
  if (!currentModule || !roomIdGrid.length) return;
  const roomId = roomIdGrid[y] && roomIdGrid[y][x];
  if (!roomId || roomsVisited.has(roomId)) return;
  roomsVisited.add(roomId);
  const desc = currentModule.room_descriptions && currentModule.room_descriptions[roomId];
  if (desc && typeof log === "function") {
    log(desc);
  }
  if (typeof tutorialManager !== "undefined" && tutorialManager) {
    tutorialManager.onRoomEntered(roomId);
  }
}
