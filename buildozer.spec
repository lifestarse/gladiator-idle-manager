[app]
title = Gladiator Idle
package.name = gladiatoridle
package.domain = com.gladiator
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,wav,ttf
source.exclude_dirs = bin,.buildozer,.git
source.exclude_patterns = generate_icons.py
version = 1.9.38
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
android.minapi = 21
android.archs = arm64-v8a
android.allow_backup = True

# 16KB page alignment required for Android 15 (API 35).
android.env = LDFLAGS=-Wl,-z,max-page-size=16384

# Google Play Services + Billing
# NOTE(ads): AdMob is intentionally NOT wired into the build. game/ads.py
# degrades to disabled ads (no banner/interstitial; rewarded never grants).
# Wiring it back needs: `kivmob` in requirements +
#   com.google.android.gms:play-services-ads:19.4.0 in gradle_dependencies +
#   com.google.android.gms.ads.APPLICATION_ID=ca-app-pub-9899076646540406~3867094053 in android.meta_data
# BUT KivMob is incompatible with Play Services Ads v20+ (legacy rewarded API
# removed) and Google no longer serves ads to the v19 SDK — reviving ad
# revenue requires migrating off KivMob first (separate task). Do not add the
# old SDK back without that migration.
# NOTE(billing): Billing library 6.2.1 — Google Play requires v8+ for app
# UPDATES submitted after 2026-08-31. Migration 6→8 touches the pyjnius
# bridge in game/iap/ and must be done (and device-tested) before then.
android.gradle_dependencies = com.google.android.gms:play-services-auth:21.0.0,com.google.android.gms:play-services-auth-base:18.0.10,com.google.android.gms:play-services-games-v2:20.1.2,com.android.billingclient:billing:6.2.1,com.google.android.play:review:2.0.2
android.enable_androidx = True

# Play Games Services APP_ID — replace YOUR_APP_ID with the numeric ID from
# Play Console > Play Games Services > Setup and management > Configuration.
# Without this the GMS SDK throws "failed to include the Play Games Services
# application id in their AndroidManifest" and online leaderboards are unavailable.
# The leaderboard button shows a local stats popup regardless of this setting.
# APP_ID from Play Games Services (Project ID: 581538611127)
android.meta_data = com.google.android.gms.games.APP_ID=581538611127

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
