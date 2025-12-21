[app]
title = QuakeProb
package.name = quakeprob
package.domain = org.example

source.dir = .
source.include_exts = py

version = 0.1

requirements = python3,kivy,requests,certifi

orientation = portrait
fullscreen = 0

android.permissons = INTERNET

android.api = 33
android.minapi = 21

android.archs = arm64-v8a,armeabi-v7a

# 🔴 КРИТИЧЕСКИ ВАЖНО
android.sdk_path = /home/runner/android-sdk
android.ndk_path = /home/runner/android-sdk/ndk/25.2.9519653

# ускорение
android.skip_update = True
android.accept_sdk_license = True

log_level = 2




