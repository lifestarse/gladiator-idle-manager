"""
In-App Purchase module.

Products:
- remove_ads: Remove all ads — 100 UAH (~$2.50)
- vip_idle: 1.5x passive income forever — 100 UAH (~$2.50)

On Android: uses Google Play Billing via pyjnius
On iOS: uses StoreKit via pyobjus
On desktop: stub mode (purchases always succeed for testing)
"""

from kivy.utils import platform


# --- Product definitions ---
PRODUCTS = {
    "remove_ads": {
        "id": "com.gladiator.remove_ads",
        "name": "Remove Ads",
        "desc": "Remove all banner & interstitial ads forever",
        "price": "100 UAH",
        "price_usd": "$2.50",
    },
    "vip_idle": {
        "id": "com.gladiator.vip_idle",
        "name": "VIP: 1.5x Income",
        "desc": "Permanently boost passive income by 50%",
        "price": "100 UAH",
        "price_usd": "$2.50",
    },
}


class IAPManager:
    """Cross-platform IAP handler."""

    def __init__(self):
        self._billing = None
        self._initialized = False
        self._purchase_callbacks = {}

    def init(self):
        if platform == "android":
            self._init_android()
        elif platform == "ios":
            self._init_ios()
        else:
            print("[IAP] Desktop stub mode — purchases auto-succeed")
            self._initialized = False

    def _init_android(self):
        """Initialize Google Play Billing."""
        try:
            from jnius import autoclass
            # Google Play Billing Library
            BillingClient = autoclass("com.android.billingclient.api.BillingClient")
            print("[IAP] Android billing initialized")
            self._initialized = True
        except Exception as e:
            print(f"[IAP] Android billing init failed: {e}")
            self._initialized = False

    def _init_ios(self):
        """Initialize StoreKit."""
        try:
            from pyobjus import autoclass as objc_autoclass
            print("[IAP] iOS StoreKit initialized")
            self._initialized = True
        except Exception as e:
            print(f"[IAP] iOS StoreKit init failed: {e}")
            self._initialized = False

    def purchase(self, product_key, on_success, on_failure=None):
        """
        Initiate purchase flow.
        product_key: "remove_ads" or "vip_idle"
        on_success: callback() on successful purchase
        on_failure: callback(reason) on failure
        """
        product = PRODUCTS.get(product_key)
        if not product:
            if on_failure:
                on_failure("Unknown product")
            return

        if not self._initialized:
            # Stub mode — auto succeed
            print(f"[IAP] Stub purchase: {product_key}")
            if on_success:
                on_success()
            return

        if platform == "android":
            self._purchase_android(product, on_success, on_failure)
        elif platform == "ios":
            self._purchase_ios(product, on_success, on_failure)

    def _purchase_android(self, product, on_success, on_failure):
        try:
            from jnius import autoclass
            # In production, use BillingClient.launchBillingFlow()
            # This is a simplified version — full implementation requires
            # PurchasesUpdatedListener and async handling
            print(f"[IAP] Launching Android purchase for {product['id']}")
            # TODO: Implement full Google Play Billing flow
            # For now, this is a placeholder
            if on_success:
                on_success()
        except Exception as e:
            if on_failure:
                on_failure(str(e))

    def _purchase_ios(self, product, on_success, on_failure):
        try:
            print(f"[IAP] Launching iOS purchase for {product['id']}")
            # TODO: Implement full StoreKit flow
            if on_success:
                on_success()
        except Exception as e:
            if on_failure:
                on_failure(str(e))

    def restore_purchases(self, on_restored):
        """
        Restore previously purchased items.
        on_restored: callback(list_of_product_keys)
        """
        if not self._initialized:
            print("[IAP] Stub: nothing to restore")
            on_restored([])
            return

        # TODO: Query store for previous purchases
        # and call on_restored with list of product keys
        on_restored([])

    def get_products(self):
        return PRODUCTS


# Singleton
iap_manager = IAPManager()
