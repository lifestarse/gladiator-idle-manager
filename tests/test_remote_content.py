# Build: 1
"""Tests for the remote content overlay.

The overlay's entire value depends on one property: a bad patch must be
rejected rather than applied. A patch reaches every player at once and cannot
be recalled without a Play release, so these tests are the safety mechanism,
not documentation of it.

Every test that touches the cache redirects Path.home() at a tmp_path — the
real home holds the player's save.
"""
import json

import pytest

from game.remote_content import _cache, _manifest, gamedata, languages


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Point Path.home() at a scratch dir and reset the module memo."""
    import pathlib
    import game.remote_content as rc
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(rc, "_enabled", None)
    yield tmp_path
    monkeypatch.setattr(rc, "_enabled", None)


BUNDLED = {
    "greeting": "Привіт, {name}!",
    "plain": "Кузня",
    "marked": "[b][color=ffd040]Покращення +{lvl}[/color][/b]: бонус",
    "enchant_names": {"burn": "Опік", "drain": "Витягування"},
    "help_sections": [["АРЕНА", "Бійці б'ються з хвилями ворогів."]],
}


# ---------------------------------------------------------------- languages

def test_accepts_a_well_formed_patch():
    accepted, rejected = languages.validate({"plain": "Кузня майстра"}, BUNDLED)
    assert accepted == {"plain": "Кузня майстра"}
    assert not rejected


def test_rejects_a_key_that_is_not_bundled():
    """A patch may only overwrite. Adding keys is how a patch and a build drift."""
    accepted, rejected = languages.validate({"brand_new_key": "текст"}, BUNDLED)
    assert not accepted
    assert "not a key of the bundled" in rejected["brand_new_key"]


def test_rejects_a_dropped_placeholder():
    """A missing {name} is a KeyError in whichever screen formats the string."""
    accepted, rejected = languages.validate({"greeting": "Привіт!"}, BUNDLED)
    assert not accepted
    assert "placeholders" in rejected["greeting"]


def test_rejects_a_renamed_placeholder():
    accepted, rejected = languages.validate({"greeting": "Привіт, {nombre}!"}, BUNDLED)
    assert not accepted


def test_rejects_broken_bbcode():
    """Kivy renders a malformed tag literally — visible garbage on the card."""
    accepted, rejected = languages.validate(
        {"marked": "[b]Покращення +{lvl}: бонус"}, BUNDLED)
    assert not accepted
    assert "BBCode" in rejected["marked"]


def test_rejects_non_strings_and_empties():
    accepted, rejected = languages.validate(
        {"plain": 42, "greeting": "   "}, BUNDLED)
    assert not accepted
    assert set(rejected) == {"plain", "greeting"}


def test_rejects_absurdly_long_values():
    accepted, rejected = languages.validate({"plain": "х" * 500}, BUNDLED)
    assert not accepted
    assert "exceeds" in rejected["plain"]
    # A short label may still grow to the floor: "OK" -> "Гаразд" is fine.
    accepted, _ = languages.validate({"plain": "Кузня майстра клинків"}, BUNDLED)
    assert accepted


def test_rejects_an_oversized_patch_wholesale():
    huge = {f"key{i}": "x" for i in range(languages.MAX_ENTRIES + 1)}
    accepted, rejected = languages.validate(huge, BUNDLED)
    assert not accepted
    assert "<patch>" in rejected


def test_one_bad_key_does_not_cost_the_good_ones():
    accepted, rejected = languages.validate(
        {"plain": "Кузня майстра", "greeting": "Привіт!"}, BUNDLED)
    assert accepted == {"plain": "Кузня майстра"}
    assert set(rejected) == {"greeting"}


def test_apply_writes_nested_paths():
    """enchant_names and help_sections are the two non-flat keys."""
    data = json.loads(json.dumps(BUNDLED))
    applied = languages.apply_patch(data, {
        "enchant_names.burn": "Опік (сильний)",
        "help_sections.0.0": "ЯМА",
        "plain": "Кузня майстра",
    })
    assert applied == 3
    assert data["enchant_names"]["burn"] == "Опік (сильний)"
    assert data["help_sections"][0][0] == "ЯМА"
    assert data["plain"] == "Кузня майстра"


def test_apply_leaves_untouched_keys_alone():
    data = json.loads(json.dumps(BUNDLED))
    languages.apply_patch(data, {"plain": "Кузня майстра"})
    assert data["greeting"] == BUNDLED["greeting"]
    assert data["enchant_names"]["drain"] == "Витягування"


# ---------------------------------------------------------------- gamedata

def test_balance_accepts_a_whitelisted_field():
    accepted, rejected = gamedata.validate({"weapons": {"rusty_blade": {"cost": 150}}})
    assert accepted == {"weapons": {"rusty_blade": {"cost": 150}}}
    assert not rejected


def test_balance_rejects_an_unknown_section():
    accepted, rejected = gamedata.validate({"fighters": {"x": {"hp": 1}}})
    assert not accepted
    assert "fighters" in rejected


def test_balance_rejects_a_field_outside_the_whitelist():
    """Identity and behaviour fields are not balance and are never patchable."""
    for field, value in (("rarity", "legendary"), ("slot", "weapon"),
                         ("id", "other"), ("name", "Blade")):
        accepted, rejected = gamedata.validate(
            {"weapons": {"rusty_blade": {field: value}}})
        assert not accepted, field
        assert "not patchable" in rejected[f"weapons.rusty_blade.{field}"]


def test_balance_rejects_non_numbers_including_bool():
    """bool subclasses int — True would silently become a cost of 1."""
    accepted, rejected = gamedata.validate(
        {"weapons": {"rusty_blade": {"cost": True}}})
    assert not accepted
    assert "must be a number" in rejected["weapons.rusty_blade.cost"]


def test_balance_rejects_values_outside_range():
    """The ranges are what stop a fat-fingered zero from resetting the economy."""
    accepted, rejected = gamedata.validate(
        {"weapons": {"rusty_blade": {"cost": 10 ** 12}}})
    assert not accepted
    assert "outside allowed range" in rejected["weapons.rusty_blade.cost"]

    accepted, rejected = gamedata.validate(
        {"expeditions": {"e1": {"relic_chance": 5.0}}})
    assert not accepted


def test_balance_applies_to_both_data_shapes():
    """Items and enemies are id-carrying lists; enchantments are keyed dicts."""
    class FakeLoader:
        _weapons = [{"id": "rusty_blade", "cost": 100, "rarity": "common"}]
        _enchantments = {"burn": {"cost_gold": 1000, "effect": "dot"}}
        _enemies = [{"id": "pit_rat", "tier": 1}]

    loader = FakeLoader()
    applied = gamedata.apply_patch(loader, {
        "weapons": {"rusty_blade": {"cost": 250}},
        "enchantments": {"burn": {"cost_gold": 900}},
        "enemies": {"pit_rat": {"tier": 3}},
    })
    assert applied == 3
    assert loader._weapons[0]["cost"] == 250
    assert loader._weapons[0]["rarity"] == "common"   # untouched
    assert loader._enchantments["burn"]["cost_gold"] == 900
    assert loader._enemies[0]["tier"] == 3


def test_balance_ignores_ids_this_build_does_not_have():
    """A patch may legitimately mention content an older build lacks."""
    class FakeLoader:
        _weapons = [{"id": "rusty_blade", "cost": 100}]

    loader = FakeLoader()
    applied = gamedata.apply_patch(loader, {
        "weapons": {"future_sword": {"cost": 500}, "rusty_blade": {"cost": 120}},
    })
    assert applied == 1
    assert loader._weapons[0]["cost"] == 120


def test_balance_cannot_add_a_field_that_does_not_exist():
    class FakeLoader:
        _weapons = [{"id": "rusty_blade", "cost": 100}]

    loader = FakeLoader()
    # base_str is whitelisted but this entry has no such field; the overlay
    # must not invent one, or a later formula reads a value nobody designed.
    applied = gamedata.apply_patch(loader, {"weapons": {"rusty_blade": {"base_str": 9}}})
    assert applied == 0
    assert "base_str" not in loader._weapons[0]


def test_whitelist_fields_exist_in_the_real_data_files():
    """The whitelist must describe the shipped files, not a remembered shape."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for section, (fname, top_key, fields) in gamedata.PATCHABLE.items():
        with open(root / "data" / fname, encoding="utf-8") as handle:
            node = json.load(handle)[top_key]
        entries = list(dict(gamedata._entries_of(node)).values())
        assert entries, f"{section}: no entries found in {fname}"
        present = {key for entry in entries for key in entry}
        unknown = set(fields) - present
        assert not unknown, f"{section}: whitelisted fields absent from {fname}: {unknown}"


