# Память проекта

Вся память Claude хранится здесь: записи — файлы в тематических подпапках, этот файл — индекс (одна строка на запись).
Имя файла = слаг записи (`name:` в frontmatter), дата — `metadata.created`. Карта кодовой базы — [PROJECT_MAP.md](../docs/PROJECT_MAP.md).

## Процесс
- [Память в папке проекта](process/memory-location.md) — где хранить память и почему не в ~/.claude
- [Автокоммит в master](process/auto-commit-to-master.md) — готовую работу коммитить и сливать в master автоматически, без подтверждений; push только по явной просьбе
- [Агенты и скиллы](process/agents-and-skills.md) — 8 субагентов в .claude/agents/ (verify/scout/factcheck/reviewer/buildcheck/testwright/i18n-translate/i18n-qa); из сторонних скиллов подошли только 2, остальные проверены и отвергнуты с доказательством
- [Сканер aislop](process/aislop-scanner.md) — установлен глобально; 7/100 в основном ложные (Build-заголовки, re-export импорты, buildozer.spec); `aislop fix` НЕ запускать
- [Опыт из «Симфонии»](process/symphony-transfer.md) — все 8 практик соседнего проекта LLM-перевода ВНЕДРЕНЫ 2026-08-03: карантин скаффолдинга, контракт агентов, prewave-гейт терминов, release_check.py, двусторонний глоссарный гейт, эскалация+леджер волн, слепой QA с калибровкой, идемпотентная публикация; их грабли — не повторять; открыто: паки v1 перегенерированы без бампа ревизии

## Архитектура
- [Сплит engine/scripting](architecture/engine-scripting-split.md) — ВЛИТО 2026-07-25: раскладка суб-mixin'ов engine и scripting; лимит 10КБ позже снят
- [Циклы импортов](architecture/import-cycles.md) — 3 из 4 разорваны, `localization ↔ remote_content` намеренный; ловушка: импорт сабмодуля НЕ развязывает с пакетом (родительский `__init__` выполняется целиком)
- [Сигналы codemap](architecture/codemap-signals.md) — чему в codemap верить нельзя: `# Build: N` не счётчик правок (наследуется при сплите), `from . import X` рождает фантомные циклы, «неупомянутый» артефакт может грузиться вычисляемым путём
- [Аудит 2026-07-24](architecture/audit-2026-07-24.md) — открыто: ротация пароля keystore (утёк в историю), валидация IAP/лидербордов, broad except; billing/реклама/UMP закрыты

## i18n
- [Переводы данных + гейт](i18n/i18n-data-translations.md) — 8 языков, конвейер scripts/i18n_tool.py; гейт test_i18n_data_quality.py (13 правил) против подделок — НЕ ослаблять
- [Качество UI-переводов](i18n/i18n-ui-quality.md) — XX.json был выводом Google Translate на 93–95%; гейт test_i18n_ui_quality.py (13 правил), глоссарий, украинский перечинен, 6 языков ждут

## Удалённый контент
- [Удалённый контент](remote-content/remote-content-overlay.md) — game/remote_content/: в APK только английский, остальные языки — скачиваемые пакеты; патчи баланса, safe-mode, применение со следующего запуска
- [Удалённые шрифты](remote-content/remote-fonts.md) — шрифт едет с языковым паком (content-addressed по sha256), список языков в пикере из манифеста: новый язык без релиза; грабли — IncompleteRead, kivy парсит argv

## Билд и деплой
- [BlueStacks-деплой](deploy/bluestacks-deploy.md) — WSL buildozer, HD-Adb/порты инстансов; анти-детект BlueStacks прячет каталоги `input` → шим kivy_input_shim.py в main.py НЕ удалять
- [Деплой на телефон](deploy/phone-deploy.md) — Pixel по adb; Play-подпись поверх не встаёт (снесена), upload-ключ в WSL ~/gladiator-build, пароль из git-истории рабочий
- [Billing 8 + реклама](deploy/billing8-ads.md) — Billing 8.3.0, game/ads/ + Java-шим, UMP; реклама ВЫКЛЮЧЕНА флагом ADS_ENABLED; девайс-чеклист перед релизом обязателен

## Игра и UI
- [Дизайн-система](game-ui/design-system.md) — ВЛИТО: variant у кнопок, ChipRow, single_line, спрайты врагов/зон/предметов подключены
- [Арена + уровень игрока](game-ui/arena-and-player-level.md) — редизайн арены, XP/анлоки; «все с нуля», скрипты последними, побег со штрафом, дальше формация
- [Скилл game-ui-patterns](game-ui/game-ui-skill.md) — .claude/skills/game-ui-patterns: жанровые паттерны боевых экранов + gap-анализ арены; сторонние скиллы не подошли (веб/Unity)
