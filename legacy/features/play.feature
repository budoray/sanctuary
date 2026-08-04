Feature: Playing a delve solo

  A player who has rolled a character and picked a dungeon should be able to
  walk in, fight what's there, find what's hidden, take what's worth taking,
  and walk out again - using nothing but the actions the table itself offers.

  Scenario: A party can enter a dungeon, fight, take treasure, and finish
    Given a solo party stands at the mouth of a small dungeon
    When the party fights its way to the treasure and leaves
    Then the delve ends with the party's own dice log to show for it
    And the party has treasure in hand

  Scenario: A monster's unmodeled attack is asked about, never skipped
    Given a solo party meets a monster with an attack the table has no rule for
    Then the party is asked how that attack goes, not left to guess
    And the fight will not continue until the party rules on it

  Scenario: The same seed and the same choices always play out the same way
    Given a solo party plays through a dungeon making a fixed set of choices
    And a second party plays through the same dungeon making the same choices
    Then both parties see the exact same dice, in the exact same order

  Scenario: A party that rests too long in a dungeon attracts company
    Given a solo party is resting in a dungeon room with a wandering danger
    When the party rests turn after turn
    Then something eventually finds them

  Scenario: A hidden passage stays hidden until searched for
    Given a solo party stands in a room with a passage nobody has found yet
    Then the party cannot walk through a passage it hasn't found
    When the party searches the room and finds it
    Then the party can walk through it

  Scenario: A generated dungeon never leaves a party with nowhere to go
    Given a GM generates dungeons on twenty different seeds
    Then a party in every one of them can always reach a way out
