---
name: design-system-2026-07-25
description: UI-редизайн (ветка project-design-improvements): варианты кнопок, ChipRow, single_line, спрайты врагов подключены
metadata:
  type: project
---

Редизайн всех экранов (2026-07-25, влит в master, merge 318e624). Новые механизмы, которые надо ИСПОЛЬЗОВАТЬ, а не дублировать:

- `MinimalButton.variant`: `primary` (заливка) / `secondary` (тёмная заливка + цветная рамка, текст = btn_color если text_color не задан) / `ghost` (прозрачная, тихая). Бевел/контур из констант `theme.BTN_OUTLINE / BEVEL_* / BTN_PRESS_OFFSET_PX`. Disabled стилизуется сам — не надо conditional btn_color.
- `ChipRow` (game/widgets/_chips.py) — ряд табов/фильтров: влезает → segmented, нет → скролл. `build_tab_row()` в ui_helpers теперь строит его; `chip_colors={value: rgba}` красит чипы (rarity).
- `AutoShrinkLabel.single_line=True` — не переносит, ужимает шрифт (мерит CoreLabel через `measure_text`). Заголовки TopBar/карточек на нём. Ловушка: text+фикс. width в конструкторе → фит по Clock.schedule_once в __init__ (не убирать).
- `PixelBadge` — бейдж с рамкой (скилл RDY/кулдаун, AWAY).
- Шрифт `BodyFont` (DroidSans) зарегистрирован в app/_shared — для длинных описаний (экспедиции, метаданные скриптов). PixelFont не имеет символов ⋮●○✗🔒 — только ASCII+кириллица, для символов иконки.
- Спрайты врагов/зон/предметов ПОДКЛЮЧЕНЫ (раньше лежали мёртвым грузом): `GladiatorAvatar.sprite_kind` enemy/boss + `constants.ENEMY_ROLE_SPRITE` (role→архетип, tier-бакет `ENEMY_SPRITE_TIER_BUCKET=10`); у Enemy появился `.role`; `zone` в expeditions.json → sprites/zones; `item_icon_source()` в ui_helpers/_widgets → sprites/items.
- Карточки арены/ростера: HP-бар `_bar` (MinimalBar) — `flash_hp_bar` снова работает (искал `._bar`, которого не было). Урон — floating numbers у карточки защитника, kill/skill — тикер `battle_ticker` в разделителе арены (не спавнить в центр поверх карточек).
- Заголовки экранов едино-золотые (title_color убран из kv экранов).

**Why:** до этого кнопки были плоскими слябами, заголовки переносились/обрезались, весь арт врагов не использовался.
**How to apply:** новые кнопки — через variant, новые табы — через build_tab_row, однострочные лейблы — single_line, не хардкодить цвета редкости в чипах.
