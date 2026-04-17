[app]
title = Gladiator Idle
package.name = gladiatoridle
package.domain = com.gladiator
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,wav,ttf
source.exclude_dirs = bin,.buildozer,.git
source.exclude_patterns = generate_icons.py
version = 1.9.11
requirements = python3,kivy==2.3.1,pillow,android,pyjnius,filetype,certifi
orientation = portrait
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
android.gradle_dependencies = com.google.android.gms:play-services-auth:21.0.0,com.google.android.gms:play-services-auth-base:18.0.10,com.google.android.gms:play-services-games-v2:20.1.2,com.android.billingclient:billing:6.2.1
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

# Signing — generate a real keystore before release:
# keytool -genkey -v -keystore gladiator-release.keystore -alias gladiator -keyalg RSA -keysize 2048 -validity 10000
android.keystore = gladiator-release.keystore
android.keyalias = gladiator
android.keystore_password = ;lfgajlk;g;jlkgajl;[iweweijrt283r234-0517045980
android.keyalias_password = ;lfgajlk;g;jlkgajl;[iweweijrt283r234-0517045980

[buildozer]
log_level = 2
warn_on_root = 1