# ---------------------------------------------------------------- manifest

def _manifest_doc(**entry):
    base = {"path": "uk.v1.json", "revision": 1}
    base.update(entry)
    return {"schema": _manifest.SCHEMA, "entries": {"lang.uk": base}}


def test_manifest_accepts_a_well_formed_entry():
    assert "lang.uk" in _manifest.validate(_manifest_doc())


def test_manifest_ignores_a_future_schema():
    doc = _manifest_doc()
    doc["schema"] = _manifest.SCHEMA + 1
    assert _manifest.validate(doc) == {}


def test_manifest_rejects_path_traversal_and_absolute_urls():
    for bad in ("../../etc/passwd", "/etc/passwd", "https://evil.example/x.json"):
        assert _manifest.validate(_manifest_doc(path=bad)) == {}


def test_manifest_gates_on_app_version():
    from game.version import APP_VERSION
    assert _manifest.validate(_manifest_doc(min_app="99.0.0")) == {}
    assert _manifest.validate(_manifest_doc(max_app="0.0.1")) == {}
    assert "lang.uk" in _manifest.validate(_manifest_doc(min_app=APP_VERSION))


def test_manifest_treats_an_unparseable_bound_as_do_not_apply():
    """A blank min_app must not read as 'applies everywhere'."""
    assert _manifest.validate(_manifest_doc(min_app="")) == {}


