---
name: engine-scripting-split-2026-07-24
description: Ветка claude/funny-lamport-92e942 — сплит 4 файлов >10КБ + уже влитые аудит-фиксы; порядок merge в master
metadata:
  type: project
---

Рефакторинг 2026-07-24 (ветка `claude/funny-lamport-92e942`, worktree funny-lamport-92e942): 4 файла-нарушителя правила «10 КБ» разбиты по паттерну плоских суб-mixin'ов (как persistencereadmixin/persistencewritemixin):

- `game/engine/_core.py` → `coreeventsmixin.py` + `corelifecyclemixin.py` (в _core.py остался только `__init__` + `_default_save_path`)
- `game/engine/_combat.py` → композер + `combatspawnmixin.py` / `combatflowmixin.py` / `combatresolvemixin.py`
- `game/scripting/interpreter.py` → `errors.py` (лист, разрывает цикл импортов) + `interpreterexecmixin.py` / `interpreterevalmixin.py`
- `game/scripting/manager.py` → композер + `managerrunmixin.py` (дом RunStats) / `managerasyncmixin.py` / `managerpersistmixin.py`

**Порядок merge:** ветка уже содержит merge-коммит `7b9a00d` с аудит-фиксами `6f514d1` (ветка `claude/fix-found-issues-c82bed` из [[audit-2026-07-24]]) — lock-ханки перенесены в новые файлы, 420 тестов зелёные. В master достаточно влить **только** `claude/funny-lamport-92e942`; фикс-ветка станет её ancestor'ом автоматически. Если фиксы вливать отдельно/раньше — конфликтов не будет (тот же коммит). Если merge-коммит не нужен: `git reset --hard b104302` на ветке оставит чистый сплит.

**Why:** без этой записи легко влить обе ветки вручную и словить конфликт заново, или искать «куда делись lock-фиксы» (они теперь в mixin-файлах, не в исходных четырёх).

**How to apply:** ВЛИТО в master 2026-07-25 (merge 07e393a); `test_cross_package_name_resolution` теперь покрывает и `game.scripting` (PKGS дополнен).

Осталось >10КБ (вне задачи, отдельный чип): `game/screens/scripts/cells.py` (45К), `game/screens/scripts/_core.py` (42К), `game/screens/scripts/popups.py` (26К), `game/scripting/builtins.py` (24К), `game/app/_core.py` (14.5К), `game/scripting/labels.py` (13.9К), `game/scripting/ast_nodes.py` (12.5К), `game/models/_fighter.py` (10.8К), `game/story.py` (10.3К), `game/iap/iapandroidpurchasemixin.py` (10.2К).
