Feature: Loading and checking a module at the table

  A GM should be able to trust that a module which loads is safe to run,
  and that one which does not load tells them exactly what is wrong and
  where, rather than making them hunt through 67 areas by hand.

  Scenario: A hand-authored module loads clean
    Given the Weeping Cistern module
    When the GM loads it
    Then it loads without complaint
    And it has two regions checking on different schedules
    And it has a monster found nowhere but this module
    And it has a discovery that only turns up after searching for a while

  Scenario: A module that sends players through a door to nowhere is refused, and says which door
    Given a module where area 1's door leads to an area that does not exist
    When the GM loads it
    Then the module is refused
    And the complaint names area 1 and the missing area

  Scenario: A module with two rooms sharing the same number is refused, and says which number
    Given a module where two areas are both numbered 1
    When the GM loads it
    Then the module is refused
    And the complaint names the duplicate area number

  Scenario: A wandering table missing an entry for one of its die faces is refused
    Given a module whose 2-sided wandering table only lists one encounter
    When the GM loads it
    Then the module is refused
    And the complaint names the mismatch between the die and the entry count

  Scenario: A discovery with unexplained odds is refused
    Given a module where a discovery has a chance to be found but no stated interval
    When the GM loads it
    Then the module is refused
    And the complaint says the discovery is missing its interval

  Scenario: A fixed module survives being saved and reloaded
    Given the Weeping Cistern module
    When the GM saves it and loads it again
    Then the reloaded module is identical to the original
