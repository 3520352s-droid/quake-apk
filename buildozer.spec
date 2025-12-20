[app]
title = Quake Prob
package.name = quakeprob
package.domain = org.sergej
# --- Force Buildozer to use GitHub Actions Android SDK/NDK ---
android.accept_sdk_license = True
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/25.2.9519653

# Pin versions to avoid build-tools 36.x
android.api = 33
android.minapi = 21
android.build_tools_version = 33.0.2


source.dir = .
source.include_exts = py,kv,png,jpg,ttf

version = 0.1

requirements = python3,kivy,requests

orientation = portrait
fullscreen = 0

android.permissions = INTERNET

[buildozer]
log_level = 2
warn_on_root = 1

