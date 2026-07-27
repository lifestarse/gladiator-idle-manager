---
name: aislop-scanner
description: Сканер aislop установлен глобально (npm); счёт 7/100 — большинство ошибок ложные из-за конвенций проекта; aislop fix НЕ запускать
metadata:
  type: project
---

2026-07-27 юзер попросил поставить https://github.com/scanaislop/aislop (v0.14.0, `npm install -g aislop`, пакет проверен: без install-хуков). Запуск: `aislop scan . --exclude .buildozer,bin,__pycache__,.pytest_cache,.obsidian,.claude,codemap,scratch,memory,Screenshoots,docs` (exclude для scratch/ не сработал — вложенные пути он всё равно сканирует).

Первый прогон: **7/100 «Critical», 55 errors / 748 warnings** — но профиль срабатываний специфичен для этого проекта:

**Ложные (не «чинить»):**
- 34 err «hallucinated import» (jnius/android/pyobjus/PIL/certifi) — объявлены в `buildozer.spec:15` (requirements p4a) или предоставляются рантаймом p4a/kivy-ios; aislop читает только requirements.txt/pyproject/Pipfile.
- ~235 warn «trivial comment» — обязательные заголовки `# Build: N` (строка 1 каждого файла, конвенция CLAUDE.md).
- Большая часть 341 warn «unused import» — паттерн re-export в `_screen_imports.py`/`_shared.py` для star-импортов mixin-пакетов (см. [[engine-scripting-split]], test_cross_package_name_resolution).
- 21 err «bare except with pass» — на деле типизированные (`except OSError: pass` и т.п.), голых `except:` в game/ ноль.

**Реальное (совпадает с [[audit-2026-07-24]]):** ~~16 broad `except Exception`~~ и ~~11 `print()`~~ (оба ЗАКРЫТЫ, см. ниже), ~~функции 120–156 строк и вложенность до 8~~ (ЗАКРЫТО 2026-07-27: workflow из 6 Opus-рефакторщиков + 6 Sonnet-верификаторов, координатор Fable; чистое code motion, хелперы-методы с уникальными префиксами `_pa_`/`_enemy_attack_`/`_applysave_`/`_quests_`/`_qpd_`/`_restore_`/`_lbview_`; deep-nesting 6→0, function-too-long 11→8 — остались только UI-билдеры forge/roster/popups, которые задачей не были), 69 «repetitive dispatch ladder», 17 chained `.get(..., {})`.

**Broad except закрыт 2026-07-27.** Все 16 сидели в `game/scripting/builtins.py` (14) и `game/screens/scripts/popups.py` (2). Диагноз: в `interpreterexecmixin._exec_Action` уже есть обёртка, которая превращает любое исключение экшена в `ScriptError` с именем экшена, а `managerrunmixin._run_program` кладёт его в `last_errors`/`RunStats.error` для экрана скриптов. Семнадцать `except Exception: pass|return` в builtins.py глушили ошибку **под** этим конвейером — упавший экшен был неотличим от законного no-op. Убраны все 17 (guard'ы `getattr`+`callable` остались — они и обрабатывают «нет API»); в popups.py два clipboard-catch'а получили `_log.warning` + `# noqa: BLE001`. Защита от возврата: `tests/test_scripting_error_surfacing.py` (16 тестов, включая AST-скан builtins.py на broad-handler'ы). После: правило `python-broad-except` — 0, счёт 7→9.

**print() закрыт 2026-07-27.** Из 11 в пакете `game/` был ровно **один** — `kivy_input_shim.py:86`, и это не забытый дебаг, а единственная диагностика BlueStacks-ветки (см. [[bluestacks-deploy-2026-07-25]]). Переведён на `_log.warning`; уровень именно WARNING, потому что шим отрабатывает до всякой настройки логирования и запись уходит через `logging.lastResort`, который режет всё ниже WARNING. Проверено обе ветки: на десктопе тихо и `SHIM_ACTIVE=False`, при спрятанном из listdir `input` — finder ставится, `kivy.input.provider` резолвится, сообщение доходит до stderr.

Оставшиеся 10 print() — ложные: корневые генераторы ассетов `generate_icons.py` и `gen_feature_graphic.py`, где print это вывод CLI-инструмента. Для сравнения: в `scripts/` 90 print(), aislop не пометил ни одного — правило пропускает по каталогу `scripts/`, а корневые скрипты ловит. Не трогать.

Оставшиеся 5 `swallowed-exception` — ложные: `except ValueError: pass` в обработчиках ввода (`_core.py` 788/803, `cells.py` 524 — срабатывают на каждое нажатие, недопечатанное значение законно не число), `except OSError: pass` в cleanup-цикле `_cache.py:92`, и файл в `scratch/fake_generators_do_not_run/`.

**НЕ запускать `aislop fix` / `aislop agent`:** 583 «fixable» включают удаление Build-заголовков и re-export-импортов — сломает name resolution mixin-пакетов и конвенцию билдов. Только точечный ручной разбор.
