"""
tweaker.py — Live UI editor for Gladiator Idle Manager.
Run:  python tweaker.py
Adjust sliders → preview updates live → SAVE writes to game/theme.py + ui_config.json
"""

import os, re, json, sys

PROJECT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT)

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.label import Label
from game.widgets import AutoShrinkLabel
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line, Ellipse
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import ListProperty, NumericProperty

Window.size = (520, 920)
Window.clearcolor = (0.06, 0.05, 0.05, 1)

THEME_PATH = os.path.join(PROJECT, "game", "theme.py")
CONFIG_PATH = os.path.join(PROJECT, "ui_config.json")

# ── Parse / Save theme.py ──────────────────────────────────

def load_theme_colors():
    colors = {}
    order = []
    with open(THEME_PATH, encoding="utf-8") as f:
        for line in f:
            m = re.match(r'^(\w+)\s*=\s*\(([^)]+)\)', line.strip())
            if m:
                name = m.group(1)
                vals = [float(v.strip()) for v in m.group(2).split(',')]
                if len(vals) >= 3:
                    while len(vals) < 4:
                        vals.append(1.0)
                    colors[name] = vals
                    order.append(name)
    return colors, order


def save_theme_colors(colors):
    with open(THEME_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    out = []
    for line in lines:
        m = re.match(r'^(\w+)\s*=\s*\(([^)]+)\)', line.strip())
        if m and m.group(1) in colors:
            name = m.group(1)
            c = colors[name]
            comment = ""
            idx = line.find("#")
            if idx != -1:
                comment = "  " + line[idx:].rstrip()
            a_fmt = f"{c[3]:.0f}" if c[3] == int(c[3]) else f"{c[3]:.2f}"
            out.append(f"{name} = ({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f}, {a_fmt}){comment}\n")
        elif line.startswith("# Build:"):
            old = re.search(r'\d+', line)
            n = int(old.group()) + 1 if old else 1
            out.append(f"# Build: {n}\n")
        else:
            out.append(line)
    with open(THEME_PATH, "w", encoding="utf-8") as f:
        f.writelines(out)


# ── Sizes config ────────────────────────────────────────────

DEFAULT_SIZES = {
    "nav_height": 80,
    "topbar_height": 44,
    "btn_action_height": 72,
    "btn_default_height": 48,
    "card_roster_height": 90,
    "card_forge_height": 100,
    "card_expedition_height": 160,
    "icon_nav": 24,
    "icon_topbar": 24,
    "font_title": 22,
    "font_body": 18,
    "font_small": 15,
    "font_btn": 16,
    "font_stat": 20,
    "spacing": 6,
    "padding": 10,
    "hp_bar_height": 60,
    "hp_bar_enemy": 56,
}

SIZE_RANGES = {
    "nav_height": (40, 120),
    "topbar_height": (28, 70),
    "btn_action_height": (40, 100),
    "btn_default_height": (30, 70),
    "card_roster_height": (60, 140),
    "card_forge_height": (60, 160),
    "card_expedition_height": (100, 220),
    "icon_nav": (16, 48),
    "icon_topbar": (16, 48),
    "font_title": (14, 36),
    "font_body": (12, 28),
    "font_small": (10, 24),
    "font_btn": (10, 28),
    "font_stat": (12, 30),
    "spacing": (0, 20),
    "padding": (0, 30),
    "hp_bar_height": (30, 100),
    "hp_bar_enemy": (30, 100),
}

SIZE_LABELS = {
    "nav_height": "NavBar height",
    "topbar_height": "TopBar height",
    "btn_action_height": "Action btns height",
    "btn_default_height": "Default btn height",
    "card_roster_height": "Roster card height",
    "card_forge_height": "Forge card height",
    "card_expedition_height": "Expedition card h.",
    "icon_nav": "Nav icon size",
    "icon_topbar": "TopBar icon size",
    "font_title": "Font: title (sp)",
    "font_body": "Font: body (sp)",
    "font_small": "Font: small (sp)",
    "font_btn": "Font: button (sp)",
    "font_stat": "Font: stat (sp)",
    "spacing": "Spacing (dp)",
    "padding": "Padding (dp)",
    "hp_bar_height": "HP bar height",
    "hp_bar_enemy": "Enemy HP bar h.",
}


def load_sizes():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
            return {**DEFAULT_SIZES, **data.get("sizes", {})}
    return dict(DEFAULT_SIZES)


def save_sizes(sizes):
    data = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    data["sizes"] = sizes
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Preview widget ──────────────────────────────────────────

class PreviewPanel(Widget):
    """Live preview of the theme — redraws on any change."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.colors = {}
        self.sizes = {}
        self.bind(pos=self._draw, size=self._draw)

    def update(self, colors, sizes):
        self.colors = colors
        self.sizes = sizes
        self._draw()

    def _c(self, name, fallback=(0.5, 0.5, 0.5, 1)):
        return self.colors.get(name, fallback)

    def _draw(self, *a):
        self.canvas.clear()
        if not self.colors:
            return
        x, y = self.pos
        w, h = self.size
        s = self.sizes or DEFAULT_SIZES

        with self.canvas:
            # Background
            Color(*self._c("BG_DARK"))
            Rectangle(pos=(x, y), size=(w, h))

            # NavBar
            nav_h = s.get("nav_height", 80)
            Color(*self._c("NAV_BG"))
            Rectangle(pos=(x, y), size=(w, nav_h))
            Color(*self._c("DIVIDER"))
            Rectangle(pos=(x, y + nav_h - 1), size=(w, 1))
            # Nav icons (circles)
            icon_s = s.get("icon_nav", 24)
            tab_w = w / 6
            for i in range(6):
                cx = x + tab_w * i + tab_w / 2 - icon_s / 2
                cy = y + nav_h * 0.4
                col = self._c("NAV_ACTIVE") if i == 0 else self._c("NAV_INACTIVE")
                Color(*col)
                Ellipse(pos=(cx, cy), size=(icon_s, icon_s))

            # TopBar
            tb_h = s.get("topbar_height", 44)
            tb_y = y + h - tb_h
            Color(*self._c("NAV_BG"))
            Rectangle(pos=(x, tb_y), size=(w, tb_h))

            # Gold / Diamond / Wins indicators
            for i, col_name in enumerate(["ACCENT_GOLD", "ACCENT_CYAN", "TEXT_SECONDARY"]):
                Color(*self._c(col_name))
                ix = x + w * 0.35 + i * w * 0.22
                Ellipse(pos=(ix, tb_y + tb_h * 0.25), size=(tb_h * 0.5, tb_h * 0.5))

            # Title text area
            Color(*self._c("ACCENT_GOLD"))
            Rectangle(pos=(x + 10, tb_y + tb_h * 0.2), size=(w * 0.25, tb_h * 0.6))

            # Cards
            card_y = y + nav_h + 20
            card_h = s.get("card_roster_height", 90)
            pad = s.get("padding", 10)
            sp_val = s.get("spacing", 6)

            for i in range(3):
                cy = card_y + i * (card_h + sp_val)
                if cy + card_h > tb_y - 10:
                    break
                Color(*self._c("BG_CARD"))
                RoundedRectangle(pos=(x + pad, cy), size=(w - pad * 2, card_h), radius=[8])
                Color(*self._c("DIVIDER"))
                Line(rounded_rectangle=(x + pad, cy, w - pad * 2, card_h, 8), width=0.7)

                # Name text
                Color(*self._c("TEXT_PRIMARY"))
                Rectangle(pos=(x + pad + 10, cy + card_h * 0.6), size=(w * 0.35, card_h * 0.22))

                # Level badge
                Color(*self._c("ACCENT_GOLD"))
                Rectangle(pos=(x + pad + w * 0.5, cy + card_h * 0.6), size=(w * 0.12, card_h * 0.22))

                # Stat icons (STR / AGI / HP)
                for j, cn in enumerate(["ACCENT_RED", "ACCENT_GREEN", "ACCENT_CYAN"]):
                    Color(*self._c(cn))
                    sx = x + pad + 10 + j * w * 0.25
                    Ellipse(pos=(sx, cy + card_h * 0.15), size=(card_h * 0.25, card_h * 0.25))

            # HP bars
            bar_h = s.get("hp_bar_height", 60)
            bar_y = card_y + 2 * (card_h + sp_val) + sp_val + 10
            if bar_y + bar_h < tb_y:
                # Player HP
                Color(*self._c("HP_PLAYER_BG"))
                RoundedRectangle(pos=(x + pad, bar_y), size=(w - pad * 2, bar_h * 0.7), radius=[4])
                Color(*self._c("HP_PLAYER"))
                RoundedRectangle(pos=(x + pad, bar_y), size=((w - pad * 2) * 0.72, bar_h * 0.7), radius=[4])

            # Enemy HP
            ebar_h = s.get("hp_bar_enemy", 56)
            ebar_y = bar_y + bar_h
            if ebar_y + ebar_h < tb_y:
                Color(*self._c("HP_ENEMY_BG"))
                RoundedRectangle(pos=(x + pad, ebar_y), size=(w - pad * 2, ebar_h * 0.6), radius=[4])
                Color(*self._c("HP_ENEMY"))
                RoundedRectangle(pos=(x + pad, ebar_y), size=((w - pad * 2) * 0.45, ebar_h * 0.6), radius=[4])

            # Buttons row
            btn_y = ebar_y + ebar_h + 10
            btn_h = s.get("btn_default_height", 48)
            if btn_y + btn_h < tb_y:
                btn_colors = ["BTN_FIGHT", "ACCENT_PURPLE", "BTN_PRIMARY", "BG_ELEVATED"]
                bw = (w - pad * 2 - sp_val * 3) / 4
                for i, bc in enumerate(btn_colors):
                    bx = x + pad + i * (bw + sp_val)
                    Color(*self._c(bc))
                    RoundedRectangle(pos=(bx, btn_y), size=(bw, btn_h * 0.7), radius=[6])


# ── Color row widget ────────────────────────────────────────

class ColorRow(BoxLayout):
    """One color: label + R/G/B sliders + swatch."""

    def __init__(self, name, rgba, on_change, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(70),
                         padding=[dp(4), 0], spacing=dp(2), **kw)
        self.color_name = name
        self.on_change = on_change

        # Header: name + swatch
        header = BoxLayout(size_hint_y=0.4, spacing=dp(6))
        self.lbl = AutoShrinkLabel(text=name, font_size=sp(13), color=(0.8, 0.8, 0.8, 1),
                         halign="left", size_hint_x=0.7)
        self.lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        header.add_widget(self.lbl)
        self.swatch = Widget(size_hint_x=0.3)
        header.add_widget(self.swatch)
        self.add_widget(header)

        # Sliders: R G B
        row = BoxLayout(size_hint_y=0.6, spacing=dp(4))
        self.sliders = []
        for i, (ch, col) in enumerate([("R", (1, .3, .3, 1)), ("G", (.3, 1, .3, 1)), ("B", (.3, .3, 1, 1))]):
            sl = Slider(min=0, max=1, value=rgba[i], step=0.01,
                        cursor_size=(dp(18), dp(18)),
                        value_track=True, value_track_color=col)
            sl.bind(value=self._on_slider)
            self.sliders.append(sl)
            row.add_widget(sl)
        self.add_widget(row)
        self._update_swatch()

    def _on_slider(self, *a):
        rgba = [sl.value for sl in self.sliders] + [1.0]
        self._update_swatch()
        self.on_change(self.color_name, rgba)

    def _update_swatch(self):
        self.swatch.canvas.clear()
        r, g, b = [sl.value for sl in self.sliders]
        with self.swatch.canvas:
            Color(r, g, b, 1)
            RoundedRectangle(pos=self.swatch.pos, size=self.swatch.size, radius=[4])
        self.swatch.bind(pos=self._redraw_swatch, size=self._redraw_swatch)

    def _redraw_swatch(self, *a):
        self._update_swatch()

    def set_rgba(self, rgba):
        for i, sl in enumerate(self.sliders):
            sl.value = rgba[i]


# ── Size row widget ─────────────────────────────────────────

class SizeRow(BoxLayout):
    def __init__(self, key, value, rng, label_text, on_change, **kw):
        super().__init__(size_hint_y=None, height=dp(40), spacing=dp(6),
                         padding=[dp(4), 0], **kw)
        self.key = key
        self.on_change = on_change
        self.add_widget(AutoShrinkLabel(text=label_text, font_size=sp(12),
                              color=(0.7, 0.7, 0.7, 1), halign="left",
                              text_size=(dp(140), None), size_hint_x=0.45))
        self.sl = Slider(min=rng[0], max=rng[1], value=value, step=1,
                         size_hint_x=0.4, cursor_size=(dp(16), dp(16)),
                         value_track=True, value_track_color=(0.5, 0.5, 0.5, 1))
        self.sl.bind(value=self._on_change)
        self.add_widget(self.sl)
        self.val_lbl = AutoShrinkLabel(text=str(int(value)), font_size=sp(13),
                             color=(1, 0.9, 0.6, 1), size_hint_x=0.15)
        self.add_widget(self.val_lbl)

    def _on_change(self, *a):
        v = int(self.sl.value)
        self.val_lbl.text = str(v)
        self.on_change(self.key, v)


# ── Main App ────────────────────────────────────────────────

class TweakerApp(App):
    def build(self):
        self.title = "Gladiator UI Tweaker"
        self.colors, self.color_order = load_theme_colors()
        self.sizes = load_sizes()
        self.color_rows = {}

        root = BoxLayout(orientation="vertical", spacing=dp(4))

        # ─ Preview (top) ─
        self.preview = PreviewPanel(size_hint_y=0.38)
        root.add_widget(self.preview)

        # ─ Separator ─
        root.add_widget(Widget(size_hint_y=None, height=dp(2)))

        # ─ Scrollable controls ─
        scroll = ScrollView(size_hint_y=0.55)
        controls = BoxLayout(orientation="vertical", size_hint_y=None,
                             spacing=dp(2), padding=[dp(6), dp(4)])
        controls.bind(minimum_height=controls.setter("height"))

        # Colors section
        controls.add_widget(self._section_header("COLORS"))
        for name in self.color_order:
            cr = ColorRow(name, self.colors[name], self._on_color_change)
            self.color_rows[name] = cr
            controls.add_widget(cr)

        # Sizes section
        controls.add_widget(self._section_header("SIZES"))
        for key in DEFAULT_SIZES:
            sr = SizeRow(key, self.sizes.get(key, DEFAULT_SIZES[key]),
                         SIZE_RANGES.get(key, (0, 200)),
                         SIZE_LABELS.get(key, key),
                         self._on_size_change)
            controls.add_widget(sr)

        scroll.add_widget(controls)
        root.add_widget(scroll)

        # ─ Buttons (bottom) ─
        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8),
                            padding=[dp(8), dp(4)])
        save_btn = Button(text="SAVE", font_size=sp(16), bold=True,
                          background_color=(0.35, 0.52, 0.28, 1))
        save_btn.bind(on_press=self._save)
        reset_btn = Button(text="RESET", font_size=sp(16),
                           background_color=(0.65, 0.15, 0.12, 1))
        reset_btn.bind(on_press=self._reset)
        btn_row.add_widget(save_btn)
        btn_row.add_widget(reset_btn)
        root.add_widget(btn_row)

        # Status
        self.status = AutoShrinkLabel(text="", font_size=sp(12), color=(0.5, 0.8, 0.5, 1),
                            size_hint_y=None, height=dp(22))
        root.add_widget(self.status)

        Clock.schedule_once(lambda dt: self._refresh_preview(), 0.1)
        return root

    def _section_header(self, text):
        lbl = AutoShrinkLabel(text=text, font_size=sp(15), bold=True,
                    color=(0.72, 0.58, 0.22, 1), halign="left",
                    size_hint_y=None, height=dp(30))
        lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        return lbl

    def _on_color_change(self, name, rgba):
        self.colors[name] = rgba
        self._refresh_preview()

    def _on_size_change(self, key, value):
        self.sizes[key] = value
        self._refresh_preview()

    def _refresh_preview(self):
        self.preview.update(self.colors, self.sizes)

    def _save(self, *a):
        save_theme_colors(self.colors)
        save_sizes(self.sizes)
        self.status.text = f"Saved to theme.py + ui_config.json"
        Clock.schedule_once(lambda dt: setattr(self.status, "text", ""), 3)

    def _reset(self, *a):
        self.colors, self.color_order = load_theme_colors()
        self.sizes = dict(DEFAULT_SIZES)
        for name, cr in self.color_rows.items():
            if name in self.colors:
                cr.set_rgba(self.colors[name])
        self._refresh_preview()
        self.status.text = "Reset to file values"
        Clock.schedule_once(lambda dt: setattr(self.status, "text", ""), 3)


if __name__ == "__main__":
    TweakerApp().run()