def test_manifest_rejects_malformed_revisions():
    assert _manifest.validate(_manifest_doc(revision="3")) == {}
    assert _manifest.validate(_manifest_doc(revision=True)) == {}


# ---------------------------------------------------------------- cache & safe mode

def test_cache_round_trip_and_revision():
    _cache.write("lang_uk", {"plain": "Кузня"}, revision=7)
    assert _cache.read("lang_uk") == {"plain": "Кузня"}
    assert _cache.revision("lang_uk") == 7


def test_cache_read_of_missing_and_corrupt_files():
    assert _cache.read("nope") is None
    path = _cache._path("broken")
    path.write_text("{not json", encoding="utf-8")
    assert _cache.read("broken") is None


def test_marker_lifecycle():
    assert not _cache.crashed_while_patched()
    assert _cache.mark_applying()
    assert _cache.crashed_while_patched()
    _cache.clear_marker()
    assert not _cache.crashed_while_patched()


def test_patching_is_inert_when_nothing_is_cached(isolated_home):
    """Fresh install, desktop dev and every test must not touch disk at all."""
    import game.remote_content as rc
    data = json.loads(json.dumps(BUNDLED))
    assert rc.patch_language("uk", data) == 0
    assert data == BUNDLED
    assert list(isolated_home.iterdir()) == []


def test_a_cached_patch_is_applied():
    import game.remote_content as rc
    _cache.write("lang_uk", {"plain": "Кузня майстра"}, revision=2)
    data = json.loads(json.dumps(BUNDLED))
    assert rc.patch_language("uk", data) == 1
    assert data["plain"] == "Кузня майстра"


def test_a_launch_that_died_while_patched_drops_the_cache():
    """The whole point: a fatal patch costs one launch, not every install."""
    import game.remote_content as rc
    _cache.write("lang_uk", {"plain": "Кузня майстра"}, revision=2)
    _cache.mark_applying()          # previous launch never cleared it

    data = json.loads(json.dumps(BUNDLED))
    assert rc.patch_language("uk", data) == 0
    assert data["plain"] == BUNDLED["plain"]
    assert _cache.read("lang_uk") is None
    assert not _cache.crashed_while_patched()


