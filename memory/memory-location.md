---
name: memory-location
description: Вся память Claude живёт в папке проекта (MEMORY.md + memory/), не в ~/.claude
metadata:
  type: feedback
---

Юзер (2026-07-24) велел хранить всю память Claude в папке проекта, а не в `~/.claude/projects/...`.

**Why:** память должна лежать рядом с кодом — видна юзеру, переживает переустановки, попадает в git вместе с проектом.

**How to apply:** новые записи — отдельными файлами в `<repo>/memory/`, индекс — строка в `<repo>/MEMORY.md`. В харнесс-директории памяти (`C:\Users\user\.claude\projects\C--Users-user-gladiator-idle-manager\memory\MEMORY.md`) лежит только редирект сюда — содержимое туда не писать. Markdown не попадает в APK (buildozer `source.include_exts` не содержит `md`), так что память билд не раздувает. Конвенция `# Build: N` на память и доки не распространяется — только на исходники.
