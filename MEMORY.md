# Память проекта

Вся память Claude хранится здесь: записи — файлы в `memory/`, этот файл — индекс (одна строка на запись).
Карта кодовой базы — [PROJECT_MAP.md](PROJECT_MAP.md).

- [Память в папке проекта](memory/memory-location.md) — где хранить память и почему не в ~/.claude
- [Аудит 2026-07-24](memory/audit-2026-07-24.md) — открыто: ротация пароля keystore (утёк в историю), валидация IAP/лидербордов, broad except; billing/реклама/UMP закрыты
- [Сплит engine/scripting 2026-07-24](memory/engine-scripting-split-2026-07-24.md) — ВЛИТО 2026-07-25: раскладка суб-mixin'ов engine и scripting; лимит 10КБ позже снят
- [Billing 8 + реклама 2026-07-25](memory/billing8-ads-2026-07-25.md) — Billing 8.3.0, game/ads/ + Java-шим, UMP; реклама ВЫКЛЮЧЕНА флагом ADS_ENABLED; девайс-чеклист перед релизом обязателен
- [Дизайн-система 2026-07-25](memory/design-system-2026-07-25.md) — ВЛИТО: variant у кнопок, ChipRow, single_line, спрайты врагов/зон/предметов подключены
- [Переводы данных + гейт 2026-07-25](memory/i18n-data-translations-2026-07-25.md) — 8 языков, конвейер scripts/i18n_tool.py; гейт test_i18n_data_quality.py (13 правил) против подделок — НЕ ослаблять
- [BlueStacks-деплой 2026-07-25](memory/bluestacks-deploy-2026-07-25.md) — WSL buildozer, HD-Adb/порты инстансов; анти-детект BlueStacks прячет каталоги `input` → шим kivy_input_shim.py в main.py НЕ удалять
- [Качество UI-переводов 2026-07-26](memory/i18n-ui-quality-2026-07-26.md) — XX.json был выводом Google Translate на 93–95%; гейт test_i18n_ui_quality.py (13 правил), глоссарий, украинский перечинен, 6 языков ждут
- [Арена + уровень игрока 2026-07-27](memory/arena-and-player-level-2026-07-27.md) — редизайн арены, XP/анлоки; «все с нуля», скрипты последними, побег со штрафом, дальше формация
- [Удалённый контент 2026-07-26](memory/remote-content-overlay-2026-07-26.md) — game/remote_content/: в APK только английский, остальные языки — скачиваемые пакеты; патчи баланса, safe-mode, применение со следующего запуска
- [Скилл game-ui-patterns 2026-07-26](memory/game-ui-skill-2026-07-26.md) — .claude/skills/game-ui-patterns: жанровые паттерны боевых экранов + gap-анализ арены; сторонние скиллы не подошли (веб/Unity)
- [Сканер aislop 2026-07-27](memory/aislop-scanner-2026-07-27.md) — установлен глобально; 7/100 в основном ложные (Build-заголовки, re-export импорты, buildozer.spec); `aislop fix` НЕ запускать
- [Автокоммит в master 2026-07-27](memory/auto-commit-to-master-2026-07-27.md) — готовую работу коммитить и сливать в master автоматически, без подтверждений; push только по явной просьбе