def test_kill_switch_disables_everything(monkeypatch):
    import game.remote_content as rc
    _cache.write("lang_uk", {"plain": "Кузня майстра"}, revision=2)
    monkeypatch.setattr(rc, "REMOTE_CONTENT_ENABLED", False)
    data = json.loads(json.dumps(BUNDLED))
    assert rc.patch_language("uk", data) == 0
    assert rc.sync("uk") == []


# ---------------------------------------------------------------- packs

def _pack_payload(lang="uk"):
    """A minimal but structurally honest pack built from bundled en.json."""
    import json as _json
    from game.localization import flatten
    from game.remote_content import packs as _packs
    with open(_packs.bundled_dir() + "/en.json", encoding="utf-8") as handle:
        reference = flatten(_json.load(handle))
    # Translating by prefixing keeps placeholders and markup intact, which is
    # what the validator actually checks.
    ui = {path: text for path, text in reference.items()}
    return {"lang": lang, "revision": 1, "ui": ui,
            "data": {"enchantments": {"burn": {"name": "Опік"}}}}


def test_english_is_bundled_and_cannot_be_removed():
    from game.remote_content import packs
    assert packs.is_installed("en")
    assert packs.remove("en") is False


def test_install_writes_both_files_and_records_revision(isolated_home):
    from game.remote_content import packs
    assert packs.install("uk", _pack_payload(), revision=3)
    directory = isolated_home / packs.PACKS_DIRNAME
    assert (directory / "uk.json").exists()
    assert (directory / "data_uk.json").exists()
    assert packs.installed_revision("uk") == 3


def test_install_restores_the_nested_shape(isolated_home):
    """enchant_names and help_sections must come back as dict/list, not paths."""
    from game.remote_content import packs
    packs.install("uk", _pack_payload(), revision=1)
    with open(isolated_home / packs.PACKS_DIRNAME / "uk.json", encoding="utf-8") as fh:
        document = json.load(fh)
    assert isinstance(document["enchant_names"], dict)
    assert isinstance(document["help_sections"], list)
    assert isinstance(document["help_sections"][0], list)


def test_pack_for_the_wrong_language_is_refused():
    from game.remote_content import packs
    payload = _pack_payload(lang="uk")
    assert packs.validate_pack(payload, "de") == (None, None)


def test_pack_missing_a_half_is_refused():
    from game.remote_content import packs
    payload = _pack_payload()
    del payload["data"]
    assert packs.validate_pack(payload, "uk") == (None, None)


def test_mostly_broken_pack_is_refused_wholesale():
    """A pack is a whole language: losing most of it must not install."""
    from game.remote_content import packs
    payload = _pack_payload()
    payload["ui"] = {"greeting_that_does_not_exist": "x"}
    assert packs.validate_pack(payload, "uk") == (None, None)


def test_remove_makes_a_language_uninstalled(isolated_home):
    from game.remote_content import packs
    packs.install("uk", _pack_payload(), revision=1)
    assert (isolated_home / packs.PACKS_DIRNAME / "uk.json").exists()
    packs.remove("uk")
    assert not (isolated_home / packs.PACKS_DIRNAME / "uk.json").exists()


def test_pack_status_reports_updates(isolated_home, monkeypatch):
    import game.remote_content as rc
    from game.remote_content import packs
    packs.install("uk", _pack_payload(), revision=1)
    _cache.write(rc.MANIFEST_CACHE, {
        "schema": _manifest.SCHEMA,
        "entries": {"pack.uk": {"path": "packs/uk.v2.json", "revision": 2}},
    })
    # resolve() finds the repo's bundled copies during development, so pin the
    # lookup to the packs directory for this assertion.
    monkeypatch.setattr(packs, "resolve",
                        lambda name: str(isolated_home / packs.PACKS_DIRNAME / name)
                        if (isolated_home / packs.PACKS_DIRNAME / name).exists() else None)
    assert rc.pack_status("uk") == rc.UPDATE_AVAILABLE
    assert rc.pack_status("en") == rc.BUNDLED
    assert rc.pack_status("de") == rc.UNAVAILABLE


