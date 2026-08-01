"""Drop-in CHECKER for what a player's browser actually receives. STDLIB ONLY.

ONE client lint, replacing ten bespoke ones. Thirteen repos asserted the 24px tap
floor in TEN incompatible ways — one of them by re-implementing the browser box
model in Python — and twelve of the thirteen read one CSS declaration deep, which
is the bug the site had already found and fixed alone.

    import tenshin_client as tc
    html = client()                       # ⚠ the string the PLAYER loads
    tc.assert_rendered(html, name="console")          # FIRST — see below
    tc.assert_no_third_party(html, name="console")
    tc.assert_tap_floor(html, CONTROLS, name="console")
    tc.assert_tokens_consumed(html, name="console")
    tc.assert_classes_ruled(html, name="console")

⚠⚠ **HAND IT THE CLIENT, NEVER A FILE GLOB.** Building this, a file-based scan
gave three confidently wrong answers in a row: Freight Mogul's client CSS lives
inside `app.py` as a Python string, A More Perfect Union composes its pages from
`tokens.css` PLUS three CSS constants in `app.py`, and globbing `*.html` found
one token in a repo that has thirty-three. The SSoT already records this trap for
the leaderboard grep — *run it against the file the player actually loads, which
for several games is a Python string inside app.py*. It is the same trap, and it
is why `CONTROLS` is a per-repo table rather than something this file discovers.

⚠ A CHECKER, like `tenshin_chrome.py`: nothing imports it to serve a page, so it
cannot become load-bearing. Its negative cases ship with it — `python
tenshin_client.py`.
"""
import re

MIN_TAP = 24            # WCAG 2.5.8 wants 24x24

# First-party by construction. Everything else in a FETCHING position is a
# third-party request, and /privacy promises visitors there are none.
# ⚠ `<a href>` is navigation, not a request — a link to another site costs the
# visitor nothing until they choose it, so anchors are not scanned at all.
FIRST_PARTY = re.compile(r"^(?:https?:)?//(?:[\w-]+\.)*tenshinarts\.com(?:[:/]|$)"
                         r"|^(?:https?:)?//(?:localhost|127\.0\.0\.1)(?:[:/]|$)", re.I)

# where a browser is TOLD to fetch something
_FETCHERS = (
    ("<script src>",    re.compile(r"""<script\b[^>]*\bsrc\s*=\s*["']([^"']+)""", re.I)),
    ("<link href>",     re.compile(r"""<link\b[^>]*\bhref\s*=\s*["']([^"']+)""", re.I)),
    ("@import",         re.compile(r"""@import\s+(?:url\()?\s*["']?([^"')\s;]+)""", re.I)),
    ("css url()",       re.compile(r"""url\(\s*["']?([^"')\s]+)""", re.I)),
    ("media src",       re.compile(r"""<(?:img|iframe|video|audio|source|embed|track)\b[^>]*"""
                                   r"""\bsrc\s*=\s*["']([^"']+)""", re.I)),
    ("fetch/XHR/ws",    re.compile(r"""(?:fetch|open|WebSocket|EventSource)\s*\(\s*["']"""
                                   r"""((?:https?:)?//[^"']+)""", re.I)),
)


def _strip_comments(t):
    """⚠ Strip BEFORE counting anything. `--acc-mark` on this platform is defined
    once and mentioned once — in the comment directly above its own definition —
    so a counter that reads comments calls a dead token alive."""
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    return re.sub(r"<!--.*?-->", "", t, flags=re.S)


def _css_of(t, css=""):
    """Inline <style> blocks (or the whole text, for a bare stylesheet), PLUS any
    external stylesheet the caller passes.

    ⚠⚠ PASS `css=` WHENEVER THE PAGE LINKS ITS STYLES RATHER THAN INLINING THEM.
    Without it this returns only the `<style>` blocks and DISCARDS everything
    else — so a page carrying one small inline block and a 47 KB linked
    stylesheet is judged against the 9 bytes. It fails OPEN, into false
    positives, which is the worse direction: run over the site's own templates it
    reported `.btn`, `.card` and `.cab` as unruled, every one of them a core rule
    in `site.css`. A checker that cries wolf gets switched off, and then it is
    checking nothing at all.
    """
    blocks = re.findall(r"<style[^>]*>(.*?)</style>", t, re.S)
    inline = "\n".join(blocks) if blocks else t
    return inline + "\n" + css


