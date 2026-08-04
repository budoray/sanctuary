Feature: Memorising and casting spells

  Clerics, druids, illusionists and magic-users all prepare their magic ahead
  of time. How many spells they can hold ready grows with level, the same
  spell can fill more than one slot, a prepared spell can be let go before
  it is cast, and the arcane classes may only prepare what is written in
  their own spell book.

  Scenario: A magic-user memorises the same spell in two different slots
    Given a 2nd level magic-user with magic missile in their spell book
    When they memorise magic missile twice
    Then both first-level slots hold magic missile

  Scenario: A caster forgets a memorised spell to free its slot
    Given a 1st level magic-user with magic missile in their spell book
    And they have memorised magic missile
    When they forget magic missile
    Then their first-level slot is empty again

  Scenario: A magic-user cannot memorise a spell that is not in their spell book
    Given a 1st level magic-user with magic missile in their spell book
    When they try to memorise fireball
    Then they are refused, because fireball is not in their spell book

  Scenario: A cleric of higher level prays for more spells
    Given a 1st level cleric
    And a 9th level cleric
    Then the 9th level cleric has more first-level prayers available than the 1st level cleric

  Scenario: A reversible spell is memorised once and cast in either orientation
    Given a cleric who has memorised continual light, a reversible spell
    Then the same memorised spell can be cast as continual light or as its reverse
