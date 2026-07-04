"""
import_steam_dialog.py

Bulk-import every installed Steam game (detected by reading Steam's own
libraryfolders.vdf / appmanifest_*.acf files, no network access needed)
into games.yaml at the press of a button, either as blank profiles or
with a highly universal default (GameMode) already applied.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ..gtk_util import esc  # noqa: E402
from ..models import Profile, slugify  # noqa: E402
from ..steam import scan_installed_games  # noqa: E402


def _unique_key(base: str, taken: set) -> str:
    if base not in taken:
        return base
    i = 2
    while f"{base}_{i}" in taken:
        i += 1
    return f"{base}_{i}"


class ImportSteamDialog(Adw.Window):
    def __init__(self, window):
        super().__init__(transient_for=window, modal=True,
                          default_width=560, default_height=680,
                          title="Import from Steam Library")
        self.window = window
        self._checks = {}  # appid -> (Gtk.CheckButton, game)

        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _b: self.close())
        header.pack_start(cancel_btn)

        self.import_btn = Gtk.Button(label="Import Selected")
        self.import_btn.add_css_class("suggested-action")
        self.import_btn.connect("clicked", self._on_import_clicked)
        header.pack_end(self.import_btn)

        self.toast_overlay = Adw.ToastOverlay()
        toolbar_view.set_content(self.toast_overlay)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                         margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        self.toast_overlay.set_child(outer)

        options_group = Adw.PreferencesGroup()
        self.defaults_row = Adw.SwitchRow(
            title="Apply basic universal defaults",
            subtitle="Adds the GameMode wrapper (gamemoderun) to every imported game. "
                     "Safe and broadly compatible; leave off to import blank profiles.",
        )
        self.defaults_row.set_active(True)
        options_group.add(self.defaults_row)
        outer.append(options_group)

        select_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.search_entry = Gtk.SearchEntry(placeholder_text="Filter…", hexpand=True)
        self.search_entry.connect("search-changed", lambda _e: self._refresh_visibility())
        select_all_btn = Gtk.Button(label="Select All")
        select_all_btn.connect("clicked", lambda _b: self._set_all(True))
        select_none_btn = Gtk.Button(label="Select None")
        select_none_btn.connect("clicked", lambda _b: self._set_all(False))
        select_row.append(self.search_entry)
        select_row.append(select_all_btn)
        select_row.append(select_none_btn)
        self.select_row = select_row
        outer.append(select_row)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        self.scroller = scroller
        outer.append(scroller)

        self.listbox = Gtk.ListBox(css_classes=["boxed-list"],
                                    selection_mode=Gtk.SelectionMode.NONE)
        scroller.set_child(self.listbox)

        self._outer = outer
        self._populate()

    def _show_status(self, icon_name, title, description):
        self.select_row.set_visible(False)
        self.scroller.set_visible(False)
        status = Adw.StatusPage(icon_name=icon_name, title=title,
                                 description=description, vexpand=True)
        self._outer.append(status)
        self.import_btn.set_sensitive(False)

    def _populate(self):
        existing_keys = {p.key for p in self.window.games_file.list_profiles()}
        games = scan_installed_games()
        new_games = [g for g in games if slugify(g.name) not in existing_keys]

        if not games:
            self._show_status(
                "dialog-warning-symbolic", "No Steam installation found",
                "Checked ~/.local/share/Steam, ~/.steam, and the Flatpak Steam data "
                "directory. If Steam is installed somewhere else, add games manually instead.",
            )
            return

        if not new_games:
            self._show_status(
                "emblem-ok-symbolic", "Everything's already imported",
                f"Found {len(games)} installed Steam game(s); all already have a "
                f"gamecmd profile.",
            )
            return

        for game in new_games:
            row = Adw.ActionRow(title=esc(game.name), subtitle=esc(f"App ID {game.appid}"))
            check = Gtk.CheckButton(valign=Gtk.Align.CENTER)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            self.listbox.append(row)
            self._checks[game.appid] = (check, game, row)

    def _refresh_visibility(self):
        query = self.search_entry.get_text().strip().lower()
        for _appid, (_check, game, row) in self._checks.items():
            row.set_visible(query in game.name.lower())

    def _set_all(self, value: bool):
        query = self.search_entry.get_text().strip().lower()
        for _appid, (check, game, _row) in self._checks.items():
            if not query or query in game.name.lower():
                check.set_active(value)

    def _on_import_clicked(self, _button):
        games_file = self.window.games_file
        taken = {p.key for p in games_file.list_profiles()}
        apply_defaults = self.defaults_row.get_active()

        imported = 0
        for _appid, (check, game, _row) in self._checks.items():
            if not check.get_active():
                continue
            key = _unique_key(slugify(game.name), taken)
            taken.add(key)
            prefix = "gamemoderun" if apply_defaults else ""
            games_file.upsert_profile(Profile(key=key, prefix=prefix))
            imported += 1

        if imported == 0:
            self.toast_overlay.add_toast(Adw.Toast(title="Nothing selected", timeout=2))
            return

        games_file.save()
        self.window.games_page.refresh()
        self.window.games_page.toast_overlay.add_toast(
            Adw.Toast(title=f"Imported {imported} game(s)", timeout=3))
        self.close()
