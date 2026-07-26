# Build: 3
"""DataLoader _TranslationMixin — overlays translated text onto loaded data."""
import os

from ._shared import _data_dir, _log


class _TranslationMixin:
    def apply_translations(self, lang_code):
        """Overlay translated name/desc from data/languages/data_{lang}.json.

        Merges translated text into already-loaded data dicts in-place.
        Falls back to original English if translation file is missing.
        """
        if lang_code == "en":
            return
        # Bundled first, then downloaded packs — only English ships in the APK,
        # so for every other language this resolves into the packs directory.
        # A missing file is the normal state for a language the player has not
        # downloaded: the data stays English and the UI says so.
        try:
            from game.remote_content.packs import resolve
            path = resolve(f"data_{lang_code}.json")
        except Exception as exc:  # noqa: BLE001 - fall back to the bundled path
            _log.warning("[DataLoader] pack lookup failed (%s)", exc)
            path = os.path.join(_data_dir(), "languages", f"data_{lang_code}.json")
        tr = self._read_json(path) if path else None
        if not tr:
            _log.info("[DataLoader] No translation file for '%s'", lang_code)
            return

        def _apply_to_list(items, section_tr, skip=()):
            for item in items:
                item_tr = section_tr.get(item.get("id", ""))
                if item_tr:
                    for field in ("name", "desc", "description", "title", "text"):
                        if field in skip:
                            continue
                        if field in item_tr:
                            item[field] = item_tr[field]

        def _apply_to_dict(data, section_tr):
            for key, item in data.items():
                item_tr = section_tr.get(key)
                if item_tr and isinstance(item, dict):
                    for field in ("name", "desc", "description"):
                        if field in item_tr:
                            item[field] = item_tr[field]

        # Equipment — item NAMES stay English by explicit request
        # (descriptions still get translated for flavor). Users prefer
        # seeing "Blade of Ruin", not "Клинок Погибели", so the same
        # label shows up in forge, inventory, fighter card, and log.
        _apply_to_list(self._weapons,     tr.get("weapons", {}),     skip=("name",))
        _apply_to_list(self._armor,       tr.get("armor", {}),       skip=("name",))
        _apply_to_list(self._accessories, tr.get("accessories", {}), skip=("name",))
        _apply_to_list(self._relics,      tr.get("relics", {}),      skip=("name",))
        _apply_to_list(self._achievements, tr.get("achievements", {}))
        _apply_to_list(self._enemies, tr.get("enemies", {}), skip=("name",))
        _apply_to_list(self._injuries, tr.get("injuries", {}))
        _apply_to_list(self._expeditions, tr.get("expeditions", {}))
        _apply_to_list(self._lore, tr.get("lore", {}))
        _apply_to_dict(self._enchantments, tr.get("enchantments", {}))
        _apply_to_dict(self._boss_modifiers, tr.get("boss_modifiers", {}))
        _apply_to_dict(self._mutators, tr.get("mutators", {}))

        classes_tr = tr.get("classes", {})
        for cls_id, cls_data in self._fighter_classes.items():
            cls_tr = classes_tr.get(cls_id)
            if not cls_tr:
                continue
            for field in ("name", "desc", "description"):
                if field in cls_tr:
                    cls_data[field] = cls_tr[field]
            pa_tr = cls_tr.get("passive_ability", {})
            pa = cls_data.get("passive_ability", {})
            for field in ("name", "description"):
                if field in pa_tr:
                    pa[field] = pa_tr[field]
            as_tr = cls_tr.get("active_skill", {})
            ask = cls_data.get("active_skill", {})
            for field in ("name", "description"):
                if field in as_tr:
                    ask[field] = as_tr[field]
            perks_tr = cls_tr.get("perks", {})
            for perk in cls_data.get("perk_tree", []):
                perk_tr = perks_tr.get(perk.get("id", ""))
                if perk_tr:
                    for field in ("name", "description"):
                        if field in perk_tr:
                            perk[field] = perk_tr[field]

        _log.info("[DataLoader] Translations applied for '%s'", lang_code)
