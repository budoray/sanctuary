"""The solo driver: one player against the engine (design §9 - "ships first").

Wraps `sanctuary.runtime`'s `State` behind a thin, JSON-friendly surface so
`app.py` (or a future party/async driver) doesn't have to know the state
machine's internals. The runtime stays ignorant of this file - `session`
sits strictly above `runtime` in the §5 dependency chain.
"""
from dataclasses import asdict, dataclass, replace

from sanctuary import runtime
from sanctuary.character import Character
from sanctuary.module import Module

# In-memory session table: enough for a single-process dev server. A
# durable store is a party/async-driver concern (design §9's later rows),
# not solo's.
# ponytail: process-local dict, not a DB - fine for one player at a time
# per process; swap for a real store when the party/async drivers land.
_SESSIONS: dict[str, runtime.State] = {}


def start(session_id: str, module_: Module, party: list[Character], seed: int) -> dict:
    """Begin a solo delve, keyed by `session_id` (the client mints this -
    a session id, not a player identity, so nothing here decides who a
    player is)."""
    st = runtime.new_game(module_, party, seed)
    _SESSIONS[session_id] = st
    return view(session_id)


def _get(session_id: str) -> runtime.State:
    st = _SESSIONS.get(session_id)
    if st is None:
        raise KeyError(f"no session {session_id!r}")
    return st


def view(session_id: str) -> dict:
    """The whole state a solo client needs to render: the current area,
    party vitals, the dice log so far, and anything awaiting a decision."""
    st = _get(session_id)
    out = runtime.describe(st)
    out["party"] = [
        {"name": runtime.party_key(c, i), "hp": st.hp[runtime.party_key(c, i)],
         "max_hp": st.max_hp[runtime.party_key(c, i)]}
        for i, c in enumerate(st.party)
    ]
    out["xp"] = st.xp
    out["inventory"] = list(st.inventory)
    out["log"] = list(st.log)
    out["rolls"] = [asdict(r) for r in st.dice.log]
    if st.combat is not None:
        out["combat"] = {
            "round": st.combat.round,
            "monsters": [{"name": m.name, "hp": m.hp, "max_hp": m.max_hp, "alive": m.alive}
                         for m in st.combat.monsters],
        }
    return out


def act(session_id: str, action: str, **kwargs) -> dict:
    """Dispatch one player action by name. Every action mutates the
    session's `State` in place and returns the resulting `view()` - the
    single choke point a client (or a reproducibility test) calls through,
    so "same seed, same sequence of `act()` calls" is the whole replay
    contract."""
    st = _get(session_id)
    handlers = {
        "move": lambda: runtime.move(st, int(kwargs["to"])),
        "search": lambda: runtime.search(st, kwargs.get("scope")),
        "rest": lambda: runtime.rest(st, int(kwargs.get("turns", 1))),
        "take_treasure": lambda: runtime.take_treasure(st),
        "attack": lambda: runtime.attack_round(st, int(kwargs.get("target", 0))),
        "flee": lambda: runtime.flee(st),
        "decide": lambda: runtime.decide(st, int(kwargs["index"]), str(kwargs["ruling"])),
        "leave": lambda: runtime.leave(st),
    }
    fn = handlers.get(action)
    if fn is None:
        raise ValueError(f"no such action {action!r}")
    fn()
    return view(session_id)


def end(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)
