# Build: 1
"""The language picker, shared by first launch and the More screen.

Only English ships in the APK; every other language is a downloadable pack
(game/remote_content/packs.py). So the picker is not a list of nine buttons any
more — each row has to say whether that language is on the device, whether an
update exists, and show real progress while it downloads.

Both callers used to build their own copy of the list. One shared builder is
what keeps the first-launch popup and the More-screen popup from drifting apart
the moment either grows a feature.

Threading contract: the download runs on a worker thread (it is a network call
and must not freeze the frame), and every widget touch is marshalled back with
Clock.schedule_once. Nothing in here mutates game state — the caller's
``on_chosen`` does that, and it is invoked on the main thread.
"""
from ._imports import *  # noqa: F401,F403

import threading

from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp, sp
from kivy.graphics import Color, Rectangle

from game.localization import t, get_language
from game.theme import (ACCENT_BLUE, ACCENT_GOLD, ACCENT_GREEN, BG_CARD,
                        BG_ELEVATED, TEXT_MUTED, TEXT_SECONDARY, popup_color)
from game.widgets import MinimalButton

ROW_HEIGHT = dp(52)
BAR_HEIGHT = dp(3)


class _ProgressBar(BoxLayout):
    """A two-rectangle determinate bar. Set .fraction, or None for a pulse.

    Deliberately not a Kivy ProgressBar: that widget cannot express "size
    unknown", and a bar that sits at zero while bytes are arriving reads as a
    hang. With fraction=None this one sweeps instead.
    """

    def __init__(self, **kwargs):
        super().__init__(size_hint_y=None, height=BAR_HEIGHT, **kwargs)
        self._fraction = 0.0
        self._pulse = 0.0
        self._pulse_event = None
        with self.canvas:
            Color(*BG_ELEVATED)
            self._track = Rectangle(pos=self.pos, size=self.size)
            Color(*ACCENT_GOLD)
            self._fill = Rectangle(pos=self.pos, size=(0, self.height))
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_args):
        self._track.pos, self._track.size = self.pos, self.size
        if self._fraction is None:
            width = self.width * 0.25
            travel = (self.width - width) * self._pulse
            self._fill.pos = (self.x + travel, self.y)
            self._fill.size = (width, self.height)
        else:
            self._fill.pos = self.pos
            self._fill.size = (self.width * self._fraction, self.height)

    def set_fraction(self, fraction):
        self._fraction = fraction
        if fraction is None and self._pulse_event is None:
            self._pulse_event = Clock.schedule_interval(self._advance_pulse, 1 / 30)
        elif fraction is not None:
            self.stop()
        self._redraw()

    def _advance_pulse(self, dt):
        # Ping-pong so the sweep never jumps back to the left edge.
        self._pulse = (self._pulse + dt * 0.6) % 2
        self._redraw()

    def stop(self):
        if self._pulse_event is not None:
            self._pulse_event.cancel()
            self._pulse_event = None


def _status_text(status):
    """Human-readable status. Keys live in the language files so this
    localizes with everything else; t() falls back to the key if a pack
    predates them, which is legible enough to ship."""
    return {
        "bundled": t("lang_status_bundled"),
        "installed": t("lang_status_installed"),
        "update": t("lang_status_update"),
        "not_installed": t("lang_status_download"),
        "unavailable": t("lang_status_unavailable"),
    }.get(status, "")


def _stage_text(stage):
    return {
        "checking": t("lang_stage_checking"),
        "downloading": t("lang_stage_downloading"),
        "installing": t("lang_stage_installing"),
        "done": t("lang_stage_done"),
        "offline": t("lang_stage_offline"),
        "failed": t("lang_stage_failed"),
        "unavailable": t("lang_status_unavailable"),
    }.get(stage, stage)


class _LanguageRow(BoxLayout):
    """One language: name button, status caption, and a progress bar."""

    def __init__(self, name, code, status, on_pick, is_current, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None,
                         height=ROW_HEIGHT, spacing=dp(2), **kwargs)
        self.code = code
        self._on_pick = on_pick
        self._busy = False

        colour = ACCENT_GOLD if is_current else (
            ACCENT_BLUE if status in ("bundled", "installed", "update")
            else TEXT_SECONDARY)
        self.button = MinimalButton(
            text=f"{'> ' if is_current else ''}{name}",
            size_hint_y=None, height=dp(34), btn_color=colour, font_size=9,
        )
        self.button.bind(on_press=self._pressed)
        self.add_widget(self.button)

        self.caption = Label(
            text=_status_text(status), size_hint_y=None, height=dp(12),
            font_size=sp(9), color=(TEXT_MUTED if status in ("bundled", "installed")
                                    else ACCENT_GREEN),
            halign="center", valign="middle",
        )
        self.caption.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        self.add_widget(self.caption)

        self.bar = _ProgressBar(opacity=0)
        self.add_widget(self.bar)

    def _pressed(self, *_args):
        if not self._busy:
            self._on_pick(self)

    def set_busy(self, busy):
        self._busy = busy
        self.button.disabled = busy
        self.bar.opacity = 1 if busy else 0
        if not busy:
            self.bar.stop()

    def show_stage(self, stage, fraction):
        """Called on the main thread only."""
        self.caption.text = _stage_text(stage)
        if stage == "downloading":
            self.bar.set_fraction(fraction)
        elif stage in ("checking", "installing"):
            self.bar.set_fraction(None)


