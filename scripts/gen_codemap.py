"""Генератор карты кода для Obsidian: main.py + game/ + kv/ → codemap/*.md.

Обходит исходники, через ast собирает импорты и пишет по заметке на модуль:
wikilinks в заметках повторяют реальные импорты (только внутрипроектные),
заметки пакетов перечисляют свои модули, kv-заметки ссылаются на модули,
где определены стилизуемые классы. Имена заметок — дотированные пути
(`game.engine._core.md`), чтобы узлы графа были уникальны и читаемы.

Запуск: python scripts/gen_codemap.py [--tests] [--scripts]
codemap/ полностью генерируемый (в .gitignore) — правки руками не выживут.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = ROOT / "game"
KV_DIR = ROOT / "kv"
OUT_DIR = ROOT / "codemap"
INDEX_NAME = "CODEMAP"
EXTRA_SOURCES = {
    "--tests": ROOT / "tests",
    "--scripts": ROOT / "scripts",
}
BUILD_RE = re.compile(r"^#\s*Build:\s*(\d+)")
KV_RULE_RE = re.compile(r"^<([^>]+)>:?\s*$")


class ModInfo:
    """Разобранный .py: метаданные + сырые импорты (резолвятся вторым проходом)."""

    def __init__(self, name: str, path: Path, is_pkg: bool) -> None:
        self.name = name
        self.path = path
        self.is_pkg = is_pkg
        self.loc = 0
        self.build = None
        self.doc = ""
        self.classes: list[str] = []
        self.funcs: list[str] = []
        self.raw_imports: list[tuple] = []  # ("abs", dotted) | ("from", level, module, [aliases])
        self.imports: set[str] = set()


def module_name(py: Path) -> str:
    parts = list(py.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def collect_sources(extra_flags: list[str]) -> list[Path]:
    files = [ROOT / "main.py"]
    files.extend(sorted(GAME_DIR.rglob("*.py")))
    for flag in extra_flags:
        files.extend(sorted(EXTRA_SOURCES[flag].rglob("*.py")))
    return files


def parse_module(py: Path) -> ModInfo | None:
    text = py.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        print(f"  ! пропущен (SyntaxError): {py.name}: {exc}")
        return None
    info = ModInfo(module_name(py), py, py.name == "__init__.py")
    info.loc = text.count("\n") + 1
    first = text.split("\n", 1)[0]
    m = BUILD_RE.match(first)
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
        lines += ["## Содержит", ""]
        lines += [f"- {wl(c)}" for c in sorted(children)]
        lines.append("")
    if info.imports:
        lines += ["## Импортирует", ""]
        lines += [f"- {wl(t)}" for t in sorted(info.imports)]
        lines.append("")
    return "\n".join(lines)


def render_kv(path: Path, rules: list[tuple[str, list[str], bool]]) -> str:
    lines = [f"# kv.{path.stem}", "", f"{src_link(path)}", ""]
    if rules:
        lines += ["## Правила", ""]
        for cls, mods, dynamic in rules:
            suffix = " *(динамический, только kv)*" if dynamic and not mods else ""
            links = " → " + ", ".join(wl(m) for m in sorted(mods)) if mods else ""
            lines.append(f"- `<{cls}>`{links}{suffix}")
        lines.append("")
    return "\n".join(lines)


def render_index(infos: dict[str, ModInfo], kv_files: list[Path]) -> str:
    top_pkgs = sorted(n for n, i in infos.items() if i.is_pkg and n.count(".") == 1)
    root_mods = sorted(
        n for n, i in infos.items()
        if not i.is_pkg and n.count(".") == 1 and n.startswith("game.")
    )
    extra = sorted(n for n in infos if not n.startswith("game") and n != "main")
    lines = [
        f"# {INDEX_NAME}",
        "",
        f"Карта кода: {len(infos)} модулей, {len(kv_files)} kv. "
        "Генерируется `scripts/gen_codemap.py` — руками не править.",
        "",
        "## Вход",
        "",
        f"- {wl('main')} → {wl('game')}",
        "",
        "## Пакеты game/",
        "",
    ]
    lines += [f"- {wl(p)}" for p in top_pkgs]
    lines += ["", "## Модули game/", ""]
    lines += [f"- {wl(m)}" for m in root_mods]
    if extra:
        lines += ["", "## Прочее (tests/scripts)", ""]
        lines += [f"- {wl(m)}" for m in extra]
    lines += ["", "## KV", ""]
    lines += [f"- {wl('kv.' + p.stem)}" for p in kv_files]
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
    flags = sys.argv[1:]
    unknown = [f for f in flags if f not in EXTRA_SOURCES]
    if unknown:
        sys.exit(f"Неизвестные флаги: {unknown}. Доступны: {sorted(EXTRA_SOURCES)}")

    infos: dict[str, ModInfo] = {}
    for py in collect_sources(flags):
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

    kv_files = sorted(KV_DIR.glob("*.kv"))

    clean_out_dir()
    for info in infos.values():
        write_note(info.name, render_module(info, children[info.name]))
    kv_linked = 0
    for kv in kv_files:
        rules = parse_kv(kv, class_index)
        kv_linked += sum(1 for _, mods, _ in rules if mods)
        write_note(f"kv.{kv.stem}", render_kv(kv, rules))
    write_note(INDEX_NAME, render_index(infos, kv_files))

    edges = sum(len(i.imports) for i in infos.values())
    print(
        f"codemap/: {len(infos)} модулей + {len(kv_files)} kv + индекс; "
        f"{edges} импорт-связей, {kv_linked} kv-правил слинковано."
    )


if __name__ == "__main__":
    main()
