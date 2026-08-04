"""The packs that ship with the game, registered at import.

Importing this package is what makes `ruleset.load("osric")` work; the
engine's lazy default (`runtime.new_game(..., ruleset=None)`) imports it
on first use so module-level import order never matters.
"""
from sanctuary import ruleset
from sanctuary.rulesets import osric

ruleset.register("osric", osric.OsricPack)

load = ruleset.load
registered = ruleset.registered
