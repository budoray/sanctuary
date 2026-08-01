Feature: The seeded dice engine keeps a faithful, replayable log

  Every die in Sanctuary comes from one place, and every roll is written to
  a log with the reason it was made - so a session can be reproduced, and a
  player who suspects the dice can go and check them.

  Scenario: Every die rolled is written to the log with its reason
    Given a dice engine seeded for a session
    When a player rolls for "opening the ancient door"
    Then the log's newest entry gives the reason "opening the ancient door"

  Scenario Outline: The same seed retells the same story
    Given a dice engine seeded with <seed>
    When the same sequence of rolls is made twice with that seed
    Then both tellings are identical, roll for roll

    Examples:
      | seed |
      | 42   |
      | 999  |
      | 7    |

  Scenario: The log records what each die actually showed, not just the total
    Given a dice engine seeded for a session
    When a player rolls three six-sided dice for Strength
    Then the log shows every individual die alongside the total

  Scenario: Rolling four dice and dropping the lowest keeps the best three
    Given a dice engine seeded for a session
    When a player rolls four six-sided dice and drops the lowest
    Then three dice are kept and the dropped one is excluded from the total

  Scenario: A modifier is recorded separately from the dice, so the arithmetic is visible
    Given a dice engine seeded for a session
    When a player rolls a twenty-sided die with a +3 bonus for an attack
    Then the log shows the bonus apart from the dice
    And the total is the dice plus the bonus