def assert_rendered(client, *, name, opens="<!doctype html"):
    """The page is a PAGE. Run this FIRST, before any other rule.

    ⚠⚠ EVERY RULE IN THIS FILE PASSES CHEERFULLY ON THE EMPTY STRING. Freight
    Mogul's lint was green on nothing for an hour: its gate runs without
    TENSHIN_DEV, so every gated surface answered 303 with an empty body and four
    checks reported a clean bill for zero bytes. That is the platform's own rule
    — GUARD ON OUTPUT, NOT INVENTORY — failing inside the tool written to enforce
    the others, and it is the single most likely way this lint goes quietly
    useless in a new repo.
    """
    assert client and client.lstrip()[:len(opens)].lower() == opens, (
        f"{name} rendered {len(client)} bytes that are not a page — every rule below "
        f"passes on an empty string, so the lint would be green on nothing. A gated "
        f"surface fetched without a session answers 303 with no body.")


def assert_no_third_party(client, *, name, allow=()):
    """No request leaves the player's browser for anyone but us.

    ⚠ THIS INVARIANT HAD ZERO LINES OF CODE ENFORCING IT ANYWHERE, while
    `/privacy` promises it to every visitor in as many words. It is a privacy
    guarantee (no font-request fingerprint, no CDN logging a reader) and an
    availability one (a game does not break when someone else's server does).
    It held in all fourteen repos when this was written — so what this stops is
    the regression, and three repos were one `&text=` font subset away from it.
    """
    bad = []
    for kind, rx in _FETCHERS:
        for url in rx.findall(_strip_comments(client)):
            url = url.strip()
            if url in allow or url.startswith(("data:", "#", "{", "$")):
                continue
            # relative and root-relative are same-origin by definition. ⚠ Match on
            # the URL's SHAPE, never on words in it: `/static/img/badges/
            # google-data-analytics.png` is a local file whose NAME contains two
            # vendor words, and a substring blacklist flags it.
            if not url.startswith(("http://", "https://", "//")):
                continue
            if FIRST_PARTY.match(url):
                continue
            bad.append(f"{kind} {url[:90]}")
    assert not bad, (f"{name}: the page tells the browser to fetch from a third party — "
                     f"/privacy promises it does not:\n  " + "\n  ".join(sorted(set(bad))))


def assert_tap_floor(client, controls, *, name, min_px=MIN_TAP, css=""):
    """Every named control declares >= min_px, read as a VALUE, scoped to its rule.

    `controls` is {label: css-selector-regex} — the PER-REPO table. There is no
    discovering this: a control is whatever that game calls a control.

    ⚠ Read the NUMBER. Twelve of thirteen bespoke versions asserted that a word
    was present, so shrinking the floor to 11px passed every one of them. And ⚠
    resolve one level of `var()`: the arcade clients declare `--tap:24px` once and
    write `min-height:var(--tap)` everywhere, which is the right way to do it and
    the wrong thing to fail on.
    """
    css = _strip_comments(_css_of(client, css))
    tokens = {m[0]: float(m[1]) for m in
              re.findall(r"(--[\w-]+)\s*:\s*([\d.]+)px", css)}
    for label, selector in controls.items():
        m = re.search(selector + r"\s*\{([^}]*)\}", css)
        assert m, (f"{name}: no rule matches {label} ({selector!r}) — renamed, or the "
                   f"fix was reverted, and either way nothing is asserting its hit box")
        decl = m.group(1).replace(" ", "")
        hit = re.search(r"min-height:([\d.]+)px", decl)
        got = float(hit.group(1)) if hit else None
        if got is None:
            v = re.search(r"min-height:var\((--[\w-]+)\)", decl)
            assert v, (f"{name}: {label} declares no min-height at all — 11px type with "
                       f"no padding is an 11px tap target")
            assert v.group(1) in tokens, \
                f"{name}: {label} reads {v.group(1)}, which is never given a px value"
            got = tokens[v.group(1)]
        assert got >= min_px, (f"{name}: {label} declares {got}px — WCAG 2.5.8 wants "
                               f"{min_px}. Read as a value, so weakening it fails as "
                               f"loudly as deleting it.")


