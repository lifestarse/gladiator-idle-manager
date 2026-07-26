---
name: bluestacks-deploy-2026-07-25
description: Деплой на BlueStacks — пайплайн (WSL buildozer, инстансы, HD-Adb) и фикс скрытия kivy/input анти-детектом BlueStacks
metadata:
  type: project
---

Первый рабочий деплой на BlueStacks — 2026-07-25. Актуальный билд **v1.9.43** (= v1.9.42 + реклама выключена флагом, см. [[billing8-ads-2026-07-25]]). 1.9.40/1.9.41 без шима — на BlueStacks падают на старте, на реальном железе должны работать.

**Сборка:** WSL, `/home/lifestarse/.local/bin/buildozer android debug` из `/mnt/c/Users/user/gladiator-idle-manager`, логи `build_*.log` в корне. Поднятие `minapi` 21→23 (Billing 8 / Ads SDK) один раз вызвало полную пересборку всех p4a-рецептов (~40 мин); дальше инкрементально ~3 мин. `.claude` добавлен в `source.exclude_dirs` (иначе worktree-копии исходников попадают в APK).

**BlueStacks (conf: `C:\ProgramData\BlueStacks_nxt\bluestacks.conf`):**
- `Nougat32` = «BlueStacks App Player», 32-бит (abi x86,arm) — arm64-APK **не ставится** (NO_MATCHING_ABIS).
- `Pie64` = «App Player 1» (arm64 ок) — основной у юзера.
- `Pie64_2` = «App Player 2» — тестовый, создан мной 2026-07-25 (Pie 64-bit, 2 CPU / 4 ГБ; `enable_root_access="1"` оставлен включённым, su всё равно молчит из adb shell — SELinux).
- adb: `& 'C:\Program Files\BlueStacks_nxt\HD-Adb.exe' connect 127.0.0.1:<port>`; порт — `bst.instance.<имя>.status.adb_port` (Pie64_2 → **5575**). Запуск инстанса без MIM: `HD-Player.exe --instance Pie64_2`. Активити: `com.gladiator.gladiatoridle/org.kivy.android.PythonActivity`.

**Баг и фикс (главное):** анти-детект BlueStacks **прячет каталоги с именем `input` из readdir внутри процессов игр** (маскирует /dev/input от анти-читов). Из-за этого `import kivy.input` падает (FileFinder питона читает листинг родительского каталога), Kivy остаётся без window provider, `Window=None` → `AttributeError ... clearcolor` в `game/app/_shared.py:47`. По **точному пути** файлы доступны (stat/open работают); adb shell не затронут; `adb backup` (идёт из процесса приложения) каталог тоже «не видит» — не верить бэкапу при диагностике этого класса проблем.

Фикс: [game/kivy_input_shim.py](../game/kivy_input_shim.py) — MetaPathFinder, резолвит `kivy.input.*` точными путями в обход листинга. Импортируется **первой строкой** в `main.py` (до любого импорта kivy) — **не удалять и не переносить ниже**. Самодиагностика: активируется только при `exact=True & listed=False`, на десктопе/реальном Android — no-op (проверено: desktop SHIM_ACTIVE=False, 432 теста зелёные). Лог на девайсе: `[kivy_input_shim] ... active=True`.

**Побочное укрепление (вне git!):** p4a-распаковщик `AssetExtract.java` пропатчен — чтение блоками 8 КБ вместо разового 1 МБ, `mkdirs` родителя, проверка размера каждой записи, итоговый лог `extracted N tar entries` (N=1022 для текущего бандла — маркер полной распаковки). Патч лежит в ДВУХ местах внутри `.buildozer` (в git НЕ попадает): p4a-клон `platform/python-for-android/.../org/renpy/android/AssetExtract.java` и текущий dist `platform/build-arm64-v8a/dists/gladiatoridle/src/main/java/org/renpy/android/AssetExtract.java`. Потеря `.buildozer` = потеря патча; функционально не критично (краш чинит шим), но лог полезен.

**Ложный след (не повторять):** гипотеза «jtar теряет синхронизацию tar-потока / битый vertex_instructions.so» опровергнута — распаковщик p4a исправен, файлы писались всегда, их прятал readdir. «Дыра 128КБ+512» была артефактом сравнения APK-tar с backup'ом, который сам не видит скрытые каталоги.

Девайс-чеклист из [[billing8-ads-2026-07-25]] теперь частично прогоняем на Player 2 (Play-сервисы есть, но аккаунт в свежем инстансе не залогинен — для purchase/restore нужен вход в Google).
