[app]
title = Gladiator Idle
package.name = gladiatoridle
package.domain = com.gladiator
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 0.2.0
requirements = python3,kivy,kivmob,android,pyjnius,google-auth,google-api-python-client
orientation = portrait
fullscreen = 0

# Android
android.permissions = INTERNET,ACCESS_NETWORK_STATE,BILLING,GET_ACCOUNTS
android.api = 34
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

# AdMob — add your real app ID here
android.meta_data = com.google.android.gms.ads.APPLICATION_ID=ca-app-pub-3940256099942544~3347511713

# Google Play Billing
android.gradle_dependencies = com.google.android.gms:play-services-ads:23.0.0,com.android.billingclient:billing:6.1.0

# iOS
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master

[buildozer]
log_level = 2
warn_on_root = 1
