Feature: Looking up the OSRIC tables at the table

  A GM should be able to trust the printed tables even though the corpus
  stores each book page exactly as extracted, quirks and all.

  Scenario Outline: A fighter's chance to hit armour class 10 by level
    Given the fighter to-hit table
    When a level <level> fighter looks up the roll needed to hit armour class 10
    Then the roll required is <roll>

    Examples:
      | level | roll |
      | 1     | 10   |
      | 9     | 2    |
      | 10    | 1    |
      | 20    | -9   |

  Scenario: A table the book split across pages is still readable in full
    Given the graveyard encounters table, which the book split across three pages
    When a GM asks for every part of that table
    Then all three parts come back, none of them mistaken for the whole

  Scenario: A full one Hit Die monster is not mistaken for a weaker one
    Given the monster to-hit table
    When a GM looks up the row for a monster with exactly 1 Hit Die
    Then the lookup does not silently hand back the sub-1-Hit-Die row

  Scenario: A character's Wisdom score yields its bonus
    Given the Wisdom table
    When a character with Wisdom 16 looks up their mental saving throw modifier
    Then the modifier is +2
