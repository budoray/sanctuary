Feature: Looking up and adjusting monsters at the table

  A GM should be able to trust the book's monster while still adjusting it for
  their own table, and to build a beast the book never printed.

  Scenario: A GM may make a goblin tougher without losing the book's goblin
    Given the goblin from the book
    When a GM raises that goblin's morale for a tougher warband
    Then the goblin on their table has the higher morale
    But the goblin printed in the book is unchanged

  Scenario: A GM changes their mind and goes back to the book's numbers
    Given a GM has already raised a goblin's morale
    When the GM discards that change
    Then the goblin is back to exactly what the book printed

  Scenario: A GM builds a brand new beast the book never printed
    When a GM creates a custom monster called "Sewer Rat King"
    Then it appears in their bestiary with the same fields as any book monster

  Scenario: A GM looks up how dangerous a monster is and gets back a level, not a raw XP number
    Given a monster worth 3,000 experience points
    When a GM checks how dangerous it is
    Then they're told it's a level 7 monster

  Scenario: No monster's abilities go missing, even the ones the table doesn't run yet
    Given the achaiyerai, a monster with a special attack beyond simple combat
    When a GM looks up what it can do
    Then its Toxic Cloud is still there in the text, not silently dropped

  Scenario: A generated encounter's printed name is recognised as a real monster
    Given the monster tables print "Wolf, Dire" for an encounter
    When the game looks up which monster that names
    Then it finds the dire wolf, ready to fight

  Scenario: An encounter name the book doesn't contain is never guessed at
    Given the monster tables print "Barghest" for an encounter
    When the game looks up which monster that names
    Then it finds no monster, rather than a wrong one

  Scenario: A dragon arrives at the table as a dragon, not a first-level chump
    Given the monster tables print "Dragon, Red" for an encounter
    When the party meets whatever that names
    Then it fights with at least 9 hit dice
    And it has more hit points than a housecat

  Scenario: A kraken is worth a kraken's experience
    Given the monster tables print "Kraken" for an encounter
    When the party meets whatever that names
    Then killing it is worth at least 10000 experience

  Scenario: The book's most heavily armoured devil is not the easiest thing to hit
    Given the monster tables print "Pit Fiend" for an encounter
    When the party meets whatever that names
    Then its armour class is better than an unarmoured commoner's
