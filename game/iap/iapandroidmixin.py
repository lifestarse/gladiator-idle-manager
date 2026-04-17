# Build: 1
"""IAPManager _IapAndroidMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _log


class _IapAndroidMixin:
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

    def _on_purchases_updated(self, response_code, purchases):
        """Handle purchase result from Google Play."""
        from jnius import autoclass

        BRC = autoclass(
            "com.android.billingclient.api.BillingClient$BillingResponseCode"
        )

        if response_code == BRC.OK and purchases is not None:
            for i in range(purchases.size()):
                purchase = purchases.get(i)
                self._handle_purchase(purchase)
        elif response_code == BRC.USER_CANCELED:
            _log.info("[IAP] User canceled purchase")
            self._fire_failure("User canceled")
        else:
            _log.error("[IAP] Purchase failed, code=%s", response_code)
            self._fire_failure(f"Error code: {response_code}")

    def _is_consumable(self, product_id):
        """Check if a product is consumable (diamonds etc)."""
        key = _PRODUCT_ID_TO_KEY.get(product_id)
        if key and key in PRODUCTS:
            return PRODUCTS[key].get("consumable", False)
        return False

    def _handle_purchase(self, purchase):
        """Acknowledge or consume and deliver a purchase."""
        from jnius import autoclass, PythonJavaClass, java_method

        PurchaseState = autoclass(
            "com.android.billingclient.api.Purchase$PurchaseState"
        )

        state = purchase.getPurchaseState()
        if state != PurchaseState.PURCHASED:
            _log.info("[IAP] Purchase not in PURCHASED state: %s", state)
            return

        # Get the product IDs from purchase
        products = purchase.getProducts()
        product_id = products.get(0) if products.size() > 0 else None

        if self._is_consumable(product_id):
            # Consumable: must call consumeAsync to allow re-purchase
            self._consume_purchase(purchase, product_id)
        elif not purchase.isAcknowledged():
            # Non-consumable: acknowledge
            self._acknowledge_purchase(purchase, product_id)
        else:
            # Already acknowledged — just deliver
            self._deliver_product(product_id)

    def _consume_purchase(self, purchase, product_id):
        """Consume a consumable purchase (diamonds) so it can be bought again."""
        from jnius import autoclass, PythonJavaClass, java_method

        ConsumeParams = autoclass(
            "com.android.billingclient.api.ConsumeParams"
        )
        params = (
            ConsumeParams.newBuilder()
            .setPurchaseToken(purchase.getPurchaseToken())
            .build()
        )
        manager = self

        class _ConsumeListener(PythonJavaClass):
            __javainterfaces__ = [
                "com/android/billingclient/api/"
                "ConsumeResponseListener"
            ]
            __javacontext__ = "app"

            @java_method(
                "(Lcom/android/billingclient/api/BillingResult;"
                "Ljava/lang/String;)V"
            )
            def onConsumeResponse(self_inner, billing_result, token):
                try:
                    code = billing_result.getResponseCode()
                except Exception as e:
                    _log.warning("[IAP] onConsumeResponse error: %s", e)
                    code = -1
                Clock.schedule_once(
                    lambda dt: manager._on_consumed(product_id, code), 0,
                )

        self._consume_listener = _ConsumeListener()
        self._billing_client.consumeAsync(params, self._consume_listener)

    def _on_consumed(self, product_id, response_code):
        from jnius import autoclass
        OK = autoclass(
            "com.android.billingclient.api.BillingClient$BillingResponseCode"
        ).OK
        if response_code == OK:
            _log.info("[IAP] Purchase consumed: %s", product_id)
            self._deliver_product(product_id)
        else:
            _log.error("[IAP] Consume failed: %s", response_code)
            self._fire_failure(f"Consume error: {response_code}")

    def _acknowledge_purchase(self, purchase, product_id):
        """Acknowledge a non-consumable purchase (remove ads)."""
        from jnius import autoclass, PythonJavaClass, java_method

        AcknowledgePurchaseParams = autoclass(
            "com.android.billingclient.api.AcknowledgePurchaseParams"
        )
        params = (
            AcknowledgePurchaseParams.newBuilder()
            .setPurchaseToken(purchase.getPurchaseToken())
            .build()
        )
        manager = self

        class _AckListener(PythonJavaClass):
            __javainterfaces__ = [
                "com/android/billingclient/api/"
                "AcknowledgePurchaseResponseListener"
            ]
            __javacontext__ = "app"

            @java_method(
                "(Lcom/android/billingclient/api/BillingResult;)V"
            )
            def onAcknowledgePurchaseResponse(
                self_inner, billing_result
            ):
                try:
                    code = billing_result.getResponseCode()
                except Exception as e:
                    _log.warning("[IAP] onAcknowledgePurchaseResponse error: %s", e)
                    code = -1
                Clock.schedule_once(
                    lambda dt: manager._on_acknowledged(
                        product_id, code
                    ),
                    0,
                )

        self._ack_listener = _AckListener()
        self._billing_client.acknowledgePurchase(params, self._ack_listener)

    def _on_acknowledged(self, product_id, response_code):
        from jnius import autoclass

        OK = autoclass(
            "com.android.billingclient.api.BillingClient$BillingResponseCode"
        ).OK
        if response_code == OK:
            _log.info("[IAP] Purchase acknowledged: %s", product_id)
            self._deliver_product(product_id)
        else:
            _log.error("[IAP] Acknowledge failed: %s", response_code)
            self._fire_failure(f"Acknowledge error: {response_code}")

    def _deliver_product(self, product_id):
        """Deliver the product and call success callback."""
        key = _PRODUCT_ID_TO_KEY.get(product_id)
        if key and key in self._purchase_callbacks:
            on_success, _ = self._purchase_callbacks.pop(key)
            if on_success:
                on_success()
            _log.info("[IAP] Delivered: %s", key)
        else:
            _log.error("[IAP] Delivered (no callback): %s", product_id)

    def _fire_failure(self, reason):
        """Call failure callback for the most recent purchase attempt."""
        if self._pending_purchase and self._pending_purchase in self._purchase_callbacks:
            _, on_failure = self._purchase_callbacks.pop(self._pending_purchase)
            if on_failure:
                on_failure(reason)
        self._pending_purchase = None

    def _purchase_android(self, product, on_success, on_failure):
        """Launch billing flow on Android."""
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            BillingFlowParams = autoclass(
                "com.android.billingclient.api.BillingFlowParams"
            )
            ProductDetailsParams = autoclass(
                "com.android.billingclient.api.BillingFlowParams"
                "$ProductDetailsParams"
            )
            ArrayList = autoclass("java.util.ArrayList")

            detail = self._product_details.get(product["id"])
            if detail is None:
                if on_failure:
                    on_failure("Product not available — try again later")
                return

            pdp = (
                ProductDetailsParams.newBuilder()
                .setProductDetails(detail)
                .build()
            )

            pdp_list = ArrayList()
            pdp_list.add(pdp)

            params = (
                BillingFlowParams.newBuilder()
                .setProductDetailsParamsList(pdp_list)
                .build()
            )

            activity = PythonActivity.mActivity
            result = self._billing_client.launchBillingFlow(activity, params)
            code = result.getResponseCode()
            _log.info("[IAP] launchBillingFlow code=%s", code)

        except Exception as e:
            _log.error("[IAP] Android purchase error: %s", e)
            if on_failure:
                on_failure(str(e))

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
