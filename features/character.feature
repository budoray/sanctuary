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
