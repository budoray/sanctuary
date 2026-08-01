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