def open_language_pack_fetch(lang, on_done, on_give_up=None):
    """Fetch one specific pack, with progress, before the game is usable.

    This is the update path, not the first-run path: the player already chose
    this language on an older build where every language was bundled. Their
    save says "ru" and this APK has only English, so without this they would
    open the game after an update and find it in a language they did not pick.

    Offline or failed, the player gets a button to continue in English rather
    than a dead popup — refusing to start the game over a text pack would be a
    worse bug than the one this prevents.
    """
    from game import remote_content

    body = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
    caption = Label(text=_stage_text("checking"), font_size=sp(11),
                    halign="center", valign="middle")
    caption.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
    bar = _ProgressBar()
    bar.set_fraction(None)
    dismiss_btn = MinimalButton(text=t("btn_continue_english"), size_hint_y=None,
                                height=dp(40), btn_color=ACCENT_BLUE,
                                font_size=9, opacity=0, disabled=True)
    body.add_widget(caption)
    body.add_widget(bar)
    body.add_widget(dismiss_btn)

    popup = Popup(title=t("lang_pack_title"), content=body,
                  size_hint=(0.8, 0.42), auto_dismiss=False,
                  background_color=popup_color(BG_CARD),
                  title_color=popup_color(ACCENT_GOLD),
                  separator_color=popup_color(ACCENT_GOLD))

    def give_up(*_args):
        bar.stop()
        popup.dismiss()
        if on_give_up:
            on_give_up()

    dismiss_btn.bind(on_press=give_up)

    def progress(stage, fraction):
        def paint(_dt):
            caption.text = _stage_text(stage)
            if stage == "downloading":
                bar.set_fraction(fraction)
        Clock.schedule_once(paint, 0)

    def worker():
        ok = remote_content.download_pack(lang, on_progress=progress)

        def finish(_dt):
            bar.stop()
            if ok:
                popup.dismiss()
                on_done(lang)
            else:
                dismiss_btn.opacity = 1
                dismiss_btn.disabled = False
        Clock.schedule_once(finish, 0)

    popup.open()
    threading.Thread(target=worker, name=f"lang-pack-{lang}", daemon=True).start()
    return popup


def open_language_picker(on_chosen, title=None, mandatory=False,
                         refresh_manifest=True):
    """Show the picker. ``on_chosen(code)`` runs on the main thread.

    A language that is already on the device is chosen instantly. One that is
    not is downloaded first, with progress in its own row, and ``on_chosen``
    fires only after the pack installed — so the caller never has to handle a
    language that turned out not to be there.

    ``mandatory=True`` disables dismiss-on-touch, for the first-launch popup
    that must not be escapable.
    """
    from game import remote_content
    from game.remote_content import packs

    current = get_language()
    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
    content = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8),
                        size_hint_y=None)
    content.bind(minimum_height=content.setter("height"))
    scroll.add_widget(content)
    popup = Popup(
        title=title or "Language / Мова / Язык",
        content=scroll,
        size_hint=(0.85, 0.85),
        background_color=popup_color(BG_CARD),
        title_color=popup_color(ACCENT_GOLD),
        separator_color=popup_color(ACCENT_GOLD),
        auto_dismiss=not mandatory,
    )

    statuses = remote_content.pack_statuses()
    rows = {}

    def pick(row):
        status = statuses.get(row.code)
        if status in ("bundled", "installed"):
            popup.dismiss()
            on_chosen(row.code)
            return
        _start_download(row)

    def _start_download(row):
        row.set_busy(True)
        row.show_stage("checking", None)

        def progress(stage, fraction):
            Clock.schedule_once(lambda _dt: row.show_stage(stage, fraction), 0)

        def worker():
            ok = remote_content.download_pack(row.code, on_progress=progress)

            def finish(_dt):
                row.set_busy(False)
                if not ok:
                    # The row already shows why (offline / failed); leave the
                    # popup open so the player can retry or pick English.
                    return
                statuses[row.code] = "installed"
                row.caption.text = _status_text("installed")
                popup.dismiss()
                on_chosen(row.code)

            Clock.schedule_once(finish, 0)

        threading.Thread(target=worker, name=f"lang-pack-{row.code}",
                         daemon=True).start()

    for name, code in packs.OFFERED:
        row = _LanguageRow(name, code, statuses.get(code, "unavailable"),
                           pick, code == current)
        rows[code] = row
        content.add_widget(row)

    popup.open()

    if refresh_manifest:
        # The cached manifest may be hours old or absent on a fresh install.
        # Refresh off-thread and repaint the captions when it lands, so the
        # popup appears immediately instead of waiting on the network.
        def refresh_worker():
            remote_content.refresh_manifest()
            fresh = remote_content.pack_statuses()

            def repaint(_dt):
                for code, status in fresh.items():
                    row = rows.get(code)
                    if row is not None and not row._busy:
                        statuses[code] = status
                        row.caption.text = _status_text(status)

            Clock.schedule_once(repaint, 0)

        threading.Thread(target=refresh_worker, name="lang-manifest",
                         daemon=True).start()

    return popup
