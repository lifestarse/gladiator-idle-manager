[app]
title = Gladiator Idle
package.name = gladiatoridle
package.domain = com.gladiator
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 0.1.0
requirements = python3,kivy
orientation = portrait
fullscreen = 0

# Android
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

# iOS
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master

[buildozer]
log_level = 2
warn_on_root = 1
