# Build: 1
"""
In-App Purchase module.

Products:
- remove_ads: Remove all ads — 100 UAH (~$2.50)

On Android: uses Google Play Billing Library v6+ via pyjnius
On iOS: uses StoreKit via pyobjus
On desktop: stub mode (purchases always succeed for testing)
"""

from kivy.utils import platform
from kivy.clock import Clock

# --- Product definitions ---
PRODUCTS = {
    "remove_ads": {
        "id": "com.gladiator.remove_ads",
        "name": "Remove Ads",
        "desc": "Remove all banner & interstitial ads forever",
        "price": "100 UAH",
        "price_usd": "$2.50",
    },
}

# Reverse map: Google/Apple product ID -> our key
_PRODUCT_ID_TO_KEY = {v["id"]: k for k, v in PRODUCTS.items()}


class IAPManager:
    """Cross-platform IAP handler."""

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
            print("[IAP] Desktop stub mode — purchases auto-succeed")
            self._initialized = False

    # ================================================================
    #  ANDROID — Google Play Billing Library v6
    # ================================================================

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
                    except Exception:
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
                    except Exception:
                        code = -1
                    Clock.schedule_once(
                        lambda dt: manager._on_billing_setup(code), 0
                    )

                @java_method("()V")
                def onBillingServiceDisconnected(self_inner):
                    print("[IAP] Billing service disconnected")
                    manager._initialized = False

            self._purchase_listener = _PurchaseListener()
            self._state_listener = _StateListener()

            activity = PythonActivity.mActivity
            builder = BillingClient.newBuilder(activity)
            builder.setListener(self._purchase_listener)
            builder.enablePendingPurchases()
            self._billing_client = builder.build()
            self._billing_client.startConnection(self._state_listener)
            print("[IAP] Android billing: connecting...")

        except Exception as e:
            print(f"[IAP] Android billing init failed: {e}")
            self._initialized = False

    def _on_billing_setup(self, response_code):
        """Called when billing client is connected."""
        from jnius import autoclass

        OK = autoclass(
            "com.android.billingclient.api.BillingClient$BillingResponseCode"
        ).OK

        if response_code == OK:
            self._initialized = True
            print("[IAP] Billing connected — querying products")
            self._query_product_details()
        else:
            print(f"[IAP] Billing setup failed, code={response_code}")
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
                        print(f"[IAP] Error reading product details: {e}")
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
            print(f"[IAP] Query product details failed: {e}")

    def _on_product_details_safe(self, details_snapshot):
        """Cache product details for later use in purchase flow."""
        if not details_snapshot:
            print("[IAP] No product details returned")
            return
        for pid, detail in details_snapshot.items():
            self._product_details[pid] = detail
            print(f"[IAP] Product loaded: {pid}")

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
            print("[IAP] User canceled purchase")
            self._fire_failure("User canceled")
        else:
            print(f"[IAP] Purchase failed, code={response_code}")
            self._fire_failure(f"Error code: {response_code}")

    def _handle_purchase(self, purchase):
        """Acknowledge and deliver a purchase."""
        from jnius import autoclass, PythonJavaClass, java_method

        PurchaseState = autoclass(
            "com.android.billingclient.api.Purchase$PurchaseState"
        )
        AcknowledgePurchaseParams = autoclass(
            "com.android.billingclient.api.AcknowledgePurchaseParams"
        )

        state = purchase.getPurchaseState()
        if state != PurchaseState.PURCHASED:
            print(f"[IAP] Purchase not in PURCHASED state: {state}")
            return

        # Get the product IDs from purchase
        products = purchase.getProducts()
        product_id = products.get(0) if products.size() > 0 else None

        if not purchase.isAcknowledged():
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
                    except Exception:
                        code = -1
                    Clock.schedule_once(
                        lambda dt: manager._on_acknowledged(
                            product_id, code
                        ),
                        0,
                    )

            self._ack_listener = _AckListener()
            self._billing_client.acknowledgePurchase(params, self._ack_listener)
        else:
            # Already acknowledged — just deliver
            self._deliver_product(product_id)

    def _on_acknowledged(self, product_id, response_code):
        from jnius import autoclass

        OK = autoclass(
            "com.android.billingclient.api.BillingClient$BillingResponseCode"
        ).OK
        if response_code == OK:
            print(f"[IAP] Purchase acknowledged: {product_id}")
            self._deliver_product(product_id)
        else:
            print(f"[IAP] Acknowledge failed: {response_code}")
            self._fire_failure(f"Acknowledge error: {response_code}")

    def _deliver_product(self, product_id):
        """Deliver the product and call success callback."""
        key = _PRODUCT_ID_TO_KEY.get(product_id)
        if key and key in self._purchase_callbacks:
            on_success, _ = self._purchase_callbacks.pop(key)
            if on_success:
                on_success()
            print(f"[IAP] Delivered: {key}")
        else:
            print(f"[IAP] Delivered (no callback): {product_id}")

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
            print(f"[IAP] launchBillingFlow code={code}")

        except Exception as e:
            print(f"[IAP] Android purchase error: {e}")
            if on_failure:
                on_failure(str(e))

    # ================================================================
    #  iOS — StoreKit
    # ================================================================

    def _init_ios(self):
        """Initialize StoreKit on iOS."""
        try:
            from pyobjus import autoclass as objc_autoclass
            from pyobjus import protocol

            NSSet = objc_autoclass("NSSet")
            SKProductsRequest = objc_autoclass("SKProductsRequest")
            SKPaymentQueue = objc_autoclass("SKPaymentQueue")

            # Build product ID set
            product_ids = [p["id"] for p in PRODUCTS.values()]
            ns_ids = NSSet.setWithObjects_(*product_ids)

            manager = self

            # Payment observer
            class _PaymentObserver:
                """Acts as SKPaymentTransactionObserver."""

                def updatedTransactions_(self_inner, queue, transactions):
                    for i in range(transactions.count()):
                        txn = transactions.objectAtIndex_(i)
                        state = txn.transactionState()
                        pid = txn.payment().productIdentifier().UTF8String()
                        Clock.schedule_once(
                            lambda dt, s=state, p=pid, t=txn: (
                                manager._ios_handle_transaction(s, p, t)
                            ),
                            0,
                        )

            self._ios_observer = _PaymentObserver()
            self._payment_queue = SKPaymentQueue.defaultQueue()
            self._payment_queue.addTransactionObserver_(self._ios_observer)

            # Request product info
            request = SKProductsRequest.alloc().initWithProductIdentifiers_(
                ns_ids
            )

            class _ProductDelegate:
                def productsRequest_didReceiveResponse_(
                    self_inner, request, response
                ):
                    products = response.products()
                    for i in range(products.count()):
                        prod = products.objectAtIndex_(i)
                        pid = prod.productIdentifier().UTF8String()
                        manager._product_details[pid] = prod
                        print(f"[IAP] iOS product loaded: {pid}")

                def request_didFailWithError_(self_inner, request, error):
                    print(
                        f"[IAP] iOS product request failed: "
                        f"{error.localizedDescription().UTF8String()}"
                    )

            self._ios_delegate = _ProductDelegate()
            request.setDelegate_(self._ios_delegate)
            request.start()

            self._initialized = True
            print("[IAP] iOS StoreKit initialized")

        except Exception as e:
            print(f"[IAP] iOS StoreKit init failed: {e}")
            self._initialized = False

    def _ios_handle_transaction(self, state, product_id, transaction):
        """Process an iOS payment transaction."""
        try:
            from pyobjus import autoclass as objc_autoclass

            SKPaymentQueue = objc_autoclass("SKPaymentQueue")
            queue = SKPaymentQueue.defaultQueue()

            # SKPaymentTransactionState values
            PURCHASED = 1
            FAILED = 2
            RESTORED = 3

            if state == PURCHASED or state == RESTORED:
                key = _PRODUCT_ID_TO_KEY.get(product_id)
                if key and key in self._purchase_callbacks:
                    on_success, _ = self._purchase_callbacks.pop(key)
                    if on_success:
                        on_success()
                print(f"[IAP] iOS purchase success: {product_id}")
                queue.finishTransaction_(transaction)

            elif state == FAILED:
                key = _PRODUCT_ID_TO_KEY.get(product_id)
                if key and key in self._purchase_callbacks:
                    _, on_failure = self._purchase_callbacks.pop(key)
                    if on_failure:
                        on_failure("Purchase failed or canceled")
                print(f"[IAP] iOS purchase failed: {product_id}")
                queue.finishTransaction_(transaction)

        except Exception as e:
            print(f"[IAP] iOS transaction handling error: {e}")

    def _purchase_ios(self, product, on_success, on_failure):
        """Launch StoreKit payment on iOS."""
        try:
            from pyobjus import autoclass as objc_autoclass

            SKPayment = objc_autoclass("SKPayment")
            SKPaymentQueue = objc_autoclass("SKPaymentQueue")

            sk_product = self._product_details.get(product["id"])
            if sk_product is None:
                if on_failure:
                    on_failure("Product not available — try again later")
                return

            payment = SKPayment.paymentWithProduct_(sk_product)
            SKPaymentQueue.defaultQueue().addPayment_(payment)
            print(f"[IAP] iOS payment queued: {product['id']}")

        except Exception as e:
            print(f"[IAP] iOS purchase error: {e}")
            if on_failure:
                on_failure(str(e))

    # ================================================================
    #  PUBLIC API
    # ================================================================

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
            print(f"[IAP] Stub purchase: {product_key}")
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
            print("[IAP] Stub: nothing to restore")
            on_restored([])
            return

        if platform == "android":
            self._restore_android(on_restored)
        elif platform == "ios":
            self._restore_ios(on_restored)
        else:
            on_restored([])

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
                        print(f"[IAP] Error reading purchases: {e}")
                    Clock.schedule_once(
                        lambda dt: on_restored(restored), 0
                    )

            self._purchases_cb = _PurchasesCb()
            self._billing_client.queryPurchasesAsync(params, self._purchases_cb)

        except Exception as e:
            print(f"[IAP] Restore failed: {e}")
            on_restored([])

    def _restore_ios(self, on_restored):
        """Restore completed transactions on iOS."""
        try:
            from pyobjus import autoclass as objc_autoclass

            SKPaymentQueue = objc_autoclass("SKPaymentQueue")

            # Store callback — the observer will capture restored txns
            self._ios_restore_callback = on_restored
            self._ios_restored_keys = []

            SKPaymentQueue.defaultQueue().restoreCompletedTransactions()

            # The observer's updatedTransactions_ will fire for
            # restored purchases. We schedule a check after a delay.
            def _finish_restore(dt):
                cb = getattr(self, "_ios_restore_callback", None)
                keys = getattr(self, "_ios_restored_keys", [])
                if cb:
                    cb(keys)
                self._ios_restore_callback = None
                self._ios_restored_keys = []

            Clock.schedule_once(_finish_restore, 5.0)

        except Exception as e:
            print(f"[IAP] iOS restore failed: {e}")
            on_restored([])

    def get_products(self):
        return PRODUCTS


# Singleton
iap_manager = IAPManager()
