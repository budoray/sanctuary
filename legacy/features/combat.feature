Feature: Combat resolves attacks, saves, turning, morale and death honestly

  Every roll the engine makes for a fight is reproducible from its seed and
  shows the arithmetic behind the outcome, not just a pass/fail. Neither the
  best nor the worst face of a d20 is ever treated as special on its own -
  the roll against the target is the whole of it.

  Scenario: A novice swinging at a well-armoured knight rarely connects
    Given a first-level fighter attacking a knight in plate mail and shield
    When the fighter swings with a very weak roll
    Then the attack misses

  Scenario: A veteran fighter connects far more easily than a novice
    Given a first-level fighter and a tenth-level fighter, both attacking the same lightly-armoured foe
    When both roll the same middling number on the die
    Then the veteran's swing is at least as likely to land as the novice's

  Scenario: Rolling the lowest number on the die is not an automatic miss
    Given an attacker with enough skill and bonuses to threaten a hit
    When the attacker rolls the worst possible number on the die
    Then the attack can still land

  Scenario: Rolling the highest number on the die is not an automatic hit
    Given an attacker facing a target far beyond their skill
    When the attacker rolls the best possible number on the die
    Then the attack can still miss

  Scenario: Rolling the lowest number on a saving throw always fails
    Given a character making a saving throw
    When the character rolls the worst possible number on the die
    Then the saving throw fails no matter the bonuses

  Scenario: A cleric turns the shambling dead
    Given a mid-level cleric confronting a handful of shambling zombies
    When the cleric presents their holy symbol and attempts to turn them
    Then the zombies are turned or destroyed

  Scenario: A powerful lich shrugs off a novice cleric's turning attempt
    Given a first-level cleric confronting an ancient lich
    When the cleric attempts to turn the lich
    Then the turning attempt has no effect

  Scenario: A battered warband loses its nerve
    Given a monster warband that has already lost several of its number
    When the warband's morale is tested under those losses
    Then the warband is more likely to break than a warband at full strength

  Scenario: A hero laden with treasure moves more slowly
    Given an adventurer carrying far more than they can comfortably bear
    When their movement rate for the day is worked out
    Then they move markedly slower than an unencumbered adventurer

  Scenario: A fallen adventurer bleeds toward death
    Given an adventurer beaten down to nothing
    When they take one more solid hit
    Then they fall unconscious rather than instantly dying

  Scenario: An adventurer who has bled out too far is beyond saving
    Given an adventurer already deep in negative hit points
    When they take one more solid hit
    Then they are dead
