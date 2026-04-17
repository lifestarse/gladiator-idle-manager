# Главное правило
Не понял задачу — спроси. Не начинай код без плана и подтверждения.

# Код
- Пиши с расчётом что это будет расширяться. Никаких хаков и "временных решений"
- Не упрощай существующую архитектуру без явного разрешения
- Не дублируй логику — найди существующую и используй
- Не ссылайся на то что не проверил в файле
- Константы вместо magic numbers, конкретные except вместо broad

# Перед работой
Читай MEMORY.md. Не доверяй памяти — сверяй с кодом.

# Перед сдачей
pytest, import check, grep на старые ключи. Не говори "готово" пока сам не проверил.

# Build
`# Build: N` на строке 1 каждого файла. Инкрементируй при каждом изменении. Версию в buildozer.spec бампай перед билдом. AAB всегда подписывай. `.buildozer/` не удаляй.

# Stat system (НЕ дуализм, а пайплайн)
**Primary stats** — `strength / agility / vitality` хранятся на бойце и предметах.
**Derived stats** — `attack / defense / max_hp / hp` вычисляются из primary:
- `ATK = total_strength × FIGHTER_ATK_PER_STR + base_attack + upgrades`
- `DEF = total_vitality + base_defense + upgrade_def`
- `max_HP = FIGHTER_BASE_HP + total_vitality × FIGHTER_HP_PER_VIT + base_hp + ...`

UI показывает **derived** (ATK/DEF/HP), бой использует **derived**, экипировка даёт **primary** (`base_str/base_agi/base_vit` в JSON → `str/agi/vit` после `data_loader.normalize`). Это нормальная RPG-модель, не наследие миграции — не "исправлять".

# Архитектура (после рефакторинга 2026-04-17)
- `game/ui_helpers/` — пакет (12 submodules), `__init__.py` re-exports всё. Внешние импорты неизменны.
- `game/engine/` — пакет из 8 mixin'ов: Fighters/Combat/Forge/Expeditions/Healing/Progression/Economy/Persistence. `GameEngine` наследует от всех.
- `game/screens/roster/`, `game/screens/forge/` — пакеты с mixin'ами (Hire/Injuries/FighterDetail/Perks/Equipment и Inventory/Upgrade/Enchant/EquipSwap/Shop).

Паттерн `import game.models as _m` — **намеренный**: `engine._wire_data()` перезаписывает module-level глобалы (`ALL_FORGE_ITEMS`, `ENCHANTMENT_TYPES`, etc.) из JSON. Прямой импорт `from game.models import X` захватил бы stale reference.
