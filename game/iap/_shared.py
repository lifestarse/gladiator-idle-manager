# Build: 4
"""
In-App Purchase module.

Products:
- remove_ads: Remove all ads — 100 UAH (~$2.50)

On Android: uses Google Play Billing Library v6+ via pyjnius
On iOS: uses StoreKit via pyobjus
On desktop: stub mode (purchases always succeed for testing)
"""

import logging

from kivy.utils import platform
from kivy.clock import Clock

_log = logging.getLogger(__name__)

# --- Product definitions ---
PRODUCTS = {
    "remove_ads": {
        "id": "com.gladiator.remove_ads",
        "name": "Remove Ads",
        "desc": "Remove all banner & interstitial ads forever",
        "price": "100 UAH",
        "price_usd": "$2.50",
        "consumable": False,
    },
    "gems_100": {
        "id": "com.gladiator.gems_100",
        "name": "100 Diamonds",
        "desc": "100 diamonds",
        "price": "20 UAH",
        "price_usd": "$0.49",
        "consumable": True,
    },
    "gems_500": {
        "id": "com.gladiator.gems_500",
        "name": "500 Diamonds",
        "desc": "500 diamonds",
        "price": "59 UAH",
        "price_usd": "$1.49",
        "consumable": True,
    },
    "gems_1000": {
        "id": "com.gladiator.gems_1000",
        "name": "1000 Diamonds",
        "desc": "1000 diamonds",
        "price": "79 UAH",
        "price_usd": "$1.99",
        "consumable": True,
    },
    "gems_2500": {
        "id": "com.gladiator.gems_2500",
        "name": "2500 Diamonds (+10%)",
        "desc": "2500 diamonds",
        "price": "179 UAH",
        "price_usd": "$4.49",
        "consumable": True,
    },
    "gems_6000": {
        "id": "com.gladiator.gems_6000",
        "name": "6000 Diamonds (+20%)",
        "desc": "6000 diamonds",
        "price": "399 UAH",
        "price_usd": "$9.99",
        "consumable": True,
    },
}

# Reverse map: Google/Apple product ID -> our key
_PRODUCT_ID_TO_KEY = {v["id"]: k for k, v in PRODUCTS.items()}


