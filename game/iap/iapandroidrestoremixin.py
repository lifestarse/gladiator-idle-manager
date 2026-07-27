# Build: 4
"""IAPManager _IapAndroidRestoreMixin — query existing purchases."""
from ._shared import *  # noqa: F401,F403
# _PRODUCT_ID_TO_KEY is an underscore name, so `import *` skips it — the
# restore callback below needs it explicitly or it NameErrors on every
# queried purchase (restore-purchases silently broken).
from ._shared import _log, _PRODUCT_ID_TO_KEY


class _IapAndroidRestoreMixin:
    def _restore_android(self, on_restored):
        """Query Google Play for existing purchases."""
        try:
            from jnius import autoclass, PythonJavaClass, java_method

            QueryPurchasesParams = autoclass(
                "com.android.billingclient.api.QueryPurchasesParams"
            )
            ProductType = autoclass(
                "com.android.billingclient.api.BillingClient$ProductType"
            )
            PurchaseState = autoclass(
                "com.android.billingclient.api.Purchase$PurchaseState"
            )

            params = (
                QueryPurchasesParams.newBuilder()
                .setProductType(ProductType.INAPP)
                .build()
            )

            manager = self  # closure ref

            class _PurchasesCb(PythonJavaClass):
                __javainterfaces__ = [
                    "com/android/billingclient/api/PurchasesResponseListener"
                ]
                __javacontext__ = "app"

                @java_method(
                    "(Lcom/android/billingclient/api/BillingResult;"
                    "Ljava/util/List;)V"
                )
                def onQueryPurchasesResponse(
                    self_inner, billing_result, purchases
                ):
                    restored = manager._restore_collect_keys(
                        purchases, PurchaseState
                    )
                    Clock.schedule_once(
                        lambda dt: on_restored(restored), 0
                    )

            self._purchases_cb = _PurchasesCb()
            self._billing_client.queryPurchasesAsync(params, self._purchases_cb)

        except Exception as e:
            _log.error("[IAP] Restore failed: %s", e)
            on_restored([])

    def _restore_collect_keys(self, purchases, purchase_state):
        """Map a queried purchase list to our product keys."""
        restored = []
        try:
            if purchases is None:
                return restored
            for i in range(purchases.size()):
                self._restore_append_purchase_keys(
                    purchases.get(i), purchase_state, restored
                )
        except Exception as e:
            _log.error("[IAP] Error reading purchases: %s", e)
        return restored

    def _restore_append_purchase_keys(self, purchase, purchase_state, restored):
        if purchase.getPurchaseState() != purchase_state.PURCHASED:
            return
        products = purchase.getProducts()
        for j in range(products.size()):
            pid = products.get(j)
            key = _PRODUCT_ID_TO_KEY.get(pid)
            if key:
                restored.append(key)