def assert_tokens_consumed(client, *, name, allow=()):
    """No `:root` token defined and never consumed.

    ⚠⚠ COUNT BOTH CONSUMPTION PATHS. A regex looking only for `var(--x)` reports
    TEN false positives on this platform: Clearance, Corpus, Ember Down and
    Progeny deliberately read tokens through
    `getComputedStyle(root).getPropertyValue('--x')`, so the token appears as a
    STRING LITERAL in JavaScript and nowhere in the CSS. Those four keep their
    palette in one place on purpose — Clearance's own comment says the canvas held
    its own copies of the hex and the tokens sat consumed by nothing, which is the
    bug they fixed BY reading them that way. Flagging it would punish the fix.

    So the predicate is occurrence-based, not syntax-based: a token is consumed if
    it appears more often than it is DEFINED. That catches `var()`, a JS string, a
    template, and whatever the next path turns out to be.

    ⚠⚠ HAND THIS ONE THE GENERATOR, not one rendered page, whenever the client has
    CONDITIONAL content — and hand it the WHOLE client, not one surface. Vested
    consumes `--warn` at exactly one place, `"var(--warn)" if g_letter in ("C","D")`,
    so a page rendered for a fresh life reports a live token as dead. Freight Mogul
    injects one shared sheet into every page, so `--shield` (used only by the map)
    and `--paint` (only by the console) each read as dead one page over. Both are
    the same mistake: the predicate is about the CLIENT, and a single render is a
    sample of it.
    """
    t = _strip_comments(client)
    defined = set(re.findall(r"(--[A-Za-z][\w-]*)\s*:", t))
    # ⚠ `(?![\w-])`, NOT `\b`. A hyphen is a NON-word character, so `--ease-in\b`
    # matches inside `--ease-in-out`: a token that is a PREFIX of another reads as
    # consumed by its own longer sibling, silently and forever. A More Perfect
    # Union carried a genuinely dead `--ease-in` this check could not see, found by
    # hand while landing it. A lint with a hole in it is worse than no lint.
    dead = sorted(tok for tok in defined - set(allow)
                  if len(re.findall(re.escape(tok) + r"(?![\w-])", t))
                  <= len(re.findall(re.escape(tok) + r"\s*:", t)))
    assert not dead, (f"{name}: token defined and never consumed — an invisible signal, "
                      f"and the screen never keeps the promise: {dead}")


def assert_classes_ruled(client, *, name, allow=(), css=""):
    """No `class="x"` without a matching `.x{}` rule.

    Progeny defined `--dim` and marked four asides `class="dim"` with no `.dim{}`
    anywhere, so every one rendered at full ink. Ashen Dragon marked loot upgrades
    `<span class="good">` with no rule — the one glyph telling a player an item
    beats their gear was in the DOM and invisible on screen. Both shipped for
    weeks, with every route test green.
    """
    t = _strip_comments(client)
    css = _css_of(t, css)
    used = set()
    for m in re.finditer(r"""class(?:Name)?\s*=\s*["'`]([^"'`]*)["'`]""", t):
        used |= set(m.group(1).split())
    for m in re.finditer(r"""classList\.(?:add|remove|toggle)\(\s*['"]([\w-]+)""", t):
        used.add(m.group(1))
    used = {u for u in used if re.fullmatch(r"[A-Za-z][\w-]*", u)} - set(allow)
    styled = set(re.findall(r"\.([A-Za-z][\w-]*)", css))
    orphan = sorted(used - styled)
    assert not orphan, (f"{name}: class in the DOM with no CSS rule anywhere — it renders, "
                        f"and it renders as nothing: {orphan}")


