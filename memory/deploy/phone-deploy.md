---
name: phone-deploy
description: Деплой на реальный телефон (Pixel 10a) — adb, подписи, где живёт upload-keystore и его пароль
metadata:
  type: project
  created: 2026-07-27
---

Первый adb-деплой на реальный телефон — 2026-07-27, v1.9.45 debug.

**Телефон:** Pixel 10a, serial `5B211JEA303918`, ЕСТЬ РУТ (su из adb shell работает). **adb-over-WiFi постоянный** (2026-08-04): `persist.adb.tcp.port=5555` установлен через su — переживает ребуты, `adb tcpip` больше не нужен. IP динамический (после ребута менялся 105→107) — искать `adb mdns services` и `adb connect <ip>:5555`; USB нужен только если WiFi-сеть сменилась совсем. adb — из scrcpy (`Genymobile.scrcpy` в WinGet Packages, есть в PATH). Остальные adb-девайсы (`127.0.0.1:5555/5556`, `emulator-5554`, model SM_S908E) — это BlueStacks, см. [[bluestacks-deploy]].

**Подписи (важно, три разных ключа):**
- До 2026-07-27 на телефоне стояла версия **из Google Play** (`installerPackageName=com.android.vending`) с подписью **Play App Signing** (SHA256 `C3:0B:CE:DC:...`, DName «CN=Android, O=Google Inc.») — её локально не воспроизвести ничем, `adb install -r` поверх невозможен. Снесена с согласия юзера (сейв потерян), теперь стоит debug-подписанная — дальнейшие `adb install -r` работают без плясок. Play-версия обратно поверх debug тоже не встанет — тоже только через uninstall.
- **Upload-ключ** (которым подписываются AAB для Play): `~/gladiator-build/gladiator-release.keystore` **в WSL** (Mar 25, 2750 байт), alias `gladiator`, SHA256 `9A:AE:40:BC:...`. Пароли (store и key) — те, что лежали в `buildozer.spec` до чистки 2026-07-24 (`git show 2c6fc13:buildozer.spec`, поля `android.keystore_password` / `android.keyalias_password`) — проверено keytool'ом 2026-07-27, подходят. В чат/файлы пароль не копировать — доставать из истории на месте.
- `gladiator-release.keystore` **в корне репо** (Mar 27, 2247 байт) — НЕ тот файл: исторический пароль к нему не подходит, отпечаток неизвестен, ни один известный ключ им не является. Похоже, мёртвый артефакт — не использовать, не удалять без разбирательства.

**Ротация пароля из аудита ([[audit-2026-07-24]]) всё ещё НЕ сделана** — пароль из git-истории рабочий для действующего upload-ключа. При ротации: `keytool -storepasswd/-keypasswd` на WSL-keystore, и помнить что Play принимает AAB только с этим upload-ключом (сброс upload-ключа — через поддержку Play Console).

**Установка:** `adb -s 5B211JEA303918 install -r bin/gladiatoridle-<ver>-arm64-v8a-debug.apk`; запуск `adb shell am start -n com.gladiator.gladiatoridle/org.kivy.android.PythonActivity`; проверка `pidof com.gladiator.gladiatoridle` + logcat на Traceback/FATAL. На старте 1.9.45 всплыл баг: remote_content пишет манифест в `/data/...` → Permission denied — **починен в 1.9.46** (`game/storage.py::user_data_dir()`, HOME на Android = /data и не писабелен; кэши теперь в `files/` рядом с сейвом). Загрузка языковых паков проверена на девайсе 2026-07-27: манифест кэшируется, ru+uk скачались и применились на лету.

**Гонка запуска после `install -r` поверх РАБОТАЮЩЕЙ игры:** Android после replace сам воскрешает таск приложения; одновременный `am start` даёт второй инстанс activity в том же процессе → NPE в `SDLActivity.handleNativeState` (mSurface=null) → мгновенный FATAL до старта Python. Это не баг игры. Лечение: `am force-stop` → `am start`. Правильный порядок деплоя: force-stop → install -r → logcat -c → am start.

**Отладка на девайсе:** debug-сборка даёт `run-as com.gladiator.gladiatoridle` — можно читать/писать `files/` (сейв, `.gladiator_content_*`, `.gladiator_lang_packs/`) без рута. `app_storage_path()` = `/data/data/com.gladiator.gladiatoridle/files`.
