# Build: 1
"""ForgeScreen _ShopMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403


class _ShopMixin:
    def buy(self, item_id):
        app = App.get_running_app()
        result = app.engine.buy_forge_item(item_id)
        if result.message:
            app.show_toast(result.message)
        self.refresh_forge()
