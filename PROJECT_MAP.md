# Карта проекта — Gladiator Idle Manager

Idle-менеджер гладиаторов: Python + Kivy, релиз на Android (Google Play) через buildozer/p4a.
Версия — в `buildozer.spec` (`version = …`), там же вся конфигурация билда. Правила работы с кодом — [CLAUDE.md](CLAUDE.md), память — [MEMORY.md](MEMORY.md) + `memory/`.
Составлено 2026-07-24 по коду v1.9.37. При расхождении карта уступает коду.

---

## Жизненный цикл

```
main.py (тонкий shim)
  └─ GladiatorIdleApp.build()                    # game/app/_core.py
       ├─ загрузка kv/*.kv
       ├─ GameEngine()                           # game/engine/_core.py
       │    ├─ data_loader.load_all()            # читает data/*.json
       │    ├─ _wire_data()                      # JSON → module-level коллекции game.models (in-place!)
       │    ├─ load()                            # сейв: JSON → состояние (fallback .bak, миграции)
       │    └─ battle_mgr = BattleManager(self)
       ├─ SwipeScreenManager (NoTransition) + NavBar
       │    экраны: arena roster forge expedition lore more (в NavBar)
       │            + scripts, script_editor (открываются программно)
       ├─ таймеры: idle-тик, автосейв
       └─ init сервисов: ads / iap / cloud_save / leaderboard
```

Доступ к движку отовсюду единообразный: `App.get_running_app().engine` (DI нет). ScreenManager — `app.sm`. Аппаратная Back — `_AppNavMixin._on_keyboard` → `screen.on_back_pressed()` → стек `_nav_history`.

**Сейв**: один JSON (`schema_version`, gold/arena_tier/diamonds/shards, `fighters[]` через `Fighter.to_dict()`, inventory, graveyard, логи с обрезкой, `scripts`, мутаторы, лор, язык…).
Путь: Android — `{app_storage_path()}/.gladiator_idle_save.json`, desktop — `~/.gladiator_idle_save.json`.
Запись атомарная: `*.tmp` → `os.replace`, прежний файл → `*.bak`; есть `save_async` (снапшот на main-потоке, дамп в daemon-потоке). Чтение: битый JSON → `.bak`; неприменимый сейв → `.corrupt` + новый старт. Миграции — реестр `_SAVE_MIGRATIONS` (`register_migration`, сейчас пуст, `CURRENT_SAVE_VERSION=1`). Облачная копия — тот же JSON в Google Drive appDataFolder.

---

## Ядро (game/)

### game/engine/ — GameEngine (9 mixin'ов)
`_core.py` — сборка, `__init__`, `_default_save_path`, создание `battle_mgr` • `_fighters.py` — найм/апгрейд/активный боец • `_combat.py` — спавн врагов/боссов, драйвер боя (`start_auto_battle`, `battle_next_turn`, `battle_skip`, `_post_battle_check`) • `_forge.py` — кузница/инвентарь/экип • `_expeditions.py` — экспедиции • `_healing.py` — лечение HP/травм • `_progression.py` — ачивки/квесты/лор • `_economy.py` — магазин расходников • `_persistence.py` = `persistencereadmixin.py` (load) + `persistencewritemixin.py` (save/save_async) • `wiringmixin.py` — `_wire_data`, миграция предметов по шаблонам • `_shared.py` — общие импорты, `CURRENT_SAVE_VERSION`, реестр миграций.

### game/models/ — Fighter/Enemy + скейлинг
`_fighter.py` — `Fighter(CombatUnit + 4 mixin'а)`: **primary-статы** (`strength/agility/vitality`) хранятся здесь; уровни, травмы, стамина/усталость, permadeath • `fighterstatsmixin.py` — **derived-статы** как property (`attack/defense/max_hp/crit/dodge/…`) — формулы см. CLAUDE.md «Stat system» • `fighterequipmixin.py` — экип и сумма статов предметов • `fighterperksmixin.py` — эффекты перков (override-семантика `*_upgrade`) • `fighterserializemixin.py` — to_dict/from_dict • `_enemy.py` — `Enemy`/`Boss` (по тиру и `from_template`) • `_combat.py` — `CombatUnit` (take/deal damage) • `_scaling.py` — `DifficultyScaler` (экспоненты наград/цен/статов) • `_helpers.py` — `Result`, форматирование чисел, редкости • `_data.py` — **пустые module-level коллекции** (`ALL_FORGE_ITEMS`, `RELICS`, `EXPEDITIONS`…), наполняются `_wire_data()` строго in-place (`.clear()`+`.extend()`) — см. «Паттерны».

