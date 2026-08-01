Feature: Rolling ability scores for a new character

  OSRIC 3.0 offers four ways to generate ability scores. Two hand the player
  the dice as they fall; two let the player arrange the results afterward.

  Scenario: A player rolling in the hardest mode takes the dice as they fall
    Given a player generating a character in the hardest mode
    When the six ability scores are rolled
    Then the player may not rearrange the results

  Scenario: A player rolling in a flexible mode may arrange the results
    Given a player generating a character in the flexible mode
    When the six ability scores are rolled
    Then the player may rearrange the results

  Scenario: A player rolling in the difficult mode may arrange the results
    Given a player generating a character in the difficult mode
    When the six ability scores are rolled
    Then the player may rearrange the results

  Scenario: A player rolling in the normal mode takes the dice as they fall
    Given a player generating a character in the normal mode
    When the six ability scores are rolled
    Then the player may not rearrange the results

  Scenario: Every rolled score falls within the range three dice can make
    Given a player generating a character in the normal mode
    When the six ability scores are rolled
    Then every ability score is between 3 and 18

  Scenario: The same seed always builds the same character
    Given a player generating a character in the normal mode
    When the six ability scores are rolled twice with the same seed
    Then both rolls produce identical ability scores

  Scenario Outline: Only fighters, paladins and rangers roll for exceptional strength
    Given a character with 18 Strength and class "<class>"
    When exceptional strength is checked
    Then a die is <rolled_or_not> for exceptional strength

    Examples:
      | class    | rolled_or_not |
      | fighter  | rolled        |
      | paladin  | rolled        |
      | ranger   | rolled        |
      | thief    | not rolled    |
      | cleric   | not rolled    |

  Scenario: A Strength below 18 never rolls for exceptional strength, whatever the class
    Given a character with 17 Strength and class "fighter"
    When exceptional strength is checked
    Then a die is not rolled for exceptional strength

  Scenario: A percentile roll of 00 gives a Strength of 19
    Given a fighter whose exceptional strength percentile roll comes up 00
    When exceptional strength is checked
    Then the character's Strength is 19

  Scenario: A Strength already settled by an exceptional roll is not rolled again
    Given a fighter whose Strength was already settled at 18.50 by an earlier exceptional roll
    When exceptional strength is checked
    Then a die is not rolled for exceptional strength
    And the character's Strength is still 18.50

  Scenario Outline: An ancestry shapes a character's abilities
    Given a player choosing the <ancestry> ancestry
    When the ancestral adjustments are applied to ability scores of 10 across the board
    Then the <ability> score becomes <score>

    Examples:
      | ancestry | ability      | score |
      | dwarf    | constitution | 11    |
      | dwarf    | charisma     | 9     |
      | elf      | dexterity    | 11    |
      | elf      | constitution | 9     |
      | halfling | dexterity    | 11    |
      | halfling | strength     | 9     |
      | half-orc | strength     | 11    |
      | half-orc | charisma     | 8     |
      | human    | strength     | 10    |

  Scenario Outline: A weak-bodied dwarf does not meet the ancestry's requirements
    Given a player choosing the dwarf ancestry
    When the player's ability scores are all <score>
    Then the character <does_or_not> meet the dwarf's ancestral requirements

    Examples:
      | score | does_or_not |
      | 6     | does not    |
      | 14    | does        |

  Scenario: A human accepts any set of ability scores
    Given a player choosing the human ancestry
    When the player's ability scores are all 3
    Then the character does meet the human's ancestral requirements

  Scenario Outline: An ancestry opens or closes the door to certain classes
    Given a player choosing the <ancestry> ancestry
    Then the player <can_or_cannot> become a <class>

    Examples:
      | ancestry | class      | can_or_cannot |
      | dwarf    | fighter    | can           |
      | dwarf    | magic-user | cannot        |
      | elf      | magic-user | can           |
      | elf      | paladin    | cannot        |
      | halfling | cleric     | cannot        |
      | halfling | thief      | can           |
      | human    | paladin    | can           |
      | human    | monk       | can           |

  Scenario: A dwarf is hardier but blunter than a human
    Given a player choosing the dwarf ancestry
    When the ancestral adjustments are applied to ability scores of 10 across the board
    Then the constitution score becomes 11
    And the charisma score becomes 9

  Scenario: Some ancestries never run out of room to advance as a thief
    Given a player choosing the dwarf ancestry
    Then the thief level limit is unlimited

  Scenario: A half-orc's ambition as an assassin has a ceiling
    Given a player choosing the half-orc ancestry
    Then the assassin level limit is 15

  Scenario: A human may rise without limit in most classes, but never past the ceiling of an assassin, druid or monk
    Given a player choosing the human ancestry
    Then the player can become a fighter
    And the fighter level limit is unlimited
    And the assassin level limit is 15
    And the druid level limit is 14
    And the monk level limit is 17

  Scenario: A character with a feeble body cannot become a fighter
    Given a character with every ability score at 6
    Then the character cannot take up fighter among a human's classes

  Scenario: A character with an able body can become a fighter
    Given a character with every ability score at 16
    Then the character can take up fighter among a human's classes

  Scenario: A dwarf's devotion never opens the door to the paladin's calling
    Given a character with every ability score at 18
    Then the character cannot take up paladin among a dwarf's classes
    But the character can take up paladin among a human's classes

  Scenario: A magic-user rolls a smaller hit die than a fighter
    Given a first-level fighter and a first-level magic-user, rolled with the same seed
    Then the fighter's hit points come from a bigger die than the magic-user's

  Scenario: A hardy character's toughness helps every level it still rolls for hit points
    Given a fighter of level 3 with a Constitution bonus of 2
    Then the bonus is added once for every level rolled

  Scenario: Hit points never fall below one for a level, however unlucky the roll
    Given a magic-user of level 2 with a Constitution penalty of 3
    Then the character still has at least 1 hit point per level

  Scenario Outline: Hit dice stop climbing at a class's own veteran level, not a shared number
    Given a <class> character
    Then hit dice stop climbing at level <stop_level>
    And every level after that grants a flat <flat_hp> hit points instead

    Examples:
      | class       | stop_level | flat_hp |
      | fighter     | 9          | 3       |
      | paladin     | 9          | 3       |
      | cleric      | 9          | 2       |
      | illusionist | 10         | 1       |
      | thief       | 10         | 2       |
      | ranger      | 10         | 2       |
      | magic-user  | 11         | 1       |
      | assassin    | 15         | 0       |
      | druid       | 14         | 0       |
      | monk        | 17         | 0       |

  Scenario: A veteran character's Constitution no longer sweetens hit points once hit dice stop
    Given a magic-user of level 13 with a Constitution bonus of 5
    Then the Constitution bonus applies only to the levels that still rolled a hit die

  Scenario: A ranger begins hardier than other warriors, rolling twice for starting hit points
    Given a first-level ranger and a first-level fighter, rolled with the same seed
    Then the ranger rolls twice as many starting hit dice as the fighter

  Scenario: Strength sharpens a character's fists and blade
    Given a character with 18 Strength
    Then the Strength hit bonus is 1
    And the Strength damage bonus is 2

  Scenario: Exceptional Strength sharpens the bonus further
    Given a character with 18.6 Strength
    Then the Strength hit bonus is 2
    And the Strength damage bonus is 3

  Scenario: An average Strength gives no bonus at all
    Given a character with 10 Strength
    Then the Strength hit bonus is 0
    And the Strength damage bonus is 0

  Scenario: A seasoned fighter hits more easily than a novice
    Given a fighter of level 1 and a fighter of level 9
    Then the level 9 fighter needs a lower roll to hit the same armour class than the level 1 fighter

  Scenario Outline: A rising adventurer of every calling resists spells better than a novice
    Given a <class> of level 1 and a <class> of level <veteran_level>
    Then the level <veteran_level> <class> resists spells at least as well as the level 1 <class>

    Examples:
      | class       | veteran_level |
      | assassin    | 13            |
      | cleric      | 13            |
      | druid       | 13            |
      | fighter     | 13            |
      | illusionist | 16             |
      | magic-user  | 16             |
      | monk        | 17             |
      | paladin     | 13             |
      | ranger      | 13             |
      | thief       | 13             |

  Scenario: OSRIC does not auto-miss on a natural 1 or auto-hit on a natural 20
    Given a fighter of level 1
    Then the to-hit target is just a number to beat, with no special case for a roll of 1 or 20

  Scenario: A new adventurer is ready to play
    Given a player creates Ilse, a human fighter, with seed 1234
    Then Ilse has a full set of ability scores
    And Ilse has at least 1 hit point
    And Ilse has all five saving throws
    And Ilse's seed is recorded as 1234

  Scenario: The same seed always builds the same adventurer
    Given a player creates a human fighter twice with seed 77
    Then both adventurers are identical in every way that matters

  Scenario: Different seeds build different adventurers
    Given a player creates a human fighter with seed 1
    And a player creates another human fighter with seed 2
    Then the two adventurers differ

  Scenario: A human must choose a single calling
    Given a player choosing the human ancestry
    Then a human may not train as both a fighter and a magic-user

  Scenario: An elf may train as both a fighter and a magic-user
    Given a player choosing the elf ancestry
    Then an elf may train as both a fighter and a magic-user

  Scenario: Any single calling is always open to those who may take it
    Given a player choosing the human ancestry
    Then a human may train as a lone fighter

  Scenario Outline: An ancestry's blessed dual callings are honoured
    Given a player choosing the <ancestry> ancestry
    Then the <ancestry> ancestry allows both <first_calling> and <second_calling>

    Examples:
      | ancestry | first_calling | second_calling |
      | dwarf    | fighter       | thief           |
      | elf      | fighter       | magic-user       |
      | elf      | fighter       | thief            |
      | elf      | magic-user    | thief            |
      | gnome    | fighter       | illusionist      |
      | gnome    | fighter       | thief            |
      | gnome    | illusionist   | thief            |
      | half-elf | cleric        | fighter          |
      | half-elf | cleric        | ranger           |
      | half-elf | cleric        | magic-user       |
      | half-elf | fighter       | magic-user       |
      | half-elf | fighter       | thief            |
      | halfling | fighter       | thief            |
      | half-orc | cleric        | fighter          |
      | half-orc | cleric        | thief            |
      | half-orc | cleric        | assassin         |
      | half-orc | fighter       | thief            |
      | half-orc | fighter       | assassin         |

  Scenario Outline: A calling combination outside an ancestry's blessing is refused
    Given a player choosing the <ancestry> ancestry
    Then the <ancestry> ancestry does not allow both <first_calling> and <second_calling>

    Examples:
      | ancestry | first_calling | second_calling |
      | dwarf    | fighter       | magic-user       |
      | elf      | cleric        | fighter          |
      | gnome    | cleric        | fighter          |
      | halfling | druid         | fighter          |
      | half-orc | fighter       | magic-user       |
      | human    | fighter       | magic-user       |

  Scenario: An elf may train as fighter, magic-user and thief all at once
    Given a player choosing the elf ancestry
    Then an elf may train as fighter, magic-user and thief all at once

  Scenario: Creating a character with a forbidden combination of callings is refused
    Given a player attempts to create a human fighter and magic-user with seed 1
    Then the attempt is refused

  Scenario: A multi-classed adventurer's hit points are shared across callings
    Given a player creates an elf fighter and magic-user with seed 5
    Then the elf's hit points come from dice rolled for both callings

  Scenario: A character who trains in two callings advances more slowly in body than in one alone
    Given a fighter and magic-user who roll 7 and 3 for their starting toughness
    Then the multi-classed adventurer's starting hit points are 4, not 5

  Scenario: Every calling a multi-classed character trains in grants at least one hit point
    Given a fighter, magic-user and thief who each roll a bare 1 for their starting toughness
    Then the triple-classed adventurer starts with at least 3 hit points, one for each calling
