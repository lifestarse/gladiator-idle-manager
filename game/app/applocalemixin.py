# Build: 6
"""App _AppLocaleMixin."""
from game.app._shared import *  # noqa: F401,F403


class _AppLocaleMixin:
    def _init_locale_strings(self):
        self.nav_pit = t("nav_pit")
        self.nav_squad = t("nav_squad")
        self.nav_anvil = t("nav_anvil")
        self.nav_hunts = t("nav_hunts")
        self.nav_lore = t("nav_lore")
        self.nav_more = t("nav_more")
        self.title_pit = t("title_pit")
        self.title_squad = t("title_squad")
        self.title_anvil = t("title_anvil")
        self.title_hunts = t("title_hunts")
        self.title_lore = t("title_lore")
        self.title_more = t("title_more")
        self.title_scripts = t("title_scripts")
        self.scr_new_btn = t("scr_new_btn")
        self.scr_tmpl_btn = t("scr_tmpl_btn")
        self.scr_export_all_btn = t("scr_export_all_btn")
        self.scr_import_btn = t("scr_import_btn")
        self.scr_run_btn = t("scr_run_btn")
        self.scr_log_btn = t("scr_log_btn")
        self.scr_tab_all = t("scr_tab_all")
        self.scr_tab_running = t("scr_tab_running")
        self.scr_stop_btn = t("scr_stop_btn")
        self.scr_undo_btn = t("scr_undo_btn")
        self.scr_redo_btn = t("scr_redo_btn")
        self.scr_online_btn = t("scr_online_btn")
        self.lbl_vs = t("vs")
        self.lbl_auto = t("btn_auto")
        self.lbl_stop = t("btn_stop")
        self.lbl_locked_lv = t("locked_lv")
        self.lbl_back_btn = t("back_btn")
        self.lbl_boss = t("btn_boss")
        self.lbl_next = t("btn_next")
        self.lbl_skip = t("btn_skip")
        self.lbl_achievements = t("achievements_label")
        self.lbl_diamond_shop = t("diamond_shop_label")
        self.lbl_stats = t("stats_label")
        self.lbl_quests = t("quests_label")
        self.lbl_tab_missions = t("tab_missions")
        self.lbl_tab_hunts = t("tab_hunts")
        self.lbl_scripts = t("scripts_btn")
        self.lbl_restore_purchases = t("restore_purchases")
        self.lbl_cloud_save = t("cloud_save")
        self.lbl_sign_in_google = t("sign_in_google")
        self.lbl_sign_out_google = t("sign_out_google")
        self.lbl_save_to_cloud = t("save_to_cloud")
        self.lbl_load_from_cloud = t("load_from_cloud")
        self.lbl_language = t("language")
        self.lbl_change_language = t("change_language")
        self.lbl_sound_volume = t("sound_volume")
        self.lbl_heal_all_injuries = t("heal_all_injuries")
        self.lbl_recruit_fighter = t("recruit_fighter_btn")
        self.lbl_remove_ads = t("remove_ads_label")
        self.lbl_remove_ads_buy = t("remove_ads_buy")
        self.lbl_leaderboard = t("leaderboard_title")
        self.lbl_view_leaderboard = t("view_leaderboard")
        self.lbl_tab_weapon = t("tab_weapon")
        self.lbl_tab_armor = t("tab_armor")
        self.lbl_tab_accessory = t("tab_accessory")
        self.lbl_tab_enchant = t("tab_enchant")
        self.lbl_common = t("btn_common")
        self.lbl_help = t("help_title")
        self.lbl_buy_diamonds = t("buy_diamonds_label")

    def _maybe_show_language_picker(self, dt=None):
        """On a brand-new install, block with a mandatory language choice.

        Only English ships in the APK, so most choices download a pack first;
        the shared picker owns that flow and calls back only once the language
        is actually on the device. Later switches go through the More tab
        (game.screens.more.helpmixin._HelpMixin.show_language_picker), which
        uses the same widget.
        """
        if not getattr(self.engine, "_is_first_launch", False):
            self._ensure_saved_language_present()
            return
        from game.ui_helpers import open_language_picker
        open_language_picker(self._finish_first_launch, mandatory=True)

    def _ensure_saved_language_present(self, dt=None):
        """A returning player's saved language may not be in this APK.

        Before packs, every language was bundled. After the change, updating
        the app removes all of them but English, so a Russian player would open
        the game and find it in English with no explanation. Fetch the pack
        first, showing the same progress UI, and only then build the strings.
        Offline, the game runs in English and retries on the next launch —
        the alternative is refusing to start, which is worse.
        """
        # Requested, not active: when the pack is missing, set_language()
        # already fell back to "en" during engine.load(), so get_language()
        # would report the fallback and this check would never fire.
        lang = get_requested_language()
        from game.remote_content import packs
        if lang in packs.BUNDLED_LANGS or packs.is_installed(lang):
            return
        from game.ui_helpers import open_language_pack_fetch
        open_language_pack_fetch(lang, on_done=self._apply_language_now)

    def _apply_language_now(self, lang_code):
        """Re-read data for a language that is now present, and repaint."""
        from game.localization import load_languages
        from game.data_loader import data_loader
        from game.engine import GameEngine
        # Reload BEFORE selecting: the pack landed on disk after the initial
        # load, so set_language() would not find the code yet and would fall
        # back to English.
        load_languages(force=True)
        set_language(lang_code)
        data_loader._loaded = False
        data_loader.load_all()
        data_loader.apply_translations(lang_code)
        GameEngine._wire_data()
        self._init_locale_strings()

    def _finish_first_launch(self, lang_code):
        self._apply_language_now(lang_code)
        self.engine._migrate_all_items()
        self.engine._is_first_launch = False
        self.engine.save()
