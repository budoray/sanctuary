Feature: Trusting the OSRIC rulebook data behind the tables

  The corpus is the books themselves, extracted rather than retyped - a GM
  should be able to trust that every table made it in, and that what is
  stored says exactly what the book says.

  Scenario: Every table in the rulebooks is available to the game
    Given the full corpus of extracted tables
    Then 194 tables can be found by id

  Scenario Outline: A table the book split across pages is still one table, read in full
    Given the table <id>, which the book printed across <parts> pages
    When a reader asks for every part of it
    Then all <parts> parts come back complete

    Examples:
      | id       | parts |
      | 1.4.2.3a | 3     |
      | 2.9.1c   | 2     |
      | 2.9.1h   | 4     |

  Scenario: A table read twice is read the same both times
    Given the fighter to-hit table
    When a reader opens it twice
    Then both readings match exactly, word for word

  Scenario: Typographic ligatures from the printed page do not survive into the data
    Given the full corpus of extracted tables
    Then none of them contain a typographic ligature character

  Scenario: A table the extractor could not use is reported, never silently dropped
    Given the tables the extractor set aside as unusable
    Then every one of them still has a surviving entry in the corpus
