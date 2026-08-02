---
name: billing8-ads-2026-07-25
description: Billing 6→8.3.0 и замена KivMob на Java-шим (v1.9.39, ветка inspiring-hopper) — что сделано и что проверять на девайсе
metadata:
  type: project
  created: 2026-07-25
---

Ветка `claude/inspiring-hopper-2bd998` (2026-07-25, v1.9.39) закрыла два блокера из [[audit-2026-07-24]]:

**Billing 6.2.1 → 8.3.0** (дедлайн Google: v8+ для обновлений после 31.08.2026):
- `game/iap/iapandroidinitmixin.py`: `enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())` + `enableAutoServiceReconnection()`; колбэк `onProductDetailsResponse` теперь получает `QueryProductDetailsResult` (JNI-сигнатура в @java_method изменена), продукты — через `getProductDetailsList()`, невыбранные логируются из `getUnfetchedProductList()`.
- purchase/restore-миксины уже были на актуальном API (BillingFlowParams/QueryPurchasesParams) — в v8 не менялись, только проверены.

**Реклама (KivMob → свой мост)**: `game/ads.py` удалён, вместо него пакет `game/ads/` (публичный API и синглтон `ad_manager` сохранены) + Java-шим `java_src/com/gladiator/ads/{AdsBridge,AdsCallback}.java`, подключаемый через `android.add_src`. Шим обязателен: колбэки загрузки GMA v20+ (`InterstitialAdLoadCallback` и др.) — абстрактные классы, PythonJavaClass умеет только интерфейсы (поэтому KivMob и умер). Все события идут через один интерфейс `AdsCallback.onAdEvent(event, data)` → Clock.schedule_once → Kivy-поток; загрузка/показ — на UI-потоке внутри Java (runOnUiThread). UMP-консент (user-messaging-platform:4.0.0, НЕ транзитивная зависимость — объявлена явно) гейтит запуск MobileAds: без `canRequestAds()` реклама выключена на сессию. Награда rewarded выдаётся ТОЛЬКО по событию `earned` (тесты `tests/test_ads_bridge.py`).

ВЛИТО в master 2026-07-25 (merge 71b21e3).

**buildozer.spec v1.9.39**: billing:8.3.0, play-services-ads:24.9.0, ump:4.0.0, `android.minapi = 23` (оба SDK требуют minSdk 23 — manifest merge ниже падает), `android.add_src = java_src`, в meta_data добавлен `com.google.android.gms.ads.APPLICATION_ID` (без него при подключённом ads-SDK приложение падает на старте процесса, до Python — MobileAdsInitProvider).

**Не проверяется без девайса** (обязательный чек перед релизом): покупка/restore/consume/pending purchase (Billing 8), UMP-форма (нужно настроить GDPR-сообщение в AdMob console → Privacy & messaging, иначе EEA-юзеры без рекламы), показ banner/interstitial, полный rewarded-флоу (earned/закрытие раньше времени), первый запуск после обновления на API 23+.

**UPDATE 2026-07-25 (v1.9.43): реклама ВЫКЛЮЧЕНА решением юзера** («нет аудитории — нет смысла») — `ADS_ENABLED = False` в `game/ads/_shared.py`, гейт в начале `AdManager.init()`. Стек цел (Java-шим, gradle deps, APPLICATION_ID — не выпиливать, см. NOTE(ads) в spec); включение = одна константа. Мост подтверждён живым показом на BlueStacks (v1.9.42, баннер с меткой Anzeige, UMP consent not required для Украины) — миграция KivMob→шим РАБОТАЕТ. Рекламные пункты девайс-чеклиста отложены до включения. При будущих тестах рекламы: юниты боевые — НЕ кликать по своей рекламе (invalid traffic → бан AdMob), сначала добавить test device ID / тестовые юниты в debug-сборках.
