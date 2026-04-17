# Build: 1
"""_IapAndroidMixin _IapAndroidInitMixin."""
# Build: 1
"""IAPManager _IapAndroidMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _log


from ._shared import _log

class _IapAndroidInitMixin:
    def _init_android(self):
        """Initialize Google Play Billing Client."""
        try:
            from jnius import autoclass, PythonJavaClass, java_method

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            BillingClient = autoclass(
                "com.android.billingclient.api.BillingClient"
            )
            BillingClientStateListener = (
                "com.android.billingclient.api.BillingClientStateListener"
            )
            PurchasesUpdatedListener = (
                "com.android.billingclient.api.PurchasesUpdatedListener"
            )
            BillingResponseCode = autoclass(
                "com.android.billingclient.api.BillingClient$BillingResponseCode"
            )

            manager = self  # closure ref

            # --- PurchasesUpdatedListener ---
            class _PurchaseListener(PythonJavaClass):
                __javainterfaces__ = [PurchasesUpdatedListener]
                __javacontext__ = "app"

                @java_method(
                    "(Lcom/android/billingclient/api/BillingResult;"
                    "Ljava/util/List;)V"
                )
                def onPurchasesUpdated(self_inner, billing_result, purchases):
                    try:
                        code = billing_result.getResponseCode()
                    except Exception as e:
                        _log.error("[IAP] onPurchasesUpdated: failed to get response code: %s", e)
                        code = -1
                    Clock.schedule_once(
                        lambda dt: manager._on_purchases_updated(
                            code, purchases
                        ),
                        0,
                    )

            # --- BillingClientStateListener ---
            class _StateListener(PythonJavaClass):
                __javainterfaces__ = [BillingClientStateListener]
                __javacontext__ = "app"

                @java_method(
                    "(Lcom/android/billingclient/api/BillingResult;)V"
                )
                def onBillingSetupFinished(self_inner, billing_result):
                    try:
                        code = billing_result.getResponseCode()
                    except Exception as e:
                        _log.error("[IAP] onBillingSetupFinished: failed to get response code: %s", e)
                        code = -1
                    Clock.schedule_once(
                        lambda dt: manager._on_billing_setup(code), 0
                    )

                @java_method("()V")
                def onBillingServiceDisconnected(self_inner):
                    _log.warning("[IAP] Billing service disconnected")
                    manager._initialized = False

            self._purchase_listener = _PurchaseListener()
            self._state_listener = _StateListener()

            activity = PythonActivity.mActivity
            builder = BillingClient.newBuilder(activity)
            builder.setListener(self._purchase_listener)
            builder.enablePendingPurchases()
            self._billing_client = builder.build()
            self._billing_client.startConnection(self._state_listener)
            _log.info("[IAP] Android billing: connecting...")

        except Exception as e:
            _log.error("[IAP] Android billing init failed: %s", e)
            self._initialized = False

    def _on_billing_setup(self, response_code):
        """Called when billing client is connected."""
        from jnius import autoclass

        OK = autoclass(
            "com.android.billingclient.api.BillingClient$BillingResponseCode"
        ).OK

        if response_code == OK:
            self._initialized = True
            _log.info("[IAP] Billing connected — querying products")
            self._query_product_details()
        else:
            _log.error("[IAP] Billing setup failed, code=%s", response_code)
            self._initialized = False

    def _query_product_details(self):
        """Query product details from Google Play."""
        try:
            from jnius import autoclass, PythonJavaClass, java_method

            QueryProductDetailsParams = autoclass(
                "com.android.billingclient.api.QueryProductDetailsParams"
            )
            ProductType = autoclass(
                "com.android.billingclient.api.BillingClient$ProductType"
            )
            Product = autoclass(
                "com.android.billingclient.api.QueryProductDetailsParams$Product"
            )
            ArrayList = autoclass("java.util.ArrayList")

            product_list = ArrayList()
            for prod in PRODUCTS.values():
                product = (
                    Product.newBuilder()
                    .setProductId(prod["id"])
                    .setProductType(ProductType.INAPP)
                    .build()
                )
                product_list.add(product)

            params = (
                QueryProductDetailsParams.newBuilder()
                .setProductList(product_list)
                .build()
            )

            manager = self

            class _DetailsCb(PythonJavaClass):
                __javainterfaces__ = [
                    "com/android/billingclient/api/"
                    "ProductDetailsResponseListener"
                ]
                __javacontext__ = "app"

                @java_method(
                    "(Lcom/android/billingclient/api/BillingResult;"
                    "Ljava/util/List;)V"
                )
                def onProductDetailsResponse(
                    self_inner, billing_result, details_list
                ):
                    # Extract data on billing thread before scheduling
                    details_snapshot = {}
                    try:
                        if details_list is not None:
                            for i in range(details_list.size()):
                                detail = details_list.get(i)
                                pid = detail.getProductId()
                                details_snapshot[pid] = detail
                    except Exception as e:
                        _log.error("[IAP] Error reading product details: %s", e)
                    Clock.schedule_once(
                        lambda dt: manager._on_product_details_safe(
                            details_snapshot
                        ),
                        0,
                    )

            self._details_cb = _DetailsCb()
            self._billing_client.queryProductDetailsAsync(
                params, self._details_cb
            )

        except Exception as e:
            _log.error("[IAP] Query product details failed: %s", e)

    def _on_product_details_safe(self, details_snapshot):
        """Cache product details for later use in purchase flow."""
        if not details_snapshot:
            _log.warning("[IAP] No product details returned")
            return
        for pid, detail in details_snapshot.items():
            self._product_details[pid] = detail
            _log.info("[IAP] Product loaded: %s", pid)
