---
name: memory-location
description: Вся память Claude живёт в memory/ в папке проекта (индекс memory/MEMORY.md, записи в тематических подпапках), не в ~/.claude
metadata:
  type: feedback
  created: 2026-07-24
---

Юзер (2026-07-24) велел хранить всю память Claude в папке проекта, а не в `~/.claude/projects/...`.

**Why:** память должна лежать рядом с кодом — видна юзеру, переживает переустановки, попадает в git вместе с проектом.

**How to apply:** новые записи — отдельными файлами в тематической подпапке `<repo>/memory/` (process / architecture / i18n / remote-content / deploy / game-ui; новая тема — новая подпапка), индекс — строка в секции темы в `<repo>/memory/MEMORY.md`. Имя файла = слаг из frontmatter `name:` (без даты), дата записи — `metadata.created`; структура введена 2026-08-03 по просьбе юзера «собрать в одну папку». В харнесс-директории памяти (`C:\Users\user\.claude\projects\C--Users-user-gladiator-idle-manager\memory\MEMORY.md`) лежит только редирект сюда — содержимое туда не писать. Markdown не попадает в APK (buildozer `source.include_exts` не содержит `md`), так что память билд не раздувает. Конвенция `# Build: N` на память и доки не распространяется — только на исходники.
