---
name: agents-and-skills
description: 8 проектных субагентов в .claude/agents/ + 2 сторонних скилла; чужие скиллы под Python/i18n/Android проверены и почти все отвергнуты
metadata:
  type: project
  created: 2026-07-28
---

Созданы 8 субагентов в `.claude/agents/` (2026-07-28) в стиле агентов проекта
«4.6 billion years of simphony»: узкая роль, урезанный `tools:`, железные правила,
самопроверка, ответ — одна строка отчёта.

| Агент | Зачем | tools |
|---|---|---|
| `verify` | весь pytest → одна строка вердикта | PowerShell, Read |
| `scout` | поиск по коду → список `file:line` | Read, Grep, Glob |
| `factcheck` | вердикт на каждое утверждение о коде + доказательство | Read, Grep, Glob |
| `reviewer` | дифф против правил CLAUDE.md, вердикт block/fix/ok | +PowerShell |
| `buildcheck` | `# Build: N`, версия в spec, 3 гейта упаковки | PowerShell, Read, Grep |
| `testwright` | пишет тест по конвенциям, правит только `tests/` | +Write, Edit |
| `i18n-translate` | переводит один батч → фрагмент в `scratch/i18n_out/` | Read, Write |
| `i18n-qa` | смысловая вычитка языка против **ru** | Read, Grep, Glob |

**Why:** экономия контекста и защита от выдумок. Полный прогон — 1025 passed /
52 skipped за 16 с и тысячи строк вывода; серия Grep/Read по пакетам mixin'ов —
десятки файлов. У субагента отдельный контекст, наружу приходит одна строка.
`factcheck` и `scout` существуют ровно под правило CLAUDE.md «не ссылайся на то,
что не проверил в файле»: вердикт без `file:line` не вердикт, «похоже на правду» =
`unfound`.

**How to apply:** зовёшь агента вместо того, чтобы делать это руками в основном
контексте. Ловушки, зашитые в промпты (чтобы не искать заново): `docs/` врёт
намеренно и доказательством не является; `# Build: N` не счётчик правок
(см. [[codemap-signals]]); ре-экспорт через `__init__.py` ≠ определение;
`translate_all.py` не запускать; гейты `test_i18n_*_quality` / `test_name_resolution`
не ослаблять; `GameEngine()` без `save_path` в тестах запрещён.

**Сторонние скиллы: проверено, почти всё мимо.** Установлены два из
[wdm0006/python-skills](https://github.com/wdm0006/python-skills) (MIT, LICENSE лежит
рядом с каждым): `keeping-git-repos-clean` (порядок «сначала ротация, потом
history scrub» — прямо по открытому пункту [[audit-2026-07-24]] про пароль keystore;
`git ls-files` на 2026-07-28 чист) и `optimizing-python-performance` (инструменты
профилирования; в шапку дописана поправка — uv и pytest-benchmark в проекте нет).

Отвергнуто с доказательством:
- `Mindrally/skills` — конвертированные Cursor-rules. `internationalization-i18n`
  это i18next/React/Next.js/Zustand, к Kivy отношения не имеет; `python-testing` —
  60 строк общих слов. Установка такого **повышает** риск галлюцинаций: подсунет
  веб-паттерны в мобильный Kivy-проект.
- `instantX-research/anthropic-anti-hallucinate-skills` — общая риторика «говори
  „не знаю“», не про код. Дублирует базовое поведение, жрёт контекст.
- Остальные скиллы `wdm0006` (`testing-strategy`, `code-quality`, `project-setup`) —
  про библиотеки на uv/ruff/mypy/PyPI; здесь ничего этого нет.

Скилла под i18n-конвейер намеренно **не** заводил: `scripts/i18n_tool.py` описывает
себя в docstring и вкладывает глоссарий прямо в батч, а контекст ошибок лежит в
[[i18n-ui-quality]]. Третья копия тех же знаний разъехалась бы с двумя
первыми. Про сторонние UI-скиллы см. [[game-ui-skill]] — тот же вывод
был получен раньше и подтвердился.
