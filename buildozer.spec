[app]
title = Gladiator Idle
package.name = gladiatoridle
package.domain = com.gladiator
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,wav,ttf
source.exclude_dirs = bin,.buildozer,.git
source.exclude_patterns = generate_icons.py
version = 1.9.39
requirements = python3,kivy==2.3.1,pillow,android,pyjnius,filetype,certifi
orientation = portrait, landscape, portrait-reverse, landscape-reverse
# Force android:screenOrientation="fullUser" so the app respects the system
# autorotate toggle. p4a maps a multi-orientation list to "unspecified", which
# on modern Android behaves like sensor (rotates regardless of the system
# autorotate setting). --manifest-orientation overrides that mapping.
p4a.extra_args = --manifest-orientation=fullUser
fullscreen = 1

# Icon & presplash
icon.filename = %(source.dir)s/icons/icon_512.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #0D0D12

# Android
android.permissions = INTERNET,ACCESS_NETWORK_STATE,com.android.vending.BILLING,com.google.android.gms.permission.AD_ID
android.api = 35
# minapi 23 is forced by the ad/billing stack: play-services-ads 24.x and
# billing 8.1+ both declare minSdk 23 in their manifests, so the manifest
# merge fails below 23. API 21/22 devices (Android 5.x, ~0 share) keep the
# last released build; Play simply stops offering them updates.
android.minapi = 23
android.archs = arm64-v8a
android.allow_backup = True

# 16KB page alignment required for Android 15 (API 35).
android.env = LDFLAGS=-Wl,-z,max-page-size=16384

# Google Play Services + Billing + Ads
# NOTE(ads): AdMob runs through game/ads/ (Python) + a Java shim compiled in
# from java_src/com/gladiator/ads/ via android.add_src below. The shim exists
# because GMA v20+ load callbacks (InterstitialAdLoadCallback etc.) are
# abstract classes, which pyjnius cannot implement — this is what killed
# KivMob. Do NOT remove play-services-ads without also stripping the
# APPLICATION_ID meta_data AND java_src (and vice versa): with the SDK
# present but APPLICATION_ID missing, the app crashes at process start
# (MobileAdsInitProvider manifest check) before any Python runs.
# user-messaging-platform (UMP) drives the GDPR consent form; it is NOT a
# transitive dep of play-services-ads and must stay declared explicitly.
# The consent form must be configured in the AdMob console (Privacy &
# messaging); consent flow, ad serving and the rewarded flow are verifiable
# only on a real device.
# NOTE(billing): Billing Library 8.3.0 (Google Play requires v8+ for app
# updates after 2026-08-31). The pyjnius bridge in game/iap/ is on the v8
# API (PendingPurchasesParams, QueryProductDetailsResult); purchase /
# restore / consume / pending-purchase flows must be device-tested before
# release.
android.gradle_dependencies = com.google.android.gms:play-services-auth:21.0.0,com.google.android.gms:play-services-auth-base:18.0.10,com.google.android.gms:play-services-games-v2:20.1.2,com.android.billingclient:billing:8.3.0,com.google.android.play:review:2.0.2,com.google.android.gms:play-services-ads:24.9.0,com.google.android.ump:user-messaging-platform:4.0.0
android.enable_androidx = True

# Java sources for the ads shim (AdsBridge/AdsCallback) — compiled into the
# app by p4a's gradle build.
android.add_src = java_src

# Play Games Services APP_ID — replace YOUR_APP_ID with the numeric ID from
# Play Console > Play Games Services > Setup and management > Configuration.
# Without this the GMS SDK throws "failed to include the Play Games Services
# application id in their AndroidManifest" and online leaderboards are unavailable.
# The leaderboard button shows a local stats popup regardless of this setting.
# APP_ID from Play Games Services (Project ID: 581538611127)
# The ads APPLICATION_ID is mandatory while play-services-ads is a gradle
# dependency — see NOTE(ads) above.
android.meta_data = com.google.android.gms.games.APP_ID=581538611127,com.google.android.gms.ads.APPLICATION_ID=ca-app-pub-9899076646540406~3867094053

# Release build — AAB for Google Play
android.release_artifact = aab

# Signing — NO credentials in this file, ever: this repo is public and the
# previous plaintext keystore password here shipped in git history (commit
# 2c6fc13). That password must be rotated (the .keystore file itself was
# never committed):
#   keytool -storepasswd -keystore gladiator-release.keystore
#   keytool -keypasswd  -keystore gladiator-release.keystore -alias gladiator
# Release signing is driven by python-for-android via environment variables,
# set them in the build shell before `buildozer android release`:
#   P4A_RELEASE_KEYSTORE=<abs path to gladiator-release.keystore>
#   P4A_RELEASE_KEYSTORE_PASSWD=<store password>
#   P4A_RELEASE_KEYALIAS=gladiator
#   P4A_RELEASE_KEYALIAS_PASSWD=<key password>

[buildozer]
log_level = 2
warn_on_root = 1
