"""Генератор карты проекта для Obsidian: весь репозиторий → codemap/*.md.

Индексируется каждый источник проекта:
- *.py везде (main, game/, tests/, scripts/, корневые генераторы) — связи =
  реальные импорты через ast; тестам добавляется связь с tests/conftest.py
  (pytest внедряет фикстуры без импорта — иначе тесты висят без рёбер);
- kv/*.kv + gladiatoridle.kv — связи с модулями, где определены их классы;
- data/**/*.json, java_src/**/*.java, buildozer.spec, ui_config.json — связи
  по упоминанию имени файла в коде (полное имя — везде; голый стем в кавычках —
  только в модулях-загрузчиках, чтобы не плодить ложные рёбра типа
  строки "lore" в SCREEN_ORDER).

Имена заметок — дотированные пути (`game.engine._core`, `data.enemies`,
`tests.test_bench`), чтобы узлы графа были уникальны и читаемы.

Запуск: python scripts/gen_codemap.py
codemap/ полностью генерируемый (в .gitignore) — правки руками не выживут.
Не индексируются: .buildozer, .git, .claude, bin, scratch (карантин),
docs/content (генерируемая публикация) и бинарные ассеты (png/wav — их пути
вычисляются в рантайме, honest-связей по тексту не построить).
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KV_DIR = ROOT / "kv"
OUT_DIR = ROOT / "codemap"
INDEX_NAME = "CODEMAP"
EXCLUDE_DIRS = {
    ".buildozer", ".git", ".claude", ".obsidian", ".pytest_cache",
    "__pycache__", "bin", "codemap", "scratch",
}
CONFTEST = "tests.conftest"
ROOT_KV = ROOT / "gladiatoridle.kv"
# Не-python артефакты: (glob-корень, паттерн). docs/content — генерируемая
# публикация пакетов, её не индексируем (как и сам codemap).
ARTIFACT_GLOBS = (
    (ROOT / "data", "**/*.json"),
    (ROOT / "java_src", "**/*.java"),
)
ARTIFACT_FILES = (ROOT / "buildozer.spec", ROOT / "ui_config.json")
# Голый стем в кавычках («enemies», «uk») — легитимная ссылка на файл только
# в загрузчиках данных/языков и дев-скриптах; в остальном коде такие строки —
# ключи/имена экранов, не файлы.
STEM_SCAN_PREFIXES = (
    "game.data_loader", "game.remote_content", "game.localization",
    "game.constants", "scripts.",
)
BUILD_RE = re.compile(r"^#\s*Build:\s*(\d+)")
KV_RULE_RE = re.compile(r"^<([^>]+)>:?\s*$")


class ModInfo:
    """Разобранный .py: метаданные + сырые импорты (резолвятся вторым проходом)."""

    def __init__(self, name: str, path: Path, is_pkg: bool) -> None:
        self.name = name
        self.path = path
        self.is_pkg = is_pkg
        self.text = ""
        self.loc = 0
        self.build = None
        self.doc = ""
        self.classes: list[str] = []
        self.funcs: list[str] = []
        self.raw_imports: list[tuple] = []  # ("abs", dotted) | ("from", level, module, [aliases])
        self.imports: set[str] = set()
        self.fixture_dep = False  # tests.* → tests.conftest


def dotted_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def collect_py() -> list[Path]:
    files = []
    for py in sorted(ROOT.rglob("*.py")):
        rel_parts = py.relative_to(ROOT).parts
        if any(p in EXCLUDE_DIRS for p in rel_parts[:-1]):
            continue
        files.append(py)
    return files


def parse_module(py: Path) -> ModInfo | None:
    text = py.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        print(f"  ! пропущен (SyntaxError): {py.name}: {exc}")
        return None
    info = ModInfo(dotted_name(py), py, py.name == "__init__.py")
    info.text = text
    info.loc = text.count("\n") + 1
    m = BUILD_RE.match(text.split("\n", 1)[0])
    if m:
        info.build = m.group(1)
    doc = ast.get_docstring(tree)
    if doc:
        info.doc = doc.strip().splitlines()[0]
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            info.classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.funcs.append(node.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                info.raw_imports.append(("abs", alias.name))
        elif isinstance(node, ast.ImportFrom):
            aliases = [a.name for a in node.names]
            info.raw_imports.append(("from", node.level, node.module or "", aliases))
    return info


def resolve(dotted: str, modules: set[str]) -> str | None:
    """Самый длинный существующий префикс дотированного имени, иначе None (внешний)."""
    parts = dotted.split(".")
    while parts:
        cand = ".".join(parts)
        if cand in modules:
            return cand
        parts.pop()
    return None


def resolve_imports(info: ModInfo, modules: set[str]) -> None:
    for raw in info.raw_imports:
        targets: list[str | None] = []
        if raw[0] == "abs":
            targets.append(resolve(raw[1], modules))
        else:
            _, level, module, aliases = raw
            if level == 0:
                base = module
            else:
                pkg = info.name if info.is_pkg else info.name.rsplit(".", 1)[0]
                pkg_parts = pkg.split(".")
                if level - 1 >= len(pkg_parts):
                    continue  # выход за корень проекта
                base = ".".join(pkg_parts[: len(pkg_parts) - (level - 1)])
                if module:
                    base += "." + module
            for alias in aliases:
                dotted = base if alias == "*" else f"{base}.{alias}" if base else alias
                targets.append(resolve(dotted, modules))
        info.imports.update(t for t in targets if t and t != info.name)
    if info.name.startswith("tests.") and info.name != CONFTEST and CONFTEST in modules:
        info.fixture_dep = True


def parse_kv(path: Path, class_index: dict[str, list[str]]) -> list[tuple[str, list[str], bool]]:
    """[(имя класса, модули где определён, динамический ли @-класс)] по правилам файла."""
    rules = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = KV_RULE_RE.match(line.strip())
        if not m:
            continue
        for piece in m.group(1).split(","):
            piece = piece.strip()
            if not piece or piece.startswith("-"):
                continue  # <-Rule> — удаление правила, не определение
            cls, _, _base = piece.partition("@")
            rules.append((cls, class_index.get(cls, []), "@" in piece))
    return rules


def artifact_name(path: Path) -> str:
    rel = path.relative_to(ROOT)
    if rel.suffix == ".java":
        return "java." + rel.stem
    if rel.parts[0] == "data":
        return ".".join(rel.with_suffix("").parts)
    return rel.name  # buildozer.spec, ui_config.json


def find_mentions(path: Path, infos: dict[str, ModInfo], kv_texts: dict[str, str],
                  spec_text: str) -> tuple[list[str], bool]:
    """Модули/kv, упоминающие файл. (список имён заметок, упомянут ли в spec)."""
    base, stem = path.name, path.stem
    quoted = (f'"{stem}"', f"'{stem}'")
    # Java-классы (CamelCase) в питоне фигурируют голым именем внутри JNI-путей
    # ("com/gladiator/ads/AdsCallback") — для них ищем стем без кавычек.
    bare_stem_ok = path.suffix == ".java"
    hits = set()
    for info in infos.values():
        if base in info.text or (bare_stem_ok and stem in info.text):
            hits.add(info.name)
        elif info.name.startswith(STEM_SCAN_PREFIXES) and any(q in info.text for q in quoted):
            hits.add(info.name)
    for kv_name, text in kv_texts.items():
        if base in text:
            hits.add(kv_name)
    return sorted(hits), base in spec_text


def wl(name: str) -> str:
    return f"[[{name}]]"


def src_link(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return f"[{rel}](../{rel})"


def render_module(info: ModInfo, children: list[str]) -> str:
    lines = [f"# {info.name}", ""]
    meta = f"{src_link(info.path)} · {info.loc} строк"
    if info.build:
        meta += f" · Build {info.build}"
    lines += [meta, ""]
    if info.doc:
        lines += [f"> {info.doc}", ""]
    if info.classes:
        lines.append("**Классы:** " + ", ".join(f"`{c}`" for c in info.classes))
    if info.funcs:
        lines.append("**Функции:** " + ", ".join(f"`{f}`" for f in info.funcs))
    if info.classes or info.funcs:
        lines.append("")
    if children:
        lines += ["## Содержит", ""] + [f"- {wl(c)}" for c in sorted(children)] + [""]
    if info.imports:
        lines += ["## Импортирует", ""] + [f"- {wl(t)}" for t in sorted(info.imports)] + [""]
    if info.fixture_dep:
        lines += ["## Фикстуры", "", f"- {wl(CONFTEST)} *(pytest внедряет без импорта)*", ""]
    return "\n".join(lines)


def render_kv(name: str, path: Path, rules: list) -> str:
    lines = [f"# {name}", "", f"{src_link(path)}", ""]
    if rules:
        lines += ["## Правила", ""]
        for cls, mods, dynamic in rules:
            suffix = " *(динамический, только kv)*" if dynamic and not mods else ""
            links = " → " + ", ".join(wl(m) for m in sorted(mods)) if mods else ""
            lines.append(f"- `<{cls}>`{links}{suffix}")
        lines.append("")
    return "\n".join(lines)


def render_artifact(name: str, path: Path, mentions: list[str], in_spec: bool) -> str:
    kb = path.stat().st_size / 1024
    lines = [f"# {name}", "", f"{src_link(path)} · {kb:.1f} КБ", ""]
    if mentions:
        lines += ["## Кто упоминает", ""] + [f"- {wl(m)}" for m in mentions] + [""]
    else:
        lines += ["Упоминаний в коде не найдено (путь может вычисляться в рантайме).", ""]
    if in_spec:
        lines += [f"Упомянут в {wl('buildozer.spec')}.", ""]
    return "\n".join(lines)


def render_index(infos: dict[str, ModInfo], kv_names: list[str],
                 artifact_names: list[str]) -> str:
    def section(title: str, names: list[str]) -> list[str]:
        return ["", f"## {title}", ""] + [f"- {wl(n)}" for n in names] if names else []

    mods = sorted(infos)
    top_pkgs = [n for n in mods if infos[n].is_pkg and n.startswith("game.") and n.count(".") == 1]
    game_mods = [n for n in mods if not infos[n].is_pkg and n.startswith("game.") and n.count(".") == 1]
    tests = [n for n in mods if n.startswith("tests.")]
    scripts = [n for n in mods if n.startswith("scripts.")]
    root_py = [n for n in mods if "." not in n and n != "main"]
    data = [n for n in artifact_names if n.startswith("data.")]
    java = [n for n in artifact_names if n.startswith("java.")]
    configs = [n for n in artifact_names if n not in data and n not in java]
    lines = [
        f"# {INDEX_NAME}",
        "",
        f"Карта проекта: {len(infos)} py-модулей, {len(kv_names)} kv, "
        f"{len(artifact_names)} данных/конфигов. Генерируется "
        "`scripts/gen_codemap.py` — руками не править.",
        "",
        "## Вход",
        "",
        f"- {wl('main')} → {wl('game')}",
    ]
    lines += section("Пакеты game/", top_pkgs)
    lines += section("Модули game/", game_mods)
    lines += section("Тесты", tests)
    lines += section("Дев-скрипты", scripts)
    lines += section("Генераторы ассетов (корень)", root_py)
    lines += section("KV", kv_names)
    lines += section("Данные", data)
    lines += section("Java", java)
    lines += section("Конфиги", configs)
    lines.append("")
    return "\n".join(lines)


def clean_out_dir() -> None:
    if not OUT_DIR.exists():
        OUT_DIR.mkdir()
        return
    alien = [p for p in OUT_DIR.iterdir() if p.suffix != ".md"]
    if alien:
        sys.exit(f"В {OUT_DIR} посторонние файлы (не .md): {alien[:3]} — не трогаю, убери их сам.")
    for p in OUT_DIR.glob("*.md"):
        p.unlink()


def write_note(name: str, content: str) -> None:
    with open(OUT_DIR / f"{name}.md", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def main() -> None:
    infos: dict[str, ModInfo] = {}
    for py in collect_py():
        info = parse_module(py)
        if info:
            infos[info.name] = info
    modules = set(infos)
    for info in infos.values():
        resolve_imports(info, modules)

    children: dict[str, list[str]] = {n: [] for n in modules}
    for name in modules:
        parent = name.rsplit(".", 1)[0] if "." in name else None
        if parent in children:
            children[parent].append(name)

    class_index: dict[str, list[str]] = {}
    for info in infos.values():
        for cls in info.classes:
            class_index.setdefault(cls, []).append(info.name)

    kv_files = [p for p in sorted(KV_DIR.glob("*.kv"))]
    if ROOT_KV.exists():
        kv_files.append(ROOT_KV)
    kv_notes = {f"kv.{p.stem}": p for p in kv_files}
    kv_texts = {name: p.read_text(encoding="utf-8") for name, p in kv_notes.items()}

    artifacts: dict[str, Path] = {}
    for base_dir, pattern in ARTIFACT_GLOBS:
        for p in sorted(base_dir.glob(pattern)):
            artifacts[artifact_name(p)] = p
    for p in ARTIFACT_FILES:
        if p.exists():
            artifacts[artifact_name(p)] = p
    spec_text = (ROOT / "buildozer.spec").read_text(encoding="utf-8")

    clean_out_dir()
    for info in infos.values():
        write_note(info.name, render_module(info, children[info.name]))
    kv_linked = 0
    for name, path in kv_notes.items():
        rules = parse_kv(path, class_index)
        kv_linked += sum(1 for _, mods, _ in rules if mods)
        write_note(name, render_kv(name, path, rules))
    mentioned = 0
    for name, path in sorted(artifacts.items()):
        mentions, in_spec = find_mentions(path, infos, kv_texts, spec_text)
        mentioned += bool(mentions)
        write_note(name, render_artifact(name, path, mentions, in_spec))
    write_note(INDEX_NAME, render_index(infos, sorted(kv_notes), sorted(artifacts)))

    edges = sum(len(i.imports) + i.fixture_dep for i in infos.values())
    print(
        f"codemap/: {len(infos)} py + {len(kv_notes)} kv + {len(artifacts)} данных/конфигов"
        f" + индекс; {edges} импорт-связей, {kv_linked} kv-правил слинковано,"
        f" {mentioned}/{len(artifacts)} артефактов упомянуты в коде."
    )


if __name__ == "__main__":
    main()