### game/battle/ — пошаговый бой
`_manager.py` — `BattleManager` (5 mixin'ов): `do_turn`/`do_full_battle`, порядок фаз • `_manager_player_attack.py` / `_manager_enemy_attack.py` — фазы атак (контратаки при додже) • `_manager_skills.py` — активные скиллы, схлопывание событий • `_manager_stats.py` — кэш статов, модификаторы босса • `_manager_support.py` — тики статусов, смерти, победа/поражение • `_resolve.py` — `_resolve_attack` (crit→dmg→dodge→DEF) • `_enchantments.py` — триггеры зачарований/дебаффы • `_types.py` — `BattlePhase/BattleEvent/BattleState/…` • `_shared.py` — `BattleResult`.
Порядок фаз хода фиксированный: статус-тики → активация скиллов → атака игроков → атака врагов → тик баффов.

### game/data_loader/ — загрузка data/*.json
`_core.py` — singleton `DataLoader.load_all()` + tier-индексы • `loadmethodsmixin.py` — чтение/нормализация ключей (`base_str`→`str`) • `translationmixin.py` — `apply_translations(lang)` накладывает name/desc из `data/languages/data_XX.json` in-place • `_shared.py` — путь к data/, валидация id.

### game/scripting/ — DSL «squad scripts»
`ast_nodes.py` — dataclass-узлы AST (`Program/If/While/ForEach/Assign/Action/BinOp/…`), `Trigger` (on_battle_end/on_tick/on_demand), whitelist'ы, `node_to_dict/from_dict` • `interpreter.py` — tree-walking `Interpreter` с лимитами (max_steps/loop_iters/depth) • `builtins.py` — реестры доступного скриптам: поля бойца/движка, вызовы, действия • `manager.py` — `ScriptManager`: программы + персистентные глобалы, диспетчер триггеров, `RunStats`, сериализация в сейв • `labels.py` — маппинг внутренних имён на i18n/категории для UI (в сейв не пишется) • `templates.py` — встроенные шаблоны программ • `online_library.py` — библиотека сообщества: JSON-манифест с GitHub Pages (HTTPS+certifi, кеш 24ч, при ошибке — fallback на templates), импорт через тот же AST-sandbox.

### Одиночные модули ядра
`constants.py` — все игровые константы • `slots.py` — `SLOTS`: единый реестр слотов экипировки (источник правды для формул апгрейда/зачарования) • `achievements.py` + `achievements_checks.py` — ачивки из JSON → callable-проверки • `boss_modifiers.py` — 1–3 модификатора на босса (regeneration/enrage/thorns/…) • `mutators.py` — `mutator_registry`, множители наград • `diamonds.py` — `DIAMOND_SHOP` (внутриигровое) и `DIAMOND_BUNDLES` (IAP) • `story.py` — туториал + главы кампании • `localization.py` — `t()`, 9 языков, цепочка lang→en→ключ, дефолт ru.

---

## UI (game/)

### game/app/ — приложение
`_core.py` — `GladiatorIdleApp` (build, таймеры, init сервисов, color/text Properties) • `appnavmixin.py` — межэкранные переходы (deep-link в Forge, стек истории, Back) • `appuimixin.py` — топбар (золото/алмазы), тосты • `applocalemixin.py` — локализованные строки как Properties • `_shared.py` — общий импорт-блок + `SwipeScreenManager` (свайпы отключены).

### game/screens/ — экраны (каждый = BaseScreen + mixin'ы, дробление ради лимита 10КБ)
- **arena/** — бой: `battleflowmixin` (старт/тик авто-боя и босса), `effectsmixin` (анимации), `enemypopupmixin`, `healmixin`, `resetmixin` (permadeath-попап).
- **roster/** — отряд: список/деталь бойца, `hiremixin`, `injuriesmixin`, `perksmixin`+`perkstree`, `skillsmixin`, `equipmentmixin`/`equipmentbuildmixin`, `actionsbuildmixin` (train/bench/dismiss), `classdetailmixin`.
- **forge/** — кузница: state-machine `view_state` (`_viewstate`, `VIEW_STATES` в `_screen_imports`), `shopmixin`, `inventorymixin`+`inventorygridmixin` (фильтры/сортировка/power-score), `upgrademixin`, `enchantmixin`, `equipswapmixin`, `equipfighterpopupmixin`, `itemdescmixin`, `navstatemixin` (снапшот для истории), `_scrollmixin`/`_tabsmixin`.
- **lore/** — лор/ачивки/логи: `statsquestsmixin`, `logsmixin` (лог боёв), `event_logs_mixin`, `diamondsmixin` (алмаз-шоп).
- **more/** — настройки: `cloudmixin` (Google вход/синк), `iapmixin` (бандлы), `leaderboardmixin`, `helpmixin`.
- **scripts/** — визуальный блочный редактор скриптов: `_core` (`ScriptsScreen` — список программ; `ScriptEditorScreen` — дерево AST-блоков, undo/redo 50 снапшотов, debounced save), `cells.py` (инлайн-редактирование «пилюль»), `popups.py` (палитра блоков, шаблоны, импорт/экспорт, онлайн-библиотека), `blocks.py` (текстовые представления узлов).
- **expedition.py** — экспедиции/охоты, тик миссий 1с.
- `base_screen.py` — общий предок (топбар, `on_back_pressed`, инвалидация кэшей) • `screens/shared.py` — `SCREEN_ORDER`, `_safe_clear/_safe_rebind`, звук.

### game/ui_helpers/ (21) — доменные билдеры контента
Билдеры `build_*`/`refresh_*_grid`, RecycleView-viewclass'ы и адаптеры «игровой объект → dict для RV»: `_roster_cell`/`_roster_grid`, `_forge`/`_forge_cell`, `_inventory_cell`, `_arena_cell`, `_combat_cards`/`_combat_animations`, `_perks_cells`, `_event_log_cell`/`_battle_log_cell`, `_detail_cells`, `_expedition`, `_lore`, `_diamond`, `_shop`, `_item_card`, `_layouts` (grid_batch, long-tap), `_widgets` (фабрики), `_imports` (общий импорт-блок). `__init__.py` реэкспортит всё — внешние импорт-пути стабильны.

### game/widgets/ (10) — переиспользуемые Kivy-примитивы без доменной логики
`_buttons` (MinimalButton/NavButton), `_bars` (MinimalBar, FloatingText), `_cards` (пиксель-арт контейнеры), `_labels` (AutoShrinkLabel), `_avatar` (спрайтовый аватар), `_nav` (NavBar, TouchPanel), `_scroll` (scroll-safe RV/ScrollView), `_inputs` (SafeTextInput). Регистрируются в `gladiatoridle.kv`.

### KV и тема
`gladiatoridle.kv` — только `#:import`-регистрации виджетов/viewclass'ов • `kv/*.kv` — по файлу на экран + `nav_bar.kv` (NavBar, TopBar) • `game/theme.py` — палитра (SNES-стиль) • `ui_config.json` — **мёртвый файл**: никакой .py его не читает (упомянут только в docs), реальные размеры — `dp()/sp()` в коде.

---

## Сервисы (Android через pyjnius; на desktop — заглушки)

| Пакет | Бэкенд | Суть |
|---|---|---|
| `game/cloud_save/` | **Google Drive appDataFolder** (не Play Games!) | Sign-In со scope `drive.appdata`, REST через urllib+certifi в фоновых потоках. `resolve_auto_sync`: авто-load только на свежую установку, авто-upload только по opt-in (`autosync_uploads`), никогда молча не перезаписывает. |
| `game/iap/` | Play Billing **6.2.1** (Android), StoreKit/pyobjus (iOS) | 6 товаров (`remove_ads` + 5 бандлов гемов, см. `_shared.PRODUCTS`). acknowledge для non-consumable, consume для гемов, фолбэк-доставка без UI-колбэка. Desktop — авто-успех (stub). |
| `game/leaderboard/` | Play Games Services v2 | 3 лидерборда (ID захардкожены в `_shared`). Поллинг вместо Java-колбэков, `_fix_classloader` против SIGBUS. |
| `game/ads.py` | AdMob через **KivMob** | banner/interstitial/rewarded; production unit ID; interstitial ~каждые 5 боёв, rewarded — 2x золото. |
| `game/play/` | Play Core In-App Review | `maybe_show_review()`, fire-and-forget. |
| `game/common/gsignin_poll.py` | — | Общий Clock-поллер результата Sign-In (для cloud и leaderboard). |

---

## Данные (data/)

Каждый JSON — dict с одним корневым ключом. `enemies.json` — 600 записей (крупнейший, ~195КБ) • `injuries.json` — 100 • `weapons/armor.json` — по 50 • `achievements.json` — 50 • `accessories.json` — 30 • `lore.json` — 30 • `relics.json`, `boss_modifiers.json`, `mutators.json` — по 20 • `enchantments.json` — 10 • `fighter_classes.json` — 6 • `expeditions.json` — 5 • `fighter_names.json` — 3 набора имён.

`data/languages/` — два слоя:
- `XX.json` (9 языков, включая en) — плоские **UI-строки** (~800 ключей);
- `data_XX.json` (8 языков, en нет — исходник и есть английский) — переводы **контента** (name/desc для 7 категорий), накладываются `apply_translations()`.

---

## Тесты (tests/, 400+ кейсов) и дев-скрипты (scripts/)

`conftest.py` — фикстура `engine` на tempfile-сейве (реальный сейв не трогается — см. CLAUDE.md).
Покрытие по файлам: сейв (roundtrip, миграции), бой (детерминизм, стан, зачарования), статы (авто-распределение, стамина/усталость, перки), кузница (апгрейды, миграция предметов), bench, импорты/MRO и **`test_name_resolution.py`** (ловит NameError после сплита пакетов — не удалять), скриптинг — 9 файлов (AST, интерпретатор, менеджер, e2e против живого движка, i18n-паритет labels, шаблоны).

`scripts/`: `make_max_save.py` (максимальный сейв), `fill_inventory.py`/`fill_roster.py` (стресс +1000), переводы (`translate_all.py` через deep_translator, `merge_translations.py`, `verify_placeholders.py`, `translations_data*.py`), `test_i18n.py`.

Генераторы ассетов (корень, оффлайн): `generate_sprites.py` (весь пиксель-арт, исключение из лимита 10КБ), `generate_icons.py` + `icon_drawing.py`, `gen_feature_graphic.py`.

---

## Билд и релиз

- `buildozer android debug` / `buildozer android release` → артефакты в `bin/` (release — **AAB**, подписывается keystore из spec; сам keystore в git не попадает — `*.keystore` в .gitignore).
- Конфиг: api 35 / minapi 21 / arm64-v8a; 16KB page alignment (Android 15); ориентация `fullUser` через `p4a.extra_args`; gradle-deps: play-services-auth/games-v2, billing, review.
- В APK пакуется всё по `source.include_exts = py,png,jpg,kv,atlas,json,wav,ttf` (**md не пакуется** — доки/память билд не раздувают).
- Патч `src/patches/SDLActivity.java.patch` применяется при сборке (повторное применение даёт warning — это норма).
- Перед билдом: бамп `version` в spec; `# Build: N` в строке 1 изменённых src-файлов инкрементится при каждом изменении.

---

## Паттерны и инварианты (почему код такой)

1. **Лимит 10КБ на src-файл** → всё крупное разбито на пакеты mixin'ов (`engine/`, `battle/`, экраны). Сабмодули берут общие имена через `from ._shared import *` / `_screen_imports.py` с динамическим `__all__`.
2. **`import game.models as _m` + мутация in-place** в `_wire_data()`: module-level коллекции нельзя ребиндить — сабмодули держат ссылки через star-import. `.clear()` + `.extend()/.update()` обязательны.
3. **Star-import пропускает underscore-имена** → риск NameError между mixin'ами одного пакета; страховка — `tests/test_name_resolution.py`.
4. **Stat-пайплайн** primary → derived (см. CLAUDE.md) — это дизайн, а не наследие.
5. Синглтоны сервисов (`data_loader`, `cloud_save_manager`, `iap_manager`, `leaderboard_manager`, `ad_manager`, `mutator_registry`) создаются на импорте своих пакетов.

---

## Известные несоответствия документации (на 2026-07-24)

- `docs/ARCHITECTURE.md` — описывает домонолитную раскладку и **ошибается по фактам**: облако названо «Play Games Saved Games» (реально Google Drive appdata), конфликт-резолюшн «по arena_tier» (реально «никогда не перезаписывать автоматически»), «data/*.json не используются в рантайме» (используются как источник).
- `docs/API.md`, `docs/BALANCE.md` — ссылаются на несуществующие монолиты (`game/engine.py`, `game/battle.py`, `game/models.py`); имена API в целом актуальны, пути — нет.
- `docs/GDD.md` — версия 1.5.2 (2026-03-29), сильно отстаёт от кода.
- `docs/privacy-policy.html` — не упоминает облачное хранение в Google Drive.
- `ui_config.json` — не читается кодом (см. UI-раздел).
