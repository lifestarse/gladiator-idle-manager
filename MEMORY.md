# Память проекта

Вся память Claude хранится здесь: записи — файлы в `memory/`, этот файл — индекс (одна строка на запись).
Карта кодовой базы — [PROJECT_MAP.md](PROJECT_MAP.md).

- [Память в папке проекта](memory/memory-location.md) — где хранить память и почему не в ~/.claude
- [Аудит 2026-07-24](memory/audit-2026-07-24.md) — топ-проблемы v1.9.37: монетизация, durability сейва, пароль keystore в публичном репо
- [Сплит engine/scripting 2026-07-24](memory/engine-scripting-split-2026-07-24.md) — ВЛИТО в master 2026-07-25: 4 файла >10КБ разбиты, аудит-фиксы внутри
- [Billing 8 + реклама 2026-07-25](memory/billing8-ads-2026-07-25.md) — ВЛИТО в master 2026-07-25 (v1.9.39): Billing 8.3.0, game/ads/ + Java-шим, UMP; девайс-чеклист перед релизом всё ещё обязателен
- [Дизайн-система 2026-07-25](memory/design-system-2026-07-25.md) — ВЛИТО в master 2026-07-25: variant у кнопок, ChipRow, single_line, спрайты врагов/зон/предметов подключены
- [Гейт переводов 2026-07-25](memory/i18n-gate-2026-07-25.md) — tests/test_i18n_data_quality.py НЕ удалять: три подделки переводов и как их ловить; переводы делаются воркфлоу-агентами через scratch/i18n_tool.py
- [Переводы данных 2026-07-25](memory/i18n-data-translations-2026-07-25.md) — 8 языков, конвейер scratch/i18n_tool.py, гейт test_i18n_data_quality.py против подделок (пороги не ослаблять)
- [BlueStacks-деплой 2026-07-25](memory/bluestacks-deploy-2026-07-25.md) — v1.9.42, WSL buildozer, HD-Adb/порты инстансов; анти-детект BlueStacks прячет каталоги `input` → шим kivy_input_shim.py в main.py НЕ удалять
