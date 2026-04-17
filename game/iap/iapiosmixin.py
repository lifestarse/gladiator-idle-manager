# Build: 1
"""IAPManager _IapIosMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _log


class _IapIosMixin:
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
                        _log.info("[IAP] iOS product loaded: %s", pid)

                def request_didFailWithError_(self_inner, request, error):
                    _log.error("[IAP] iOS product request failed: %s",
                               error.localizedDescription().UTF8String())

            self._ios_delegate = _ProductDelegate()
            request.setDelegate_(self._ios_delegate)
            request.start()

            self._initialized = True
            _log.info("[IAP] iOS StoreKit initialized")

        except Exception as e:
            _log.error("[IAP] iOS StoreKit init failed: %s", e)
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
                _log.info("[IAP] iOS purchase success: %s", product_id)
                queue.finishTransaction_(transaction)

            elif state == FAILED:
                key = _PRODUCT_ID_TO_KEY.get(product_id)
                if key and key in self._purchase_callbacks:
                    _, on_failure = self._purchase_callbacks.pop(key)
                    if on_failure:
                        on_failure("Purchase failed or canceled")
                _log.error("[IAP] iOS purchase failed: %s", product_id)
                queue.finishTransaction_(transaction)

        except Exception as e:
            _log.error("[IAP] iOS transaction handling error: %s", e)

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
            _log.info("[IAP] iOS payment queued: %s", product['id'])

        except Exception as e:
            _log.error("[IAP] iOS purchase error: %s", e)
            if on_failure:
                on_failure(str(e))

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
            _log.error("[IAP] iOS restore failed: %s", e)
            on_restored([])
