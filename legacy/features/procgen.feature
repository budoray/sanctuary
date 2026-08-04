Feature: Generating a random dungeon at the table

  A GM reaching for the random dungeon generator between sessions should get
  a playable map back, not a half-built graph or a room nobody can walk out
  of - and when the book's own tables produce something impossible, the GM
  should be able to see what got fudged and why.

  Scenario: The same seed always builds the same dungeon
    Given a GM rolls up a dungeon with seed 42
    And a second GM rolls up a dungeon with the same seed 42
    Then both dungeons are identical, room for room

  Scenario: A generated dungeon never traps its party behind a door they cannot open
    Given a GM rolls up a dungeon with seed 7
    Then an empty-handed party can reach every area from the start

  Scenario: A generated dungeon is a real campaign module, not a lookalike
    Given a GM rolls up a dungeon with seed 7
    Then the GM's own module loader accepts it without complaint

  Scenario: Every corridor connects both ways, unless the book says it's one-way
    Given a GM rolls up a dungeon with seed 7
    Then every door and passage can be walked back the way it came, except stairs and chutes marked one-way

  Scenario: An impossible table result is fudged out loud, not hidden
    Given a GM rolls up a dungeon that hits an impossible table result
    Then the roll log shows what was fudged and why

  Scenario: Two hundred different dungeons all come back playable
    Given a GM rolls up two hundred dungeons on two hundred different seeds
    Then none of them crash, none of them are empty, and every area in each is reachable
