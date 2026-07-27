# Build: 2
"""Tests for remote font delivery and the manifest-driven language list.

A font is a binary handed to a native renderer, so the failure modes worth
testing are the hostile ones: wrong hash, not-a-font body, corrupt file on
disk, a pack that must not install without its font. And the picker list is
what lets a language ship without a Play release, so the merge rules are
load-bearing, not cosmetic.
"""
import hashlib
import io
import json

import pytest

from game.remote_content import _cache, _http, _manifest, packs


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Point Path.home() at a scratch dir and reset the module memo."""
    import pathlib
    import game.remote_content as rc
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(rc, "_enabled", None)
    yield tmp_path
    monkeypatch.setattr(rc, "_enabled", None)


# TTF magic + filler: enough to pass the file-type check, nothing more.
FONT_BODY = b"\x00\x01\x00\x00" + b"fake-glyph-tables" * 10
FONT_SHA = hashlib.sha256(FONT_BODY).hexdigest()


def font_entry(revision=1, path="fonts/test.ttf", sha=FONT_SHA, size=None):
    font = {"path": path, "sha256": sha}
    if size is not None:
        font["bytes"] = size
    return {"path": "packs/tr.v1.json", "revision": revision, "font": font}


class _FakeResp:
    def __init__(self, body, declared_length=True):
        self._stream = io.BytesIO(body)
        self.headers = {"Content-Length": str(len(body))} if declared_length else {}

    def read(self, n):
        return self._stream.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


# ------------------------------------------------------------- fetch_bytes

def test_fetch_bytes_returns_body_when_sha_matches(monkeypatch):
    monkeypatch.setattr(_http.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(FONT_BODY))
    assert _http.fetch_bytes("https://x/f.ttf", sha256=FONT_SHA) == FONT_BODY


def test_fetch_bytes_rejects_sha_mismatch(monkeypatch):
    monkeypatch.setattr(_http.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(FONT_BODY))
    assert _http.fetch_bytes("https://x/f.ttf", sha256="0" * 64) is None


def test_fetch_bytes_enforces_the_cap_mid_read(monkeypatch):
    # No Content-Length, so the cap must trip during the read itself.
    body = b"x" * 4096
    monkeypatch.setattr(_http.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(body, declared_length=False))
    assert _http.fetch_bytes("https://x/f.ttf", max_bytes=1024) is None


class _TruncatedResp(_FakeResp):
    """A server that declares a length and then closes mid-body."""

    def read(self, n):
        import http.client
        raise http.client.IncompleteRead(b"partial", 500)


def test_fetch_survives_a_body_cut_short(monkeypatch):
    """IncompleteRead is an HTTPException, not an OSError — urllib does not
    wrap it, so an unguarded except list lets it escape and kill the worker
    thread, freezing the picker row it was downloading."""
    monkeypatch.setattr(_http.urllib.request, "urlopen",
                        lambda *a, **k: _TruncatedResp(FONT_BODY))
    assert _http.fetch_bytes("https://x/f.ttf") is None
    assert _http.fetch_json("https://x/f.json") is None


# ------------------------------------------------------- manifest extensions

def _validated(entry):
    return _manifest.validate({"schema": 1, "entries": {"pack.tr": entry}})


def test_manifest_passes_font_and_name_through():
    entry = font_entry(size=123)
    entry["name"] = "Türkçe"
    usable = _validated(entry)
    assert usable["pack.tr"]["font"] == {"path": "fonts/test.ttf",
                                         "sha256": FONT_SHA, "bytes": 123}
    assert usable["pack.tr"]["name"] == "Türkçe"


def test_manifest_drops_the_whole_entry_on_a_bad_font_hash():
    # The language cannot render without its font — a half-valid entry would
    # install a pack that shows tofu, which is worse than no entry.
    assert _validated(font_entry(sha="not-hex")) == {}


def test_manifest_drops_the_entry_on_a_climbing_font_path():
    assert _validated(font_entry(path="../../etc/evil.ttf")) == {}


def test_manifest_ignores_an_oversized_display_name():
    entry = {"path": "packs/tr.v1.json", "revision": 1, "name": "x" * 41}
    assert "name" not in _validated(entry)["pack.tr"]


def test_manifest_drops_a_font_path_with_no_filename():
    # "fonts/" survives the traversal check but basenames to "" — which would
    # resolve back to the fonts directory and install a pack with no font.
    assert _validated(font_entry(path="fonts/")) == {}
    assert _validated(font_entry(path="fonts/sub/")) == {}


def test_manifest_rejects_a_language_code_that_could_steer_a_path():
    """The picker's language list is remote input now, and a code becomes a
    filename (<code>.json) under the packs dir."""
    hostile = {"schema": 1, "entries": {
        "pack.../../.gladiator_idle_save": {"path": "packs/evil.v1.json",
                                            "revision": 1, "name": "Türkçe"},
        "pack.a/b": {"path": "packs/evil.v1.json", "revision": 1},
        "pack.": {"path": "packs/evil.v1.json", "revision": 1},
        "pack.TR": {"path": "packs/evil.v1.json", "revision": 1},
        "pack.tr": {"path": "packs/tr.v1.json", "revision": 1},
    }}
    usable = _manifest.validate(hostile)
    assert list(usable) == ["pack.tr"]


def test_manifest_rejects_a_lang_patch_with_a_hostile_code():
    hostile = {"schema": 1, "entries": {
        "lang.../evil": {"path": "evil.v1.json", "revision": 1}}}
    assert _manifest.validate(hostile) == {}


# ------------------------------------------------------------- ensure_font

def test_ensure_font_downloads_verifies_and_records(monkeypatch):
    monkeypatch.setattr(packs._http, "fetch_bytes",
                        lambda url, **k: FONT_BODY)
    assert packs.ensure_font("tr", "https://x/", font_entry()) is True
    installed = packs.verified_font_path("tr")
    assert installed is not None and installed.read_bytes() == FONT_BODY
    # Content-addressed: the store name is the hash, never the remote name.
    assert installed.name == f"{FONT_SHA}.ttf"
    # Second call is a quiet no-op — no re-download.
    monkeypatch.setattr(packs._http, "fetch_bytes",
                        lambda url, **k: pytest.fail("must not re-download"))
    assert packs.ensure_font("tr", "https://x/", font_entry()) is True


def test_ensure_font_is_true_when_no_font_is_declared():
    assert packs.ensure_font("de", "https://x/",
                             {"path": "packs/de.v1.json", "revision": 1}) is True


def test_ensure_font_rejects_a_body_that_is_not_a_font(monkeypatch):
    body = b"<html>404</html>"
    sha = hashlib.sha256(body).hexdigest()
    monkeypatch.setattr(packs._http, "fetch_bytes", lambda url, **k: body)
    assert packs.ensure_font("tr", "https://x/", font_entry(sha=sha)) is False
    assert packs.verified_font_path("tr") is None


def test_download_refuses_the_pack_when_its_font_fails(monkeypatch):
    monkeypatch.setattr(packs._net, "is_online", lambda: True)
    monkeypatch.setattr(packs._http, "fetch_bytes", lambda url, **k: None)
    monkeypatch.setattr(packs._http, "fetch_json",
                        lambda url, **k: pytest.fail(
                            "pack must not download when its font failed"))
    assert packs.download("tr", "https://x/", font_entry()) is False
    assert not packs.is_installed("tr")


def test_verified_font_path_drops_a_corrupt_file():
    packs.fonts_dir().joinpath("test.ttf").write_bytes(b"rotted")
    packs._record_font("tr", "test.ttf", FONT_SHA)
    assert packs.verified_font_path("tr") is None
    assert not (packs.fonts_dir() / "test.ttf").exists()
    assert packs._fonts_state() == {}


def test_remove_forgets_the_font_and_gcs_an_unreferenced_file():
    directory = packs.packs_dir()
    (directory / "tr.json").write_text("{}", encoding="utf-8")
    (directory / "data_tr.json").write_text("{}", encoding="utf-8")
    packs.fonts_dir().joinpath("test.ttf").write_bytes(FONT_BODY)
    packs._record_font("tr", "test.ttf", FONT_SHA)
    packs.remove("tr")
    assert packs._fonts_state() == {}
    assert not (packs.fonts_dir() / "test.ttf").exists()


def test_remove_keeps_a_font_another_language_still_uses():
    packs.fonts_dir().joinpath("shared.ttf").write_bytes(FONT_BODY)
    packs._record_font("tr", "shared.ttf", FONT_SHA)
    packs._record_font("az", "shared.ttf", FONT_SHA)
    packs.remove("tr")
    assert "az" in packs._fonts_state()
    assert (packs.fonts_dir() / "shared.ttf").exists()


def test_two_languages_declaring_the_same_filename_do_not_poison_each_other(monkeypatch):
    """Content addressing: same published name, different bytes, both usable."""
    other_body = b"\x00\x01\x00\x00" + b"a-different-font" * 10
    other_sha = hashlib.sha256(other_body).hexdigest()
    monkeypatch.setattr(packs._http, "fetch_bytes", lambda url, **k: FONT_BODY)
    assert packs.ensure_font("tr", "https://x/", font_entry()) is True
    monkeypatch.setattr(packs._http, "fetch_bytes", lambda url, **k: other_body)
    # Same remote path "fonts/test.ttf", different content.
    assert packs.ensure_font("az", "https://x/", font_entry(sha=other_sha)) is True

    tr_path, az_path = packs.verified_font_path("tr"), packs.verified_font_path("az")
    assert tr_path is not None and az_path is not None
    assert tr_path.read_bytes() == FONT_BODY
    assert az_path.read_bytes() == other_body


def test_rotating_to_a_new_font_collects_the_old_file(monkeypatch):
    """publish_content mandates a new filename per font revision, so the
    upgrade path must not leave the old megabytes on the device forever."""
    new_body = b"\x00\x01\x00\x00" + b"v2-font" * 20
    new_sha = hashlib.sha256(new_body).hexdigest()
    monkeypatch.setattr(packs._http, "fetch_bytes", lambda url, **k: FONT_BODY)
    packs.ensure_font("tr", "https://x/", font_entry())
    monkeypatch.setattr(packs._http, "fetch_bytes", lambda url, **k: new_body)
    packs.ensure_font("tr", "https://x/",
                      font_entry(path="fonts/test.v2.ttf", sha=new_sha))
    assert [p.name for p in packs.fonts_dir().iterdir()] == [f"{new_sha}.ttf"]


def test_font_state_survives_a_corrupt_record():
    """A half-written .fonts.json must degrade to "no font", not raise: this
    runs inside engine.load(), whose blanket handler would quarantine the save."""
    packs.packs_dir().joinpath(packs.FONTS_STATE_NAME).write_text(
        json.dumps({"tr": {"file": 123, "sha256": None}, "az": "nonsense"}),
        encoding="utf-8")
    assert packs._fonts_state() == {}
    assert packs.verified_font_path("tr") is None


# ---------------------------------------------- manifest-driven language list

def _cache_manifest(entries):
    _cache.write("manifest", {"schema": 1, "entries": entries})


def test_offered_languages_extends_from_the_manifest():
    import game.remote_content as rc
    _cache_manifest({
        "pack.tr": {"path": "packs/tr.v1.json", "revision": 1, "name": "Türkçe"},
        "pack.ru": {"path": "packs/ru.v9.json", "revision": 9,
                    "name": "shadowed"},  # already offered: APK name wins
    })
    offered = rc.offered_languages()
    assert offered[:len(packs.OFFERED)] == list(packs.OFFERED)
    assert ("Türkçe", "tr") in offered
    assert sum(1 for _n, code in offered if code == "ru") == 1


def test_offered_languages_falls_back_to_the_code_without_a_name():
    import game.remote_content as rc
    _cache_manifest({"pack.tr": {"path": "packs/tr.v1.json", "revision": 1}})
    assert ("tr", "tr") in rc.offered_languages()


def test_offered_languages_keeps_an_installed_language_without_a_manifest():
    """Safe-mode wipes the manifest cache. An offline player running tr must
    still see their own language in the picker."""
    import game.remote_content as rc
    directory = packs.packs_dir()
    (directory / "tr.json").write_text("{}", encoding="utf-8")
    (directory / "data_tr.json").write_text("{}", encoding="utf-8")
    assert ("tr", "tr") in rc.offered_languages()


def test_pack_statuses_cover_manifest_only_languages():
    import game.remote_content as rc
    _cache_manifest({"pack.tr": {"path": "packs/tr.v1.json", "revision": 1,
                                 "name": "Türkçe"}})
    statuses = rc.pack_statuses()
    assert statuses["tr"] == rc.NOT_INSTALLED
    assert statuses["en"] == rc.BUNDLED


def test_installed_codes_on_disk_requires_the_full_pair():
    directory = packs.packs_dir()
    (directory / "tr.json").write_text("{}", encoding="utf-8")
    (directory / "data_tr.json").write_text("{}", encoding="utf-8")
    (directory / "az.json").write_text("{}", encoding="utf-8")  # data half missing
    (directory / ".revisions.json").write_text("{}", encoding="utf-8")
    assert packs.installed_codes_on_disk() == {"tr"}


# ------------------------------------------------------- font registration

def test_set_language_registers_the_downloaded_font(monkeypatch):
    import game.localization as loc
    packs.fonts_dir().joinpath("test.ttf").write_bytes(FONT_BODY)
    packs._record_font("tr", "test.ttf", FONT_SHA)
    monkeypatch.setattr(loc, "_LANG_DATA", {"en": {}, "tr": {}})
    monkeypatch.setattr(loc, "_current_lang", "en")
    monkeypatch.setattr(loc, "_requested_lang", None)
    registered = {}
    monkeypatch.setattr(loc, "_register_fonts", registered.update)

    loc.set_language("tr")
    expected = str(packs.fonts_dir() / "test.ttf")
    assert registered == {"PixelFont": expected, "BodyFont": expected}

    loc.set_language("en")
    assert registered == loc._BUNDLED_FONT_FILES


def test_fallback_to_english_uses_the_bundled_fonts(monkeypatch):
    # Requested language has a font on disk but its pack is not loaded: the
    # ACTIVE language is the en fallback, and en must render in bundled fonts.
    import game.localization as loc
    packs.fonts_dir().joinpath("test.ttf").write_bytes(FONT_BODY)
    packs._record_font("tr", "test.ttf", FONT_SHA)
    monkeypatch.setattr(loc, "_LANG_DATA", {"en": {}})
    monkeypatch.setattr(loc, "_current_lang", "en")
    monkeypatch.setattr(loc, "_requested_lang", None)
    registered = {}
    monkeypatch.setattr(loc, "_register_fonts", registered.update)

    loc.set_language("tr")
    assert loc.get_language() == "en"
    assert registered == loc._BUNDLED_FONT_FILES
