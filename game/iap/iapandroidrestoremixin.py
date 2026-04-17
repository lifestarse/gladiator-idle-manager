# Build: 1
"""_IapAndroidMixin _IapAndroidRestoreMixin."""
# Build: 1
"""IAPManager _IapAndroidMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _log


from ._shared import _log

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
                    restored = []
                    try:
                        if purchases is not None:
                            for i in range(purchases.size()):
                                p = purchases.get(i)
                                if p.getPurchaseState() == PurchaseState.PURCHASED:
                                    products = p.getProducts()
                                    for j in range(products.size()):
                                        pid = products.get(j)
                                        key = _PRODUCT_ID_TO_KEY.get(pid)
                                        if key:
                                            restored.append(key)
                    except Exception as e:
                        _log.error("[IAP] Error reading purchases: %s", e)
                    Clock.schedule_once(
                        lambda dt: on_restored(restored), 0
                    )

            self._purchases_cb = _PurchasesCb()
            self._billing_client.queryPurchasesAsync(params, self._purchases_cb)

        except Exception as e:
            _log.error("[IAP] Restore failed: %s", e)
            on_restored([])