# ---------------------------------------------------------------- transport

def test_fetch_reports_progress_and_respects_a_declared_size(monkeypatch):
    from game.remote_content import _http
    body = json.dumps({"ok": True}).encode("utf-8") + b" " * 40000
    seen = []

    class Resp:
        def __init__(self):
            self._rest = body
            self.headers = {"Content-Length": str(len(body))}

        def read(self, n=-1):
            chunk, self._rest = self._rest[:n], self._rest[n:]
            return chunk

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(_http.urllib.request, "urlopen", lambda *a, **k: Resp())
    parsed = _http.fetch_json("https://x/y.json",
                              on_bytes=lambda got, tot: seen.append((got, tot)))
    assert parsed == {"ok": True}
    # More than one report, or the bar would jump straight from 0 to done.
    assert len(seen) > 1
    assert seen[-1] == (len(body), len(body))


def test_fetch_rejects_an_oversized_body_declared_up_front(monkeypatch):
    from game.remote_content import _http

    class Resp:
        headers = {"Content-Length": "999999999"}

        def read(self, n=-1):
            pytest.fail("body must not be read once the declared size is over the cap")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(_http.urllib.request, "urlopen", lambda *a, **k: Resp())
    assert _http.fetch_json("https://x/y.json", max_bytes=1024) is None


def test_fetch_rejects_an_undeclared_body_that_overruns(monkeypatch):
    """A lying or silent server is caught by counting bytes as they arrive."""
    from game.remote_content import _http

    class Resp:
        headers = {}

        def read(self, n=-1):
            return b"x" * (n or 1024)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(_http.urllib.request, "urlopen", lambda *a, **k: Resp())
    assert _http.fetch_json("https://x/y.json", max_bytes=8192) is None


# ---------------------------------------------------------------- integration

def test_set_language_falls_back_to_english_not_russian():
    """Russian is a downloadable pack now; only English is guaranteed."""
    import game.localization as loc
    saved = dict(loc._LANG_DATA)
    try:
        loc._LANG_DATA.clear()
        loc._LANG_DATA["en"] = {"plain": "Forge"}
        loc.set_language("ru")
        assert loc.get_language() == "en"
        loc.set_language("en")
        assert loc.get_language() == "en"
    finally:
        loc._LANG_DATA.clear()
        loc._LANG_DATA.update(saved)
        loc.set_language("ru")


def test_load_languages_reads_installed_packs_and_skips_data_files(isolated_home):
    """A downloaded pack becomes selectable; its data_ half is not a language."""
    import game.localization as loc
    from game.remote_content import packs

    directory = isolated_home / packs.PACKS_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "zz.json").write_text(json.dumps({"plain": "Кузня"}),
                                       encoding="utf-8")
    (directory / "data_zz.json").write_text(json.dumps({"enchantments": {}}),
                                            encoding="utf-8")

    saved = dict(loc._LANG_DATA)
    try:
        loc._LANG_DATA.clear()
        loc.load_languages(force=True)
        assert "zz" in loc._LANG_DATA, "pack in the packs directory must load"
        assert "data_zz" not in loc._LANG_DATA, "data_ files are not languages"
        assert "en" in loc._LANG_DATA, "bundled English must still load"
    finally:
        loc._LANG_DATA.clear()
        loc._LANG_DATA.update(saved)
        loc.set_language("ru")


def test_bundled_english_is_not_shadowed_by_a_pack(isolated_home):
    """resolve() is bundled-first so t()'s terminal fallback cannot be replaced."""
    from game.remote_content import packs
    directory = isolated_home / packs.PACKS_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "en.json").write_text('{"plain": "hijacked"}', encoding="utf-8")
    resolved = packs.resolve("en.json")
    assert resolved is not None
    assert packs.PACKS_DIRNAME not in resolved
