# Build: 1
"""LoreScreen _DiamondsMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _DiamondsMixin:
    def buy_diamond_item(self, item_id):
        app = App.get_running_app()
        result = app.engine.buy_diamond_item(item_id)
        if result.code == "name_change":
            self._show_rename_popup()
            return
        if not result.ok and result.message:
            app.show_toast(result.message)
        self.refresh_lore()

    def _show_rename_popup(self):
        """Popup: select fighter → enter new name → confirm."""

        engine = App.get_running_app().engine
        fighters = [(i, f) for i, f in enumerate(engine.fighters) if f.alive]
        if not fighters:
            return

        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=[dp(12), dp(8)])

        # Fighter selector buttons
        selected = {"idx": fighters[0][0]}
        btn_refs = []
        selector = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
        for i, f in fighters:
            btn = MinimalButton(
                text=f.name, font_size=11,
                btn_color=ACCENT_GOLD if i == selected["idx"] else BTN_DISABLED,
            )
            def on_select(inst, idx=i):
                selected["idx"] = idx
                for b, (bi, _) in zip(btn_refs, fighters):
                    b.btn_color = ACCENT_GOLD if bi == idx else BTN_DISABLED
                name_input.text = engine.fighters[idx].name
            btn.bind(on_press=on_select)
            btn_refs.append(btn)
            selector.add_widget(btn)
        content.add_widget(selector)

        # Text input
        name_input = TextInput(
            text=engine.fighters[selected["idx"]].name,
            font_size=sp(10), multiline=False,
            size_hint_y=None, height=dp(44),
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)],
        )
        content.add_widget(name_input)

        # Confirm button
        popup = Popup(
            title=t("rename_title"),
            title_size=sp(10),
            content=content,
            size_hint=(0.9, 0.38),
            background_color=BG_CARD,
        )
        confirm_btn = MinimalButton(
            text=t("confirm_btn"), font_size=9,
            btn_color=ACCENT_GOLD, size_hint_y=None, height=dp(42),
        )
        def do_rename(inst):
            engine.rename_fighter(selected["idx"], name_input.text)
            popup.dismiss()
            self.refresh_lore()
        confirm_btn.bind(on_press=do_rename)
        content.add_widget(confirm_btn)
        popup.open()
