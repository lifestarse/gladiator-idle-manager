# Build: 1
"""IAPManager core."""
from ._shared import *  # noqa: F401,F403
from ._shared import _log
from .iapandroidmixin import _IapAndroidMixin
from .iapiosmixin import _IapIosMixin


class IAPManager(_IapAndroidMixin, _IapIosMixin):
    def __init__(self):
        self._billing_client = None
        self._initialized = False
        self._purchase_callbacks = {}  # product_id -> (on_success, on_failure)
        self._product_details = {}     # product_id -> ProductDetails Java object
        self._pending_purchase = None
        # iOS
        self._payment_queue = None
        self._ios_observer = None

    def init(self):
        if platform == "android":
            self._init_android()
        elif platform == "ios":
            self._init_ios()
        else:
            _log.info("[IAP] Desktop stub mode — purchases auto-succeed")
            self._initialized = False

    def purchase(self, product_key, on_success, on_failure=None):
        """
        Initiate purchase flow.
        product_key: "remove_ads"
        on_success: callback() on successful purchase
        on_failure: callback(reason) on failure
        """
        product = PRODUCTS.get(product_key)
        if not product:
            if on_failure:
                on_failure("Unknown product")
            return

        if not self._initialized:
            # Stub mode — auto succeed (desktop testing)
            _log.info("[IAP] Stub purchase: %s", product_key)
            if on_success:
                on_success()
            return

        # Store callbacks
        self._purchase_callbacks[product_key] = (on_success, on_failure)
        self._pending_purchase = product_key

        if platform == "android":
            self._purchase_android(product, on_success, on_failure)
        elif platform == "ios":
            self._purchase_ios(product, on_success, on_failure)

    def restore_purchases(self, on_restored):
        """
        Restore previously purchased items.
        on_restored: callback(list_of_product_keys)
        """
        if not self._initialized:
            _log.info("[IAP] Stub: nothing to restore")
            on_restored([])
            return

        if platform == "android":
            self._restore_android(on_restored)
        elif platform == "ios":
            self._restore_ios(on_restored)
        else:
            on_restored([])

    def get_products(self):
        return PRODUCTS
