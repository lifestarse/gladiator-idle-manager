# Build: 1
"""MoreScreen _IapMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _IapMixin:
    def _refresh_diamond_bundles(self):
        grid = self.ids.get("diamond_bundles_grid")
        if not grid:
            return
        # Static data — build once, reuse forever
        if getattr(self, '_bundle_cards', None):
            _batch_fill_grid(grid, self._bundle_cards)
            return
        cards = []
        for bundle in DIAMOND_BUNDLES:
            row = BaseCard(orientation="horizontal", size_hint_y=None, height=dp(48),
                           padding=[dp(10), dp(4)], spacing=dp(6))
            row.border_color = ACCENT_CYAN
            # Left side: count label tight against a gem icon — no bonus
            # suffix ("+10%" etc.) so the pure diamond quantity is the
            # only thing shown next to the gem. AnchorLayout centres the
            # pair in the left half of the card; shrink the label to its
            # texture width so the icon always sits right beside it.
            from kivy.uix.anchorlayout import AnchorLayout
            left_anchor = AnchorLayout(anchor_x="center", anchor_y="center",
                                        size_hint_x=0.5)
            pair = BoxLayout(orientation="horizontal",
                             size_hint=(None, None), spacing=dp(6))
            count_lbl = row._make_label(
                str(bundle['diamonds']), sp(11), True, ACCENT_CYAN,
                "right", None,
            )
            count_lbl.size_hint_x = None
            count_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
            pair.add_widget(count_lbl)
            gem = Image(
                source="sprites/icons/ic_gem.png", fit_mode="contain",
                size_hint=(None, None), width=dp(20), height=dp(20),
                pos_hint={'center_y': 0.5},
            )
            pair.add_widget(gem)
            pair.bind(minimum_width=pair.setter('width'))
            pair.height = dp(40)
            left_anchor.add_widget(pair)
            row.add_widget(left_anchor)
            buy_btn = MinimalButton(
                text=t("buy_btn"), font_size=11, size_hint_x=0.5,
                btn_color=ACCENT_CYAN, text_color=BG_DARK,
            )
            def _buy(inst, bid=bundle["id"]):
                self.buy_diamonds(bid)
            buy_btn.bind(on_press=_buy)
            row.add_widget(buy_btn)
            cards.append(row)
        self._bundle_cards = cards
        _batch_fill_grid(grid, cards)

    def buy_diamonds(self, bundle_id):
        app = App.get_running_app()
        engine = app.engine
        def on_success():
            result = engine.purchase_diamonds(bundle_id)
            # Async save — previously blocked the main thread for ~300-500ms
            # on desktop and multiple seconds on Android while the 8 MB
            # save file was serialized + written. The save snapshot is
            # built synchronously (fast); the JSON + disk write run on a
            # daemon thread. Diamonds and toast appear immediately.
            engine.save_async()
            self.refresh_more()
            app.update_top_bar()
            if result.message:
                app.show_toast(result.message)
        iap_manager.purchase(bundle_id, on_success)

    def buy_remove_ads(self):
        engine = App.get_running_app().engine
        def on_success():
            engine.purchase_remove_ads()
            ad_manager.hide_banner()
            engine.save_async()
            self.refresh_more()
        iap_manager.purchase("remove_ads", on_success)

    def restore_purchases(self):
        engine = App.get_running_app().engine
        def on_restored(product_keys):
            engine.restore_purchases(product_keys)
            if engine.ads_removed:
                ad_manager.hide_banner()
            engine.save_async()
            self.refresh_more()
        iap_manager.restore_purchases(on_restored)
