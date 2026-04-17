# Build: 1
"""MoreScreen _HelpMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _HelpMixin:
    def show_help(self):
        """Show help popup with all game mechanics explained."""
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        content = BoxLayout(orientation="vertical", size_hint_y=None,
                            padding=[dp(12), dp(8)], spacing=dp(6))
        content.bind(minimum_height=content.setter("height"))

        sections = t("help_sections")
        for title, body in sections:
            content.add_widget(AutoShrinkLabel(
                text=title, font_size="11sp", bold=True,
                color=ACCENT_GOLD, halign="left",
                size_hint_y=None, height=dp(28),
            ))
            lbl = AutoShrinkLabel(
                text=body, font_size="11sp",
                color=TEXT_SECONDARY, halign="left", valign="top",
                markup=True, size_hint_y=None,
            )
            lbl.bind(width=lambda inst, w: setattr(inst, 'text_size', (w, None)))
            lbl.bind(texture_size=lambda inst, ts: setattr(inst, 'height', ts[1] + dp(8)))
            content.add_widget(lbl)

        scroll.add_widget(content)
        popup = Popup(
            title=t("help_title"),
            title_color=popup_color(ACCENT_GOLD),
            title_size=sp(12),
            content=scroll,
            size_hint=(0.95, 0.85),
            background_color=popup_color(BG_CARD),
            separator_color=popup_color(ACCENT_GOLD),
            auto_dismiss=True,
        )
        popup.open()

    def show_language_picker(self):
        languages = [("English", "en"), ("Русский", "ru")]
        current = get_language()
        content = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        popup = Popup(
            title=t("language"),
            content=content,
            size_hint=(0.85, 0.4),
            background_color=popup_color(BG_CARD),
            title_color=popup_color(ACCENT_GOLD),
            separator_color=popup_color(ACCENT_GOLD),
        )
        for name, code in languages:
            is_current = code == current
            btn = MinimalButton(
                text=f"{'> ' if is_current else ''}{name}",
                size_hint_y=None, height=dp(44),
                btn_color=ACCENT_GOLD if is_current else ACCENT_BLUE,
                font_size=sp(9),
            )
            btn.bind(on_press=lambda inst, c=code, p=popup: self._set_language(c, p))
            content.add_widget(btn)
        popup.open()

    def _set_language(self, lang_code, popup):
        popup.dismiss()
        set_language(lang_code)
        from game.data_loader import data_loader
        from game.engine import GameEngine
        data_loader._loaded = False
        data_loader.load_all()
        data_loader.apply_translations(lang_code)
        GameEngine._wire_data()
        # Explicitly migrate inventory + equipment so item names update to the
        # new language immediately. (save() no longer migrates — see engine.save
        # note about detached UI references breaking upgrade-many-times.)
        App.get_running_app().engine._migrate_all_items()
        App.get_running_app().engine.save()
        App.get_running_app()._init_locale_strings()
        self.refresh_more()
