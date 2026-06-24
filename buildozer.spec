[app]
title = WA2TG
package.name = wa2tg
package.domain = org.wa2tg
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

requirements = python3,kivy==2.3.0,requests,certifi,charset-normalizer,urllib3,idna

orientation = portrait
fullscreen = 0

android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

# أيقونة التطبيق (اختياري)
# icon.filename = %(source.dir)s/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
