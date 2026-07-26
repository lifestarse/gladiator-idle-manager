# НЕ ЗАПУСКАТЬ

Здесь лежат генераторы, каждый из которых при повторном запуске затрёт настоящие
переводы. Хранятся как улики и как напоминание, зачем существуют оба приёмочных гейта.

## Подделки данных (2026-07-25)

`apply_full_translations.py`, `build_and_apply_all_translations.py`, `build_clean_data.py`,
`build_perfect_translations.py`, `generate_all_guaranteed.py`, `populate_*.py`, `inspect_*.py`

Написал LLM-исполнитель, который трижды подделал переводы. Они не переводят: берут
английский оригинал и приклеивают к нему локализованную приставку либо раскатывают один
боилерплейт с подставленным id на всю секцию. Затрут `data/languages/data_*.json`
(все 8 языков). Гейт против них — `tests/test_i18n_data_quality.py`.

## Машинный перевод интерфейса (2026-07-01, перемещён сюда 2026-07-26)

`translate_all.py`

Гонял `en.json` через `deep_translator.GoogleTranslator` построчно, без контекста и без
глоссария, и записывал результат в `data/languages/{uk,de,es,fr,it,pt,pl}.json`. Именно
он породил «Автопоїзд» (Auto-train → залізничний поїзд), «{n} винищувачі» (fighter →
літак), «-{dmg}KM» (HP → кінські сили), «+{diamonds} Durchm.» (dia. → діаметр) и
«дзвонити» (call → телефонний дзвінок). 93–95% строк каждого языка были его выводом.

Повторный запуск затрёт `data/languages/<lang>.json` (7 языков, 856 строк каждый).
Гейт против него — `tests/test_i18n_ui_quality.py`.

## Настоящий конвейер

`../../scripts/i18n_tool.py`

- данные: `extract` / `merge <lang>` / `status`
- интерфейс: `extract-ui <lang>` / `merge-ui <lang>` / `status-ui`

Терминология — `../../scripts/i18n_glossary.json`. Переводят воркфлоу-агенты по батчам
из `scratch/i18n_src/`, пишут в `scratch/i18n_out/`, merge — детерминированный.
