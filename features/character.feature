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
