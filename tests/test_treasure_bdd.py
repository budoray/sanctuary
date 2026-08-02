"""Step definitions for features/treasure.feature."""
from pytest_bdd import scenarios, given, when, then

from sanctuary.dice import Dice
from sanctuary import treasure

scenarios("../features/treasure.feature")


@given(
    "a Cache 1 - the meagre hoard classes reserved for weak monsters",
    target_fixture="class_name",
)
def cache_1():
    return "cache_1"


@given(
    "a Hoard 1 - the rich, worked-example hoard class from the book",
    target_fixture="class_name",
)
def hoard_1_named():
    return "hoard_1"


@given("a Hoard 1", target_fixture="class_name")
def hoard_1():
    return "hoard_1"


@given(
    "an Individual 2 - what one rank-and-file NPC carries",
    target_fixture="class_name",
)
def individual_2():
    return "individual_2"


@when(
    "the GM rolls it for a beaten kobold warren, on a seed that misses every line",
    target_fixture="hoard",
)
def roll_missing_every_line(class_name):
    # Found by brute force: seed 0 misses both of Cache 1's lines.
    return treasure.roll_hoard(Dice(0), class_name)


@then("the party finds nothing at all")
def nothing_at_all(hoard):
    assert hoard == []


@when("the GM rolls it on a seed that hits every line", target_fixture="hoard")
def roll_hitting_every_line(class_name):
    # Found by brute force: seed 6750 hits every one of Hoard 1's 8 lines.
    return treasure.roll_hoard(Dice(6750), class_name)


@then("coin, gems, jewellery and magic items can all turn up together")
def coin_gems_jewellery_and_magic_items(hoard):
    kinds = {line.kind for line in hoard}
    assert kinds == {"cp", "sp", "ep", "gp", "pp", "gems", "jewellery", "magic_item"}


@when("the GM rolls it twice from the same seed", target_fixture="two_hoards")
def roll_twice_same_seed(class_name):
    return (
        treasure.roll_hoard(Dice(42), class_name),
        treasure.roll_hoard(Dice(42), class_name),
    )


@then("both hoards match down to the last coin")
def hoards_match(two_hoards):
    first, second = two_hoards
    assert first == second


@when("the GM rolls it for a fallen guard", target_fixture="hoard")
def roll_for_fallen_guard(class_name):
    return treasure.roll_hoard(Dice(1), class_name)


@then("the guard is carrying at least a few silver pieces")
def carrying_silver(hoard):
    line, = hoard
    assert line.kind == "sp"
    assert line.amount > 0


@given("a satchel of gems", target_fixture="seed")
def a_satchel_of_gems():
    return 11


@when("the GM rolls one gem's worth", target_fixture="gem")
def roll_one_gem(seed):
    return treasure.gem_value(Dice(seed))


@then("it comes back with a value in gold and a jeweller's category")
def gem_has_value_and_category(gem):
    value, category = gem
    assert value > 0
    assert category in treasure._GEM_CATEGORIES


@given("a piece of unidentified jewellery", target_fixture="seed")
def unidentified_jewellery():
    return 3


@when("the GM rolls what it actually is", target_fixture="piece")
def roll_the_jewellery(seed):
    return treasure.jewellery(Dice(seed))


@then("it comes back as a recognisable kind of jewellery with a value")
def jewellery_is_recognisable(piece):
    value, form, tier = piece
    assert value > 0
    assert form  # e.g. "Ring", "Amulet", "Crown"
    assert tier in {t[0] for t in treasure.TIER_DICE}


@given("the GM needs a magic item of no particular kind", target_fixture="seed")
def needs_any_magic_item():
    return 5


@when("the type of magic item is rolled", target_fixture="category")
def roll_the_type(seed):
    return treasure.roll_magic_item_type(Dice(seed))


@then("the result names one of the book's own magic item families")
def names_a_family(category):
    assert category in {
        "armour_or_shield", "miscellaneous_magic", "miscellaneous_weapon",
        "potion", "ring", "rod_staff_wand", "scroll", "sword",
    }


@given("the GM is rolling a miscellaneous magic item", target_fixture="seed")
def rolling_misc_magic_item():
    return 2


@when("the rarity and the specific item are both rolled", target_fixture="item")
def roll_rarity_and_item(seed):
    return treasure.roll_miscellaneous_magic_item(Dice(seed))


@then("a single named item comes back, not a rarity label alone")
def a_single_named_item(item):
    assert item.name
    assert item.table_id in {"2.13.1q", "2.13.1r", "2.13.1s", "2.13.1t"}
