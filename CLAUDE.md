# Главное правило
Не понял задачу — спроси. Если задача ясна — делай, не жди подтверждения плана.

# Код
- Пиши с расчётом что это будет расширяться. Никаких хаков и "временных решений"
- Не дублируй логику — найди существующую и используй или переделай существующее на что-то лучшее.
- Не ссылайся на то что не проверил в файле
- Константы вместо magic numbers, конкретные except вместо broad

# Перед работой
Читай MEMORY.md. Не доверяй памяти — сверяй с кодом.

# Перед сдачей
pytest, import check, grep на старые ключи. Не говори "готово" пока сам не проверил.

# Перед записью в `~/.gladiator_idle_save.json` или вызовом `engine.load()` / `engine.save()` на нём
**Закрой игру сначала.** Юзер забывает её закрывать. Если игра запущена, её in-memory state перезатрёт любую внешнюю запись на ближайшем автосейве — твой edit будет потерян и ты будешь долго думать «почему он не видит мою программу». Команда (PowerShell через `pwsh.exe` или `powershell.exe`):
```
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*gladiator-idle-manager*' -and $_.CommandLine -like '*main.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; 'Killed PID ' + $_.ProcessId }"
```
Не убивает текущий шелл — фильтр по `main.py` отсекает test-runner'ы. Идемпотентно: если процесса нет, ничего не печатает и возвращает 0. Делай это **первым шагом** любого скрипта который трогает save или симулирует engine.load — pytest сюда не входит (он создаёт свой engine на tmp_save_path и реальный save не трогает).

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
- `game/engine/` — пакет из 11 mixin'ов: CoreEvents/CoreLifecycle/Fighters/Combat/Forge/Expeditions/Healing/Progression/Economy/Persistence/Wiring. `GameEngine` наследует от всех.
- `game/screens/roster/`, `game/screens/forge/` — пакеты с mixin'ами (Hire/Injuries/FighterDetail/Perks/Equipment и Inventory/Upgrade/Enchant/EquipSwap/Shop).

Паттерн `import game.models as _m` — **намеренный**: `engine._wire_data()` мутирует in-place (`.clear()` + `.update()/.extend()`) module-level коллекции (`ALL_FORGE_ITEMS`, `ENCHANTMENT_TYPES`, etc.). Это требование subpackage-шардинга — сабмодули (`_fighter.py`, `_data.py`) держат ссылки через `from ._data import *`.

# Размер файлов
Жёсткого лимита нет (снят 2026-07-25 по решению юзера). Разбивай файл, когда он реально мешает читать или редактировать, а не по счётчику байт. Уже разбитые пакеты (`game/battle/` — 10 submodules, `game/engine/`, `game/ui_helpers/`, `game/screens/roster|forge/`) обратно не склеивать: их mixin-раскладка и `test_cross_package_name_resolution` завязаны друг на друга.

# Кросс-файловые имена
После sub-mixin расщепления есть риск: метод в mixin_A ссылается на global-имя определённое в mixin_B, но не импортированное. `from X import *` **пропускает** underscore-имена. Защита: `tests/test_name_resolution.py::test_cross_package_name_resolution` обходит bytecode каждого split-пакета и ловит такие случаи. НЕ удалять этот тест.