# ── the negative cases, which are the point ──────────────────────────────────
_OK = """<!doctype html><html><head><style>
/* a comment mentioning --ghost, which must NOT count as consuming it */
:root{--tap:24px;--ink:#111}
footer a,footer button{min-height:var(--tap)}
.badge{color:var(--ink)}
</style></head><body>
<link rel="stylesheet" href="/static/site.css">
<script src="/static/vendor/htmx.min.js"></script>
<img src="/static/img/badges/google-data-analytics.png">
<iframe src="https://titer.tenshinarts.com/live/embed"></iframe>
<script>fetch('/leaderboard.json'); new EventSource('/live/stream');
const c = getComputedStyle(document.documentElement).getPropertyValue('--ink');</script>
<span class="badge">ok</span>
<a href="https://example.com/somewhere-else">an anchor is navigation, not a request</a>
</body></html>"""

_CTL = {"footer controls": r"footer a,\s*footer button"}
_ARGS = dict(name="fixture")


def _rejects(fn, html, because, **kw):
    try:
        fn(html, **{**_ARGS, **kw})
    except AssertionError as e:
        assert because in str(e), f"rejected for the wrong reason: {e}"
        return str(e)
    raise AssertionError(f"ACCEPTED a page it must reject ({because})")


def _self_check():
    # the healthy page passes all five — without this, a function that rejected
    # everything would satisfy every case below
    assert_rendered(_OK, **_ARGS)
    assert_no_third_party(_OK, **_ARGS)
    assert_tap_floor(_OK, _CTL, **_ARGS)
    assert_tokens_consumed(_OK, **_ARGS)
    assert_classes_ruled(_OK, **_ARGS)

    n = [
        # ⚠⚠ THE EMPTY PAGE, first, because every other rule here passes on it.
        _rejects(assert_rendered, "", "green on nothing"),
        _rejects(assert_rendered, "   ", "green on nothing"),
        _rejects(assert_rendered, "<div>a fragment, not a page</div>", "green on nothing"),
        # ...and the proof that it is worth having: the other rules DO accept it
        # (asserted positively below, outside this list)

        # (d) third-party requests, one per fetching position
        _rejects(assert_no_third_party, _OK.replace('href="/static/site.css"',
                 'href="https://fonts.googleapis.com/css2?family=X"'), "third party"),
        _rejects(assert_no_third_party, _OK.replace('src="/static/vendor/htmx.min.js"',
                 'src="https://unpkg.com/htmx.org@2"'), "third party"),
        _rejects(assert_no_third_party, _OK.replace("</style>",
                 "@import url('https://cdn.jsdelivr.net/x.css');</style>"), "third party"),
        _rejects(assert_no_third_party, _OK.replace("--ink:#111",
                 "--ink:#111;background:url(https://gravatar.com/a.png)"), "third party"),
        _rejects(assert_no_third_party, _OK.replace("fetch('/leaderboard.json')",
                 "fetch('https://api.example.com/x')"), "third party"),
        # ⚠ and the FALSE positives it must NOT raise, which is the harder half:
        #    a local file whose name contains two vendor words, a first-party
        #    subdomain iframe, and an <a href> to anywhere at all.
        #    (all three are in _OK, which passed above)

        # (a) the tap floor, read as a VALUE and scoped to the rule
        _rejects(assert_tap_floor, _OK.replace("--tap:24px", "--tap:11px"),
                 "WCAG 2.5.8", controls=_CTL),
        _rejects(assert_tap_floor, _OK.replace("min-height:var(--tap)", "color:red"),
                 "no min-height at all", controls=_CTL),
        _rejects(assert_tap_floor, _OK.replace("min-height:var(--tap)", "min-height:18px"),
                 "declares 18.0px", controls=_CTL),
        _rejects(assert_tap_floor, _OK.replace("footer a,footer button", ".foot a"),
                 "no rule matches", controls=_CTL),

        # (b) a token defined and never consumed
        _rejects(assert_tokens_consumed, _OK.replace("--ink:#111", "--ink:#111;--ghost:#eee"),
                 "--ghost"),
        # ⚠ THE PREFIX HOLE. `--ink` is consumed and `--ink-deep` is not, and a ``
        # boundary let the shorter name hide inside the longer one's occurrences.
        # This case is the whole reason the pattern is a negative lookahead.
        _rejects(assert_tokens_consumed,
                 _OK.replace("--ink:#111", "--ink:#111;--ink-deep:#000"), "--ink-deep"),
        # ⚠ and NOT flagged when read through getComputedStyle — the ten-false-
        # positive case. _OK consumes --ink only as a JS string literal.
        # (proven by the healthy pass above; assert it explicitly too)

        # (c) a class in the DOM with no rule
        _rejects(assert_classes_ruled, _OK.replace('class="badge"', 'class="badge dim"'), "dim"),
        _rejects(assert_classes_ruled,
                 _OK.replace("const c =", "el.classList.add('good'); const c ="), "good"),
    ]

    # ⚠⚠ THE EXTERNAL-STYLESHEET HOLE, both rules and both directions. A page that
    # LINKS its CSS and carries one small inline block is judged against the inline
    # block ALONE unless `css=` is passed — and it fails OPEN, into false positives,
    # which is the direction that gets a checker switched off. Run over the site's
    # own templates without it, `.btn`, `.card` and `.cab` all read as unruled.
    _linked = '<html><style>.inline{}</style><body class="btn"></body></html>'
    n.append(_rejects(assert_classes_ruled, _linked, "['btn']"))
    assert_classes_ruled(_linked, name="linked", css=".btn{color:red}")
    n.append(_rejects(assert_tap_floor, _linked, "no rule matches",
                      controls={"btn": r"\.btn"}))
    assert_tap_floor(_linked, {"btn": r"\.btn"}, name="linked", css=".btn{min-height:24px}")

    # ...and the reverse must NOT fire: the SHORT name dead, the LONG one live.
    # Without the lookahead this direction was fine; with it, it is what proves the
    # lookahead did not simply break the check the other way round.
    long_live = _OK.replace("--ink:#111", "--ink-deep:#000").replace("var(--ink)", "var(--ink-deep)")
    assert "'--ink'" in long_live                       # the JS read still names --ink
    assert_tokens_consumed(long_live.replace("'--ink'", "'--ink-deep'"), name="prefix sibling")

    # ⚠ the reason assert_rendered exists, stated as a test: on the empty string
    # every other rule in this file reports a clean bill.
    for _fn in (assert_no_third_party, assert_tokens_consumed, assert_classes_ruled):
        _fn("", name="empty")            # must NOT raise — that is the whole problem

    # the explicit version of the trap: --ink is consumed ONLY as a JS string
    only_js = _OK.replace(".badge{color:var(--ink)}", ".badge{color:#111}")
    assert "var(--ink)" not in only_js and "'--ink'" in only_js
    assert_tokens_consumed(only_js, name="getComputedStyle path")

    print(f"tenshin_client self-check OK — {len(n)} broken pages REJECTED across all five rules "
          f"(an EMPTY page, on which every other rule reports clean; a third-party fetch in five "
          f"different positions; an {MIN_TAP}px floor weakened to 11 "
          f"and to 18 and deleted, a dead token, an unruled class) — and the three that must NOT "
          f"fire did not: a local file named google-data-analytics.png, a first-party subdomain "
          f"iframe, an <a href> off-site, and a token read only through getComputedStyle")


if __name__ == "__main__":
    _self_check()
