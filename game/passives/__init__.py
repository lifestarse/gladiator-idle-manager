# Build: 2
"""Per-item passive effects — kind registry, compiler, slot rules, renderer.

Import side effect, and it is deliberate: importing this package registers
every kind, so PASSIVE_KINDS is complete for anything that imports it. Same
shape as the service singletons created on package import (data_loader,
mutator_registry, ...).
"""
from ._registry import (CATEGORY_STATIC, CATEGORY_TRIGGERED, CATEGORIES,
                        COMPILED_PASSIVES, PASSIVE_KINDS, STATIC_EFFECT_KINDS,
                        PassiveKind, PassiveSpec, register_kind,
                        static_effect_for)
from ._slots import is_unlocked, slot_count, unlock_threshold
from ._validate import COND_ALWAYS, compile_all, install, slot_index
from ._render import (PASSIVE_MARK, fmt_amount, passive_count, passive_marker,
                      render, render_args, render_item, render_slots,
                      unlocked_count)

# Declarations last: they call register_kind, which the names above provide.
from . import _kinds_static  # noqa: F401,E402

__all__ = [
    "CATEGORY_STATIC", "CATEGORY_TRIGGERED", "CATEGORIES",
    "COMPILED_PASSIVES", "PASSIVE_KINDS", "STATIC_EFFECT_KINDS",
    "PassiveKind", "PassiveSpec", "register_kind", "static_effect_for",
    "is_unlocked", "slot_count", "unlock_threshold",
    "COND_ALWAYS", "compile_all", "install", "slot_index",
    "PASSIVE_MARK", "fmt_amount", "passive_count", "passive_marker",
    "render", "render_args", "render_item", "render_slots", "unlocked_count",
]
