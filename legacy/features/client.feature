Feature: Opening Sanctuary in the browser

  Sanctuary is a table in the browser: a player opens the page, rolls a
  character, and can see every die that built it.

  Scenario: A player opens Sanctuary and sees the licence notice
    Given a player opens Sanctuary
    Then the page carries the OSRIC licence notice
    And the game's name carries the trademark symbol

  Scenario: A player opens Sanctuary and sees the house chrome in order
    Given a player opens Sanctuary
    Then the house chrome appears in the order build, report, back, sign out
    And the back door leads to the Tenshin Arts site root, not the games list

  Scenario: A player opens Sanctuary and rolls a character
    Given a player opens Sanctuary
    When the player rolls a human fighter
    Then the character sheet shows the character's name and ancestry
    And the dice tray shows every die that made the character

  Scenario: A rolled character is shown with a portrait of their calling
    Given a player opens Sanctuary
    When the player rolls a human fighter
    Then the character sheet shows a portrait of their calling

  Scenario: A player chooses their calling by its portrait
    Given a player opens Sanctuary
    Then every calling in the forge is offered as its own portrait tile
    And each portrait tile is a real, keyboard-selectable choice

  Scenario: A player rolls the same character twice
    Given a player opens Sanctuary
    When the player rolls the same character twice with the same seed
    Then both rolls produce the exact same character

  Scenario: A player tries to build an illegal character
    Given a player opens Sanctuary
    When the player rolls a human fighter and magic-user
    Then Sanctuary refuses the combination instead of crashing

  Scenario: A player is not offered a calling their people cannot follow
    Given a player opens Sanctuary
    When the player looks at what callings a half-elf may follow
    Then the monk calling is not among them
    But the monk calling is open to a human

  Scenario: A player reads the full licence
    Given a player opens Sanctuary
    When the player follows the full licence link
    Then the licence page carries the OSRIC notice and the SRD 5.1 notice
