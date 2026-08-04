Feature: Treasure and loot classes

  A kobold's hoard is rarely worth the trip, and a dragon's is worth risking
  your neck for - the same loot-class system produces both, because every
  line of a hoard is its own coin flip rather than a guarantee.

  Scenario: A kobold's hoard is rarely worth the trip
    Given a Cache 1 - the meagre hoard classes reserved for weak monsters
    When the GM rolls it for a beaten kobold warren, on a seed that misses every line
    Then the party finds nothing at all

  Scenario: A dragon's hoard can hold everything at once
    Given a Hoard 1 - the rich, worked-example hoard class from the book
    When the GM rolls it on a seed that hits every line
    Then coin, gems, jewellery and magic items can all turn up together

  Scenario: The same seed retells the same hoard
    Given a Hoard 1
    When the GM rolls it twice from the same seed
    Then both hoards match down to the last coin

  Scenario: A lone bandit's purse is never empty
    Given an Individual 2 - what one rank-and-file NPC carries
    When the GM rolls it for a fallen guard
    Then the guard is carrying at least a few silver pieces

  Scenario: A found gem is appraised on the spot
    Given a satchel of gems
    When the GM rolls one gem's worth
    Then it comes back with a value in gold and a jeweller's category

  Scenario: A piece of jewellery is described, not just priced
    Given a piece of unidentified jewellery
    When the GM rolls what it actually is
    Then it comes back as a recognisable kind of jewellery with a value

  Scenario: Rolling for a random magic item names a family before a specific item
    Given the GM needs a magic item of no particular kind
    When the type of magic item is rolled
    Then the result names one of the book's own magic item families

  Scenario: A miscellaneous magic item is drawn from the right rarity tier
    Given the GM is rolling a miscellaneous magic item
    When the rarity and the specific item are both rolled
    Then a single named item comes back, not a rarity label alone
